import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path

import globals
from config import API_TO_UI, BASE_URL, SPYEYE_API_KEY, FOUR_SIM_API_KEY, OTPDOCTOR_API_KEY, TEMPOTP_API_KEY, TEMPORASMS_API_KEY
from spyeye import spyeye_client
from utils.google_sheet import init_google_sheet
from pipeline.registration import core_engine_orchestrator
from game_sequence import get_game_sequence, save_game_sequence
from primary_game import get_primary_game, save_primary_game

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent


@router.get("/api/spyeye/account-info")
async def get_spyeye_account_info():
    async with aiohttp.ClientSession() as session:
        try:
            data = await spyeye_client.get_account_info(session)
            return JSONResponse(content=data)
        except Exception as e:
            return JSONResponse(
                status_code=500, content={"success": False, "error": str(e)}
            )


class GameSequenceRequest(BaseModel):
    sequence: list[str]



class PrimaryGameRequest(BaseModel):
    game: str


@router.get("/api/primary-game")
async def get_primary_game_api():
    from config import GAME_MAP
    return {
        "success": True,
        "primary_game": get_primary_game(),
        "available": list(GAME_MAP.keys()),
    }


@router.post("/api/primary-game")
async def save_primary_game_api(body: PrimaryGameRequest):
    try:
        game = save_primary_game(body.game)
        from config import GAME_MAP
        return {
            "success": True,
            "primary_game": game,
            "sequence": get_game_sequence(),
            "available": list(GAME_MAP.keys()),
            "message": "Primary game saved successfully",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/game-sequence")
async def get_game_sequence_api():
    sequence = get_game_sequence()
    # Keep the saved order authoritative; expose all configured games so the
    # dashboard can enable/disable individual games without changing the
    # existing GAME_MAP or registration pipeline.
    from config import GAME_MAP
    available = list(GAME_MAP.keys())
    return {"success": True, "sequence": sequence, "available": available}


@router.post("/api/game-sequence")
async def save_game_sequence_api(body: GameSequenceRequest):
    try:
        sequence = save_game_sequence(body.sequence)
        return {"success": True, "sequence": sequence, "message": "Game sequence saved successfully"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/autogame/device-queue")
async def get_autogame_device_queue():
    async with globals.stats_lock:
        return {
            "success": True,
            "device_ids": list(globals.live_stats.get("auto_game_device_ids", [])),
            "count": globals.live_stats.get("auto_game_queue_count", 0),
            "last_fetch": globals.live_stats.get("auto_game_last_fetch"),
            "source_count": globals.live_stats.get("auto_game_source_count", 0),
            "last_error": globals.live_stats.get("auto_game_last_error"),
        }


@router.get("/api/4sim/balance")
async def get_4sim_balance():
    async with globals.stats_lock:
        return {
            "success": True,
            "foursim_balance": globals.live_stats.get("foursim_balance", "₹0"),
        }


@router.get("/api/otpdoctor/balance")
async def get_otpdoctor_balance():
    async with globals.stats_lock:
        return {
            "success": True,
            "otpdoctor_balance": globals.live_stats.get(
                "otpdoctor_balance", "₹0"
            ),
        }


@router.get("/api/tempotp/balance")
async def get_tempotp_balance():
    async with globals.stats_lock:
        return {
            "success": True,
            "tempotp_balance": globals.live_stats.get("tempotp_balance", "₹0"),
        }

@router.get("/api/temporasms/balance")
async def get_temporasms_balance():
    async with globals.stats_lock:
        return {
            "success": True,
            "temporasms_balance": globals.live_stats.get("temporasms_balance", "₹0"),
        }


def find_first_records_list(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        preferred_keys = [
            "history",
            "data",
            "result",
            "list",
            "items",
            "servers",
            "records",
            "logs",
        ]
        for key in preferred_keys:
            if key in obj and isinstance(obj[key], list):
                return obj[key]
        for value in obj.values():
            result = find_first_records_list(value)
            if result is not None:
                return result
    return None


def _parse_history_datetime(value):
    """Best-effort parser for SPYEYE history timestamps."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    formats = (
        "%Y-%m-%d %I:%M:%S %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",
        "%d %B %Y, %I:%M:%S %p",
        "%d %B %Y %I:%M:%S %p",
        "%d-%m-%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        except Exception:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        return parsed
    except Exception:
        return None


def filter_and_paginate_history(records, date_filter, date, page, limit, sort_order="new_first"):
    formatted_history = []
    seen = set()

    for item in records:
        if not isinstance(item, dict):
            continue

        raw_app = (
            item.get("app_name") or item.get("app") or item.get("game") or ""
        )
        app_name = (
            API_TO_UI.get(raw_app.lower(), raw_app) if raw_app else "-"
        )

        deviceid = item.get("deviceid") or item.get("device_id") or "-"
        balance = (
            item.get("balance") if item.get("balance") is not None else 0
        )
        phone = item.get("phone") or item.get("number") or "-"
        password = item.get("password") or "-"
        date_val = item.get("date") or "-"
        uid = item.get("uid") or "-"
        gid = item.get("gid") or "-"

        unique_key = (
            str(app_name).lower(),
            str(phone),
            str(deviceid),
            str(uid),
        )
        if unique_key in seen:
            continue
        seen.add(unique_key)

        formatted_history.append(
            {
                "app_name": app_name,
                "deviceid": deviceid,
                "balance": balance,
                "phone": phone,
                "password": password,
                "date": date_val,
                "uid": uid,
                "gid": gid,
            }
        )

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    today_dt = now_ist
    yesterday_dt = now_ist - timedelta(days=1)

    filtered_history = []
    for item in formatted_history:
        date_str = str(item.get("date") or "")
        match = False

        if date_filter == "all":
            match = True
        elif date_filter == "today":
            t1 = today_dt.strftime("%Y-%m-%d")
            t2 = today_dt.strftime("%d %B %Y")
            t3 = today_dt.strftime("%d-%m-%Y")
            t4 = today_dt.strftime("%Y/%m/%d")
            if any(t.lower() in date_str.lower() for t in [t1, t2, t3, t4]):
                match = True
        elif date_filter == "yesterday":
            y1 = yesterday_dt.strftime("%Y-%m-%d")
            y2 = yesterday_dt.strftime("%d %B %Y")
            y3 = yesterday_dt.strftime("%d-%m-%Y")
            y4 = yesterday_dt.strftime("%Y/%m/%d")
            if any(y.lower() in date_str.lower() for y in [y1, y2, y3, y4]):
                match = True
        elif date_filter == "date" and date:
            d_targets = [date]
            try:
                parsed = datetime.strptime(date, "%Y-%m-%d")
                d_targets.append(parsed.strftime("%d %B %Y"))
                d_targets.append(parsed.strftime("%d-%m-%Y"))
                d_targets.append(parsed.strftime("%Y/%m/%d"))
            except Exception:
                pass
            if any(dt.lower() in date_str.lower() for dt in d_targets):
                match = True
        else:
            match = True

        if match:
            filtered_history.append(item)

    # Keep history ordering deterministic. New First is the default.
    # When timestamps are unavailable, preserve the SPYEYE API order.
    indexed = list(enumerate(filtered_history))
    if any(_parse_history_datetime(item.get("date")) is not None for _, item in indexed):
        if sort_order == "old_first":
            indexed.sort(
                key=lambda pair: (
                    _parse_history_datetime(pair[1].get("date")) is None,
                    _parse_history_datetime(pair[1].get("date")) or datetime.min.replace(tzinfo=timezone.utc),
                    pair[0],
                )
            )
        else:
            indexed.sort(
                key=lambda pair: (
                    _parse_history_datetime(pair[1].get("date")) is None,
                    -(_parse_history_datetime(pair[1].get("date")).timestamp()
                      if _parse_history_datetime(pair[1].get("date")) else 0),
                    pair[0],
                )
            )
        filtered_history = [item for _, item in indexed]

    total = len(filtered_history)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    if page > total_pages:
        page = total_pages
    if page < 1:
        page = 1

    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_slice = []
    for serial, item in enumerate(filtered_history[start_idx:end_idx], start=start_idx + 1):
        row = dict(item)
        row["serial_no"] = serial
        paginated_slice.append(row)

    start_num = start_idx + 1 if total > 0 else 0
    end_num = min(end_idx, total)

    return (
        filtered_history,
        paginated_slice,
        {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "start": start_num,
            "end": end_num,
        },
    )


@router.get("/api/spyeye/history/sync-status")
async def get_spyeye_history_sync_status():
    async with globals.stats_lock:
        return {
            "success": True,
            "enabled": True,
            "last_sync": globals.live_stats.get("history_sheet_sync_last"),
            "new_records": globals.live_stats.get("history_sheet_sync_new", 0),
            "error": globals.live_stats.get("history_sheet_sync_error"),
        }


@router.get("/api/spyeye/history")
async def get_spyeye_history(
    date_filter: str = Query("all", pattern="^(all|today|yesterday|date)$"),
    date: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50),
    sort_order: str = Query("new_first", pattern="^(new_first|old_first)$"),
):
    async with aiohttp.ClientSession() as session:
        try:
            raw = await spyeye_client.get_history(session)
            records = find_first_records_list(raw)
            if records is None:
                records = []

            _, paginated_slice, pagination_meta = (
                filter_and_paginate_history(
                    records, date_filter, date, page, limit, sort_order
                )
            )

            return JSONResponse(
                content={
                    "success": True,
                    "history": paginated_slice,
                    "pagination": pagination_meta,
                }
            )

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "history": [],
                    "pagination": {
                        "page": 1,
                        "limit": limit,
                        "total": 0,
                        "total_pages": 1,
                        "start": 0,
                        "end": 0,
                    },
                    "error": str(e),
                },
            )


class HistorySyncRequest(BaseModel):
    sheet_key: str
    sync_type: str
    date_filter: str = "all"
    date: str | None = None
    page: int = 1
    limit: int = 50
    sort_order: str = "new_first"


@router.post("/api/spyeye/history/sync")
async def sync_spyeye_history(body: HistorySyncRequest):
    try:
        target_sheet_key = body.sheet_key.strip()
        if not target_sheet_key:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Sheet key cannot be empty",
                },
            )

        target_spreadsheet = init_google_sheet(target_sheet_key)
        if not target_spreadsheet:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Failed to connect to Google Sheet",
                },
            )

        async with aiohttp.ClientSession() as session:
            raw = await spyeye_client.get_history(session)
            records = find_first_records_list(raw)
            if records is None:
                records = []

        filtered_full, paginated_slice, _ = filter_and_paginate_history(
            records, body.date_filter, body.date, body.page, body.limit, body.sort_order
        )

        target_records = (
            paginated_slice
            if body.sync_type == "current_page"
            else filtered_full
        )

        if not target_records:
            return JSONResponse(
                content={
                    "success": True,
                    "synced_records": 0,
                    "message": "History synced successfully",
                }
            )

        # HISTORY SYNC IS APPEND-ONLY. Never clear or rewrite existing sheet data.
        # A record is considered the same existing record only when all three
        # identity fields match: App Name + Android/Device ID + Mobile Number.
        # Other fields (balance/date/password/UID/GID) are never used to overwrite
        # an existing row.
        headers = [
            "App Name",
            "Device ID",
            "Balance",
            "Phone",
            "Password",
            "Date",
            "UID",
            "GID",
        ]

        def _norm_phone(value):
            digits = "".join(ch for ch in str(value or "") if ch.isdigit())
            return digits[-10:] if len(digits) >= 10 else digits

        def _identity(app_name, device_id, phone):
            return (
                str(app_name or "-").strip().lower(),
                str(device_id or "-").strip().lower(),
                _norm_phone(phone),
            )

        loop = asyncio.get_event_loop()

        # Read existing rows from every SheetN tab so sync never duplicates or
        # destroys data when a sheet has already rolled over to another tab.
        existing_keys = set()
        worksheets = await loop.run_in_executor(None, target_spreadsheet.worksheets)
        if not worksheets:
            worksheets = [await loop.run_in_executor(None, target_spreadsheet.sheet1)]

        for ws_existing in worksheets:
            try:
                values = await loop.run_in_executor(None, ws_existing.get_all_values)
            except Exception:
                continue

            if not values:
                continue

            # The normal project schema is: App, Device ID, Balance, Phone,
            # Password, Date, UID, GID.  Also tolerate the older sync order
            # where Date and Phone were swapped.
            for row in values[1:]:
                if len(row) < 4:
                    continue
                app_name = row[0] if len(row) > 0 else "-"
                device_id = row[1] if len(row) > 1 else "-"
                phone = row[3] if len(row) > 3 else ""
                # If column 4 is a date-like value and column 5 looks like a
                # phone, recognize the old layout too.
                if len(row) > 4:
                    c4 = str(row[3] or "")
                    c5 = str(row[4] or "")
                    if not _norm_phone(c4) and _norm_phone(c5):
                        phone = c5
                existing_keys.add(_identity(app_name, device_id, phone))

        new_rows = []
        skipped_duplicates = 0
        seen_in_sync = set()

        for item in target_records:
            app_name = str(item.get("app_name", "-") or "-")
            device_id = str(item.get("deviceid", "-") or "-")
            phone = str(item.get("phone", "-") or "-")
            key = _identity(app_name, device_id, phone)

            if key in existing_keys or key in seen_in_sync:
                skipped_duplicates += 1
                continue

            seen_in_sync.add(key)
            new_rows.append(
                [
                    app_name,
                    device_id,
                    str(item.get("balance", "-")),
                    phone,
                    str(item.get("password", "-")),
                    str(item.get("date", "-")),
                    str(item.get("uid", "-")),
                    str(item.get("gid", "-")),
                ]
            )

        # Find/create the first SheetN tab with room. Existing data is preserved.
        target_ws = None
        for index in range(1, 1000):
            sheet_name = f"Sheet{index}"
            try:
                ws = await loop.run_in_executor(None, target_spreadsheet.worksheet, sheet_name)
            except Exception:
                if index == 1:
                    ws = target_spreadsheet.sheet1
                else:
                    ws = await loop.run_in_executor(
                        None,
                        target_spreadsheet.add_worksheet,
                        sheet_name,
                        1001,
                        10,
                    )
                target_ws = ws
                break

            try:
                values = await loop.run_in_executor(None, ws.get_all_values)
                data_rows = max(0, len(values) - 1)
            except Exception:
                data_rows = 0

            if data_rows < 1000:
                target_ws = ws
                break

        if target_ws is None:
            raise RuntimeError("Unable to find a writable SheetN tab")

        current_values = await loop.run_in_executor(None, target_ws.get_all_values)
        if not current_values:
            await loop.run_in_executor(None, target_ws.append_row, headers)

        if new_rows:
            await loop.run_in_executor(None, target_ws.append_rows, new_rows)

        return JSONResponse(
            content={
                "success": True,
                "synced_records": len(new_rows),
                "skipped_duplicates": skipped_duplicates,
                "message": (
                    f"History appended safely: {len(new_rows)} new records; "
                    f"{skipped_duplicates} existing records skipped."
                ),
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(e)}
        )


@router.get("/api/spyeye/grouped-otp-history")
async def get_grouped_otp_history():
    async with globals.stats_lock:
        history_list = list(globals.live_stats.get("otp_history", []))

    grouped = {}
    for item in history_list:
        phone = item.get("phone", "Unknown")
        if phone not in grouped:
            grouped[phone] = []
        grouped[phone].append(item)

    return JSONResponse(
        content={"success": True, "grouped_otp_history": grouped}
    )


@router.post("/api/start")
async def api_start(request: Request):
    if globals.stop_event.is_set():
        globals.stop_event.clear()

    try:
        data = await request.json()
    except Exception:
        data = {}

    target = int(data.get("target", 10))
    threads = int(data.get("threads", 2))

    globals.global_provider = str(data.get("provider", "4sim")).strip()
    globals.global_service_id = str(data.get("service_id", "1929")).strip()
    # Keep the legacy variable synchronized for any older code paths.
    globals.global_otpdoctor_service_id = globals.global_service_id
    globals.global_otpdoctor_api_key = OTPDOCTOR_API_KEY
    globals.global_tempotp_api_key = TEMPOTP_API_KEY
    globals.global_temporasms_api_key = TEMPORASMS_API_KEY
    globals.global_temporasms_operator = str(data.get("operator", "10")).strip() or "10"

    asyncio.create_task(core_engine_orchestrator(target, threads))
    return {"status": "success"}


@router.post("/api/stop")
async def api_stop():
    globals.stop_event.set()
    return {"status": "graceful_stop_initiated"}


@router.get("/api/logs")
async def api_logs(
    filter: str = Query("all", pattern="^(all|today|yesterday|date)$"),
    date: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50),
):
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    today_str = now_ist.strftime("%d %B %Y")
    yesterday_str = (now_ist - timedelta(days=1)).strftime("%d %B %Y")

    async with globals.stats_lock:
        records = list(globals.live_stats.get("success_records", []))

    filtered_records = []
    for rec in records:
        rec_time_str = rec.get("time", "")
        match_inclusion = False

        if filter == "date" and date:
            try:
                parsed_date = datetime.strptime(date, "%Y-%m-%d")
                target_formatted = parsed_date.strftime("%d %B %Y")
                if target_formatted.lower() in rec_time_str.lower():
                    match_inclusion = True
            except Exception:
                if date in rec_time_str:
                    match_inclusion = True
        elif filter == "today":
            if today_str.lower() in rec_time_str.lower():
                match_inclusion = True
        elif filter == "yesterday":
            if yesterday_str.lower() in rec_time_str.lower():
                match_inclusion = True
        else:
            match_inclusion = True

        if match_inclusion:
            filtered_records.append(rec)

    total = len(filtered_records)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_slice = filtered_records[start_idx:end_idx]

    start_num = start_idx + 1 if total > 0 else 0
    end_num = min(end_idx, total)

    response_data = dict(globals.live_stats)
    response_data["success_records"] = paginated_slice
    response_data["pagination"] = {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "start": start_num,
        "end": end_num,
    }

    return JSONResponse(content=response_data)


