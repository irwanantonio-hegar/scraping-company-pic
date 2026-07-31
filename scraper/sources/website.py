"""Direct company website scraping for contact pages and staff directories."""
from __future__ import annotations
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
            context_el = name_el.find_next(["p", "span", "div"]) or name_el.parent
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