import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import tracker_app.store as store
from tracker_app.model import Interval, Section, TrackerModel


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "trackers"
    d.mkdir()
    monkeypatch.setattr(store, "DATA_DIR", d)
    return d


@pytest.fixture
def simple_model():
    model = TrackerModel.new("work")
    model.start(datetime(2026, 1, 1, 9, 0, 0))
    model.stop(datetime(2026, 1, 1, 9, 30, 0))
    return model


# ---------------------------------------------------------------------------
# tracker_path uses UUID, not name
# ---------------------------------------------------------------------------

def test_tracker_path_uses_uuid(data_dir, simple_model):
    path = store.tracker_path(simple_model)
    assert path.name == f"{simple_model.id}.json"
    assert "work" not in path.name


# ---------------------------------------------------------------------------
# save + load roundtrip
# ---------------------------------------------------------------------------

def test_save_and_load_roundtrip(data_dir, simple_model):
    store.save(simple_model)

    loaded, err = store.load(store.tracker_path(simple_model))

    assert err is None
    assert loaded is not None
    assert loaded.id == simple_model.id
    assert loaded.name == simple_model.name
    assert loaded.created == simple_model.created
    assert len(loaded.sections) == 1
    assert len(loaded.sections[0].intervals) == 1
    assert loaded.sections[0].intervals[0].start == simple_model.sections[0].intervals[0].start
    assert loaded.sections[0].intervals[0].end == simple_model.sections[0].intervals[0].end


def test_roundtrip_preserves_running_state(data_dir, simple_model):
    simple_model.start(datetime(2026, 1, 1, 10, 0, 0))
    store.save(simple_model)

    loaded, _ = store.load(store.tracker_path(simple_model))
    assert loaded.is_running()
    assert loaded.current_section.last_start == datetime(2026, 1, 1, 10, 0, 0)


def test_roundtrip_preserves_multiple_sections(data_dir, simple_model):
    simple_model.reset(datetime(2026, 1, 1, 10, 0, 0))
    simple_model.start(datetime(2026, 1, 1, 11, 0, 0))
    store.save(simple_model)

    loaded, _ = store.load(store.tracker_path(simple_model))
    assert len(loaded.sections) == 2
    assert loaded.sections[0].finished is True
    assert loaded.sections[1].finished is False


# ---------------------------------------------------------------------------
# load returns (None, reason) on corrupt JSON
# ---------------------------------------------------------------------------

def test_load_returns_none_on_corrupt_json(data_dir):
    bad = data_dir / "bad.json"
    bad.write_text("not json at all", encoding="utf-8")

    model, err = store.load(bad)
    assert model is None
    assert err is not None
    assert len(err) > 0


def test_load_returns_none_on_missing_fields(data_dir):
    bad = data_dir / "incomplete.json"
    bad.write_text(json.dumps({"name": "oops"}), encoding="utf-8")

    model, err = store.load(bad)
    assert model is None


# ---------------------------------------------------------------------------
# atomic write uses os.replace
# ---------------------------------------------------------------------------

def test_atomic_write_uses_os_replace(data_dir, simple_model):
    with patch("tracker_app.store.os.replace") as mock_replace:
        store.save(simple_model)
        assert mock_replace.called
        tmp_arg, final_arg = mock_replace.call_args[0]
        assert str(tmp_arg).endswith(".json.tmp")
        assert str(final_arg).endswith(".json")
        assert not str(final_arg).endswith(".tmp")


# ---------------------------------------------------------------------------
# load_all
# ---------------------------------------------------------------------------

def test_load_all_returns_sorted_by_created(data_dir):
    m1 = TrackerModel.new("first")
    m1.created = datetime(2026, 1, 1)
    m2 = TrackerModel.new("second")
    m2.created = datetime(2026, 1, 3)
    m3 = TrackerModel.new("third")
    m3.created = datetime(2026, 1, 2)

    for m in [m2, m3, m1]:
        store.save(m)

    loaded = store.load_all()
    assert [m.name for m in loaded] == ["first", "third", "second"]


def test_load_all_skips_corrupt_files(data_dir):
    good = TrackerModel.new("good")
    store.save(good)
    (data_dir / "corrupt.json").write_text("garbage", encoding="utf-8")

    loaded = store.load_all()
    assert len(loaded) == 1
    assert loaded[0].name == "good"


def test_load_all_returns_empty_when_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "nonexistent")
    assert store.load_all() == []


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def test_delete_removes_file(data_dir, simple_model):
    store.save(simple_model)
    assert store.tracker_path(simple_model).exists()

    store.delete(simple_model)
    assert not store.tracker_path(simple_model).exists()


def test_delete_is_silent_when_file_missing(data_dir, simple_model):
    store.delete(simple_model)  # should not raise


def test_adjustments_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    model = TrackerModel.new("adjusted")
    model.adjust(420, datetime(2026, 1, 1, 12, 0, 0), reason="forgot to start")
    model.adjust(-60, datetime(2026, 1, 1, 12, 5, 0))
    store.save(model)

    loaded, err = store.load(store.tracker_path(model))
    assert err is None
    adjustments = loaded.current_section.adjustments
    assert [a.seconds for a in adjustments] == [420.0, -60.0]
    assert adjustments[0].created == datetime(2026, 1, 1, 12, 0, 0)
    assert adjustments[0].reason == "forgot to start"
    assert adjustments[1].reason == ""


def test_section_without_adjustments_key_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({
        "id": "abc",
        "name": "legacy",
        "created": "2026-01-01T12:00:00",
        "sections": [
            {"id": "s1", "finished": False, "intervals": [], "last_start": None}
        ],
    }), encoding="utf-8")

    loaded, err = store.load(path)
    assert err is None
    assert loaded.current_section.adjustments == []
