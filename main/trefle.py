"""
Thin service layer around the Trefle API (https://trefle.io) used by the
Katalog Tanaman (plant catalog) module.

Kept deliberately separate from views.py so that:
  - HTTP/request concerns (timeouts, retries, error translation) live in
    one place instead of being duplicated across views.
  - views.py stays about HTTP request/response handling for *our* app,
    not about talking to a third-party API.
  - This module can be unit tested by mocking ``requests.get`` without
    touching Django's request/response cycle.

Design notes
------------
* No local database model is used to mirror Trefle's catalog. The catalog
  is read-only reference data owned by Trefle; the simplest solution that
  satisfies "browse + search + view detail" is: call the API and cache the
  JSON response for a while. A local model would mean writing a sync job,
  handling staleness, and a migration — none of which this feature needs.
* Caching uses Django's built-in cache framework (``django.core.cache``).
  No cache backend is configured in settings.py, so Django falls back to
  its local-memory cache automatically — no new dependency, no settings
  change required for caching itself.
* Every field pulled out of a Trefle response is read defensively with
  ``.get()``. Trefle's public field list for `/species/search` is
  documented (see https://docs.trefle.io/docs/guides/getting-started):
  author, bibliography, common_name, family, family_common_name, genus,
  genus_id, id, links, rank, scientific_name, slug, status,
  synonyms_count, year. Growth/care fields (light, watering, temperature,
  humidity, etc.) are documented to exist on the *species detail* response
  but their exact shape was not confirmed against a live response in this
  environment (no network access to trefle.io, and no API token was
  available — see README). This module therefore never invents a value:
  if a field is missing from the response, callers get ``None`` for it,
  and templates show an honest "not available" message instead.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TREFLE_BASE_URL = "https://trefle.io/api/v1"
REQUEST_TIMEOUT = 8  # seconds

CACHE_TTL_LIST = 60 * 30       # 30 minutes — list/search results change rarely
CACHE_TTL_DETAIL = 60 * 60 * 6  # 6 hours — a single species' data is near-static
CACHE_VERSION_PREFIX = "trefle:v1"


class TrefleError(Exception):
    """Base class for every catalog-facing error. ``message`` is safe to
    show directly to the end user (never includes the token or raw
    exception internals)."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class TrefleNotConfigured(TrefleError):
    """Raised when there is no API token, or the token was rejected."""


class TrefleUnavailable(TrefleError):
    """Raised for network failures, timeouts, and unexpected server errors."""


class TrefleRateLimited(TrefleError):
    """Raised when Trefle responds with HTTP 429."""


def _get_token() -> str:
    token = getattr(settings, "TREFLE_API_TOKEN", "") or ""
    if not token:
        raise TrefleNotConfigured(
            "Katalog tanaman belum terhubung ke Trefle API. "
            "Admin perlu mengatur environment variable TREFLE_API_TOKEN."
        )
    return token


