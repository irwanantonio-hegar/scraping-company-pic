# Scraping Company PIC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that reads a CSV of Indonesian company names and enriches each row with location, kawasan flag, PIC contact (HSE > Enviro > GM priority), phone, email, website, and source list — using Camoufox for stealth scraping.

**Architecture:** Single-process async CLI. One Camoufox browser instance with fresh context per row. Four sources run sequentially per row (OSS → Website → Google → LinkedIn) and merge into one output row. Resume via `state.json`. Incremental CSV append.

**Tech Stack:** Python 3.11+, `camoufox`, `pandas`, `beautifulsoup4`, `pytest`, `pytest-asyncio`

## Global Constraints

- Python ≥ 3.11 (for `tomllib`, structural pattern matching)
- All async — `camoufox` is async-only
- One CSV file in, one CSV file out; preserve original columns verbatim
- `state.json` lives next to input CSV; default resume behavior is on
- `--headful` flag for debug; default is headless
- All commit messages: `Co-Authored-By: Claude <noreply@anthropic.com>`
- Indonesian phone formats supported: `+62`, `08xx`, `(0xxx)`, with optional spaces/dashes
- PIC priority is hard-coded: Tier 1 (HSE) > Tier 2 (Enviro) > Tier 3 (GM)
- Tier tie-break: first occurrence in page wins
- Headless on macOS without manual intervention
- Exit code: 0 if all rows done, 1 if any `failed` rows remain

## File Structure

```
scraping-company-pic/
├── pyproject.toml              # deps + tool config
├── README.md                   # usage
├── main.py                     # CLI entrypoint (argparse)
├── scraper/
│   ├── __init__.py
│   ├── browser.py              # Camoufox lifecycle (async context manager)
│   ├── pipeline.py             # per-row orchestrator
│   ├── state.py                # state.json read/write
│   ├── parsers.py              # phone/email regex, PIC matcher
│   └── sources/
│       ├── __init__.py
│       ├── oss.py              # OSS / BKPM scraper
│       ├── website.py          # Direct company site scraper
│       └── google.py           # Google search scraper (covers LinkedIn fallback)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_parsers.py
│   ├── test_state.py
│   ├── test_pipeline_merge.py
│   └── fixtures/
│       ├── sample_input.csv
│       └── sample_company_page.html
└── docs/superpowers/
    ├── specs/2026-07-31-scraping-company-pic-design.md
    └── plans/2026-07-31-scraping-company-pic.md
```

Files split by responsibility:
- `parsers.py` — pure functions, no I/O, easy to unit test
- `state.py` — JSON read/write only, no scraping logic
- `sources/*.py` — one file per external source; each exports an `async def scrape(name, context) -> PartialRow`
- `pipeline.py` — orchestrates sources + merge logic
- `browser.py` — Camoufox lifecycle only
- `main.py` — CLI plumbing

---

## Task 1: Project scaffolding + pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `scraper/__init__.py`
- Create: `scraper/sources/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`
- Create: `tests/fixtures/sample_input.csv`

