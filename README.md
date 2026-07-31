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

## PIC priority

When multiple PICs are found for a company, only one is kept per row:

1. **HSE / K3** — `HSE Manager`, `Health Safety Environment`, `K3`, `Keselamatan Kesehatan Kerja`
2. **Environmental / EHS** — `Environmental Manager`, `EHS`, `Lingkungan`
3. **General Manager / Director** — `General Manager`, `Direktur`

## Sources (in order)

1. **OSS / BKPM** (`oss.go.id`) — official licensing portal
2. **Direct website** — visits `/about`, `/team`, `/contact`, etc.
3. **Google** — searches with job-title keywords
4. **LinkedIn** (fallback) — `site:linkedin.com` search

## Resume

If interrupted (Ctrl+C), rerun the same command without `--no-resume` to continue from where it stopped. State is stored in `<input>.state.json`.

## Validation

A smoke run on 3 well-known companies produces ≥1 row with PIC Name populated. See `tests/fixtures/sample_real_companies.csv`.

## Troubleshooting

- Browser bundle missing: `python -m camoufox fetch`
- Google captcha: retry with longer delay (modify `random.uniform(2, 8)` in `pipeline.py`)
- OSS selectors stale: edit `scraper/sources/oss.py` — selectors change as the site evolves