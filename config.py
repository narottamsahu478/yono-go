# API Keys
FOUR_SIM_API_KEY = "14e85c47b09e50a92a2239e6aea7a481"
OTPDOCTOR_API_KEY = "9o8nv46avmnc5y4g87gc6rypndemfhbn"
TEMPOTP_API_KEY = "74a2d7337a50ef729e17419a6165d341"
TEMPORASMS_API_KEY = "4886507db9a85fe9352c0eef83f5bbbd43"

# SpyEye
BASE_URL = "https://spyeyeloots3.online/up_yono/"

# License
LICENSE_KEY = "LF-SUMANTA-002"
SPYEYE_API_KEY = "TBRASAHUREG2993"
SECRET_KEY = "7a5d8fda4b2e9c4d"
LICENSE_SERVER = "https://spyeye-cv4o.onrender.com/api/check-license"

# Timers
MAIN_GAME_WAIT = 130
SUBGAME_FOREGROUND_WAIT = 40
NEXT_GAME_DELAY = 3

BACKGROUND_TIMEOUT_4SIM = 900
BACKGROUND_TIMEOUT_OTPDOCTOR = 1200
BACKGROUND_TIMEOUT_TEMPOTP = 900
BACKGROUND_TIMEOUT_TEMPORASMS = 900

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Games map...
GAME_MAP = {
    "567slots": {"api": "567slots", "ui": "567slots"},
    "MBMBet": {"api": "mbmbet", "ui": "MBMBet"},
    "Bingo": {"api": "bingo101", "ui": "Bingo"},
    "IndSlots": {"api": "indslots", "ui": "IndSlots"},
    "HiRummy": {"api": "hirummy", "ui": "HiRummy"},
    "Maha": {"api": "mahagames", "ui": "Maha"},
    "YonoVip": {"api": "yonovip", "ui": "YonoVip"},
    "789Jackpots": {"api": "789jackpots", "ui": "789Jackpots"},
    "INDRummy": {"api": "indrummy", "ui": "INDRummy"},
    "YonoGames": {"api": "yonogames", "ui": "YonoGames"},
    "SpinCrush": {"api": "spincrush", "ui": "SpinCrush"},
    "YonoSlots": {"api": "yonoslots", "ui": "YonoSlots"},
    "GoGoRummy": {"api": "gogorummy", "ui": "GoGoRummy"},
    "INDclub": {"api": "indclub", "ui": "INDclub"},
    "YonoArcade": {"api": "yonoarcade", "ui": "YonoArcade"},
    "Rummy91": {"api": "rummy91", "ui": "Rummy91"},
    "RummyLudo": {"api": "rummyludo", "ui": "RummyLudo"},
    "YonoRummy": {"api": "yonorummy", "ui": "YonoRummy"},
}

API_TO_UI = {v["api"].lower(): v["ui"] for v in GAME_MAP.values()}
