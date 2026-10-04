import os
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import globals
from config import SCOPES

try:
    import gspread
    from google.oauth2.service_account import Credentials

    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False


BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Google Sheet Connection
# ---------------------------------------------------------------------------

def init_google_sheet(custom_sheet_key=None):
    """
    Initialize a Google Sheet connection for an explicit history-sync target key.
    Google Sheets are not connected or written to during registration/realtime
    processing; callers must provide a target key for a history sync operation.
    """

    if not HAS_GSPREAD:
        print(" gspread package missing!")
        return None

    try:
        target_key = str(custom_sheet_key or "").strip()
        if not target_key:
            print("Google Sheet key is required for history sync.")
            return None

        possible_paths = [
            BASE_DIR / "credentials.json",
            "/sdcard/Amit/test10/credentials.json",
            "credentials.json",
            os.path.expanduser("~/credentials.json"),
            "/etc/secrets/credentials.json",
        ]

        creds = None
        creds_json = os.getenv("GOOGLE_CREDENTIALS")

        if creds_json:
            creds = Credentials.from_service_account_info(
                json.loads(creds_json),
                scopes=SCOPES,
            )
        else:
            for path in possible_paths:
                if os.path.exists(path):
                    print(f" Found credentials at: {path}")
                    creds = Credentials.from_service_account_file(
                        path,
                        scopes=SCOPES,
                    )
                    break

        if not creds:
            print(" Credentials file not found!")
            return None

        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(target_key)

        print(" Google Sheets Connected Successfully via Key!")

        globals.global_sheet_instance = spreadsheet

        return spreadsheet

    except Exception as e:
        print(f"Google Sheet Connection Warning/Error: {e}")
        return None


# ---------------------------------------------------------------------------
# Time Helpers
# ---------------------------------------------------------------------------

def format_time_only(ts_val):
    if not ts_val:
        return "N/A"

    ist_tz = timezone(timedelta(hours=5, minutes=30))

    if isinstance(ts_val, (int, float)):
        dt = datetime.fromtimestamp(ts_val, tz=ist_tz)

    elif isinstance(ts_val, datetime):
        dt = ts_val.astimezone(ist_tz)

    else:
        return str(ts_val)

    return dt.strftime("%I:%M:%S %p")


def get_ist_time():
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist_tz).strftime(
        "%d %B %Y, %I:%M:%S %p"
    )


# ---------------------------------------------------------------------------
# OTP History
# ---------------------------------------------------------------------------

async def log_otp_history(
    phone,
    game_name,
    otp_code,
    send_time,
    rec_time,
    verified_time,
    status_text,
):
    async with globals.stats_lock:
        globals.live_stats["otp_history"].insert(
            0,
            {
                "phone": phone,
                "game_name": game_name,
                "send_otp_time": format_time_only(send_time),
                "otp_code": otp_code,
                "otp_received_time": format_time_only(rec_time),
                "otp_verified_time": format_time_only(verified_time),
                "status": status_text,
            },
        )

        if len(globals.live_stats["otp_history"]) > 300:
            globals.live_stats["otp_history"].pop()


# ---------------------------------------------------------------------------
# Sync History Into One Spreadsheet
# ---------------------------------------------------------------------------

def _sync_history_spreadsheet_sync(
    spreadsheet,
    records,
):
    """
    Append only history records missing from one spreadsheet.

    Duplicate identity:
        App Name + Device ID + Phone

    Existing rows are never overwritten or deleted.
    """

    if not spreadsheet or not records:
        return 0

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

    existing_keys = set()

    # -----------------------------------------------------------------------
    # Get Existing Worksheets
    # -----------------------------------------------------------------------

    try:
        worksheets = spreadsheet.worksheets()

    except Exception:
        worksheets = []

    if not worksheets:

        try:
            worksheets = [spreadsheet.sheet1]

        except Exception:
            worksheets = []

    # -----------------------------------------------------------------------
    # Read Existing Rows
    # -----------------------------------------------------------------------

    for ws in worksheets:

        try:
            values = ws.get_all_values()

        except Exception:
            continue

        for row in values[1:]:

            if len(row) < 4:
                continue

            phone = (
                row[3]
                if len(row) > 3
                else ""
            )

            # Compatibility with older sheet layouts.
            if (
                not _history_norm_phone(phone)
                and len(row) > 4
            ):
                phone = row[4]

            existing_keys.add(
                (
                    str(
                        row[0]
                        if len(row) > 0
                        else "-"
                    ).strip().lower(),

                    str(
                        row[1]
                        if len(row) > 1
                        else "-"
                    ).strip().lower(),

                    _history_norm_phone(phone),
                )
            )

    # -----------------------------------------------------------------------
    # Find New Records
    # -----------------------------------------------------------------------

    new_rows = []
    seen = set()

    for item in records:

        if not isinstance(item, dict):
            continue

        key = _history_identity(item)

        if key in existing_keys:
            continue

        if key in seen:
            continue

        seen.add(key)

        new_rows.append(
            _history_row(item)
        )

    if not new_rows:
        return 0

    # -----------------------------------------------------------------------
    # Find Writable SheetN
    # -----------------------------------------------------------------------

    target_ws = None

    for index in range(1, 1000):

        sheet_name = f"Sheet{index}"

        try:
            ws = spreadsheet.worksheet(
                sheet_name
            )

        except Exception:

            if index == 1:

                try:
                    ws = spreadsheet.sheet1

                except Exception:
                    ws = spreadsheet.add_worksheet(
                        title=sheet_name,
                        rows=1001,
                        cols=10,
                    )

            else:

                ws = spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=1001,
                    cols=10,
                )

            target_ws = ws
            break

        try:
            row_count = max(
                0,
                len(
                    ws.get_all_values()
                ) - 1,
            )

        except Exception:
            row_count = 0

        if row_count < 1000:
            target_ws = ws
            break

    if target_ws is None:
        raise RuntimeError(
            "Unable to find a writable SheetN tab"
        )

    # -----------------------------------------------------------------------
    # Add Header If Empty
    # -----------------------------------------------------------------------

    try:
        current = target_ws.get_all_values()

    except Exception:
        current = []

    if not current:

        target_ws.append_row(
            headers
        )

    # -----------------------------------------------------------------------
    # Append New Rows
    # -----------------------------------------------------------------------

    target_ws.append_rows(
        new_rows
    )

    return len(new_rows)


