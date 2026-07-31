"""Camoufox browser lifecycle — one browser per run, fresh context per row."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncIterator

from camoufox.async_api import AsyncCamoufox


@asynccontextmanager
async def camoufox_session(headless: bool = True) -> AsyncIterator:
    """Yield a Playwright BrowserContext. Creates a fresh browser and a single context.

    Usage:
        async with camoufox_session() as ctx:
            page = await ctx.new_page()
            ...
    """
    async with AsyncCamoufox(headless=headless) as browser:
        context = await browser.new_context()
        try:
            yield context
        finally:
            await context.close()