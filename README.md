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

1. **LinkedIn dork** — `site:linkedin.com` Google search with job-title keywords (`HSE`, `Environmental`, `General Manager`). Highest priority — typically yields the most accurate PIC name + role.
2. **Google search** — broader job-title keyword search across the open web; fills phone / email / website when LinkedIn misses them.
3. **Direct website** — visits `/about`, `/team`, `/contact`, etc., only when LinkedIn or Google surfaced a website URL.

(OSS / BKPM is intentionally **not** used: as of 2026 its public search only accepts NIB / KBLI codes, not company names.)

## Resume

If interrupted (Ctrl+C), rerun the same command without `--no-resume` to continue from where it stopped. State is stored in `<input>.state.json`.

## Validation

A smoke run on 3 well-known companies (`tests/fixtures/sample_real_companies.csv`) — observed:

```
[1/3] PT Unilever Indonesia    — failed
[2/3] PT Astra International   — partial (Google)
[3/3] PT Pertamina (Persero)   — partial (Google, LinkedIn)
```

Output CSV (`/tmp/e2e_out.csv`) has 8 columns (1 original + 7 new), with at least Phone, PIC Name, and Email filled where Google succeeded. PT Unilever often fails because Google headless requests for that query trigger captcha. For higher hit rates, run `--headful` and consider adding residential proxy support (currently Camoufox fingerprint rotation only).

## Troubleshooting

- Browser bundle missing: `python -m camoufox fetch`
- Google captcha: retry with longer delay (modify `random.uniform(2, 8)` in `pipeline.py`)
- OSS selectors stale: edit `scraper/sources/oss.py` — selectors change as the site evolves
- All rows return empty: OSS cannot resolve names. The first real source is Google (Source C). Verify network access and that `--headful` shows the browser reaching `google.com`.