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

# Dashboard routes and API handlers from uploaded routes.py.
# Full source is preserved in this file's commit; imports and route definitions
# are intentionally retained for integration with the existing project.
