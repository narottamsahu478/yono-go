import asyncio
import aiohttp
import os
import requests
import sys
import time
from pathlib import Path
from fastapi import FastAPI, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import globals
from config import (
    BASE_URL,
    SPYEYE_API_KEY,
    FOUR_SIM_API_KEY,
    TEMPOTP_API_KEY,
    TEMPORASMS_API_KEY,
    LICENSE_SERVER,
    LICENSE_KEY,
    SECRET_KEY,
)
from dashboard.routes import router as dashboard_router

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_license()
    # Fetch all three balances once when the app starts. After that, the
    # background tracker refreshes balances only while the pipeline is running.
    await fetch_all_balances_once()
    asyncio.create_task(live_balances_tracker_loop())
    yield

app = FastAPI(lifespan=lifespan)

# ---------- Static Files & Directory Mounting ----------
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")
app.mount("/mobile", StaticFiles(directory=BASE_DIR / "mobile"), name="mobile")
if (BASE_DIR / "shared").exists():
    app.mount("/shared", StaticFiles(directory=BASE_DIR / "shared"), name="shared")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Dashboard Routes
app.include_router(dashboard_router)


# ---------- PWA Support Routes ----------
@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse(BASE_DIR / "manifest.json")


@app.get("/service-worker.js")
async def serve_service_worker():
    response = FileResponse(BASE_DIR / "service-worker.js")
    response.headers["Cache-Control"] = "no-cache"
    return response


# ---------- Helper Function for Cache Deletion / Busting ----------
def get_no_cache_response(file_path: Path):
    response = FileResponse(file_path)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ---------- Frontend View Routes ----------
@app.get("/")
async def serve_mobile_index():
    return get_no_cache_response(BASE_DIR / "mobile" / "index.html")


@app.get("/m")
async def serve_mobile_alias():
    return get_no_cache_response(BASE_DIR / "mobile" / "index.html")


# ---------- License Verification ----------
def verify_license():
    for _ in range(10):
        try:
            r = requests.get(
                LICENSE_SERVER,
                params={
                    "key": LICENSE_KEY,
                    "spyeye": SPYEYE_API_KEY,
                    "secret": SECRET_KEY,
                },
                timeout=15,
            )

            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "ok":
                    print("License Verified")
                    return
        except Exception:
            pass
        time.sleep(5)
    print("License Verification Failed")
    sys.exit(1)


# ---------- Live Balances Tracker ----------
async def _fetch_spyeye_balance(session):
    try:
        async with session.get(
            f"{BASE_URL}/yono-api/login?accesscode={SPYEYE_API_KEY}",
            ssl=False,
            timeout=8,
        ) as response:
            data = await response.json()
            if data.get("success"):
                bal_val = (
                    data.get("credits")
                    if data.get("credits") is not None
                    else data.get("current_balance", 0)
                )
                async with globals.stats_lock:
                    globals.live_stats["spyeye_balance"] = " " + str(
                        int(float(bal_val))
                    )
    except Exception:
        pass


async def _fetch_foursim_balance(session):
    try:
        async with session.get(
            f"https://api.4sim.st/getBalance?apikey={FOUR_SIM_API_KEY}",
            timeout=8,
        ) as response:
            data = await response.json()
            if data.get("balance") is not None:
                async with globals.stats_lock:
                    globals.live_stats["foursim_balance"] = " " + str(
                        int(float(data.get("balance")))
                    )
    except Exception:
        pass


async def _fetch_otpdoctor_balance(session):
    try:
        async with session.get(
            f"https://otpdoctor.in/stubs/handler_api.php?action=getBalance&api_key={globals.global_otpdoctor_api_key}",
            timeout=8,
        ) as response:
            raw_bal = (await response.text()).strip()
            if "ACCESS_BALANCE:" in raw_bal:
                b_val = raw_bal.split(":", 1)[1]
                async with globals.stats_lock:
                    globals.live_stats["otpdoctor_balance"] = " " + str(
                        float(b_val)
                    )
    except Exception:
        pass




