"""
Satellite vegetation health (NDVI) provider using the ORNL DAAC MODIS/VIIRS Land
Products Web Service — free, public, no API key required.
Docs: https://daac.ornl.gov/MODIS/MODIS-menu/modis_webservice.html

NOTE: this integration could not be network-tested from the sandbox this backend
was developed in (modis.ornl.gov was not reachable from that environment's egress
allowlist) — the request/response handling follows ORNL's documented API exactly,
but please verify it against a live region once you run this yourself, and report
back if the response shape has changed since.
"""
import datetime
import logging

import requests
from django.utils import timezone

from .models import Region, NdviReading

logger = logging.getLogger(__name__)

MODIS_BASE_URL = "https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset"
REQUEST_TIMEOUT = 20


class NdviProviderError(Exception):
    pass


def _modis_date(d: datetime.date) -> str:
    """ORNL's MODIS API expects dates as AYYYYDDD (4-digit year + day-of-year)."""
    return f"A{d.year}{d.timetuple().tm_yday:03d}"


def fetch_latest_ndvi(latitude: float, longitude: float) -> tuple[datetime.date, float]:
    """
    Fetches the most recent available NDVI value (MOD13Q1, 16-day composite) for a
    point. Returns (date, ndvi_value) with ndvi_value already scaled to the standard
    -1..1 range (the raw MODIS band is scaled by 10000).

    Notes from testing against the live API:
    - kmAboveBelow / kmLeftRight must be >= 1 (0 causes a 400 Bad Request) — this
      returns a small 3x3 km pixel grid around the point, not a single pixel, so we
      take the center pixel as the point value.
    - The `band` query parameter is not reliably honored server-side (it can return
      every band regardless) — filter the response client-side for the NDVI band
      instead of trusting the request to have already filtered it.
    """
    today = timezone.now().date()
    start = today - datetime.timedelta(days=40)  # a bit over 2 composite cycles, in case the latest isn't published yet

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "startDate": _modis_date(start),
        "endDate": _modis_date(today),
        "kmAboveBelow": 1,
        "kmLeftRight": 1,
    }
    try:
        resp = requests.get(
            MODIS_BASE_URL, params=params,
            headers={"Accept": "application/json", "User-Agent": "Mogota-AgriTech/1.0 (agricultural advisory platform)"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        subset = data.get("subset", [])
        ndvi_entries = [e for e in subset if e.get("band") == "250m_16_days_NDVI"]
        if not ndvi_entries:
            raise NdviProviderError("Aucune donnée NDVI dans la réponse pour ce point.")
        latest = ndvi_entries[-1]  # most recent composite period
        pixels = latest["data"]
        center_pixel = pixels[len(pixels) // 2]
        ndvi = center_pixel / 10000.0
        date = datetime.datetime.strptime(latest["calendar_date"], "%Y-%m-%d").date()
        return date, ndvi
    except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
        raise NdviProviderError(f"Échec de récupération NDVI ORNL/MODIS : {exc}") from exc


def sync_region_ndvi(region: Region) -> NdviReading:
    if region.latitude is None or region.longitude is None:
        raise NdviProviderError(f"La région {region.name} n'a pas de latitude/longitude renseignée.")
    date, ndvi = fetch_latest_ndvi(region.latitude, region.longitude)
    reading, _ = NdviReading.objects.update_or_create(
        region=region, date=date, source="modis_mod13q1", defaults={"ndvi_value": ndvi},
    )
    return reading


def ndvi_health_label(ndvi_value: float) -> str:
    """Rough, commonly-used thresholds for cropland vegetation vigor."""
    if ndvi_value < 0.2:
        return "Sol nu / stress sévère"
    if ndvi_value < 0.4:
        return "Végétation clairsemée"
    if ndvi_value < 0.6:
        return "Végétation modérée"
    return "Végétation dense et saine"
