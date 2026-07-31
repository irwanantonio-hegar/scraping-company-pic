# Design: scraping-company-pic CLI

**Date:** 2026-07-31
**Status:** Approved
**Owner:** TBD

## Purpose

A Python CLI script that takes a CSV of Indonesian company names and enriches each row with contact data for the company's PIC (Person In Charge) holding one of these roles — in priority order:

1. **HSE** (Health, Safety, Environment) — also K3 / Keselamatan Kesehatan Kerja
2. **Enviro / EHS** (Environmental)
3. **General Manager / Director**

If multiple matches exist, the highest-priority tier wins and only one PIC is returned per row.

The script uses **Camoufox** (anti-detect Firefox) to avoid being blocked while scraping public business directories, search engines, and company websites.

## Input

CSV with at minimum:

| Column | Required | Description |
|---|---|---|
| `Nama Perusahaan` | yes | Company name as it should appear in search queries |

The script reads **all** columns from the input CSV and passes them through to the output unchanged. Extra columns are preserved.

## Output

Same CSV plus these columns (appended to the right):

| Column | Source(s) | Description |
|---|---|---|
| `Kabupaten/Kota` | OSS, website, Google | Regency/city of the company |
| `Kawasan atau Non Kawasan` | OSS, website | `Kawasan` if the company sits in a known industrial estate, else `Non Kawasan` |
| `PIC Name` | website, Google | Single name; HSE > Enviro > GM priority |
| `Phone` | OSS, website, Google | PIC phone or main company line |
| `Email` | OSS, website, Google | PIC email or general contact email |
| `Website` | OSS, Google | Company website URL |
| `Sumber data` | (meta) | Semicolon-joined list of sources that contributed any field |

Output file: `<input>_enriched.csv` by default. Overridable via `--output`.

## Architecture

```
scraping-company-pic/
├── pyproject.toml          # camoufox, pandas, beautifulsoup4, click (or argparse)
├── main.py                 # CLI entrypoint
├── scraper/
│   ├── __init__.py
│   ├── browser.py          # Camoufox lifecycle, per-row context rotation
│   ├── pipeline.py         # Per-row orchestrator + PIC priority merge
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── oss.py          # oss.go.id search + detail
│   │   ├── google.py       # Google search + top-result parsing
│   │   └── website.py      # Direct company site /about, /team, /contact
│   ├── parsers.py          # Phone/email regex, PIC title matcher
│   └── state.py            # Resume state (state.json)
└── README.md
```

## Components

### `main.py` — CLI

Single command:

```bash
python main.py --input companies.csv [--output enriched.csv] [--headful] [--limit N]
```

- `--input` — path to input CSV (required)
- `--output` — output CSV path (default: `<input>_enriched.csv`)
- `--headful` — open Camoufox with a visible window (debugging)
- `--limit` — process only first N rows (testing)
- `--resume` — default true; set `--no-resume` to start fresh

Loads CSV → for each row → runs pipeline → writes row to output CSV in append mode.

### `browser.py` — Camoufox lifecycle

- One `AsyncCamoufox` browser instance for the whole run
- For each company: `await browser.new_context()` (fresh fingerprint, isolated cookies)
- After processing: `await context.close()`
- Randomized delay `await asyncio.sleep(random.uniform(2, 8))` between rows

### `pipeline.py` — per-row orchestrator

For each company name, runs sources in order and merges:

1. **Source A — OSS / BKPM** (`oss.py`)
   - Query: search company name on `oss.go.id`
   - Extract: location (Kabupaten/Kota), Kawasan/Non Kawasan flag, website, phone, email
   - Mark these fields as "filled by OSS"
2. **Source B — Direct website** (`website.py`) — only if Source A provided a URL or if Source C found one
   - Visit `/about`, `/team`, `/struktur-organisasi`, `/management`, `/contact`, `/kontak`
   - Extract names + titles; pass through PIC matcher
   - Extract phone/email if not already filled
3. **Source C — Google with job-title keywords** (`google.py`)
   - Query: `"<company>" ("HSE Manager" OR "Environmental Manager" OR "General Manager")`
   - Visit top 3 results
   - Extract names + titles from result snippets / target pages
   - Pass through PIC matcher
