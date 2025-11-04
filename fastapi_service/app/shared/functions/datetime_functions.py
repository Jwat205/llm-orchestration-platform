# shared/functions/datetime_functions.py
from datetime import datetime, timedelta

def current_time() -> str:
    return datetime.utcnow().isoformat()

def add_days(date_iso: str, days: int) -> str:
    dt = datetime.fromisoformat(date_iso)
    return (dt + timedelta(days=days)).isoformat()