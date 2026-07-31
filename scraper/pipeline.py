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