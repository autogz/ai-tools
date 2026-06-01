"""
Free run tracker — tracks 3 free runs/day per user across all tools.
Resets daily. Stores in ~/.ai-dev-tools/tracker.json
"""
import json
from pathlib import Path
from datetime import datetime, date

TRACKER_DIR = Path.home() / ".ai-dev-tools"
TRACKER_FILE = TRACKER_DIR / "tracker.json"
FIRST_100_FILE = TRACKER_DIR / "first_100.json"

DAILY_LIMIT = 3
PRICING = {
    "early_access": {"name": "Early Access", "price_usd": 10, "slots": 100},
    "regular": {"name": "Regular", "price_usd": 29},
    "founder": {"name": "Founder", "price_usd": 49},
}
USDT_ADDRESS = "0xafc32581a9e4ea30aa03cb8ef5879c2366d35f46"
USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"


def _ensure_dir():
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)


def _default_tracker():
    return {"today": str(date.today()), "runs_used": 0, "total_runs": 0, "is_paid": False, "paid_tier": None}


def load_tracker() -> dict:
    _ensure_dir()
    if TRACKER_FILE.exists():
        try:
            data = json.loads(TRACKER_FILE.read_text())
            # Reset if different day
            if data.get("today") != str(date.today()):
                data["today"] = str(date.today())
                data["runs_used"] = 0
                save_tracker(data)
            return data
        except (json.JSONDecodeError, KeyError):
            pass
    data = _default_tracker()
    save_tracker(data)
    return data


def save_tracker(data: dict):
    _ensure_dir()
    TRACKER_FILE.write_text(json.dumps(data, indent=2))


def get_remaining() -> int:
    data = load_tracker()
    if data.get("is_paid"):
        return 99999
    return max(0, DAILY_LIMIT - data.get("runs_used", 0))


def record_run() -> int:
    """Record a free run. Returns remaining count."""
    data = load_tracker()
    if not data.get("is_paid"):
        data["runs_used"] = data.get("runs_used", 0) + 1
    data["total_runs"] = data.get("total_runs", 0) + 1
    save_tracker(data)
    return get_remaining()


def is_paid() -> bool:
    data = load_tracker()
    return data.get("is_paid", False)


def activate_bundle() -> bool:
    """Mark user as paid. Track first_100 count."""
    data = load_tracker()
    data["is_paid"] = True
    data["paid_tier"] = "bundle"
    data["paid_at"] = datetime.now().isoformat()
    save_tracker(data)

    # Track first 100
    _ensure_dir()
    f100 = {"count": 0, "users": []}
    if FIRST_100_FILE.exists():
        try:
            f100 = json.loads(FIRST_100_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    f100["count"] = f100.get("count", 0) + 1
    f100["users"].append({"activated_at": datetime.now().isoformat(), "tier": "bundle"})
    FIRST_100_FILE.write_text(json.dumps(f100, indent=2))

    return True


def get_first_100_count() -> int:
    if FIRST_100_FILE.exists():
        try:
            return json.loads(FIRST_100_FILE.read_text()).get("count", 0)
        except (json.JSONDecodeError, KeyError):
            pass
    return 0
