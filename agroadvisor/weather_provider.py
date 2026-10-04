"""
Real weather data provider using NASA POWER (https://power.larc.nasa.gov/).

NASA POWER is free, requires no API key, and its precipitation/temperature
data covers the Sahel reasonably well — a good default for this project.
Data is cached into WeatherReading so repeated requests for the same
region/period don't re-hit the API every time.
"""
import datetime
import logging

import requests
from django.utils import timezone

from .models import Region, WeatherReading

logger = logging.getLogger(__name__)

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = "PRECTOTCORR,T2M"  # corrected precipitation (mm/day), temperature at 2m (°C)
REQUEST_TIMEOUT = 20


class WeatherProviderError(Exception):
    pass


def fetch_nasa_power_daily(latitude: float, longitude: float, start: datetime.date, end: datetime.date) -> dict:
    """
    Calls the NASA POWER API for one point and date range.
    Returns the raw `properties.parameter` dict: {"PRECTOTCORR": {"20250101": 0.4, ...}, "T2M": {...}}
    """
    params = {
        "parameters": PARAMETERS,
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    try:
        resp = requests.get(NASA_POWER_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data["properties"]["parameter"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise WeatherProviderError(f"Échec de récupération NASA POWER pour ({latitude}, {longitude}) : {exc}") from exc


def sync_region_weather(region: Region, year: int) -> int:
    """
    Fetches a full calendar year of daily data for a region from NASA POWER
    and stores/updates it in WeatherReading. Returns the number of days saved.

    Requires region.latitude / region.longitude to be set.
    """
    if region.latitude is None or region.longitude is None:
        raise WeatherProviderError(f"La région {region.name} n'a pas de latitude/longitude renseignée.")

    start = datetime.date(year, 1, 1)
    today = timezone.now().date()
    end = min(datetime.date(year, 12, 31), today)

    raw = fetch_nasa_power_daily(region.latitude, region.longitude, start, end)
    precip = raw.get("PRECTOTCORR", {})
    temp = raw.get("T2M", {})

    saved = 0
    for date_str, mm in precip.items():
        # NASA POWER uses -999 as a "no data" sentinel.
        if mm is None or mm < -900:
            continue
        day = datetime.datetime.strptime(date_str, "%Y%m%d").date()
        WeatherReading.objects.update_or_create(
            region=region, date=day, source="nasa_power",
            defaults={"rainfall_mm": mm, "temperature_c": temp.get(date_str)},
        )
        saved += 1
    return saved


def get_monthly_rainfall_from_cache(region: Region, year: int) -> dict:
    """
    Returns {month_num: total_mm} built from cached WeatherReading rows for
    a region/year (source='nasa_power'), or an empty dict if nothing is cached yet.
    """
    readings = WeatherReading.objects.filter(region=region, date__year=year, source="nasa_power")
    totals = {}
    for r in readings:
        totals[r.date.month] = totals.get(r.date.month, 0) + r.rainfall_mm
    return {m: round(mm) for m, mm in totals.items()}
