"""Resume state for the scraping pipeline."""
from __future__ import annotations
import json
import threading
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Literal

Status = Literal["done", "partial", "failed", "pending"]


@dataclass
class RowState:
    index: int
    company: str
    status: Status
    sources: list[str] = field(default_factory=list)
    fields_filled: list[str] = field(default_factory=list)


class State:
    """Thread-safe per-input state file. One State instance per input CSV."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._cache: dict[int, RowState] = self._read()

    def _read(self) -> dict[int, RowState]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {}
        rows = data.get("rows", [])
        out: dict[int, RowState] = {}
        for r in rows:
            rs = RowState(
                index=r["index"],
                company=r["company"],
                status=r["status"],
                sources=r.get("sources", []),
                fields_filled=r.get("fields_filled", []),
            )
            out[rs.index] = rs
        return out

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [asdict(rs) for rs in self._cache.values()]
        self.path.write_text(json.dumps({"rows": rows}, indent=2, ensure_ascii=False))

    def load(self) -> dict[int, RowState]:
        with self._lock:
            return dict(self._cache)

    def update(self, state: RowState) -> None:
        with self._lock:
            self._cache[state.index] = state
            self._write()

    def is_done(self, index: int) -> bool:
        with self._lock:
            rs = self._cache.get(index)
            return rs is not None and rs.status == "done"

    def clear(self) -> None:
        with self._lock:
            self._cache = {}
            if self.path.exists():
                self.path.unlink()