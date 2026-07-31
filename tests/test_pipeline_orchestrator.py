from unittest.mock import AsyncMock, MagicMock
import pytest

from scraper.pipeline import process_row
from scraper.state import State, RowState
from scraper.parsers import PICMatch


@pytest.mark.asyncio
async def test_process_row_runs_linkedin_then_google(tmp_path):
    ctx = MagicMock()
    state = State(tmp_path / "s.state.json")
    src = {"Nama Perusahaan": "PT Test"}

    import scraper.sources.google as google_mod

    google_mod.search_linkedin = AsyncMock(return_value=MagicMock(
        phone="08111", email=None, website=None,
        sources=["LinkedIn"], pic_candidates=[],
    ))
    google_mod.search_google = AsyncMock(return_value=MagicMock(
        phone=None, email="x@y.com",
        sources=["Google"],
        pic_candidates=[PICMatch(tier=1, name="HSE Person", context="HSE Manager")],
    ))

    final = await process_row(ctx, state, 0, src, sources={
        "linkedin": google_mod.search_linkedin,
        "google": google_mod.search_google,
    })

    google_mod.search_linkedin.assert_awaited_once()
    google_mod.search_google.assert_awaited_once()
    assert final.phone == "08111"  # from LinkedIn (runs first)
    assert final.email == "x@y.com"  # from Google (LinkedIn had no email)
    assert final.pic_name == "HSE Person"
    assert "LinkedIn" in final.sources
    assert "Google" in final.sources


@pytest.mark.asyncio
async def test_process_row_visits_website_when_url_discovered(tmp_path):
    ctx = MagicMock()
    state = State(tmp_path / "s.state.json")
    src = {"Nama Perusahaan": "PT Test"}

    import scraper.sources.google as google_mod
    import scraper.sources.website as website_mod

    google_mod.search_linkedin = AsyncMock(return_value=MagicMock(
        phone=None, email=None, website="https://test.co.id",
        sources=["LinkedIn"], pic_candidates=[],
    ))
    google_mod.search_google = AsyncMock(return_value=MagicMock(
        phone=None, email=None, website=None,
        sources=[], pic_candidates=[],
    ))
    website_mod.visit_website = AsyncMock(return_value=MagicMock(
        phone="022", email="info@test.co.id", website=None,
        sources=["Website"],
        pic_candidates=[PICMatch(tier=1, name="Budi", context="HSE")],
    ))

    final = await process_row(ctx, state, 0, src, sources={
        "linkedin": google_mod.search_linkedin,
        "google": google_mod.search_google,
        "website": website_mod.visit_website,
    })

    website_mod.visit_website.assert_awaited_once_with(
        ctx, "https://test.co.id", "PT Test"
    )
    assert final.pic_name == "Budi"
    assert final.email == "info@test.co.id"
    assert "Website" in final.sources


@pytest.mark.asyncio
async def test_process_row_skips_website_when_no_url(tmp_path):
    ctx = MagicMock()
    state = State(tmp_path / "s.state.json")
    src = {"Nama Perusahaan": "PT Test"}

    import scraper.sources.google as google_mod
    import scraper.sources.website as website_mod

    google_mod.search_linkedin = AsyncMock(return_value=MagicMock(
        phone=None, email=None, website=None,
        sources=[], pic_candidates=[],
    ))
    google_mod.search_google = AsyncMock(return_value=MagicMock(
        phone=None, email=None, website=None,
        sources=[], pic_candidates=[],
    ))
    website_mod.visit_website = AsyncMock()

    await process_row(ctx, state, 0, src, sources={
        "linkedin": google_mod.search_linkedin,
        "google": google_mod.search_google,
        "website": website_mod.visit_website,
    })

    website_mod.visit_website.assert_not_called()