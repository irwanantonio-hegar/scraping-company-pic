import pytest
from scraper.browser import camoufox_session


@pytest.mark.skip(reason="requires camoufox bundle; run manually with: pytest -m smoke")
@pytest.mark.asyncio
async def test_camoufox_launches_and_loads():
    async with camoufox_session(headless=True) as ctx:
        page = await ctx.new_page()
        await page.goto("about:blank")
        assert page is not None