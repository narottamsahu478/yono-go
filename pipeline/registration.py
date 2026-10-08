import asyncio
import aiohttp
import time
import globals
from config import (
    GAME_MAP,
    MAIN_GAME_WAIT,
    SUBGAME_FOREGROUND_WAIT,
    NEXT_GAME_DELAY,
    BACKGROUND_TIMEOUT_4SIM,
    BACKGROUND_TIMEOUT_OTPDOCTOR,
    BACKGROUND_TIMEOUT_TEMPOTP,
    BACKGROUND_TIMEOUT_TEMPORASMS,
    FOUR_SIM_API_KEY,
    TEMPOTP_API_KEY,
    TEMPORASMS_API_KEY,
)
from spyeye import spyeye_client
from utils.google_sheet import get_ist_time
from utils.helpers import (
    log_game_metric,
    add_error_log,
    add_timeline_event,
    update_live_status,
    remove_recent_activity,
    terminate_gateway_order_async,
    handle_already_number,
    complete_number_once,
    delayed_cancel_after_proxy_errors,
)
from poller.global_poller import global_inbox_poller
from game_sequence import get_game_sequence
from primary_game import get_primary_game
from provider.tempotp import TempOTPProvider
from provider.temporasms import TemporaSMSProvider


def get_otp_fallback_sequence(current_game, full_sequence=None):
    """
    Returns fallback games from current game position up to the top in reverse order.
    Example: If sequence is [A, B, C, D, E] and current_game is D (idx 3),
    fallback_games -> [C, B, A]
    """
    if full_sequence is None:
        full_sequence = get_game_sequence()

    if current_game not in full_sequence:
        return []

    current_idx = full_sequence.index(current_game)
    return list(reversed(full_sequence[:current_idx]))


