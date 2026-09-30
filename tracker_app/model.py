from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

_DURATION_PART = re.compile(r"(\d+(?:[.,]\d+)?)\s*([hms]?)\s*")
_UNIT_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0}


def parse_duration(text: str) -> Optional[float]:
    """Parse a human-written duration into (signed) seconds.

    Accepts forms like "+7m", "-30s", "1h 30m", "2:15" (mm:ss),
    "1:02:15" (h:mm:ss) or a bare number, which is read as minutes.
    Returns None if the text cannot be parsed.
    """
    text = text.strip().lower()
    if not text:
        return None

    sign = 1.0
    if text[0] in "+-":
        sign = -1.0 if text[0] == "-" else 1.0
        text = text[1:].strip()
    if not text:
        return None

    # Colon form: h:mm or h:mm:ss
    if ":" in text:
        parts = text.split(":")
        if len(parts) > 3 or not all(p.strip().isdigit() for p in parts):
            return None
        units = [3600.0, 60.0, 1.0][-len(parts):]
        return sign * sum(int(p) * u for p, u in zip(parts, units))

    total = 0.0
    pos = 0
    for match in _DURATION_PART.finditer(text):
        if match.start() != pos:
            return None
        pos = match.end()
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2) or "m"  # bare numbers are minutes
        total += value * _UNIT_SECONDS[unit]
    if pos != len(text):
        return None
    return sign * total


def format_duration(seconds: float) -> str:
    """Format signed seconds as +H:MM:SS / -H:MM:SS."""
    sign = "-" if seconds < 0 else "+"
    total = int(abs(seconds))
    return f"{sign}{total // 3600:d}:{total % 3600 // 60:02d}:{total % 60:02d}"


@dataclass
class Interval:
    start: datetime
    end: Optional[datetime]

    def duration_seconds(self) -> float:
        if self.end is None:
            return 0.0
        return (self.end - self.start).total_seconds()


@dataclass
class Adjustment:
    """A manual correction of the elapsed time, independent of the intervals."""

    seconds: float
    created: datetime
    reason: str = ""


@dataclass
class Section:
    id: str
    finished: bool
    intervals: list[Interval]
    last_start: Optional[datetime]
    note: str = ""
    note_created: Optional[datetime] = None
    adjustments: list[Adjustment] = field(default_factory=list)

    def adjustment_seconds(self) -> float:
        return sum(a.seconds for a in self.adjustments)

    def is_running(self) -> bool:
        return self.last_start is not None

    def elapsed_seconds(self, now: datetime) -> float:
        total = sum(iv.duration_seconds() for iv in self.intervals)
        total += self.adjustment_seconds()
        if self.last_start is not None:
            total += (now - self.last_start).total_seconds()
        return max(total, 0.0)

    @classmethod
    def new(cls) -> "Section":
        return cls(
            id=str(uuid.uuid4()),
            finished=False,
            intervals=[],
            last_start=None,
            note="",
            note_created=None,
            adjustments=[],
        )


class TrackerModel:
    def __init__(
        self,
        id: str,
        name: str,
        created: datetime,
        sections: list[Section],
    ) -> None:
        self.id = id
        self.name = name
        self.created = created
        self.sections = sections

    @classmethod
    def new(cls, name: str) -> "TrackerModel":
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            created=now,
            sections=[Section.new()],
        )

    @property
    def current_section(self) -> Section:
        return self.sections[-1]

    def is_running(self) -> bool:
        return self.current_section.is_running()

    def elapsed_seconds(self, now: datetime) -> float:
        return self.current_section.elapsed_seconds(now)

    def last_reset_date(self) -> Optional[datetime]:
        if len(self.sections) == 1:
            return self.created
        # The start of the current section is the end of the last interval
        # of the previous section, or the created time of the tracker.
        # We track this via a convention: the reset timestamp is stored as
        # the created time of the new section. We infer it from the previous
        # section's last interval end, or use the tracker created time.
        prev = self.sections[-2]
        if prev.intervals:
            return prev.intervals[-1].end
        return self.created

    def start(self, now: datetime) -> None:
        sec = self.current_section
        if sec.is_running():
            return
        sec.last_start = now

    def stop(self, now: datetime) -> None:
        sec = self.current_section
        if not sec.is_running():
            return
        sec.intervals.append(Interval(start=sec.last_start, end=now))
        sec.last_start = None

    def adjust(self, seconds: float, now: datetime, reason: str = "") -> None:
        """Add a manual time correction to the current section.

        The adjustment is recorded on its own and never touches the intervals,
        so a running timer keeps running unaffected.
        """
        if seconds == 0:
            return
        self.current_section.adjustments.append(
            Adjustment(seconds=float(seconds), created=now, reason=reason)
        )

    def reset(self, now: datetime) -> None:
        sec = self.current_section
        if sec.is_running():
            sec.intervals.append(Interval(start=sec.last_start, end=now))
            sec.last_start = None
        sec.finished = True
        self.sections.append(Section.new())
