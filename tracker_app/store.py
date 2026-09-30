from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from tracker_app.model import Adjustment, Interval, Section, TrackerModel

log = logging.getLogger(__name__)

DATA_DIR = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    / "tracker_app"
    / "trackers"
)


def tracker_path(model: TrackerModel) -> Path:
    return DATA_DIR / f"{model.id}.json"


def _dt(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    return datetime.fromisoformat(s)


def _dt_s(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _section_to_dict(sec: Section) -> dict:
    return {
        "id": sec.id,
        "finished": sec.finished,
        "intervals": [
            {"start": _dt_s(iv.start), "end": _dt_s(iv.end)}
            for iv in sec.intervals
        ],
        "last_start": _dt_s(sec.last_start),
        "note": sec.note,
        "note_created": _dt_s(sec.note_created),
        "adjustments": [
            {
                "seconds": a.seconds,
                "created": _dt_s(a.created),
                "reason": a.reason,
            }
            for a in sec.adjustments
        ],
    }


def _section_from_dict(d: dict) -> Section:
    intervals = [
        Interval(start=_dt(iv["start"]), end=_dt(iv["end"]))
        for iv in d.get("intervals", [])
    ]
    adjustments = [
        Adjustment(
            seconds=float(a["seconds"]),
            created=_dt(a["created"]),
            reason=a.get("reason", ""),
        )
        for a in d.get("adjustments", [])
    ]
    return Section(
        id=d["id"],
        finished=d["finished"],
        intervals=intervals,
        last_start=_dt(d.get("last_start")),
        note=d.get("note", ""),
        note_created=_dt(d.get("note_created")),
        adjustments=adjustments,
    )


def _model_to_dict(model: TrackerModel) -> dict:
    return {
        "id": model.id,
        "name": model.name,
        "created": _dt_s(model.created),
        "sections": [_section_to_dict(s) for s in model.sections],
    }


def _model_from_dict(d: dict) -> TrackerModel:
    return TrackerModel(
        id=d["id"],
        name=d["name"],
        created=_dt(d["created"]),
        sections=[_section_from_dict(s) for s in d.get("sections", [])],
    )


def save(model: TrackerModel) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = tracker_path(model)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(_model_to_dict(model), indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load(path: Path) -> tuple[Optional[TrackerModel], Optional[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _model_from_dict(data), None
    except Exception as exc:
        msg = f"Failed to load tracker from {path}: {exc}"
        log.warning(msg)
        return None, msg


def load_all() -> list[TrackerModel]:
    if not DATA_DIR.exists():
        return []
    trackers = []
    for path in sorted(DATA_DIR.glob("*.json")):
        model, _ = load(path)
        if model is not None:
            trackers.append(model)
    trackers.sort(key=lambda m: m.created)
    return trackers


def delete(model: TrackerModel) -> None:
    path = tracker_path(model)
    try:
        path.unlink()
    except FileNotFoundError:
        log.warning("Tried to delete non-existent tracker file: %s", path)
