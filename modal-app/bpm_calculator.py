"""
BPM Calculator for Dutch vehicle import tax.
Implements keuzerecht (optimaal regime) based on historical BPM tariffs.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from constants import (
    CO2_BRACKETS, DIESEL_SURCHARGE_RATE, DIESEL_SURCHARGE_THRESHOLD,
    DIESEL_SURCHARGE_SUBTRACT, DEPRECIATION_TABLE, HISTORICAL_BPM_REGIMES,
)
from utils import calculate_vehicle_age_months, normalize_fuel_type


@dataclass
class BPMResult:
    """Result of BPM calculation."""
    gross_bpm: float
    rest_bpm: float
    depreciation_percentage: float
    diesel_surcharge: float
    vehicle_age_months: int
    co2_gkm: int
    fuel_type: str
    # Keuzerecht fields
    regime_year: int = 2026
    regime_label: str = "2026 (WLTP)"
    regime_verified: bool = True
    bpm_2026_regime: float = 0  # BPM under 2026 regime for comparison
    regime_savings: float = 0  # Savings vs 2026 regime
    pre_wltp_note: str = ""  # Note for pre-July 2020 cars about NEDC optimization


def calculate_gross_bpm(co2_gkm: int) -> float:
    """
    Calculate gross BPM based on CO2 emissions using current (2026) regime.

    Args:
        co2_gkm: CO2 emissions in g/km

    Returns:
        Gross BPM amount in euros
    """
    return _calculate_gross_bpm_for_brackets(co2_gkm, CO2_BRACKETS)


def _calculate_gross_bpm_for_brackets(co2_gkm: int, brackets: list) -> float:
    """Calculate gross BPM using a specific set of CO2 brackets."""
    for bracket in brackets:
        if bracket["min"] <= co2_gkm <= bracket["max"]:
            bpm = (co2_gkm - bracket["threshold"]) * bracket["rate"] + bracket["base"]
            return round(bpm, 2)

    # If beyond all brackets, use the last bracket
    last_bracket = brackets[-1]
    bpm = (co2_gkm - last_bracket["threshold"]) * last_bracket["rate"] + last_bracket["base"]
    return round(bpm, 2)


def calculate_diesel_surcharge(co2_gkm: int, fuel_type: str) -> float:
    """
    Calculate diesel surcharge using current (2026) regime.

    Args:
        co2_gkm: CO2 emissions in g/km
        fuel_type: Normalized fuel type

    Returns:
        Diesel surcharge amount in euros
    """
    return _calculate_diesel_surcharge_for_regime(
        co2_gkm, fuel_type,
        DIESEL_SURCHARGE_THRESHOLD, DIESEL_SURCHARGE_SUBTRACT, DIESEL_SURCHARGE_RATE
    )


def _calculate_diesel_surcharge_for_regime(
    co2_gkm: int, fuel_type: str,
    threshold: int, subtract: int, rate: float
) -> float:
    """Calculate diesel surcharge using a specific regime's parameters."""
    if fuel_type != "diesel":
        return 0

    if co2_gkm <= threshold:
        return 0

    excess_grams = co2_gkm - subtract
    return round(excess_grams * rate, 2)


def get_depreciation_percentage(age_months: int) -> float:
    """
    Get depreciation percentage from forfaitaire tabel.
    Uses official method: base_percentage + (months_in_period * monthly_addition)

    Args:
        age_months: Vehicle age in months

    Returns:
        Depreciation percentage (0-100)
    """
    for bracket in DEPRECIATION_TABLE:
        if bracket["min_months"] <= age_months <= bracket["max_months"]:
            months_in_bracket = age_months - bracket["min_months"]
            depreciation = bracket["base_percentage"] + (months_in_bracket * bracket["monthly_addition"])
            return min(depreciation, 100.0)

    last_bracket = DEPRECIATION_TABLE[-1]
    return min(last_bracket["base_percentage"] + (12 * last_bracket["monthly_addition"]), 100.0)


def _calculate_bpm_for_regime(co2_gkm: int, fuel_type: str, regime: dict) -> tuple:
    """
    Calculate gross BPM + diesel surcharge for a specific historical regime.

    Returns:
        Tuple of (gross_bpm, diesel_surcharge, total_gross)
    """
    # EV exemption: pre-2025 EVs pay €0 BPM
    if fuel_type == "electric" and regime.get("ev_exempt", False):
        return (0, 0, 0)

    gross_bpm = _calculate_gross_bpm_for_brackets(co2_gkm, regime["co2_brackets"])
    diesel_surcharge = _calculate_diesel_surcharge_for_regime(
        co2_gkm, fuel_type,
        regime["diesel_threshold"], regime["diesel_subtract"], regime["diesel_rate"]
    )
    total_gross = gross_bpm + diesel_surcharge
    return (gross_bpm, diesel_surcharge, total_gross)


