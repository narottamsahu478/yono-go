import asyncio

from config import OTPDOCTOR_API_KEY, TEMPOTP_API_KEY, TEMPORASMS_API_KEY

# ---------- Background ----------
background_active_tasks = 0
background_lock = asyncio.Lock()


# ---------- Global Tracker ----------
global_active_requests_tracker = {}
tracker_lock = asyncio.Lock()


# Per-number completion state.
# Each registration owns one state object; the
# state is explicit so poller/foreground/background
# paths share one completion gate.
number_completion_states = {}


# ---------- Google Sheet ----------
global_sheet_instance = None


# ---------- Dashboard Live Stats ----------
live_stats = {
    "total_targeted": 0,
    "total_thread_count": 0,
    "active_threads": 0,
    "success_otps": 0,
    "already_registered": 0,
    "cancelled_orders": 0,
    "total_secured": 0,
    "system_status": "Ready to Start",
    "pipeline_running": False,
    "progress": 0,
    "eta": "---",
    "success_records": [],
    "error_logs": [],
    "recent_activity": [],
    "game_analytics": {},
    "registration_summary": {},
    "activity_timeline": [],
    "otp_history": [],
    "health_check": {
        "internet": "Connected",
        "gateway": "Connected",
        "SPYEYE": "Connected"
    },
    "realtime_active_threads": 0,
    "realtime_already_logs": 0,
    "cancel_failed_logs": 0,
    "cancel_failed_numbers_list": [],
    "cancel_logs": [],
    "delayed_cancel_queue": [],
    "spyeye_balance": "₹0",
    "foursim_balance": "₹0",
    "otpdoctor_balance": "₹0",
    "tempotp_balance": "₹0",
    "temporasms_balance": "₹0",
    "gateway_balance": "₹0",
    "selected_provider": "4sim",

    "auto_game_device_ids": [],
    "auto_game_last_fetch": None,
    "auto_game_source_count": 0,
    "auto_game_queue_count": 0,
    "auto_game_last_error": None,

    "history_sheet_sync_last": None,
    "history_sheet_sync_new": 0,
    "history_sheet_sync_error": None
}


# ---------- Locks / Events ----------
stats_lock = asyncio.Lock()
buy_lock = asyncio.Lock()
stop_event = asyncio.Event()


# ---------- Cancellation Tracking ----------
logged_cancels = set()
active_already_tasks = set()
delayed_cancel_tasks = set()


# ---------- Counters ----------
success_buy_count = 0
input_total_accounts = 0
active_task_counter = 0


# ---------- Provider ----------
global_provider = "4sim"

global_service_id = "1929"

global_otpdoctor_service_id = "16311"

global_otpdoctor_api_key = OTPDOCTOR_API_KEY
global_tempotp_api_key = TEMPOTP_API_KEY
global_temporasms_api_key = TEMPORASMS_API_KEY
global_temporasms_operator = "10"