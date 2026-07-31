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
from scraper.state import State, RowState


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
        # Also truncate output so previous-run data doesn't mix with the new run
        if out_path.exists():
            out_path.unlink()

    df = pd.read_csv(in_path, dtype=str, keep_default_na=False)
    rows = df.to_dict(orient="records")

    if args.limit:
        rows = rows[: args.limit]

    output_columns = list(df.columns) + [
        "Kabupaten/Kota", "Kawasan atau Non Kawasan", "PIC Name",
        "Phone", "Email", "Website", "Sumber data",
    ]

    # Prepare output CSV header (write once)
    if not out_path.exists():
        pd.DataFrame(columns=output_columns).to_csv(out_path, index=False)

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
                    if status == "OK":
                        done += 1
                    else:
                        partial += 1
                else:
                    status = "failed"
                    failed += 1
                print(f"[{i+1}/{total}] {company} — {status} ({', '.join(final.sources) or '—'})", file=sys.stderr)
            except Exception as e:
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