async def run_game_step_async(
    phone,
    txn_id,
    game_key,
    used_otps,
    tested_game_otps,
    active_requests_tracker,
    success_chains_count,
    registered_games_list,
    game_balances_map,
    is_sub_game=False,
    is_last_game=False,
    number_state=None,
):
    if game_key not in GAME_MAP:
        return "failed", False, "0 INR"

    if number_state is not None and number_state.get("number_completed"):
        return "number_complete", False, "0 INR"

    send_attempt = 1
    proxy_error_attempts = 0
    api_name = GAME_MAP[game_key]["api"]
    ui_name = GAME_MAP[game_key]["ui"]

    async with aiohttp.ClientSession() as session:
        while send_attempt <= 5:
            try:
                await update_live_status(
                    phone,
                    "Sending OTP...",
                    target_game=ui_name,
                    retry_idx=send_attempt,
                    progress_val=15,
                )
                send_timestamp = time.time()
                v_res = await spyeye_client.send_otp(session, api_name, phone)
                error_msg = str(
                    v_res.get("msg") or v_res.get("message") or ""
                ).lower()

                if (
                    v_res.get("success") is not True
                    and v_res.get("status") != "success"
                ):
                    if "already" in error_msg or "555" in error_msg:
                        await update_live_status(
                            phone, "Already Reg", progress_val=0
                        )
                        await log_game_metric(ui_name, "already")
                        # The final app must finish the number immediately instead
                        # of entering the normal Already-Reg delayed queue.
                        if is_last_game:
                            return "last_game_already", False, "0 INR"
                        return "already", False, "0 INR"

                    if (
                        globals.global_provider in ("4sim", "tempotp", "temporasms")
                        and not is_sub_game
                        and any(
                            x in error_msg
                            for x in ("proxy", "proxy error", "proxy_error")
                        )
                    ):
                        proxy_error_attempts += 1
                        await add_error_log(
                            phone, ui_name, f"Proxy error {proxy_error_attempts}/5"
                        )
                        await update_live_status(
                            phone,
                            f"Proxy Error Retry {proxy_error_attempts}/5",
                            target_game=ui_name,
                            retry_idx=proxy_error_attempts,
                            progress_val=10,
                        )
                        if proxy_error_attempts >= 5:
                            return "primary_proxy_error_5", False, "0 INR"

                    send_attempt += 1
                    await asyncio.sleep(1)
                    continue

                request_id = v_res.get("requestid") or v_res.get("task_id")
                loop = asyncio.get_running_loop()
                result_future = loop.create_future()

                expiry = (
                    send_timestamp + BACKGROUND_TIMEOUT_OTPDOCTOR
                    if globals.global_provider == "otpdoctor"
                    else send_timestamp + (BACKGROUND_TIMEOUT_OTPDOCTOR if globals.global_provider == "otpdoctor" else BACKGROUND_TIMEOUT_TEMPOTP if globals.global_provider == "tempotp" else BACKGROUND_TIMEOUT_TEMPORASMS if globals.global_provider == "temporasms" else BACKGROUND_TIMEOUT_4SIM)
                )

                track_payload = {
                    "request_id": request_id,
                    "api_name": api_name,
                    "ui_name": ui_name,
                    "send_time": send_timestamp,
                    "result_future": result_future,
                    "is_main_game": not is_sub_game,
                    "background_mode": False,
                    "background_expiry": expiry,
                    "completed": False,
                    "cleanup_done": False,
                    "otp_received": False,
                    "verify_response_lost": False,
                    "phone": phone,
                }

                active_requests_tracker[game_key] = track_payload
                async with globals.tracker_lock:
                    globals.global_active_requests_tracker[
                        f"{phone}_{game_key}"
                    ] = track_payload

                await update_live_status(
                    phone, "Waiting Global Poller...", progress_val=40
                )

                if globals.global_provider == "temporasms":
                    # TemporaSMS: primary game gets the standard 130s wait;
                    # every sub-game gets 60s.
                    otp_wait_timeout = MAIN_GAME_WAIT if not is_sub_game else 60
                elif is_last_game:
                    otp_wait_timeout = 60
                else:
                    otp_wait_timeout = (
                        SUBGAME_FOREGROUND_WAIT if is_sub_game else MAIN_GAME_WAIT
                    )

                async def otp_countdown_updater():
                    deadline = time.monotonic() + otp_wait_timeout
                    while not result_future.done():
                        remaining = max(
                            0, int(deadline - time.monotonic() + 0.999)
                        )
                        track_payload["otp_timeout_remaining"] = remaining
                        await update_live_status(
                            phone,
                            f"OTP Waiting — {remaining}s",
                            target_game=ui_name,
                            retry_idx=send_attempt,
                            progress_val=40,
                            otp_timeout_remaining=remaining,
                            otp_timeout_total=otp_wait_timeout,
                        )
                        if remaining <= 0:
                            break
                        try:
                            await asyncio.wait_for(
                                asyncio.shield(result_future), timeout=1.0
                            )
                            break
                        except asyncio.TimeoutError:
                            continue

                countdown_task = asyncio.create_task(otp_countdown_updater())
                try:
                    result, otp_flag, balance = await asyncio.wait_for(
                        result_future, timeout=otp_wait_timeout
                    )
                    track_payload["otp_timeout_remaining"] = None
                    await update_live_status(
                        phone,
                        "OTP Received — Verifying..." if otp_flag else "Processing...",
                        target_game=ui_name,
                        retry_idx=send_attempt,
                        progress_val=70,
                        otp_timeout_remaining=0,
                    )
                    return result, otp_flag, balance

                except asyncio.TimeoutError:
                    countdown_task.cancel()
                    await asyncio.gather(countdown_task, return_exceptions=True)
                    track_payload["otp_timeout_remaining"] = 0
                    if is_last_game:
                        if game_key in active_requests_tracker:
                            active_requests_tracker[game_key]["completed"] = True
                        await log_game_metric(ui_name, "failed")
                        return "last_game_timeout", False, "0 INR"

                    if is_sub_game:
                        async with globals.background_lock:
                            globals.background_active_tasks += 1

                        active_requests_tracker[game_key][
                            "background_mode"
                        ] = True

                        await update_live_status(
                            phone, "Background Waiting", progress_val=40
                        )

                        return "background", False, "0 INR"

                    if game_key in active_requests_tracker:
                        active_requests_tracker[game_key]["completed"] = True

                    active_requests_tracker.pop(game_key, None)
                    async with globals.tracker_lock:
                        globals.global_active_requests_tracker.pop(
                            f"{phone}_{game_key}", None
                        )

                    await log_game_metric(ui_name, "failed")

                    return "timeout", False, "0 INR"

            except Exception as exc:
                error_text = str(exc).lower()
                if (
                    globals.global_provider in ("4sim", "tempotp", "temporasms")
                    and not is_sub_game
                    and any(
                        x in error_text
                        for x in ("proxy", "proxy error", "proxy_error")
                    )
                ):
                    proxy_error_attempts += 1
                    await add_error_log(
                        phone, ui_name, f"Proxy error {proxy_error_attempts}/5: {exc}"
                    )
                    await update_live_status(
                        phone,
                        f"Proxy Error Retry {proxy_error_attempts}/5",
                        target_game=ui_name,
                        retry_idx=proxy_error_attempts,
                        progress_val=10,
                    )
                    if proxy_error_attempts >= 5:
                        return "primary_proxy_error_5", False, "0 INR"

                if game_key in active_requests_tracker:
                    active_requests_tracker[game_key]["completed"] = True
                active_requests_tracker.pop(game_key, None)
                async with globals.tracker_lock:
                    globals.global_active_requests_tracker.pop(
                        f"{phone}_{game_key}", None
                    )
                send_attempt += 1
                await asyncio.sleep(1)

    return "failed", False, "0 INR"


