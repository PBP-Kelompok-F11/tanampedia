# Service untuk mengambil dan mengolah data katalog tanaman dari Trefle API
# Request API, cache, error handling, dan ekstraksi data perawatan dipisahkan
# dari views agar mudah diuji dan digunakan kembali
from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TREFLE_BASE_URL = "https://trefle.io/api/v1"
REQUEST_TIMEOUT = 8  # batas waktu request dalam detik

CACHE_TTL_LIST = 60 * 30       # cache daftar dan pencarian selama 30 menit
CACHE_TTL_DETAIL = 60 * 60 * 6  # cache detail tanaman selama 6 jam
CACHE_VERSION_PREFIX = "trefle:v1"


class TrefleError(Exception):
    # Error dasar untuk seluruh proses katalog
    pass

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class TrefleNotConfigured(TrefleError):
    # Error saat token belum tersedia atau ditolak
    pass


class TrefleUnavailable(TrefleError):
    # Error saat API tidak dapat diakses atau mengembalikan error server
    pass


class TrefleRateLimited(TrefleError):
    # Error saat jumlah request melewati batas Trefle
    pass


def _get_token() -> str:
    token = getattr(settings, "TREFLE_API_TOKEN", "") or ""
    if not token:
        raise TrefleNotConfigured(
            "Katalog tanaman belum terhubung ke Trefle API. "
            "Admin perlu mengatur environment variable TREFLE_API_TOKEN."
        )
    return token


def _normalize_page(page: int | str | None) -> int:
    # Pastikan nomor halaman selalu berupa bilangan positif
    try:
        return max(int(page or 1), 1)
    except (TypeError, ValueError):
        return 1


def _build_cache_key(resource: str, *parts: object) -> str:
    # Buat key cache berdasarkan resource dan parameter request
    suffix = ":".join(str(part) for part in parts)
    return f"{CACHE_VERSION_PREFIX}:{resource}:{suffix}" if suffix else f"{CACHE_VERSION_PREFIX}:{resource}"


def _request(path: str, params: dict | None = None) -> dict | None:
    # Kirim satu request GET dan ubah error API menjadi TrefleError
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
        # Menangani error requests lain yang belum ditangani
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


def _extract_catalog_result(payload: dict | None) -> tuple[list[dict], dict]:
    # Ambil data dan metadata dengan format return yang konsisten
    payload = payload or {}
    return payload.get("data") or [], payload.get("meta") or {}


def _fetch_catalog_page(
    endpoint: str,
    params: dict,
    cache_key: str,
) -> tuple[list[dict], dict]:
    # Ambil, proses, dan simpan satu halaman katalog ke cache
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = _extract_catalog_result(_request(endpoint, params))
    cache.set(cache_key, result, CACHE_TTL_LIST)
    return result


def list_plants(page: int = 1) -> tuple[list[dict], dict]:
    # Ambil daftar tanaman tanpa kata pencarian
    page = _normalize_page(page)
    return _fetch_catalog_page(
        "/species",
        {"page": page},
        _build_cache_key("list", page),
    )


def search_plants(query: str, page: int = 1) -> tuple[list[dict], dict]:
    # Cari tanaman berdasarkan nama umum atau nama ilmiah
    query = (query or "").strip()
    page = _normalize_page(page)
    if not query:
        return list_plants(page=page)

    return _fetch_catalog_page(
        "/species/search",
        {"q": query, "page": page},
        _build_cache_key("search", query.lower(), page),
    )


_MISSING = object()


def get_plant_detail(slug: str) -> dict | None:
    # Ambil detail tanaman berdasarkan slug dan kembalikan None jika tidak ada
    cache_key = _build_cache_key("detail", slug)
    cached = cache.get(cache_key, _MISSING)
    if cached is not _MISSING:
        return cached

    payload = _request(f"/species/{slug}")
    data = (payload or {}).get("data") if payload else None
    cache.set(cache_key, data, CACHE_TTL_DETAIL)
    return data


# Cari data pertumbuhan pada main_species.growth atau growth di level utama
def _find_growth_dict(plant: dict) -> dict:
    main_species = plant.get("main_species") or {}
    growth = main_species.get("growth") or plant.get("growth") or {}
    return growth if isinstance(growth, dict) else {}


def _format_care_value(value: object) -> object | None:
    # Ubah nilai perawatan ke format yang siap ditampilkan
    if value in (None, "", [], {}):
        return None
    if isinstance(value, dict):
        min_value = value.get("min")
        max_value = value.get("max")
        if min_value is None and max_value is None:
            return None
        return f"{min_value if min_value is not None else '?'} - {max_value if max_value is not None else '?'}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value


# Field perawatan yang dibaca dari data growth tanpa membuat nilai tambahan
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
    # Bentuk daftar informasi dari field perawatan yang tersedia
    growth = _find_growth_dict(plant)
    entries = []
    for key, label in _CARE_FIELD_MAP:
        value = _format_care_value(growth.get(key))
        if value is None:
            continue
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
    # Bentuk kartu perawatan berskala 0 sampai 10 dan data bulan berbunga
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
    months = _format_care_value(months)
    if months is not None:
        cards.append({"label": "Bulan berbunga", "value": months, "categorical": True})
    return cards
