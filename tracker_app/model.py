from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Interval:
    start: datetime
    end: Optional[datetime]

    def duration_seconds(self) -> float:
        if self.end is None:
            return 0.0
        return (self.end - self.start).total_seconds()


@dataclass
class Section:
    id: str
    finished: bool
    intervals: list[Interval]
    last_start: Optional[datetime]

    def is_running(self) -> bool:
        return self.last_start is not None

    def elapsed_seconds(self, now: datetime) -> float:
        total = sum(iv.duration_seconds() for iv in self.intervals)
        if self.last_start is not None:
            total += (now - self.last_start).total_seconds()
        return max(total, 0.0)

    @classmethod
    def new(cls) -> "Section":
        return cls(id=str(uuid.uuid4()), finished=False, intervals=[], last_start=None)


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

    def reset(self, now: datetime) -> None:
        sec = self.current_section
        if sec.is_running():
            sec.intervals.append(Interval(start=sec.last_start, end=now))
            sec.last_start = None
        sec.finished = True
        self.sections.append(Section.new())