4. **Source D — Google `site:linkedin.com`** — only if Source C found no PIC
   - Query: `"<company>" ("HSE" OR "Environmental" OR "General Manager") site:linkedin.com`
   - Parse names from LinkedIn snippets

After all sources: pick top-tier PIC, fill `Sumber data` = list of contributing source names.

### `parsers.py`

- `extract_phones(text: str) -> list[str]` — regex for ID phone formats (`+62`, `08xx`, `(0xxx)`)
- `extract_emails(text: str) -> list[str]` — RFC-lite regex
- `match_pic(name: str, context: str) -> Optional[PICMatch]` — returns the matched tier (1/2/3) and name if context contains role keywords

PIC matcher keyword sets (case-insensitive):

| Tier | Keywords (English) | Keywords (Indonesian) |
|---|---|---|
| 1 (HSE) | `HSE`, `Health Safety`, `Safety Officer` | `K3`, `Keselamatan`, `Kesehatan Kerja` |
| 2 (Enviro) | `Environmental`, `EHS`, `Enviro` | `Lingkungan` |
| 3 (GM) | `General Manager`, `GM`, `Director` | `Direktur` |

Tier 1 > Tier 2 > Tier 3. If two names tie, prefer the one whose name appears earlier in the page.

### `state.py` — resume support

File: `<input>.state.json` next to the input CSV.

Schema:

```json
{
  "rows": [
    {
      "index": 0,
      "company": "PT Maju Jaya",
      "status": "done",
      "sources": ["OSS", "Website"],
      "fields_filled": ["Kabupaten/Kota", "PIC Name", "Phone", "Email", "Website"]
    }
  ]
}
```

- After each row: status updated to `done` or `failed`
- On startup: rows with `status == "done"` are skipped
- `--no-resume` deletes state file before run

## Data flow

```
CSV → main.py
  → for each row not yet "done":
      pipeline.process(company_name) →
          oss.search(company) → partial_row
          google.search(company) → partial_row
          website.visit(url) → partial_row (if URL known)
          pic_matcher.pick_best(row) → final_row
      state.update(index, "done", sources)
      csv.append(final_row)
```

## Error handling

| Failure | Behavior |
|---|---|
| Source A (OSS) times out | Mark `failed_sources = ["OSS"]`, continue to B |
| Source B (Website) 404 / unreachable | Skip, continue to C |
| Source C (Google) blocked / captcha | Retry once after 30s; then skip |
| No PIC matched in any source | Leave `PIC Name` blank; row marked `done` |
| All sources fail | Row marked `failed`; written to output with `Sumber data = "—"` |
| Process killed (Ctrl+C) | state.json saved; resume on next run |

Exit code: `0` if all rows done, `1` if any `failed` rows remain.

## CLI output

Per-row progress printed to stderr:

```
[3/120] PT Maju Jaya — OK (OSS, Website)
[4/120] PT Sentosa — partial (OSS only)
[5/120] PT Gagal — failed (all sources blocked)
```

Final summary on exit:

```
Summary: 98 done, 15 partial, 7 failed
Output:  companies_enriched.csv
```

## Testing strategy

- **Unit tests** for `parsers.py` (phone regex, email regex, PIC matcher tiers)
- **Integration test** with 5 well-known Indonesian companies (manual sample): e.g. `PT Astra International`, `PT Unilever Indonesia`, `PT Pertamina` — verify at least location + PIC tier filled
- **Smoke test** with `--limit 3 --headful` to confirm Camoufox launches and writes output

## Dependencies

- `camoufox` — anti-detect Firefox browser automation
- `pandas` — CSV I/O
- `beautifulsoup4` — HTML parsing
- `click` (or stdlib `argparse`) — CLI

## Success criteria

- ≥70% of rows have `PIC Name` + `Phone` + `Email` filled from at least one source
- `Sumber data` always populated when any field is filled
- Script resumable from interruption (state.json)
- Runs headless on macOS without manual intervention
- No `TODO` / placeholder fields in the final spec

## Out of scope (YAGNI)

- Proxy rotation — Camoufox fingerprint rotation is sufficient for the target scale
- Database storage — CSV output only
- Multi-threading — sequential per row is fast enough and safer
- Web UI — CLI only
- Captcha solving service — retry + skip on captcha