def _request(path: str, params: dict | None = None) -> dict | None:
    """Perform one GET request against the Trefle API.

    Returns the parsed JSON body, or ``None`` if Trefle returned 404.
    Raises a ``TrefleError`` subclass for every other failure mode so
    callers only ever have to handle one exception family.
    """
    token = _get_token()
    query = dict(params or {})
    query["token"] = token
    url = f"{TREFLE_BASE_URL}{path}"

    try:
        response = requests.get(url, params=query, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout as exc:
        logger.warning("Trefle API timeout on %s", path)
        raise TrefleUnavailable(
            "Trefle API tidak merespons dalam waktu yang wajar. Coba lagi sebentar lagi."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        logger.warning("Trefle API connection error on %s", path)
        raise TrefleUnavailable(
            "Tidak dapat terhubung ke Trefle API. Periksa koneksi jaringan server."
        ) from exc
    except requests.exceptions.RequestException as exc:
        # Catch-all for anything requests raises that isn't more specific
        # above (e.g. malformed URL, too many redirects).
        logger.warning("Trefle API request error on %s: %s", path, exc.__class__.__name__)
        raise TrefleUnavailable(
            "Terjadi kesalahan saat menghubungi Trefle API."
        ) from exc

    if response.status_code == 429:
        raise TrefleRateLimited(
            "Batas permintaan ke Trefle API tercapai. Coba lagi dalam beberapa menit."
        )
    if response.status_code in (401, 403):
        raise TrefleNotConfigured(
            "Token Trefle API tidak valid atau ditolak oleh Trefle."
        )
    if response.status_code == 404:
        return None
    if not response.ok:
        logger.warning("Trefle API returned HTTP %s on %s", response.status_code, path)
        raise TrefleUnavailable(
            f"Trefle API mengembalikan status tak terduga ({response.status_code})."
        )

    try:
        return response.json()
    except ValueError as exc:
        logger.warning("Trefle API returned invalid JSON on %s", path)
        raise TrefleUnavailable(
            "Trefle API mengembalikan data yang tidak valid."
        ) from exc


def list_plants(page: int = 1) -> tuple[list[dict], dict]:
    """Browse the catalog without a search term."""
    page = max(int(page or 1), 1)
    cache_key = f"{CACHE_VERSION_PREFIX}:list:{page}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    payload = _request("/species", {"page": page})
    data = (payload or {}).get("data") or []
    meta = (payload or {}).get("meta") or {}
    result = (data, meta)
    cache.set(cache_key, result, CACHE_TTL_LIST)
    return result


def search_plants(query: str, page: int = 1) -> tuple[list[dict], dict]:
    """Search the catalog by common/scientific name."""
    query = (query or "").strip()
    page = max(int(page or 1), 1)
    if not query:
        return list_plants(page=page)

    cache_key = f"{CACHE_VERSION_PREFIX}:search:{query.lower()}:{page}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    payload = _request("/species/search", {"q": query, "page": page})
    data = (payload or {}).get("data") or []
    meta = (payload or {}).get("meta") or {}
    result = (data, meta)
    cache.set(cache_key, result, CACHE_TTL_LIST)
    return result


_MISSING = object()


def get_plant_detail(slug: str) -> dict | None:
    """Fetch one species by its Trefle slug. Returns ``None`` if Trefle
    has no such species (caller should turn that into an HTTP 404)."""
    cache_key = f"{CACHE_VERSION_PREFIX}:detail:{slug}"
    cached = cache.get(cache_key, _MISSING)
    if cached is not _MISSING:
        return cached

    payload = _request(f"/species/{slug}")
    data = (payload or {}).get("data") if payload else None
    cache.set(cache_key, data, CACHE_TTL_DETAIL)
    return data


# Candidate locations for growth/care data within a Trefle species-detail
# response. Trefle's community-documented schema nests this information
# under `main_species.growth`, but some responses may expose it at the
# top level instead. We check both and use whichever is present, without
# assuming either exists — see module docstring.
def _find_growth_dict(plant: dict) -> dict:
    main_species = plant.get("main_species") or {}
    growth = main_species.get("growth") or plant.get("growth") or {}
    return growth if isinstance(growth, dict) else {}


# (label, path-within-growth-dict) — every one of these is looked up with
# .get() and simply omitted from the UI if absent. None are guessed or
# defaulted to a plausible-looking value.
_CARE_FIELD_MAP = [
    ("light", "Kebutuhan cahaya (skala 0-10)"),
    ("atmospheric_humidity", "Kelembapan udara (skala 0-10)"),
    ("minimum_temperature", "Suhu minimum"),
    ("maximum_temperature", "Suhu maksimum"),
    ("minimum_precipitation", "Curah hujan minimum"),
    ("maximum_precipitation", "Curah hujan maksimum"),
    ("soil_nutriments", "Kebutuhan nutrisi tanah (skala 0-10)"),
    ("soil_salinity", "Toleransi salinitas tanah (skala 0-10)"),
    ("soil_humidity", "Kelembapan tanah (skala 0-10)"),
    ("growth_months", "Bulan masa tumbuh"),
    ("bloom_months", "Bulan berbunga"),
    ("fruit_months", "Bulan berbuah"),
]


def extract_care_info(plant: dict) -> list[dict]:
    """Build a list of {label, value} entries for whichever care fields
    Trefle actually returned. Fields that are missing or null are left
    out entirely — the template separately shows an honest "not
    available" note when this list comes back empty."""
    growth = _find_growth_dict(plant)
    entries = []
    for key, label in _CARE_FIELD_MAP:
        value = growth.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):
            min_v = value.get("min")
            max_v = value.get("max")
            if min_v is None and max_v is None:
                continue
            value = f"{min_v if min_v is not None else '?'} - {max_v if max_v is not None else '?'}"
        elif isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        entries.append({"label": label, "value": value})
    return entries


_SCALE_CARE_FIELDS = [
    ("light", "Kebutuhan cahaya"),
    ("atmospheric_humidity", "Kelembapan udara"),
    ("soil_nutriments", "Nutrisi tanah"),
    ("soil_salinity", "Toleransi salinitas"),
    ("soil_humidity", "Kelembapan tanah"),
]


def extract_care_cards(plant: dict) -> list[dict]:
    """Return verified 0-10 care cards and categorical month data."""
    growth = _find_growth_dict(plant)
    cards = []
    for key, label in _SCALE_CARE_FIELDS:
        value = growth.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        cards.append({
            "label": label,
            "value": value,
            "progress": max(0, min(float(value), 10)) * 10,
            "scale": "0–10",
        })

    months = growth.get("bloom_months")
    if months not in (None, "", [], {}):
        if isinstance(months, list):
            months = ", ".join(str(month) for month in months)
        cards.append({"label": "Bulan berbunga", "value": months, "categorical": True})
    return cards
