"""NSE option-chain fetch with cookie priming, retries, and expiry resolution.

Times in fetched JSON follow NSE server timestamps (IST, naive in normalize).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Literal

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_NSE_HOME = "https://www.nseindia.com"
_OPTION_CHAIN_PAGE = f"{_NSE_HOME}/option-chain"
_CHAIN_API = f"{_NSE_HOME}/api/option-chain-v3"
_INDICES_API = f"{_NSE_HOME}/api/allIndices"
_EXPIRY_FMT = "%d-%b-%Y"  # e.g. 09-Jun-2026

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": f"{_NSE_HOME}/option-chain",
    "Connection": "keep-alive",
}

ExpiryMode = Literal["nearest", "nearest_weekly"]


class NseFetchError(Exception):
    """NSE returned an error or empty payload after retries."""


def _expiry_dates(raw: dict) -> list[date]:
    records = raw.get("records")
    if not isinstance(records, dict):
        return []
    raw_dates = records.get("expiryDates") or []
    parsed: list[date] = []
    for item in raw_dates:
        if not item:
            continue
        try:
            parsed.append(datetime.strptime(str(item), _EXPIRY_FMT).date())
        except ValueError:
            continue
    return sorted(set(parsed))


def resolve_expiry(
    raw: dict,
    mode: ExpiryMode = "nearest",
    today: date | None = None,
) -> str:
    """Pick the nearest expiry >= today from records.expiryDates."""
    ref = today or date.today()
    candidates = [d for d in _expiry_dates(raw) if d >= ref]
    if not candidates:
        raise ValueError("No expiryDates >= today in NSE response")

    if mode == "nearest_weekly":
        # Weekly = Thursday expiries for NIFTY index options.
        thursdays = [d for d in candidates if d.weekday() == 3]
        chosen = thursdays[0] if thursdays else candidates[0]
    else:
        chosen = candidates[0]

    return chosen.strftime(_EXPIRY_FMT)


def is_empty_response(raw: dict) -> bool:
    if not raw:
        return True
    records = raw.get("records")
    if not isinstance(records, dict):
        return True
    data = records.get("data")
    return not data


def has_expiry_dates(raw: dict) -> bool:
    return bool(_expiry_dates(raw))


def _bootstrap_expiry(today: date | None = None) -> str:
    """Guess the nearest Thursday expiry when NSE returns an empty probe."""
    ref = today or date.today()
    days_ahead = (3 - ref.weekday()) % 7
    return (ref + timedelta(days=days_ahead)).strftime(_EXPIRY_FMT)


def _prime_session(session: requests.Session, timeout: float) -> None:
    session.get(f"{_NSE_HOME}/", timeout=timeout)
    session.get(_OPTION_CHAIN_PAGE, timeout=timeout)


def _chain_url(symbol: str, expiry: str | None) -> str:
    url = f"{_CHAIN_API}?type=Indices&symbol={symbol}"
    if expiry:
        url += f"&expiry={expiry}"
    return url


def _get_json(
    session: requests.Session,
    url: str,
    timeout: float,
) -> dict:
    resp = session.get(url, timeout=timeout)
    if resp.status_code in (401, 403):
        raise NseFetchError(f"NSE auth blocked ({resp.status_code})")
    if resp.status_code >= 500:
        raise NseFetchError(f"NSE server error ({resp.status_code})")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise NseFetchError("Unexpected NSE response type")
    return data


def fetch_chain(
    symbol: str,
    expiry: str | None = None,
    *,
    timeout: float = 15.0,
    max_retries: int = 3,
    expiry_mode: ExpiryMode = "nearest",
) -> dict:
    """Fetch raw NSE option-chain JSON for an index symbol."""
    session = requests.Session()
    session.headers.update(_DEFAULT_HEADERS)
    _prime_session(session, timeout)

    @retry(
        retry=retry_if_exception_type(
            (NseFetchError, requests.Timeout, requests.ConnectionError)
        ),
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _fetch(url: str) -> dict:
        return _get_json(session, url, timeout)

    if expiry:
        raw = _fetch(_chain_url(symbol, expiry))
        if is_empty_response(raw):
            raise NseFetchError("Empty NSE response")
        return raw

    # Auto-resolve expiryDates, then re-fetch with the chosen expiry.
    probe = _fetch(_chain_url(symbol, None))
    meta = probe
    if not has_expiry_dates(probe):
        bootstrap = _bootstrap_expiry()
        logger.debug("NSE probe empty; bootstrapping expiry=%s", bootstrap)
        meta = _fetch(_chain_url(symbol, bootstrap))
        if not has_expiry_dates(meta):
            raise NseFetchError("Could not read expiryDates from NSE")

    resolved = resolve_expiry(meta, mode=expiry_mode)
    raw = _fetch(_chain_url(symbol, resolved))
    if is_empty_response(raw):
        raise NseFetchError("Empty NSE response after expiry resolve")
    return raw


def fetch_india_vix(
    *,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> float | None:
    """Fetch India VIX last value. Returns None on failure."""
    session = requests.Session()
    session.headers.update(_DEFAULT_HEADERS)
    try:
        _prime_session(session, timeout)

        @retry(
            retry=retry_if_exception_type(
                (NseFetchError, requests.Timeout, requests.ConnectionError)
            ),
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=15),
            reraise=True,
        )
        def _fetch() -> float | None:
            url = f"{_INDICES_API}?index=INDIA%20VIX"
            resp = session.get(url, timeout=timeout)
            if resp.status_code in (401, 403, 500, 502, 503):
                raise NseFetchError(f"India VIX fetch failed ({resp.status_code})")
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                return None
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("index", "")).upper()
                if "INDIA VIX" in name or name == "INDIAVIX":
                    last = row.get("last")
                    return float(last) if last is not None else None
            return None

        return _fetch()
    except Exception as exc:  # noqa: BLE001 — fail soft per PRD
        logger.warning("India VIX fetch failed: %s", exc)
        return None
