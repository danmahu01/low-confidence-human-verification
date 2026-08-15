"""In-memory results store.

Good enough for a demo: everything resets when the process restarts. Swap the
body of these functions for SQLite when you need results to survive a reboot.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

_lock = threading.Lock()
_analyses: OrderedDict[str, dict] = OrderedDict()

MAX_ENTRIES = 50


def save_analysis(upload: dict, people: list[dict], verdict: dict | None = None) -> dict:
    entry = {"upload": upload, "people": people, "verdict": verdict}
    with _lock:
        _analyses[upload["id"]] = entry
        while len(_analyses) > MAX_ENTRIES:
            _analyses.popitem(last=False)
    return entry


def get_analysis(upload_id: str) -> dict | None:
    with _lock:
        return _analyses.get(upload_id)


def latest_analysis() -> dict | None:
    with _lock:
        if not _analyses:
            return None
        return next(reversed(_analyses.values()))


def all_people() -> list[dict]:
    """Every person across every analysis, newest upload first."""
    with _lock:
        entries = list(_analyses.values())
    return [person for entry in reversed(entries) for person in entry["people"]]
