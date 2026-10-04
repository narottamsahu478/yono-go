# API Keys
FOUR_SIM_API_KEY = "52c0b4799f07c15cf5a3e2ffde329a29"
OTPDOCTOR_API_KEY = "etykgs81yei5w3zzj0r3gpkob2dpw8pu"
TEMPOTP_API_KEY = "ce281f8ca8910e6b50808d11a87c1"
TEMPORASMS_API_KEY = "4886507db9a85fe9352c0eef83f5bbbd43"

# SpyEye
BASE_URL = "https://spyeyeloots3.online/up_yono/"

# License
LICENSE_KEY = "LF-SUMANTA-001"
SPYEYE_API_KEY = "TBRSUMANTHA1212"
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
