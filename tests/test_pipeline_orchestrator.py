from unittest.mock import AsyncMock, MagicMock
import pytest

from scraper.pipeline import process_row
from scraper.state import State, RowState
from scraper.parsers import PICMatch


@pytest.mark.asyncio
async def test_process_row_uses_oss_first_then_google(tmp_path):
    ctx = MagicMock()
    state = State(tmp_path / "s.state.json")
    src = {"Nama Perusahaan": "PT Test"}

    import scraper.sources.oss as oss_mod
    import scraper.sources.google as google_mod

    oss_mod.search_oss = AsyncMock(return_value=MagicMock(
        kabupaten_kota="Bandung", kawasan="Kawasan",
        phone="08111", email=None, website="https://test.co.id",
        sources=["OSS"], pic_candidates=[],
    ))
    google_mod.search_google = AsyncMock(return_value=MagicMock(
        phone=None, email=None,
        sources=["Google"],
        pic_candidates=[PICMatch(tier=1, name="HSE Person", context="HSE")],
    ))

    final = await process_row(ctx, state, 0, src, sources={
        "oss": oss_mod.search_oss,
        "google": google_mod.search_google,
    })

    assert final.kabupaten_kota == "Bandung"
    assert final.pic_name == "HSE Person"
    assert "OSS" in final.sources
    assert "Google" in final.sources


@pytest.mark.asyncio
async def test_process_row_skips_google_when_oss_has_pic(tmp_path):
    ctx = MagicMock()
    state = State(tmp_path / "s.state.json")
    src = {"Nama Perusahaan": "PT Test"}

    import scraper.sources.oss as oss_mod
    import scraper.sources.google as google_mod

    oss_mod.search_oss = AsyncMock(return_value=MagicMock(
        phone="08111", email="a@b.co.id", website="https://test.co.id",
        sources=["OSS"], pic_candidates=[PICMatch(tier=1, name="Budi", context="HSE")],
        kabupaten_kota=None, kawasan=None,
    ))
    google_mod.search_google = AsyncMock()

    final = await process_row(ctx, state, 0, src, sources={
        "oss": oss_mod.search_oss,
        "google": google_mod.search_google,
    })

    google_mod.search_google.assert_not_called()
    assert final.pic_name == "Budi"