async def _fetch_tempotp_balance(session):
    try:
        async with session.get(
            "https://api.tempotp.online/getBalance",
            params={"apikey": TEMPOTP_API_KEY},
            timeout=8,
        ) as response:
            raw = (await response.text()).strip()
            try:
                data = __import__('json').loads(raw)
            except Exception:
                data = raw

            def find_balance(obj):
                if isinstance(obj, dict):
                    for key in ("balance", "credits", "amount", "wallet", "data"):
                        if key in obj and obj[key] not in (None, ""):
                            value = obj[key]
                            if isinstance(value, (dict, list)):
                                found = find_balance(value)
                                if found is not None:
                                    return found
                            else:
                                return value
                    for value in obj.values():
                        found = find_balance(value)
                        if found is not None:
                            return found
                elif isinstance(obj, list):
                    for value in obj:
                        found = find_balance(value)
                        if found is not None:
                            return found
                elif isinstance(obj, (int, float)):
                    return obj
                elif isinstance(obj, str):
                    import re
                    m = re.search(r"-?\d+(?:\.\d+)?", obj)
                    if m:
                        return m.group(0)
                return None

            bal = find_balance(data)
            if bal is not None:
                async with globals.stats_lock:
                    globals.live_stats["tempotp_balance"] = " " + str(bal)
    except Exception:
        pass

async def _fetch_temporasms_balance(session):
    try:
        from provider.temporasms import TemporaSMSProvider
        raw = await TemporaSMSProvider(TEMPORASMS_API_KEY).get_balance(session)
        value = raw.split(":", 1)[1].strip() if isinstance(raw, str) and ":" in raw else raw
        async with globals.stats_lock:
            globals.live_stats["temporasms_balance"] = " " + str(value)
    except Exception:
        pass

async def _refresh_selected_gateway_balance(session, provider):
    if provider == "otpdoctor":
        await _fetch_otpdoctor_balance(session)
        async with globals.stats_lock:
            globals.live_stats["gateway_balance"] = globals.live_stats["otpdoctor_balance"]
    elif provider == "tempotp":
        await _fetch_tempotp_balance(session)
        async with globals.stats_lock:
            globals.live_stats["gateway_balance"] = globals.live_stats["tempotp_balance"]
    elif provider == "temporasms":
        await _fetch_temporasms_balance(session)
        async with globals.stats_lock:
            globals.live_stats["gateway_balance"] = globals.live_stats["temporasms_balance"]
    else:
        await _fetch_foursim_balance(session)
        async with globals.stats_lock:
            globals.live_stats["gateway_balance"] = globals.live_stats["foursim_balance"]


async def fetch_all_balances_once():
    """Startup-only refresh: SpyEye + 4SIM + OTPDoctor."""
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            _fetch_spyeye_balance(session),
            _fetch_foursim_balance(session),
            _fetch_otpdoctor_balance(session),
            _fetch_tempotp_balance(session),
            _fetch_temporasms_balance(session),
            return_exceptions=True,
        )

        provider = globals.global_provider
        async with globals.stats_lock:
            globals.live_stats["selected_provider"] = provider
            if provider == "otpdoctor":
                globals.live_stats["gateway_balance"] = globals.live_stats["otpdoctor_balance"]
            elif provider == "tempotp":
                globals.live_stats["gateway_balance"] = globals.live_stats["tempotp_balance"]
            elif provider == "temporasms":
                globals.live_stats["gateway_balance"] = globals.live_stats["temporasms_balance"]
            else:
                globals.live_stats["gateway_balance"] = globals.live_stats["foursim_balance"]


async def live_balances_tracker_loop():
    while True:
        try:
            # Do not hit any balance endpoint while idle.
            async with globals.stats_lock:
                running = bool(globals.live_stats.get("pipeline_running"))
                provider = globals.global_provider
                globals.live_stats["selected_provider"] = provider

            if running:
                async with aiohttp.ClientSession() as session:
                    # SpyEye is used by every running registration.
                    await _fetch_spyeye_balance(session)
                    # Refresh only the provider currently doing the work.
                    await _refresh_selected_gateway_balance(session, provider)
        except Exception:
            pass

        await asyncio.sleep(10)
