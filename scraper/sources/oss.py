"""OSS / BKPM (oss.go.id) source — Indonesian business licensing portal."""
from __future__ import annotations
import logging

from scraper.pipeline import PartialRow

log = logging.getLogger(__name__)

OSS_SEARCH_URL = "https://oss.go.id/search"
NAV_TIMEOUT_MS = 30_000


async def search_oss(context, company_name: str) -> PartialRow:
    """Search oss.go.id for the company. Returns whatever fields could be extracted.

    Selector notes (to be tuned in Task 11 against live site):
    - search input: input[name='q'] or input[type='search']
    - result rows: .company-row, .search-result, or table tr
    - detail fields: typically labelled in Bahasa Indonesia
      - Kabupaten/Kota: contains 'Kabupaten' or 'Kota'
      - Kawasan: 'Kawasan Industri' or 'Non Kawasan'
      - PIC: 'Penanggung Jawab' or 'Pengarah'
      - Phone: 'Telepon' or 'No HP'
      - Email: 'Email'
      - Website: 'Website'
    """
    log.debug("OSS search: %s", company_name)
    # TODO(tune-selectors): wire up live selectors after manual inspection.
    # Until then, return empty PartialRow so pipeline proceeds to next source.
    return PartialRow(sources=[])