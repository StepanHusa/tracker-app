from datetime import datetime, timedelta

import pytest

from tracker_app.model import (
    Interval,
    Section,
    TrackerModel,
    format_duration,
    parse_duration,
)


def make_dt(offset_seconds: float = 0) -> datetime:
    base = datetime(2026, 1, 1, 12, 0, 0)
    return base + timedelta(seconds=offset_seconds)


# ---------------------------------------------------------------------------
# Section.elapsed_seconds
# ---------------------------------------------------------------------------

def test_elapsed_is_zero_for_fresh_section():
    sec = Section.new()
    assert sec.elapsed_seconds(make_dt()) == 0.0


def test_elapsed_accumulates_across_intervals():
    sec = Section.new()
    sec.intervals = [
        Interval(start=make_dt(0), end=make_dt(30)),   # 30 s
        Interval(start=make_dt(60), end=make_dt(105)), # 45 s
    ]
    assert sec.elapsed_seconds(make_dt(200)) == 75.0


def test_elapsed_includes_live_duration_when_running():
    sec = Section.new()
    sec.intervals = [
        Interval(start=make_dt(0), end=make_dt(10)),  # 10 s completed
    ]
    sec.last_start = make_dt(20)
    assert sec.elapsed_seconds(make_dt(35)) == 25.0  # 10 + 15 live


def test_elapsed_live_only_when_no_completed_intervals():
    sec = Section.new()
    sec.last_start = make_dt(0)
    assert sec.elapsed_seconds(make_dt(42)) == 42.0


# ---------------------------------------------------------------------------
# TrackerModel.start / stop
# ---------------------------------------------------------------------------

def test_start_sets_last_start():
    model = TrackerModel.new("test")
    model.start(make_dt(0))
    assert model.current_section.last_start == make_dt(0)


def test_start_is_noop_when_already_running():
    model = TrackerModel.new("test")
    model.start(make_dt(0))
    model.start(make_dt(5))  # second start should be ignored
    assert model.current_section.last_start == make_dt(0)


def test_stop_clears_last_start_and_appends_interval():
    model = TrackerModel.new("test")
    model.start(make_dt(0))
    model.stop(make_dt(10))

    sec = model.current_section
    assert sec.last_start is None
    assert len(sec.intervals) == 1
    assert sec.intervals[0].start == make_dt(0)
    assert sec.intervals[0].end == make_dt(10)


def test_stop_is_noop_when_not_running():
    model = TrackerModel.new("test")
    model.stop(make_dt(10))
    assert model.current_section.intervals == []


# ---------------------------------------------------------------------------
# TrackerModel.reset
# ---------------------------------------------------------------------------

def test_reset_marks_section_finished_and_creates_new():
    model = TrackerModel.new("test")
    model.start(make_dt(0))
    model.stop(make_dt(10))
    model.reset(make_dt(20))

    assert len(model.sections) == 2
    assert model.sections[0].finished is True
    assert model.sections[1].finished is False
    assert model.sections[1].last_start is None
    assert model.sections[1].intervals == []


def test_reset_while_running_stops_and_marks_finished():
    model = TrackerModel.new("test")
    model.start(make_dt(0))
    model.reset(make_dt(15))

    finished_sec = model.sections[0]
    assert finished_sec.finished is True
    assert finished_sec.last_start is None
    assert len(finished_sec.intervals) == 1
    assert finished_sec.intervals[0].end == make_dt(15)


def test_elapsed_resets_to_zero_after_reset():
    model = TrackerModel.new("test")
    model.start(make_dt(0))
    model.stop(make_dt(100))
    model.reset(make_dt(100))

    # New section has no time
    assert model.elapsed_seconds(make_dt(100)) == 0.0


# ---------------------------------------------------------------------------
# TrackerModel.is_running
# ---------------------------------------------------------------------------

def test_is_running_reflects_current_section_state():
    model = TrackerModel.new("test")
    assert not model.is_running()
    model.start(make_dt())
    assert model.is_running()
    model.stop(make_dt(5))
    assert not model.is_running()


# ---------------------------------------------------------------------------
# parse_duration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("+7m", 420.0),
        ("7", 420.0),
        ("-30s", -30.0),
        ("1h30m", 5400.0),
        ("1h 30 m", 5400.0),
        ("1.5h", 5400.0),
        ("2:15", 135.0),
        ("1:02:15", 3735.0),
        ("-1:00", -60.0),
    ],
)
def test_parse_duration_accepts(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "abc", "5x", "+", "1:2:3:4", "h"])
def test_parse_duration_rejects(text):
    assert parse_duration(text) is None


def test_format_duration_signs():
    assert format_duration(420) == "+0:07:00"
    assert format_duration(-3735) == "-1:02:15"


# ---------------------------------------------------------------------------
# TrackerModel.adjust
# ---------------------------------------------------------------------------

def test_adjust_adds_to_elapsed():
    model = TrackerModel.new("test")
    model.adjust(420, make_dt(0))
    assert model.elapsed_seconds(make_dt(0)) == 420.0


def test_adjust_does_not_touch_intervals_of_running_timer():
    model = TrackerModel.new("test")
    model.start(make_dt(0))
    model.adjust(420, make_dt(300))
    assert model.current_section.last_start == make_dt(0)
    assert model.current_section.intervals == []
    assert model.elapsed_seconds(make_dt(300)) == 720.0  # 5 min run + 7 min


def test_adjustments_accumulate_and_can_be_negative():
    model = TrackerModel.new("test")
    model.adjust(420, make_dt(0))
    model.adjust(-60, make_dt(10), reason="too much")
    assert len(model.current_section.adjustments) == 2
    assert model.current_section.adjustment_seconds() == 360.0
    assert model.current_section.adjustments[1].reason == "too much"


def test_adjust_ignores_zero():
    model = TrackerModel.new("test")
    model.adjust(0, make_dt(0))
    assert model.current_section.adjustments == []


def test_elapsed_never_goes_below_zero():
    model = TrackerModel.new("test")
    model.adjust(-600, make_dt(0))
    assert model.elapsed_seconds(make_dt(0)) == 0.0


def test_reset_leaves_adjustments_in_old_section():
    model = TrackerModel.new("test")
    model.adjust(420, make_dt(0))
    model.reset(make_dt(10))
    assert model.sections[0].adjustment_seconds() == 420.0
    assert model.current_section.adjustments == []
    assert model.elapsed_seconds(make_dt(10)) == 0.0