async def safely_stop_poller(poller_stop_event, poller_task):
    poller_stop_event.set()
    try:
        await asyncio.wait_for(poller_task, timeout=10.0)
    except Exception:
        poller_task.cancel()
        await asyncio.gather(poller_task, return_exceptions=True)


async def process_single_registration():
    if (
        globals.stop_event.is_set()
        or globals.success_buy_count >= globals.input_total_accounts
    ):
        return

    phone, txn_id = None, None
    used_otps = set()
    tested_game_otps = set()
    active_requests_tracker = {}
    otp_received_anywhere = False

    success_chains_count = [0]
    already_chains_count = 0
    failed_or_timeout_count = 0

    registered_games_list = []
    game_balances_map = {}
    primary_game = get_primary_game()
    number_state = {
        "number_completed": False,
        "completion_reason": None,
        "completion_lock": asyncio.Lock(),
        "otp_received_anywhere": False,
    }
    if globals.global_provider == "temporasms":
        provider_threshold = None
    elif globals.global_provider == "otpdoctor":
        # OTPDoctor normally completes after 6 registrations.
        # Service IDs 9776 and 16905 complete after 5 registrations.
        otpdoctor_service_id = str(globals.global_service_id).strip()
        provider_threshold = 5 if otpdoctor_service_id in {"9776", "16905"} else 6
    else:
        provider_threshold = 5

    async with globals.buy_lock:
        if (
            globals.stop_event.is_set()
            or globals.success_buy_count >= globals.input_total_accounts
        ):
            return
        async with globals.stats_lock:
            globals.live_stats["system_status"] = "Securing Stock..."

        try:
            txn_id = None
            phone = None
            async with aiohttp.ClientSession() as session:
                if globals.global_provider == "otpdoctor":
                    buy_url = f"https://otpdoctor.in/stubs/handler_api.php?action=getNumber&api_key={globals.global_otpdoctor_api_key}&service={globals.global_service_id}"
                    async with session.get(buy_url, timeout=12) as response:
                        raw_text = (await response.text()).strip()
                        if raw_text.startswith("ACCESS_NUMBER:"):
                            parts = raw_text.split(":")
                            if len(parts) >= 3:
                                txn_id = parts[1]
                                phone = parts[2][-10:]
                elif globals.global_provider == "temporasms":
                    provider = TemporaSMSProvider(TEMPORASMS_API_KEY)
                    # TemporaSMS uses the common SERVICE ID input as its
                    # `service` parameter. OPERATOR is the only provider-
                    # specific extra field.
                    raw_text = await provider.buy_number(
                        session,
                        globals.global_service_id,
                        "22",
                        globals.global_temporasms_operator,
                    )
                    if raw_text.startswith("ACCESS_NUMBER:"):
                        parts = raw_text.split(":")
                        if len(parts) >= 3:
                            txn_id = parts[1]
                            phone = parts[2][-10:]

                elif globals.global_provider == "tempotp":
                    provider = TempOTPProvider(TEMPOTP_API_KEY)
                    buy_res = await provider.buy_number(session, globals.global_service_id, "22")
                    # TEMPOTP response fields are normalized here so minor API
                    # response-shape changes do not break the registration flow.
                    def _find_value(obj, keys):
                        if isinstance(obj, dict):
                            for key in keys:
                                if obj.get(key) not in (None, ""):
                                    return obj.get(key)
                            for value in obj.values():
                                found = _find_value(value, keys)
                                if found not in (None, ""):
                                    return found
                        elif isinstance(obj, list):
                            for value in obj:
                                found = _find_value(value, keys)
                                if found not in (None, ""):
                                    return found
                        return None

                    txn_id = _find_value(buy_res, ("id", "tid", "transaction_id", "transactionId", "activation_id"))
                    phone = _find_value(buy_res, ("number", "phone", "mobile", "phone_number"))
                    if phone is not None:
                        phone = str(phone)[-10:]
                    if txn_id is not None:
                        txn_id = str(txn_id)
                else:
                    buy_url = f"https://api.4sim.st/buyNumber?apikey={FOUR_SIM_API_KEY}&id={globals.global_service_id}&country=22"
                    async with session.get(buy_url, timeout=12) as response:
                        buy_res = await response.json()
                        phone = str(buy_res.get("number", ""))[-10:]
                        txn_id = buy_res.get("tid") or buy_res.get("id")

            if not phone:
                return
            globals.success_buy_count += 1
            globals.active_task_counter += 1
        except Exception:
            return

    async with globals.stats_lock:
        globals.live_stats["total_secured"] = globals.success_buy_count
        globals.live_stats["realtime_active_threads"] += 1
        globals.live_stats["recent_activity"].insert(
            0,
            {
                "phone": phone,
                "started_at": get_ist_time(),
                "last_update": get_ist_time(),
                "current_game": primary_game,
                "status": "Initializing...",
                "balance": "₹0",
                "game_balances": {},
                "retry": 1,
                "progress": 0,
                "thread_color": "🟢",
                "log_type": "active",
                "otp_received": False,
            },
        )

    poller_stop_event = asyncio.Event()
    poller_task = asyncio.create_task(
        global_inbox_poller(
            phone,
            txn_id,
            active_requests_tracker,
            used_otps,
            tested_game_otps,
            success_chains_count,
            registered_games_list,
            game_balances_map,
            poller_stop_event,
            number_state,
            provider_threshold,
        )
    )

    # 1. Primary Game Initiation
    main_res, m_otp_flag, main_bal = await run_game_step_async(
        phone,
        txn_id,
        primary_game,
        used_otps,
        tested_game_otps,
        active_requests_tracker,
        success_chains_count,
        registered_games_list,
        game_balances_map,
        is_sub_game=False,
        is_last_game=(len(get_game_sequence()) == 0),
        number_state=number_state,
    )
    if m_otp_flag:
        otp_received_anywhere = True
        number_state["otp_received_anywhere"] = True

    if main_res == "primary_proxy_error_5" and globals.global_provider in ("4sim", "tempotp", "temporasms"):
        await add_timeline_event(
            phone, f"Primary Game: 5 Proxy Errors -> {globals.global_provider.upper()} Delayed Cancel 130s"
        )
        await update_live_status(
            phone,
            "Delayed Cancel Queue — 130s",
            log_type="cancel",
            target_game=primary_game,
            retry_idx=5,
            progress_val=0,
            otp_timeout_remaining=None,
        )
        asyncio.create_task(delayed_cancel_after_proxy_errors(phone, txn_id, 130))
        async with globals.stats_lock:
            globals.live_stats["realtime_active_threads"] = max(
                0, globals.live_stats["realtime_active_threads"] - 1
            )
        await safely_stop_poller(poller_stop_event, poller_task)
        await remove_recent_activity(phone)
        return

    track_data = active_requests_tracker.get(primary_game, {})
    is_otp_received_in_poller = (
        track_data.get("otp_received", False) or m_otp_flag
    )
    is_verify_lost = track_data.get("verify_response_lost", False)

    if main_res == "already":
        if is_verify_lost and is_otp_received_in_poller:
            main_res = True
            main_bal = "₹0"
            if primary_game not in registered_games_list:
                registered_games_list.append(primary_game)
                success_chains_count[0] += 1
            await update_live_status(
                phone,
                "Verify Lost Recovered via Poller -> Starting Sub Games",
            )
            await add_timeline_event(
                phone, "Main Game Timeout Recovered -> Sub Games Triggered"
            )
        else:
            async with globals.stats_lock:
                globals.live_stats["already_registered"] += 1
                globals.live_stats["realtime_active_threads"] = max(
                    0, globals.live_stats["realtime_active_threads"] - 1
                )

            asyncio.create_task(
                handle_already_number(phone, txn_id, otp_received_anywhere)
            )
            await safely_stop_poller(poller_stop_event, poller_task)
            return

    elif main_res in ["timeout", "failed"]:
        cancel_status = await terminate_gateway_order_async(
            txn_id, otp_received_anywhere, phone, force_cancel=True
        )

        if (
            cancel_status == "SMS_RECEIVED_CANNOT_CANCEL"
            or is_verify_lost
            or is_otp_received_in_poller
        ):
            main_res = True
            main_bal = "₹0"
            if primary_game not in registered_games_list:
                registered_games_list.append(primary_game)
                success_chains_count[0] += 1
            await update_live_status(
                phone, "Cannot Cancel (OTP Received) -> Starting Sub Games"
            )
            await add_timeline_event(
                phone,
                "Main Game OTP Detected via Cannot Cancel -> Sub Games Triggered",
            )
        else:
            async with globals.stats_lock:
                globals.live_stats["realtime_active_threads"] = max(
                    0, globals.live_stats["realtime_active_threads"] - 1
                )
            await remove_recent_activity(phone)
            await safely_stop_poller(poller_stop_event, poller_task)
            return

    if number_state.get("number_completed"):
        async with globals.stats_lock:
            globals.live_stats["success_otps"] += 0
        await safely_stop_poller(poller_stop_event, poller_task)
        async with globals.stats_lock:
            globals.live_stats["success_records"].insert(
                0,
                {
                    "phone": phone,
                    "games": registered_games_list,
                    "game_balances": game_balances_map,
                    "success": success_chains_count[0],
                    "already": already_chains_count,
                    "failed": failed_or_timeout_count,
                    "completion": number_state.get("completion_reason"),
                    "time": get_ist_time(),
                },
            )
            globals.live_stats["realtime_active_threads"] = max(
                0, globals.live_stats["realtime_active_threads"] - 1
            )
        await remove_recent_activity(phone)
        return

    if provider_threshold is not None and success_chains_count[0] >= provider_threshold:
        await complete_number_once(
            phone,
            txn_id,
            active_requests_tracker,
            poller_stop_event,
            number_state,
            f"{globals.global_provider.upper()} threshold {provider_threshold}",
        )
        return

    # 2. Sequential Sub-Games Flow (Top to Bottom Registration)
    if main_res is True:
        async with globals.stats_lock:
            globals.live_stats["success_otps"] += 1
        if primary_game not in registered_games_list:
            success_chains_count[0] += 1
            registered_games_list.append(primary_game)
        game_balances_map[primary_game] = "₹" + str(main_bal).replace(
            " INR", ""
        ).replace("₹", "")
        await asyncio.sleep(NEXT_GAME_DELAY)

        other_games = get_game_sequence()

        for index, game in enumerate(other_games):
            if number_state.get("number_completed"):
                break

            result, otp_flag, bal = await run_game_step_async(
                phone,
                txn_id,
                game,
                used_otps,
                tested_game_otps,
                active_requests_tracker,
                success_chains_count,
                registered_games_list,
                game_balances_map,
                is_sub_game=True,
                is_last_game=(index == len(other_games) - 1),
                number_state=number_state,
            )

            if otp_flag:
                otp_received_anywhere = True
                number_state["otp_received_anywhere"] = True

            if result in ("last_game_timeout", "last_game_already"):
                completion_reason = (
                    "last game already registered"
                    if result == "last_game_already"
                    else "last game 60-second OTP timeout"
                )
                await complete_number_once(
                    phone,
                    txn_id,
                    active_requests_tracker,
                    poller_stop_event,
                    number_state,
                    completion_reason,
                )
                break

            if number_state.get("number_completed"):
                break

            if provider_threshold is not None and success_chains_count[0] >= provider_threshold:
                await complete_number_once(
                    phone,
                    txn_id,
                    active_requests_tracker,
                    poller_stop_event,
                    number_state,
                    f"{globals.global_provider.upper()} threshold {provider_threshold}",
                )
                break

            if result in ("background", "already", True):
                await asyncio.sleep(NEXT_GAME_DELAY)
                continue

            await asyncio.sleep(NEXT_GAME_DELAY)

    try:
        wait_start = time.time()
        background_timeout = (
            BACKGROUND_TIMEOUT_OTPDOCTOR
            if globals.global_provider == "otpdoctor"
            else BACKGROUND_TIMEOUT_TEMPOTP
            if globals.global_provider == "tempotp"
            else BACKGROUND_TIMEOUT_TEMPORASMS
            if globals.global_provider == "temporasms"
            else BACKGROUND_TIMEOUT_4SIM
        )
        while (
            not number_state.get("number_completed")
            and any(
                t.get("background_mode") and not t.get("completed")
                for t in active_requests_tracker.values()
            )
        ):
            if time.time() - wait_start > background_timeout:
                break
            await asyncio.sleep(2)
    except Exception:
        pass

    await safely_stop_poller(poller_stop_event, poller_task)

    if not number_state.get("number_completed"):
        await complete_number_once(
            phone,
            txn_id,
            active_requests_tracker,
            poller_stop_event,
            number_state,
            "sequence finished",
        )

    async with globals.stats_lock:
        globals.live_stats["success_records"].insert(
            0,
            {
                "phone": phone,
                "games": registered_games_list,
                "game_balances": game_balances_map,
                "success": success_chains_count[0],
                "already": already_chains_count,
                "failed": failed_or_timeout_count,
                "completion": number_state.get("completion_reason"),
                "time": get_ist_time(),
            },
        )
        globals.live_stats["progress"] = int(
            (globals.success_buy_count / globals.input_total_accounts) * 100
        )
        globals.live_stats["realtime_active_threads"] = max(
            0, globals.live_stats["realtime_active_threads"] - 1
        )

    await remove_recent_activity(phone)


