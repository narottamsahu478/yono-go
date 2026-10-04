import json
from pathlib import Path
from config import GAME_MAP

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SEQUENCE_FILE = DATA_DIR / "game_sequence.json"

DEFAULT_GAME_SEQUENCE = [
    "789Jackpots",
    "Maha",
    "MBMBet",
    "YonoSlots",
    "YonoGames",
    "Bingo",
    "IndSlots",
    "INDRummy",
    "HiRummy",
    "YonoVip",
    "SpinCrush",
]


def _ensure_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SEQUENCE_FILE.exists():
        SEQUENCE_FILE.write_text(
            json.dumps(DEFAULT_GAME_SEQUENCE, indent=2), encoding="utf-8"
        )


def get_game_sequence():
    _ensure_file()
    try:
        data = json.loads(SEQUENCE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("sequence must be a list")
        valid = [name for name in data if name in GAME_MAP]
        if valid:
            return valid
    except Exception:
        pass
    return list(DEFAULT_GAME_SEQUENCE)


def save_game_sequence(sequence):
    if not isinstance(sequence, list):
        raise ValueError("sequence must be a list")

    cleaned = []
    seen = set()
    for name in sequence:
        name = str(name).strip()
        if not name or name not in GAME_MAP or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)

    if not cleaned:
        raise ValueError("At least one valid game is required")

    _ensure_file()
    tmp = SEQUENCE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    tmp.replace(SEQUENCE_FILE)
    return cleaned
