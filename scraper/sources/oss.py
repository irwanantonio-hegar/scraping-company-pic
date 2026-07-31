"""OSS / BKPM (oss.go.id) source — Indonesian business licensing portal.

NOTE: As of 2026, oss.go.id's public search only accepts NIB (Nomor Induk
Berusaha) or KBLI (business classification code), NOT company names. To
find a company's NIB from a name, an intermediate lookup is needed
(e.g., a NIB directory or Google search). Until that integration exists,
this source is effectively a no-op for our 'Nama Perusahaan' input.

The wiring remains so the pipeline can be extended later.
"""
from __future__ import annotations
import asyncio
import logging

from bs4 import BeautifulSoup

from scraper.pipeline import PartialRow

log = logging.getLogger(__name__)

OSS_PENCARIAN_URL = "https://oss.go.id/pencarian"
NAV_TIMEOUT_MS = 30_000


async def search_oss(context, company_name: str) -> PartialRow:
    """Visit oss.go.id/pencarian.

    OSS's public search page only takes NIB or KBLI, not company names.
    We attempt the visit to confirm structure but cannot extract company
    details from a name query. Returns an empty PartialRow unless the
    caller has a NIB to pass in directly.
    """
    log.debug("OSS search skipped for %s (NIB/KBLI only)", company_name)
    # TODO(nib-lookup): integrate a NIB directory to translate company name → NIB,
    # then re-issue search with the NIB to extract detail fields.
    return PartialRow(sources=[])


__all__ = ["search_oss", "OSS_PENCARIAN_URL", "NAV_TIMEOUT_MS"]