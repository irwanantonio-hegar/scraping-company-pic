"""Per-row pipeline orchestration and merge logic."""
from __future__ import annotations
import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from scraper.parsers import PICMatch
from scraper.state import RowState, State


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

    # Decide website URL: from OSS if present
    website_url = None
    for p in parts:
        if p.website:
            website_url = p.website
            break

    # Source B: Website (only if URL known)
    if website_url:
        try:
            parts.append(await sources["website"](context, website_url, company))
        except Exception as e:
            log.warning("Website failed for %s: %s", company, e)

    # Source C: Google (with job-title keywords) — skip if a PIC already found
    oss_had_pic = any(p.pic_candidates for p in parts)
    if not oss_had_pic:
        try:
            g = await sources["google"](context, company)
            parts.append(g)
        except Exception as e:
            log.warning("Google failed for %s: %s", company, e)

    # Source D: LinkedIn fallback — only if still no PIC
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