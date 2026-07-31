"""Google search source for PIC + contact info. Includes LinkedIn site: fallback."""
from __future__ import annotations
import asyncio
import logging
import random
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from scraper.parsers import extract_phones, extract_emails, match_pic
from scraper.pipeline import PartialRow

log = logging.getLogger(__name__)

GOOGLE_SEARCH_URL = "https://www.google.com/search"
NAV_TIMEOUT_MS = 30_000

PIC_KEYWORDS = [
    "HSE Manager",
    "Environmental Manager",
    "General Manager",
    "EHS Manager",
    "Health Safety Environment",
    "Direktur",
]

PIC_NAME_SELECTORS = ["h3"]


def _build_query(company: str, extra_keywords: list[str] | None = None) -> str:
    if extra_keywords:
        kw = " OR ".join(f'"{k}"' for k in extra_keywords)
        return f'"{company}" ({kw})'
    return f'"{company}"'


async def _google_results(context, query: str, max_results: int = 5) -> list[str]:
    """Returns top-N result page URLs."""
    try:
        page = await context.new_page()
        # Force English locale + global region to avoid the ID consent interstitial
        await page.goto(
            f"{GOOGLE_SEARCH_URL}?q={query}&hl=en&gl=us",
            timeout=NAV_TIMEOUT_MS,
            wait_until="domcontentloaded",
        )
        # Random small delay to mimic human
        await asyncio.sleep(random.uniform(1.0, 2.5))
        html = await page.content()
        await page.close()
    except Exception as e:
        log.debug("google search failed: %s", e)
        return []

    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        # Modern Google: result URLs are in plain <a href="https://...">
        # Older format: /url?q=<encoded>
        actual = ""
        if href.startswith("/url?q="):
            actual = unquote(href.split("/url?q=", 1)[1].split("&", 1)[0])
        elif href.startswith("http") and "google.com" not in href and "google.co" not in href:
            actual = href
        if not actual or actual in seen:
            continue
        seen.add(actual)
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
    # Google result pattern: <a><h3>NAME - TITLE @ COMPANY</h3></a>
    for h3 in soup.select("h3"):
        full = h3.get_text(" ", strip=True)
        if not full or len(full) > 200:
            continue
        # Split on " - " or " — " or " | " to separate name from role
        parts = re.split(r"\s+[-—|]\s+", full, maxsplit=1)
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        role_context = parts[1].strip()
        if not name or len(name) > 60:
            continue
        # Skip generic section names
        if name.lower() in {"corporate secretary", "about", "contact", "home", "menu",
                            "expression of interest", "more locations", "map"}:
            continue
        # Heuristic: a real name has 1-4 words, each starting with a letter.
        # Reject headings that look like phrases (verbs, generic terms).
        words = name.split()
        if not (1 <= len(words) <= 4):
            continue
        # Reject if any word starts with a digit or is all-lowercase generic
        # word like "of", "the". Allow Title-case proper nouns.
        generic = {"of", "the", "a", "an", "and", "for", "to", "in", "on", "at"}
        if all(w.lower() in generic for w in words):
            continue
        m = match_pic(name, role_context)
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