def _get_applicable_regimes(first_registration_date: datetime) -> list:
    """
    Get all applicable regimes for the keuzerecht based on the DET date.
    The importeur may choose any regime from DET year to 2026.
    """
    det_year = first_registration_date.year

    # For pre-2020 cars: oldest available WLTP regime is 2020 H2
    # For 2020+ cars: start from DET year
    start_year = max(det_year, 2020)

    return [r for r in HISTORICAL_BPM_REGIMES if r["year"] >= start_year]


def calculate_bpm(
    co2_gkm: int,
    fuel_type: str,
    first_registration_date: datetime
) -> BPMResult:
    """
    Calculate complete BPM for a vehicle using keuzerecht (optimal regime).

    Evaluates all applicable historical regimes and selects the one
    resulting in the lowest BPM, as legally permitted under Article 110 VWEU.

    Args:
        co2_gkm: CO2 emissions in g/km
        fuel_type: Fuel type string
        first_registration_date: Date of first registration

    Returns:
        BPMResult with all calculation details including regime info
    """
    normalized_fuel = normalize_fuel_type(fuel_type)
    age_months = calculate_vehicle_age_months(first_registration_date)
    depreciation = get_depreciation_percentage(age_months)

    # Calculate BPM under 2026 regime (for comparison)
    regime_2026 = next(r for r in HISTORICAL_BPM_REGIMES if r["year"] == 2026)
    _, _, total_gross_2026 = _calculate_bpm_for_regime(co2_gkm, normalized_fuel, regime_2026)
    rest_bpm_2026 = round(total_gross_2026 * (1 - depreciation / 100), 2)

    # Find optimal regime (lowest BPM)
    applicable_regimes = _get_applicable_regimes(first_registration_date)

    best_regime = None
    best_total_gross = float("inf")
    best_gross_bpm = 0
    best_diesel_surcharge = 0

    for regime in applicable_regimes:
        gross_bpm, diesel_surcharge, total_gross = _calculate_bpm_for_regime(
            co2_gkm, normalized_fuel, regime
        )
        if total_gross < best_total_gross:
            best_total_gross = total_gross
            best_gross_bpm = gross_bpm
            best_diesel_surcharge = diesel_surcharge
            best_regime = regime

    # Fallback to 2026 if no regime found (shouldn't happen)
    if best_regime is None:
        best_regime = regime_2026
        best_gross_bpm = total_gross_2026
        best_diesel_surcharge = 0
        best_total_gross = total_gross_2026

    # Calculate rest BPM with optimal regime
    rest_bpm = round(best_total_gross * (1 - depreciation / 100), 2)

    # Savings vs 2026 regime
    regime_savings = round(rest_bpm_2026 - rest_bpm, 2)

    # Note for pre-WLTP cars
    det_year = first_registration_date.year
    pre_wltp_note = ""
    if det_year < 2020 or (det_year == 2020 and first_registration_date.month < 7):
        pre_wltp_note = (
            "Uw auto dateert van voor de WLTP-overgang (juli 2020). "
            "Met de NEDC CO2-waarde en het historisch NEDC-regime kan de BPM "
            "aanzienlijk lager zijn. Raadpleeg een BPM-specialist."
        )

    return BPMResult(
        gross_bpm=round(best_gross_bpm, 2),
        rest_bpm=rest_bpm,
        depreciation_percentage=depreciation,
        diesel_surcharge=round(best_diesel_surcharge, 2),
        vehicle_age_months=age_months,
        co2_gkm=co2_gkm,
        fuel_type=normalized_fuel,
        regime_year=best_regime["year"],
        regime_label=best_regime["label"],
        regime_verified=best_regime["verified"],
        bpm_2026_regime=rest_bpm_2026,
        regime_savings=regime_savings,
        pre_wltp_note=pre_wltp_note,
    )


def bpm_to_dict(result: BPMResult) -> dict:
    """Convert BPMResult to dictionary for JSON serialization."""
    d = {
        "grossBPM": result.gross_bpm,
        "restBPM": result.rest_bpm,
        "depreciationPercentage": result.depreciation_percentage,
        "dieselSurcharge": result.diesel_surcharge,
        "vehicleAgeMonths": result.vehicle_age_months,
        "co2_gkm": result.co2_gkm,
        "fuelType": result.fuel_type,
        # Keuzerecht info
        "regimeYear": result.regime_year,
        "regimeLabel": result.regime_label,
        "regimeVerified": result.regime_verified,
        "bpm2026Regime": result.bpm_2026_regime,
        "regimeSavings": result.regime_savings,
    }
    if result.pre_wltp_note:
        d["preWltpNote"] = result.pre_wltp_note
    return d