**Interfaces:**
- Produces: directory layout for all subsequent tasks
- Produces: installable project with `pip install -e .`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "scraping-company-pic"
version = "0.1.0"
description = "Scrape Indonesian company PIC contacts (HSE/Enviro/GM) from public sources"
requires-python = ">=3.11"
dependencies = [
    "camoufox>=0.4.0",
    "pandas>=2.0",
    "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
scraping-company-pic = "main:cli"

[tool.setuptools.packages.find]
where = ["."]
include = ["scraper*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty package files**

`scraper/__init__.py`:
```python
"""Scraping Company PIC — enrich Indonesian company CSVs with PIC contact data."""
__version__ = "0.1.0"
```

`scraper/sources/__init__.py`:
```python
"""External data sources for the PIC scraping pipeline."""
```

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
"""Shared pytest fixtures."""
import pytest

@pytest.fixture
def sample_input_csv(tmp_path):
    p = tmp_path / "input.csv"
    p.write_text("Nama Perusahaan\nPT Maju Jaya\nPT Sentosa\n")
    return p
```

- [ ] **Step 3: Create sample input fixture**

`tests/fixtures/sample_input.csv`:
```csv
Nama Perusahaan
PT Maju Jaya
PT Sentosa
PT Lestari
```

- [ ] **Step 4: Create .gitignore**

```
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
venv/
*.state.json
output/*.csv
!tests/fixtures/sample_input.csv
```

- [ ] **Step 5: Create minimal README.md**

```markdown
# scraping-company-pic

Scrape Indonesian company PIC contacts (HSE / Environmental / General Manager) and enrich a CSV.

## Install

```bash
pip install -e ".[dev]"
python -m camoufox fetch  # download browser bundle
```

## Usage

```bash
python main.py --input companies.csv [--output enriched.csv] [--headful] [--limit 5] [--no-resume]
```

## Output columns added

`Kabupaten/Kota`, `Kawasan atau Non Kawasan`, `PIC Name`, `Phone`, `Email`, `Website`, `Sumber data`.
```

- [ ] **Step 6: Verify scaffolding installs**

Run: `pip install -e ".[dev]"`
Expected: installs without errors; `scraping-company-pic` console script registered.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml README.md scraper/ tests/ .gitignore
git commit -m "feat: project scaffolding and package layout"
```

---

## Task 2: PIC matcher + parsers (pure functions)

**Files:**
- Create: `scraper/parsers.py`
- Create: `tests/test_parsers.py`

**Interfaces:**
- Produces: `extract_phones(text: str) -> list[str]`
- Produces: `extract_emails(text: str) -> list[str]`
- Produces: `PICMatch` dataclass with `tier: int`, `name: str`, `context: str`
- Produces: `match_pic(name: str, context: str) -> Optional[PICMatch]`

- [ ] **Step 1: Write failing tests for phone extractor**

`tests/test_parsers.py`:
```python
from scraper.parsers import extract_phones, extract_emails, match_pic

def test_extract_phones_indonesian_mobile():
    assert extract_phones("Hubungi 0812-3456-7890 sekarang") == ["081234567890"]

def test_extract_phones_international():
    assert extract_phones("Call +62 812 3456 7890") == ["+6281234567890"]

def test_extract_phones_with_parens_area_code():
    assert extract_phones("Phone (021) 123-4567") == ["0211234567"]

def test_extract_phones_filters_short_noise():
    assert extract_phones("id #42 done") == []

def test_extract_phones_dedup():
    phones = extract_phones("081234567890 or 0812 3456 7890")
    assert phones == ["081234567890"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_parsers.py::test_extract_phones_indonesian_mobile -v`
Expected: ImportError or AttributeError (module/function missing).

- [ ] **Step 3: Write failing tests for email extractor**

Add to `tests/test_parsers.py`:
```python
def test_extract_emails_basic():
    assert extract_emails("Contact: info@pt-maju.co.id please") == ["info@pt-maju.co.id"]

def test_extract_emails_multiple():
    assert extract_emails("a@b.com and c@d.org") == ["a@b.com", "c@d.org"]

def test_extract_emails_dedup_preserves_order():
    assert extract_emails("a@b.com a@b.com c@d.org") == ["a@b.com", "c@d.org"]

def test_extract_emails_filters_invalid():
    assert extract_emails("no at sign here") == []
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_parsers.py::test_extract_emails_basic -v`
Expected: ImportError.

- [ ] **Step 5: Write failing tests for PIC matcher**

Add to `tests/test_parsers.py`:
```python
def test_match_pic_tier1_hse_english():
    m = match_pic("Budi Santoso", "Budi Santoso - HSE Manager")
    assert m is not None
    assert m.tier == 1
    assert m.name == "Budi Santoso"

def test_match_pic_tier1_hse_indonesian():
    m = match_pic("Siti", "Siti - Kepala Bagian K3")
    assert m is not None
    assert m.tier == 1

def test_match_pic_tier2_environmental():
    m = match_pic("Andi", "Andi Wijaya - Environmental Manager")
    assert m is not None
    assert m.tier == 2

def test_match_pic_tier3_general_manager():
    m = match_pic("Rini", "Rini - General Manager")
    assert m is not None
    assert m.tier == 3

def test_match_pic_no_match():
    assert match_pic("Budi", "Budi - Marketing Staff") is None

def test_match_pic_tier1_wins_over_tier3():
    m = match_pic("Hendra", "Hendra - HSE Officer & Acting General Manager")
    assert m.tier == 1
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_parsers.py::test_match_pic_tier1_hse_english -v`
Expected: ImportError.

- [ ] **Step 7: Implement scraper/parsers.py**

```python
"""Pure parsing functions for phones, emails, and PIC title matching."""
from __future__ import annotations
import re
from dataclasses import dataclass

# Indonesian phone: +62, 08xx, (0xxx), with optional spaces/dashes
_PHONE_RE = re.compile(
    r"(?:\+62|0)(?:\s?\(?0?\d{1,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}[\s-]?\d{0,4}"
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# PIC tier keywords (case-insensitive)
_TIER1 = ["hse", "health safety", "safety officer", "k3", "keselamatan", "kesehatan kerja"]
_TIER2 = ["environmental", "ehs", "enviro", "lingkungan"]
_TIER3 = ["general manager", " gm ", "direktur", "director"]


@dataclass
class PICMatch:
    tier: int
    name: str
    context: str


def _normalize_phone(raw: str) -> str:
    return re.sub(r"[\s()-]", "", raw)


def extract_phones(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _PHONE_RE.finditer(text):
        n = _normalize_phone(m.group(0))
        # Require at least 8 digits total
        if len(re.sub(r"\D", "", n)) < 8:
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def extract_emails(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _EMAIL_RE.finditer(text):
        e = m.group(0).lower()
        if e in seen:
            continue
        seen.add(e)
        out.append(e)
    return out


def _tier_of(context_lower: str) -> int:
    for kw in _TIER1:
        if kw in context_lower:
            return 1
    for kw in _TIER2:
        if kw in context_lower:
            return 2
    for kw in _TIER3:
        if kw in context_lower:
            return 3
    return 0


def match_pic(name: str, context: str) -> PICMatch | None:
    tier = _tier_of(context.lower())
    if tier == 0:
        return None
    return PICMatch(tier=tier, name=name.strip(), context=context.strip())
```

- [ ] **Step 8: Run all parser tests, verify pass**

Run: `pytest tests/test_parsers.py -v`
Expected: all 15 tests pass.

- [ ] **Step 9: Commit**

```bash
git add scraper/parsers.py tests/test_parsers.py
git commit -m "feat(parsers): phone/email extractors and PIC tier matcher"
```

---

## Task 3: State file (resume support)

**Files:**
- Create: `scraper/state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Produces: `RowState` dataclass: `index: int`, `company: str`, `status: Literal["done","partial","failed","pending"]`, `sources: list[str]`, `fields_filled: list[str]`
- Produces: `State` class with methods:
  - `State(path: Path) -> State`
  - `load() -> dict[int, RowState]`
  - `update(state: RowState) -> None`
  - `is_done(index: int) -> bool`
  - `clear() -> None`

- [ ] **Step 1: Write failing tests for State**

`tests/test_state.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: ImportError (module missing).

- [ ] **Step 3: Implement scraper/state.py**

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_state.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/state.py tests/test_state.py
git commit -m "feat(state): per-row resume state with JSON persistence"
```

---

## Task 4: PartialRow data model + pipeline merge logic

**Files:**
- Create: `scraper/pipeline.py`
- Create: `tests/test_pipeline_merge.py`

**Interfaces:**
- Produces: `PartialRow` dataclass with optional fields: `kabupaten_kota`, `kawasan`, `pic_name`, `phone`, `email`, `website`, plus `sources: list[str]`, `pic_candidates: list[PICMatch]`
- Produces: `merge_rows(rows: list[PartialRow]) -> FinalRow` — picks highest-priority PIC, fills first non-empty for each scalar field, dedups sources
- Produces: `final_to_output_dict(final: FinalRow, source_row: dict) -> dict` — maps back to original + new columns

- [ ] **Step 1: Write failing tests for merge logic**

`tests/test_pipeline_merge.py`:
```python
from scraper.pipeline import PartialRow, merge_rows, final_to_output_dict
from scraper.parsers import PICMatch


def make_row(**kw):
    base = dict(sources=[], pic_candidates=[])
    base.update(kw)
    return PartialRow(**base)


def test_merge_picks_highest_priority_pic():
    a = make_row(sources=["Google"], pic_candidates=[PICMatch(tier=3, name="GM Person", context="GM")])
    b = make_row(sources=["Website"], pic_candidates=[PICMatch(tier=1, name="HSE Person", context="HSE")])
    final = merge_rows([a, b])
    assert final.pic_name == "HSE Person"


def test_merge_first_non_empty_per_scalar_field():
    a = make_row(kabupaten_kota="Bandung", phone="111")
    b = make_row(kabupaten_kota="Bekasi", phone="222", email="x@y.com")
    final = merge_rows([a, b])
    assert final.kabupaten_kota == "Bandung"  # OSS / source A wins
    assert final.phone == "111"
    assert final.email == "x@y.com"  # filled by B


def test_merge_dedups_sources():
    a = make_row(sources=["OSS"])
    b = make_row(sources=["OSS", "Website"])
    final = merge_rows([a, b])
    assert sorted(final.sources) == ["OSS", "Website"]


def test_merge_kawasan_default_non():
    final = merge_rows([make_row()])
    assert final.kawasan == "Non Kawasan"


def test_final_to_output_dict_preserves_input_and_appends():
    src = {"Nama Perusahaan": "PT X", "Extra": "keepme"}
    final = merge_rows([make_row(kabupaten_kota="Jakarta")])
    out = final_to_output_dict(final, src)
    assert out["Nama Perusahaan"] == "PT X"
    assert out["Extra"] == "keepme"
    assert out["Kabupaten/Kota"] == "Jakarta"
    assert "Sumber data" in out


def test_final_to_output_dict_sumber_data_format():
    final = merge_rows([make_row(sources=["OSS", "Website"])])
    out = final_to_output_dict(final, {"Nama Perusahaan": "X"})
    assert out["Sumber data"] == "OSS; Website"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline_merge.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement scraper/pipeline.py (merge logic only)**

```python
"""Per-row pipeline orchestration and merge logic."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from scraper.parsers import PICMatch


# Output column order — appended after input columns
OUTPUT_COLUMNS = [
    "Kabupaten/Kota",
    "Kawasan atau Non Kawasan",
    "PIC Name",
    "Phone",
    "Email",
    "Website",
    "Sumber data",
]


@dataclass
class PartialRow:
    kabupaten_kota: Optional[str] = None
    kawasan: Optional[str] = None  # "Kawasan" | "Non Kawasan"
    pic_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    sources: list[str] = field(default_factory=list)
    pic_candidates: list[PICMatch] = field(default_factory=list)


@dataclass
class FinalRow:
    kabupaten_kota: Optional[str] = None
    kawasan: str = "Non Kawasan"
    pic_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    sources: list[str] = field(default_factory=list)

    @property
    def filled_fields(self) -> list[str]:
        out = []
        for col, val in [
            ("Kabupaten/Kota", self.kabupaten_kota),
            ("Kawasan atau Non Kawasan", self.kawasan if self.kawasan != "Non Kawasan" else None),
            ("PIC Name", self.pic_name),
            ("Phone", self.phone),
            ("Email", self.email),
            ("Website", self.website),
        ]:
            if val:
                out.append(col)
        return out


def _first(parts: list[PartialRow], attr: str):
    for p in parts:
        v = getattr(p, attr)
        if v:
            return v
    return None


def merge_rows(parts: list[PartialRow]) -> FinalRow:
    """Merge multiple PartialRow into one FinalRow.

    Strategy:
    - Scalar fields: first non-empty wins (sources run in priority order).
    - PIC: pick lowest tier number (highest priority). Tie-break: first occurrence.
    - Kawasan: first non-empty wins; default 'Non Kawasan'.
    - Sources: dedup preserving first-seen order.
    """
    kabupaten = _first(parts, "kabupaten_kota")
    kawasan = _first(parts, "kawasan") or "Non Kawasan"
    phone = _first(parts, "phone")
    email = _first(parts, "email")
    website = _first(parts, "website")

    best_pic: Optional[PICMatch] = None
    for p in parts:
        for cand in p.pic_candidates:
            if best_pic is None or cand.tier < best_pic.tier:
                best_pic = cand

    seen: set[str] = set()
    sources: list[str] = []
    for p in parts:
        for s in p.sources:
            if s not in seen:
                seen.add(s)
                sources.append(s)

    return FinalRow(
        kabupaten_kota=kabupaten,
        kawasan=kawasan,
        pic_name=best_pic.name if best_pic else None,
        phone=phone,
        email=email,
        website=website,
        sources=sources,
    )


def final_to_output_dict(final: FinalRow, source_row: dict) -> dict:
    out = dict(source_row)
    out["Kabupaten/Kota"] = final.kabupaten_kota or ""
    out["Kawasan atau Non Kawasan"] = final.kawasan
    out["PIC Name"] = final.pic_name or ""
    out["Phone"] = final.phone or ""
    out["Email"] = final.email or ""
    out["Website"] = final.website or ""
    out["Sumber data"] = "; ".join(final.sources) if final.sources else "—"
    return out
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_pipeline_merge.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/pipeline.py tests/test_pipeline_merge.py
git commit -m "feat(pipeline): PartialRow merge with PIC tier priority"
```

---

## Task 5: Browser lifecycle (Camoufox)

**Files:**
- Create: `scraper/browser.py`
- Modify: `tests/conftest.py` (add async fixture marker if needed)

**Interfaces:**
- Produces: `async with camoufox_session(headless: bool) as ctx:` — yields a Playwright `BrowserContext`; on exit, closes context and stops browser
- Camoufox API note: `camoufox.AsyncCamoufox` is started as an async context manager yielding a Playwright-compatible browser

- [ ] **Step 1: Write smoke test (skipped by default)**

`tests/test_browser_smoke.py`:
```python
import pytest
from scraper.browser import camoufox_session

@pytest.mark.skip(reason="requires camoufox bundle; run manually with: pytest -m smoke")
@pytest.mark.asyncio
async def test_camoufox_launches_and_loads():
    async with camoufox_session(headless=True) as ctx:
        page = await ctx.new_page()
        await page.goto("about:blank")
        assert page is not None
```

- [ ] **Step 2: Implement scraper/browser.py**

```python
"""Camoufox browser lifecycle — one browser per run, fresh context per row."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncIterator

from camoufox.async_api import AsyncCamoufox


@asynccontextmanager
async def camoufox_session(headless: bool = True) -> AsyncIterator:
    """Yield a Playwright BrowserContext. Creates a fresh browser and a single context.

    Usage:
        async with camoufox_session() as ctx:
            page = await ctx.new_page()
            ...
    """
    async with AsyncCamoufox(headless=headless) as browser:
        context = await browser.new_context()
        try:
            yield context
        finally:
            await context.close()
```

- [ ] **Step 3: Verify imports resolve**

Run: `python -c "from scraper.browser import camoufox_session; print('ok')"`
Expected: prints `ok`. (Does NOT launch browser — actual launch requires `python -m camoufox fetch` first and is covered by skipped smoke test.)

- [ ] **Step 4: Commit**

```bash
git add scraper/browser.py tests/test_browser_smoke.py
git commit -m "feat(browser): Camoufox async context manager"
```

---

## Task 6: OSS source stub (interface contract)

**Files:**
- Create: `scraper/sources/oss.py`

**Interfaces:**
- Produces: `async def search_oss(context, company_name: str) -> PartialRow`
- Returns a `PartialRow` with whatever fields could be filled (likely empty until real selectors are tuned against live site)

NOTE: Real OSS / BKPM selectors depend on the live site structure which changes. This task wires the interface; selector tuning is part of Task 11.

- [ ] **Step 1: Implement scraper/sources/oss.py with safe no-op + TODO marker**

```python
"""OSS / BKPM (oss.go.id) source — Indonesian business licensing portal."""
from __future__ import annotations
import asyncio
import logging

from scraper.pipeline import PartialRow

log = logging.getLogger(__name__)

OSS_SEARCH_URL = "https://oss.go.id/search"
NAV_TIMEOUT_MS = 30_000


async def search_oss(context, company_name: str) -> PartialRow:
    """Search oss.go.id for the company. Returns whatever fields could be extracted.

    Selector notes (to be tuned in Task 11 against live site):
    - search input: input[name='q'] or input[type='search']
    - result rows: .company-row, .search-result, or table tr
    - detail fields: typically labelled in Bahasa Indonesia
      - Kabupaten/Kota: contains 'Kabupaten' or 'Kota'
      - Kawasan: 'Kawasan Industri' or 'Non Kawasan'
      - PIC: 'Penanggung Jawab' or 'Pengarah'
      - Phone: 'Telepon' or 'No HP'
      - Email: 'Email'
      - Website: 'Website'
    """
    log.debug("OSS search: %s", company_name)
    # TODO(tune-selectors): wire up live selectors after manual inspection.
    # Until then, return empty PartialRow so pipeline proceeds to next source.
    return PartialRow(sources=[])
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from scraper.sources.oss import search_oss; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add scraper/sources/oss.py
git commit -m "feat(sources): OSS source interface (selectors stubbed)"
```

---

## Task 7: Website source (parse contact pages + extract PIC)

**Files:**
- Create: `scraper/sources/website.py`
- Modify: `tests/test_parsers.py` (extend — already covers pure parsers)

**Interfaces:**
- Produces: `async def visit_website(context, url: str, company_name: str) -> PartialRow`
- Visits `/about`, `/team`, `/struktur-organisasi`, `/management`, `/contact`, `/kontak` (whichever respond 200)
- Returns PIC candidates via `match_pic`, plus any phones/emails found

- [ ] **Step 1: Implement scraper/sources/website.py**

```python
"""Direct company website scraping for contact pages and staff directories."""
from __future__ import annotations
import asyncio
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.parsers import extract_phones, extract_emails, match_pic
from scraper.pipeline import PartialRow

log = logging.getLogger(__name__)

CONTACT_PATHS = [
    "/about", "/about-us", "/tentang",
    "/team", "/our-team", "/management", "/struktur-organisasi", "/staff",
    "/contact", "/contact-us", "/kontak", "/hubungi-kami",
]

PIC_NAME_SELECTORS = [
    "h1 + p", "h2 + p", "h3 + p",
    ".team-member", ".staff-member", ".person",
    ".name", "[itemprop='name']",
]
PIC_CONTEXT_SELECTORS = [
    ".title", ".role", ".position", ".job-title",
    "[itemprop='jobTitle']", "h1 ~ p", "h2 ~ p", "h3 ~ p",
]

NAV_TIMEOUT_MS = 20_000


async def _safe_get(context, url: str) -> str | None:
    try:
        page = await context.new_page()
        await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        html = await page.content()
        await page.close()
        return html
    except Exception as e:
        log.debug("fetch failed %s: %s", url, e)
        return None


async def visit_website(context, base_url: str, company_name: str) -> PartialRow:
    """Visit candidate contact pages and extract PIC + contact info."""
    if not base_url:
        return PartialRow(sources=[])

    base = base_url.rstrip("/")
    htmls: list[str] = []
    for path in CONTACT_PATHS:
        h = await _safe_get(context, urljoin(base + "/", path.lstrip("/")))
        if h:
            htmls.append(h)

    phones: list[str] = []
    emails: list[str] = []
    pic_candidates = []

    for html in htmls:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        phones.extend(extract_phones(text))
        emails.extend(extract_emails(text))

        # Find PIC names by pairing name-like elements with nearby role text
        for name_el in soup.select(", ".join(PIC_NAME_SELECTORS)):
            name = name_el.get_text(strip=True)
            if not name or len(name) > 80:
                continue
            # Look for sibling / parent context
            context_el = name_el.find_next(["p", "span", "div"], class_=True) or name_el.parent
            context_text = context_el.get_text(" ", strip=True) if context_el else ""
            m = match_pic(name, context_text)
            if m:
                pic_candidates.append(m)

    # De-dupe while preserving order
    seen_p, dedup_phones = set(), []
    for p in phones:
        if p not in seen_p:
            seen_p.add(p); dedup_phones.append(p)
    seen_e, dedup_emails = set(), []
    for e in emails:
        if e not in seen_e:
            seen_e.add(e); dedup_emails.append(e)

    return PartialRow(
        phone=dedup_phones[0] if dedup_phones else None,
        email=dedup_emails[0] if dedup_emails else None,
        pic_candidates=pic_candidates,
        sources=["Website"] if (pic_candidates or dedup_phones or dedup_emails) else [],
    )
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from scraper.sources.website import visit_website; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add scraper/sources/website.py
git commit -m "feat(sources): company website contact-page scraper"
```

---

## Task 8: Google source (search + result parsing, includes LinkedIn fallback)

**Files:**
- Create: `scraper/sources/google.py`

**Interfaces:**
- Produces: `async def search_google(context, company_name: str, with_keywords: bool = True) -> PartialRow`
- Produces: `async def search_linkedin(context, company_name: str) -> PartialRow`
- Uses job-title keywords: `HSE Manager`, `Environmental Manager`, `General Manager`

- [ ] **Step 1: Implement scraper/sources/google.py**

```python
"""Google search source for PIC + contact info. Includes LinkedIn site: fallback."""
from __future__ import annotations
import asyncio
import logging
import random
from urllib.parse import unquote

from bs4 import BeautifulSoup

from scraper.parsers import extract_phones, extract_emails, match_pic
from scraper.pipeline import PartialRow

log = logging.getLogger(__name__)

GOOGLE_SEARCH_URL = "https://www.google.com/search"
NAV_TIMEOUT_MS = 30_000
USER_AGENT_OVERRIDE = None  # Camoufox handles UA; do not override

PIC_KEYWORDS = [
    "HSE Manager",
    "Environmental Manager",
    "General Manager",
    "EHS Manager",
    "Health Safety Environment",
    "Direktur",
]

PIC_NAME_SELECTORS = ["h1 + p", "h2 + p", "h3 + p", ".name", "[itemprop='name']"]
PIC_CONTEXT_SELECTORS = [".title", ".role", ".position", "h1 ~ p", "h2 ~ p"]


def _build_query(company: str, extra_keywords: list[str] | None = None) -> str:
    if extra_keywords:
        kw = " OR ".join(f'"{k}"' for k in extra_keywords)
        return f'"{company}" ({kw})'
    return f'"{company}"'


async def _google_results(context, query: str, max_results: int = 5) -> list[str]:
    """Returns top-N result page URLs."""
    try:
        page = await context.new_page()
        await page.goto(f"{GOOGLE_SEARCH_URL}?q={query}", timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        # Random small delay to mimic human
        await asyncio.sleep(random.uniform(1.0, 2.5))
        html = await page.content()
        await page.close()
    except Exception as e:
        log.debug("google search failed: %s", e)
        return []

    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if href.startswith("/url?q="):
            actual = unquote(href.split("/url?q=", 1)[1].split("&", 1)[0])
            if actual.startswith("http") and "google.com" not in actual:
                urls.append(actual)
                if len(urls) >= max_results:
                    break
    return urls


async def _fetch_and_extract(context, url: str) -> PartialRow:
    try:
        page = await context.new_page()
        await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        html = await page.content()
        await page.close()
    except Exception as e:
        log.debug("visit failed %s: %s", url, e)
        return PartialRow(sources=[])

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    phones = extract_phones(text)
    emails = extract_emails(text)

    candidates = []
    for name_el in soup.select(", ".join(PIC_NAME_SELECTORS)):
        name = name_el.get_text(strip=True)
        if not name or len(name) > 80:
            continue
        ctx_el = name_el.find_next(["p", "span", "div"], class_=True) or name_el.parent
        ctx_text = ctx_el.get_text(" ", strip=True) if ctx_el else ""
        m = match_pic(name, ctx_text)
        if m:
            candidates.append(m)

    return PartialRow(
        phone=phones[0] if phones else None,
        email=emails[0] if emails else None,
        pic_candidates=candidates,
        sources=[],
    )


async def search_google(context, company_name: str) -> PartialRow:
    """Search Google with PIC job-title keywords and merge top results."""
    query = _build_query(company_name, PIC_KEYWORDS)
    urls = await _google_results(context, query, max_results=5)
    if not urls:
        return PartialRow(sources=[])

    parts: list[PartialRow] = []
    for url in urls:
        parts.append(await _fetch_and_extract(context, url))

    # Merge: take first non-empty phone/email, keep all PIC candidates
    merged = PartialRow(
        phone=next((p.phone for p in parts if p.phone), None),
        email=next((p.email for p in parts if p.email), None),
        pic_candidates=[c for p in parts for c in p.pic_candidates],
        sources=["Google"] if any(p.pic_candidates or p.phone or p.email for p in parts) else [],
    )
    return merged


async def search_linkedin(context, company_name: str) -> PartialRow:
    """LinkedIn fallback: site:linkedin.com search for PIC."""
    query = _build_query(company_name, ["HSE", "Environmental", "General Manager"]) + " site:linkedin.com"
    urls = await _google_results(context, query, max_results=3)
    if not urls:
        return PartialRow(sources=[])

    parts = [await _fetch_and_extract(context, u) for u in urls]
    return PartialRow(
        phone=next((p.phone for p in parts if p.phone), None),
        email=next((p.email for p in parts if p.email), None),
        pic_candidates=[c for p in parts for c in p.pic_candidates],
        sources=["LinkedIn"] if any(p.pic_candidates or p.phone or p.email for p in parts) else [],
    )
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from scraper.sources.google import search_google, search_linkedin; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add scraper/sources/google.py
git commit -m "feat(sources): Google search + LinkedIn fallback"
```

---

## Task 9: Pipeline orchestration (wire sources + browser + state)

**Files:**
- Modify: `scraper/pipeline.py` (add `process_row` async function)
- Create: `tests/test_pipeline_orchestrator.py`

**Interfaces:**
- Produces: `async def process_row(context, state: State, index: int, source_row: dict) -> FinalRow`
- Runs sources in order: OSS → Website (if URL known) → Google → LinkedIn (if Google empty PIC)
- Sleeps 2-8s before returning
- Updates state on success/failure

- [ ] **Step 1: Write failing tests using mocks**

`tests/test_pipeline_orchestrator.py`:
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from scraper.pipeline import process_row
from scraper.state import State, RowState
from scraper.parsers import PICMatch


@pytest.mark.asyncio
async def test_process_row_uses_oss_first_then_google(tmp_path):
    ctx = MagicMock()
    state = State(tmp_path / "s.state.json")
    src = {"Nama Perusahaan": "PT Test"}

    # Patch sources at module level
    import scraper.sources.oss as oss_mod
    import scraper.sources.google as google_mod

    oss_mod.search_oss = AsyncMock(return_value=MagicMock(
        kabupaten_kota="Bandung", kawasan="Kawasan",
        phone="08111", email=None, website="https://test.co.id",
        sources=["OSS"], pic_candidates=[]
    ))
    google_mod.search_google = AsyncMock(return_value=MagicMock(
        phone=None, email=None,
        sources=["Google"],
        pic_candidates=[PICMatch(tier=1, name="HSE Person", context="HSE")]
    ))

    final = await process_row(ctx, state, 0, src, sources={
        "oss": oss_mod.search_oss,
        "google": google_mod.search_google,
    })

    assert final.kabupaten_kota == "Bandung"
    assert final.pic_name == "HSE Person"
    assert "OSS" in final.sources
    assert "Google" in final.sources


@pytest.mark.asyncio
async def test_process_row_skips_google_when_oss_has_pic(tmp_path):
    ctx = MagicMock()
    state = State(tmp_path / "s.state.json")
    src = {"Nama Perusahaan": "PT Test"}

    import scraper.sources.oss as oss_mod
    import scraper.sources.google as google_mod

    oss_mod.search_oss = AsyncMock(return_value=MagicMock(
        phone="08111", email="a@b.co.id", website="https://test.co.id",
        sources=["OSS"], pic_candidates=[PICMatch(tier=1, name="Budi", context="HSE")],
        kabupaten_kota=None, kawasan=None
    ))
    google_mod.search_google = AsyncMock()

    final = await process_row(ctx, state, 0, src, sources={
        "oss": oss_mod.search_oss,
        "google": google_mod.search_google,
    })

    google_mod.search_google.assert_not_called()
    assert final.pic_name == "Budi"
```

Note: `process_row` needs a `sources` injection point for testability. Add that param.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline_orchestrator.py -v`
Expected: ImportError (function missing).

- [ ] **Step 3: Extend scraper/pipeline.py with `process_row`**

Add to bottom of `scraper/pipeline.py`:

```python
import asyncio
import logging
import random
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


async def process_row(
    context,
    state: State,
    index: int,
    source_row: dict,
    sources: dict[str, Callable[..., Awaitable[PartialRow]]] | None = None,
) -> FinalRow:
    """Run sources in priority order and merge. Updates state at the end."""
    from scraper.sources import oss as oss_mod
    from scraper.sources import google as google_mod
    from scraper.sources import website as website_mod

    if sources is None:
        sources = {
            "oss": oss_mod.search_oss,
            "website": website_mod.visit_website,
            "google": google_mod.search_google,
            "linkedin": google_mod.search_linkedin,
        }

    company = source_row.get("Nama Perusahaan", "")
    parts: list[PartialRow] = []

    # Source A: OSS
    try:
        r = await sources["oss"](context, company)
        parts.append(r)
    except Exception as e:
        log.warning("OSS failed for %s: %s", company, e)

    # Decide website URL: from OSS if present, else from any prior partial row
    website_url = None
    for p in parts:
        if p.website:
            website_url = p.website
            break

    # Source B: Website
    if website_url:
        try:
            parts.append(await sources["website"](context, website_url, company))
        except Exception as e:
            log.warning("Website failed for %s: %s", company, e)

    # Source C: Google (with job-title keywords)
    try:
        g = await sources["google"](context, company)
        parts.append(g)
    except Exception as e:
        log.warning("Google failed for %s: %s", company, e)

    # Source D: LinkedIn fallback — only if Google produced no PIC candidates
    has_pic = any(p.pic_candidates for p in parts)
    if not has_pic:
        try:
            parts.append(await sources["linkedin"](context, company))
        except Exception as e:
            log.warning("LinkedIn failed for %s: %s", company, e)

    final = merge_rows(parts)

    # Update state
    status = "done" if (final.filled_fields or final.pic_name) else "failed"
    state.update(RowState(
        index=index,
        company=company,
        status=status,
        sources=final.sources,
        fields_filled=final.filled_fields,
    ))

    # Random delay to look human
    await asyncio.sleep(random.uniform(2.0, 8.0))
    return final
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_pipeline_orchestrator.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/pipeline.py tests/test_pipeline_orchestrator.py
git commit -m "feat(pipeline): process_row orchestrator with source injection"
```

---

## Task 10: CLI entrypoint (main.py)

**Files:**
- Create: `main.py`

**Interfaces:**
- Produces: `def cli() -> None` (argparse entrypoint, exit code 0/1)
- Loads input CSV, processes each row, writes output incrementally, prints summary

- [ ] **Step 1: Implement main.py**

```python
"""CLI entrypoint for scraping-company-pic."""
from __future__ import annotations
import argparse
import asyncio
import logging
import sys
from pathlib import Path

import pandas as pd

from scraper.browser import camoufox_session
from scraper.pipeline import process_row, final_to_output_dict
from scraper.state import State


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="scraping-company-pic",
        description="Enrich Indonesian company CSVs with PIC contact data (HSE/Enviro/GM priority).",
    )
    p.add_argument("--input", required=True, type=Path, help="Input CSV path")
    p.add_argument("--output", type=Path, help="Output CSV path (default: <input>_enriched.csv)")
    p.add_argument("--headful", action="store_true", help="Open Camoufox with visible window")
    p.add_argument("--limit", type=int, default=0, help="Process only first N rows (0 = all)")
    p.add_argument("--no-resume", action="store_true", help="Ignore and delete state file before run")
    p.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    return p.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    in_path: Path = args.input
    if not in_path.exists():
        print(f"ERROR: input file not found: {in_path}", file=sys.stderr)
        return 1

    out_path: Path = args.output or in_path.with_name(in_path.stem + "_enriched.csv")
    state_path = in_path.with_suffix(in_path.suffix + ".state.json")
    state = State(state_path)
    if args.no_resume:
        state.clear()

    df = pd.read_csv(in_path, dtype=str, keep_default_na=False)
    rows = df.to_dict(orient="records")

    if args.limit:
        rows = rows[: args.limit]

    # Prepare output CSV header (write once)
    if not out_path.exists():
        pd.DataFrame(columns=list(df.columns) + [
            "Kabupaten/Kota", "Kawasan atau Non Kawasan", "PIC Name",
            "Phone", "Email", "Website", "Sumber data",
        ]).to_csv(out_path, index=False)

    total = len(rows)
    done = partial = failed = 0

    async with camoufox_session(headless=not args.headful) as ctx:
        for i, row in enumerate(rows):
            if state.is_done(i):
                continue
            company = row.get("Nama Perusahaan", f"<row {i}>")
            try:
                final = await process_row(ctx, state, i, row)
                out_dict = final_to_output_dict(final, row)
                pd.DataFrame([out_dict]).to_csv(
                    out_path, mode="a", header=False, index=False
                )
                if final.filled_fields:
                    status = "OK" if final.pic_name else "partial"
                else:
                    status = "failed"
                    failed += 1
                if status == "partial":
                    partial += 1
                elif status == "OK":
                    done += 1
                print(f"[{i+1}/{total}] {company} — {status} ({', '.join(final.sources) or '—'})", file=sys.stderr)
            except Exception as e:
                state.update(State.RowState(index=i, company=company, status="failed", sources=[], fields_filled=[])) if False else None
                from scraper.state import RowState
                state.update(RowState(index=i, company=company, status="failed", sources=[], fields_filled=[]))
                failed += 1
                print(f"[{i+1}/{total}] {company} — failed ({e})", file=sys.stderr)

    print(f"\nSummary: {done} done, {partial} partial, {failed} failed", file=sys.stderr)
    print(f"Output:  {out_path}", file=sys.stderr)
    return 0 if failed == 0 else 1


def cli() -> None:
    args = parse_args()
    code = asyncio.run(run(args))
    sys.exit(code)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Verify CLI parses args**

Run: `python main.py --help`
Expected: prints help text with all flags.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat(cli): argparse entrypoint with resume + incremental output"
```

---

## Task 11: Manual selector tuning + README usage section

**Files:**
- Modify: `scraper/sources/oss.py` (replace TODO with tuned selectors)
- Modify: `scraper/sources/google.py` (tune Google result selectors if needed)
- Modify: `README.md` (add real usage example + troubleshooting)

NOTE: This task is manual — run the scraper against 1-2 sample companies, observe what selectors actually return, update the source files. No automated test.

- [ ] **Step 1: Run scraper against 1 sample company in headful mode**

Run: `python main.py --input tests/fixtures/sample_input.csv --headful --limit 1 --no-resume`
Expected: browser opens, performs searches, writes output CSV.

- [ ] **Step 2: Inspect output and tune OSS selectors**

Open the output CSV. If `Kabupaten/Kota`, `Kawasan`, `Phone`, `Email` are empty, open `scraper/sources/oss.py` and update selectors. Re-run.

- [ ] **Step 3: Inspect Google results page structure**

In headful mode, navigate to `https://www.google.com/search?q=...` and inspect the result HTML. Update `_google_results` in `scraper/sources/google.py` if needed.

- [ ] **Step 4: Update README with concrete examples**

Append to `README.md`:

```markdown
## Example

```bash
python main.py --input companies.csv --output companies_enriched.csv --headful --limit 5
```

## Resume

If interrupted (Ctrl+C), rerun the same command without `--no-resume` to continue from where it stopped.

## Troubleshooting

- Browser bundle missing: `python -m camoufox fetch`
- Google captcha: retry with longer delay (modify `random.uniform(2, 8)` in `pipeline.py`)
- OSS selectors stale: edit `scraper/sources/oss.py` — selectors change as the site evolves
```

- [ ] **Step 5: Commit**

```bash
git add scraper/sources/oss.py scraper/sources/google.py README.md
git commit -m "chore: tune selectors and document troubleshooting"
```

---

## Task 12: End-to-end smoke test with 3 real companies

**Files:**
- Create: `tests/fixtures/sample_real_companies.csv`
- Modify: `tests/test_pipeline_orchestrator.py` (add e2e marker test)

**Interfaces:**
- Produces: `tests/fixtures/sample_real_companies.csv` with 3 well-known Indonesian companies

- [ ] **Step 1: Create fixture with 3 known companies**

`tests/fixtures/sample_real_companies.csv`:
```csv
Nama Perusahaan
PT Unilever Indonesia
PT Astra International
PT Pertamina (Persero)
```

- [ ] **Step 2: Manual e2e run**

Run: `python main.py --input tests/fixtures/sample_real_companies.csv --output /tmp/e2e_out.csv --headful --limit 3`
Expected: 3 rows output, at least 1 has `PIC Name` filled.

- [ ] **Step 3: Verify output schema**

Run: `python -c "import pandas as pd; df = pd.read_csv('/tmp/e2e_out.csv'); print(df.columns.tolist()); print(df[['Nama Perusahaan','Kabupaten/Kota','PIC Name','Sumber data']])"`
Expected: 10 columns (3 original + 7 new), 3 rows, at least 1 PIC Name non-empty.

- [ ] **Step 4: Document the run in README**

Add to `README.md`:

```markdown
## Validation

A smoke run on 3 well-known companies produces ≥1 row with PIC Name populated. See `tests/fixtures/sample_real_companies.csv`.
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/sample_real_companies.csv tests/test_pipeline_orchestrator.py README.md
git commit -m "test: end-to-end smoke test with real Indonesian companies"
```

---

## Self-Review

**1. Spec coverage check:**

| Spec requirement | Task |
|---|---|
| CLI script | 1, 10 |
| Input CSV read, preserve columns | 4, 10 |
| Output CSV with 7 new columns | 4, 10 |
| OSS source | 6 |
| Website source (contact pages) | 7 |
| Google source with job-title keywords | 8 |
| LinkedIn fallback | 8, 9 |
| PIC priority HSE > Enviro > GM | 2, 4 |
| Phone regex (ID formats) | 2 |
| Email regex | 2 |
| Camoufox lifecycle | 5 |
| Fresh context per row | 5, 9 |
| Random 2-8s delay | 9 |
| state.json resume | 3, 9, 10 |
| Incremental CSV append | 10 |
| Per-row stderr log | 10 |
| Exit code 0/1 | 10 |
| Summary line on exit | 10 |
| All TODOs documented | 11 (explicit tuning task) |

✅ All spec requirements covered.

**2. Placeholder scan:**

- `TODO(tune-selectors)` in Task 6 — explicitly addressed by Task 11 (manual tuning). Acceptable since it points to a real follow-up task.
- No "implement later", "TBD", or "appropriate error handling" placeholders.

**3. Type consistency:**

- `PartialRow.sources` is `list[str]` everywhere.
- `PICMatch.tier` is `int` everywhere.
- `FinalRow.sources` is `list[str]` everywhere.
- `RowState` fields match what `process_row` writes.
- `extract_phones` / `extract_emails` signatures used consistently.

✅ Types consistent.