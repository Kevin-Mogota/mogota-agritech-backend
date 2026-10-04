"""
Advisory computation logic — server-side port of the prototype's frontend rules.

This keeps the sowing / irrigation / drought-risk logic in one place so the
Django API and the React prototype produce consistent recommendations, and so
this becomes the single place to plug in real weather data later (replace
`get_rainfall_series` with a call to a weather provider or the WeatherReading
model instead of the seeded pseudo-random generator).
"""
import math
import datetime
from dataclasses import dataclass, field
from typing import Optional

MONTH_NAMES = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]


def _seeded(seed: float) -> float:
    x = math.sin(seed) * 10000
    return x - math.floor(x)


def _simulated_rainfall_series(region, year_offset: int = 0) -> list[dict]:
    """Fallback series used when no real cached weather data is available yet."""
    series = []
    for m in range(12):
        month_num = m + 1
        if region.rain_start_month <= month_num <= region.rain_end_month:
            mid = (region.rain_start_month + region.rain_end_month) / 2
            spread = (region.rain_end_month - region.rain_start_month) / 2 or 1
            bell = math.exp(-(((month_num - mid) / spread) ** 2))
            noise = 0.75 + _seeded(month_num * 13 + len(region.name) * 3 + year_offset * 97) * 0.5
            mm = round(region.rain_peak_mm * bell * noise)
        else:
            mm = round(_seeded(month_num * 7 + len(region.name) + year_offset * 51) * 4)
        series.append({"month": MONTH_NAMES[m], "mm": mm, "month_num": month_num})
    return series


def get_rainfall_series(region, year_offset: int = 0, year: Optional[int] = None, use_real_data: bool = True) -> list[dict]:
    """
    Returns 12 monthly rainfall estimates (mm) for a Region instance.

    If `use_real_data` is True and NASA POWER data has already been synced
    for the target year (see weather_provider.sync_region_weather), the real
    cached totals are used. Any month missing from the cache falls back to
    the simulated estimate, so the series is always complete even with
    partial real data (e.g. the current, still-incomplete year).
    """
    target_year = year or (datetime.date.today().year - year_offset)
    simulated = _simulated_rainfall_series(region, year_offset)

    if not use_real_data:
        return simulated

    from .weather_provider import get_monthly_rainfall_from_cache  # local import avoids a hard dependency at module load

    real_totals = get_monthly_rainfall_from_cache(region, target_year)
    if not real_totals:
        return simulated

    for entry in simulated:
        if entry["month_num"] in real_totals:
            entry["mm"] = real_totals[entry["month_num"]]
            entry["source"] = "nasa_power"
        else:
            entry["source"] = "simulated"
    return simulated


@dataclass
class Advisory:
    sowing_advice: str
    sowing_level: str
    irrigation_advice: str
    irrigation_level: str
    risk_advice: str
    risk_level: str
    drought_index: str
    this_month_rain_mm: int
    total_season_rain_mm: int
    rain_ratio: float
    rain_series: list = field(default_factory=list)


def compute_advice(region, crop, today: Optional[datetime.date] = None) -> Advisory:
    today = today or datetime.date.today()
    now = today.month

    rain = get_rainfall_series(region, year=today.year)
    this_month_rain = next((x["mm"] for x in rain if x["month_num"] == now), 0)
    total_season_rain = sum(
        x["mm"] for x in rain if region.rain_start_month <= x["month_num"] <= region.rain_end_month
    )

    in_sow_window = crop.sow_window_start_month <= now <= crop.sow_window_end_month
    before_sow_window = now < crop.sow_window_start_month
    after_sow_window = crop.sow_window_end_month < now <= region.rain_end_month

    if in_sow_window:
        sowing_advice = (
            f"Fenêtre de semis optimale pour le {crop.name.lower()} : semer dès un cumul de pluie "
            f"utile d'au moins 20 mm sur 3 jours consécutifs."
        )
        sowing_level = "go"
    elif before_sow_window:
        sowing_advice = (
            f"Trop tôt : la fenêtre de semis pour le {crop.name.lower()} à {region.name} commence en "
            f"{MONTH_NAMES[crop.sow_window_start_month - 1]}. Préparer les parcelles en attendant."
        )
        sowing_level = "wait"
    elif after_sow_window:
        sowing_advice = (
            "Fenêtre de semis dépassée pour un cycle plein. Un semis tardif à cycle court reste "
            "possible, avec un risque accru de fin de saison sèche avant maturité."
        )
        sowing_level = "risk"
    else:
        sowing_advice = f"Hors saison des pluies à {region.name} — aucun semis pluvial recommandé actuellement."
        sowing_level = "risk"

    if this_month_rain < 30 and region.rain_start_month - 1 <= now <= region.rain_end_month:
        irrigation_advice = (
            f"Déficit hydrique probable ce mois-ci (~{this_month_rain} mm estimés). Irrigation "
            f"d'appoint ou paillage conseillés pour un besoin {crop.get_water_need_display().lower()}."
        )
        irrigation_level = "alert"
    elif 30 <= this_month_rain < 80:
        irrigation_advice = (
            f"Pluviométrie modérée estimée (~{this_month_rain} mm). Surveiller l'humidité du sol ; "
            f"irrigation possible après 10 jours sans pluie."
        )
        irrigation_level = "watch"
    else:
        irrigation_advice = (
            f"Pluviométrie estimée suffisante ce mois-ci (~{this_month_rain} mm). Pas d'irrigation "
            f"d'appoint nécessaire dans l'immédiat."
        )
        irrigation_level = "ok"

    rain_ratio = total_season_rain / crop.min_rain_mm if crop.min_rain_mm else 0
    drought_index = "Faible" if rain_ratio >= 0.9 else "Modéré" if rain_ratio >= 0.6 else "Sévère"

    if rain_ratio >= 0.75:
        risk_advice = (
            f"Cumul saisonnier estimé ({total_season_rain} mm) proche des besoins du {crop.name.lower()} "
            f"({crop.min_rain_mm} mm). Risque climatique modéré cette saison."
        )
        risk_level = "watch"
    else:
        risk_advice = (
            f"Cumul saisonnier estimé ({total_season_rain} mm) en-dessous du besoin du {crop.name.lower()} "
            f"({crop.min_rain_mm} mm). Envisager une variété plus résistante ou une diversification."
        )
        risk_level = "alert"

    return Advisory(
        sowing_advice=sowing_advice,
        sowing_level=sowing_level,
        irrigation_advice=irrigation_advice,
        irrigation_level=irrigation_level,
        risk_advice=risk_advice,
        risk_level=risk_level,
        drought_index=drought_index,
        this_month_rain_mm=this_month_rain,
        total_season_rain_mm=total_season_rain,
        rain_ratio=round(rain_ratio, 2),
        rain_series=rain,
    )
