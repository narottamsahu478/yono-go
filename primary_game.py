import json
from pathlib import Path
from config import GAME_MAP

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRIMARY_GAME_FILE = DATA_DIR / "primary_game.json"
DEFAULT_PRIMARY_GAME = "567slots"


def _ensure_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PRIMARY_GAME_FILE.exists():
        PRIMARY_GAME_FILE.write_text(
            json.dumps({"primary_game": DEFAULT_PRIMARY_GAME}, indent=2),
            encoding="utf-8",
        )


def get_primary_game():
    _ensure_file()
    try:
        data = json.loads(PRIMARY_GAME_FILE.read_text(encoding="utf-8"))
        game = str(data.get("primary_game", "")).strip()
        if game in GAME_MAP:
            return game
    except Exception:
        pass
    return DEFAULT_PRIMARY_GAME


def save_primary_game(game):
    """Save the primary game and swap it with the old primary in the sequence.

    When the newly selected primary already exists in game_sequence.json, the
    old primary takes that game's exact position and the new primary takes the
    old primary's position. This keeps the configured sequence stable while
    making the primary selection a true swap (and avoids duplicate games).
    """
    game = str(game).strip()
    if game not in GAME_MAP:
        raise ValueError("Invalid primary game")

    _ensure_file()
    old_primary = get_primary_game()

    if game != old_primary:
        sequence_file = DATA_DIR / "game_sequence.json"
        if sequence_file.exists():
            try:
                sequence = json.loads(sequence_file.read_text(encoding="utf-8"))
                if isinstance(sequence, list):
                    new_idx = sequence.index(game) if game in sequence else -1
                    old_idx = sequence.index(old_primary) if old_primary in sequence else -1

                    if new_idx >= 0 and old_idx >= 0:
                        # Swap the two games in-place.
                        sequence[new_idx], sequence[old_idx] = sequence[old_idx], sequence[new_idx]
                    elif new_idx >= 0:
                        # Old primary has no sequence slot: replace the new
                        # primary's slot with the old primary.
                        sequence[new_idx] = old_primary

                    tmp_seq = sequence_file.with_suffix(".tmp")
                    tmp_seq.write_text(
                        json.dumps(sequence, indent=2), encoding="utf-8"
                    )
                    tmp_seq.replace(sequence_file)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                # Primary selection should still work if the optional sequence
                # file is malformed; it can be repaired from the dashboard.
                pass

    tmp = PRIMARY_GAME_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"primary_game": game}, indent=2), encoding="utf-8"
    )
    tmp.replace(PRIMARY_GAME_FILE)
    return game
