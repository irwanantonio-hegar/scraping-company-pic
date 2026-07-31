import json
from pathlib import Path
import pytest
from scraper.state import State, RowState


def test_state_load_empty(tmp_path):
    p = tmp_path / "x.state.json"
    s = State(p)
    assert s.load() == {}


def test_state_update_and_is_done(tmp_path):
    p = tmp_path / "x.state.json"
    s = State(p)
    s.update(RowState(index=0, company="PT A", status="done", sources=["OSS"], fields_filled=["Phone"]))
    assert s.is_done(0) is True
    assert s.is_done(1) is False


def test_state_persists_to_disk(tmp_path):
    p = tmp_path / "x.state.json"
    s1 = State(p)
    s1.update(RowState(index=2, company="PT B", status="done", sources=["Google"], fields_filled=["PIC Name"]))
    s2 = State(p)
    loaded = s2.load()
    assert 2 in loaded
    assert loaded[2].company == "PT B"


def test_state_clear(tmp_path):
    p = tmp_path / "x.state.json"
    s = State(p)
    s.update(RowState(index=0, company="X", status="done", sources=[], fields_filled=[]))
    s.clear()
    assert p.exists() is False or json.loads(p.read_text()) == {"rows": []}