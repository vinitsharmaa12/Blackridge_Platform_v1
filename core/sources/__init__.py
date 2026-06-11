"""External data sources (NSE fetch, etc.)."""

from core.sources.nse import fetch_chain, fetch_india_vix, resolve_expiry

__all__ = ["fetch_chain", "fetch_india_vix", "resolve_expiry"]