async def dynamic_pipeline_runner(semaphore):
    while (
        not globals.stop_event.is_set()
        and globals.success_buy_count < globals.input_total_accounts
    ):
        async with semaphore:
            await process_single_registration()
        await asyncio.sleep(1.5)


async def core_engine_orchestrator(target, threads):
    globals.success_buy_count = 0
    globals.active_task_counter = 0
    globals.background_active_tasks = 0
    globals.input_total_accounts = target

    globals.logged_cancels.clear()
    globals.active_already_tasks.clear()
    async with globals.tracker_lock:
        globals.global_active_requests_tracker.clear()

    async with globals.stats_lock:
        globals.live_stats["total_targeted"] = target
        globals.live_stats["total_thread_count"] = threads
        globals.live_stats["active_threads"] = threads
        globals.live_stats["pipeline_running"] = True
        globals.live_stats["success_otps"] = 0
        globals.live_stats["already_registered"] = 0
        globals.live_stats["cancelled_orders"] = 0
        globals.live_stats["cancel_logs"] = []
        globals.live_stats["total_secured"] = 0
        globals.live_stats["progress"] = 0
        globals.live_stats["eta"] = "Calculating..."
        globals.live_stats["recent_activity"] = []
        globals.live_stats["error_logs"] = []
        globals.live_stats["game_analytics"] = {}
        globals.live_stats["registration_summary"] = {}
        globals.live_stats["activity_timeline"] = []
        globals.live_stats["otp_history"] = []
        globals.live_stats["realtime_active_threads"] = 0
        globals.live_stats["realtime_already_logs"] = 0
        globals.live_stats["cancel_failed_logs"] = 0
        globals.live_stats["cancel_failed_numbers_list"] = []
        globals.live_stats["delayed_cancel_queue"] = []
        globals.live_stats["selected_provider"] = globals.global_provider

    semaphore = asyncio.Semaphore(threads)
    workers = [
        asyncio.create_task(dynamic_pipeline_runner(semaphore))
        for _ in range(threads)
    ]

    start_time = time.time()
    while (
        globals.success_buy_count < globals.input_total_accounts
        and not globals.stop_event.is_set()
    ):
        async with globals.stats_lock:
            globals.live_stats["active_threads"] = len(
                [w for w in workers if not w.done()]
            )
            globals.live_stats["system_status"] = (
                "Running | Active Pipeline Loop"
            )

            elapsed = time.time() - start_time
            if globals.success_buy_count > 0:
                avg_time = elapsed / globals.success_buy_count
                rem_acc = (
                    globals.input_total_accounts - globals.success_buy_count
                )
                eta_secs = int(avg_time * rem_acc)
                globals.live_stats["eta"] = f"{eta_secs // 60}m {eta_secs % 60}s"

        await asyncio.sleep(1)

    async with globals.stats_lock:
        globals.live_stats["system_status"] = (
            "Stop Received. Completing active runs..."
        )

    await asyncio.gather(*workers, return_exceptions=True)

    while True:
        async with globals.tracker_lock:
            tracker_len = len(globals.global_active_requests_tracker)
        if (
            globals.background_active_tasks <= 0
            and tracker_len <= 0
            and len(globals.active_already_tasks) <= 0
        ):
            break
        async with globals.stats_lock:
            globals.live_stats["system_status"] = (
                f"Awaiting Background Tasks ({globals.background_active_tasks}) / Delay Holds ({len(globals.active_already_tasks)})..."
            )
        await asyncio.sleep(2)

    globals.logged_cancels.clear()

    async with globals.stats_lock:
        globals.live_stats["pipeline_running"] = False
        globals.live_stats["active_threads"] = 0
        globals.live_stats["realtime_active_threads"] = 0
        globals.live_stats["system_status"] = "Pipeline Finished / Idle"
        globals.live_stats["eta"] = "---"
