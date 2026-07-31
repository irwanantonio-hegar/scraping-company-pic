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