"""
BPM Calculator for Dutch vehicle import tax.
Based on 2026 Belastingdienst forfaitaire tabel.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from constants import CO2_BRACKETS, DIESEL_SURCHARGE_RATE, DIESEL_SURCHARGE_THRESHOLD, DIESEL_SURCHARGE_SUBTRACT, DEPRECIATION_TABLE
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


def calculate_gross_bpm(co2_gkm: int) -> float:
    """
    Calculate gross BPM based on CO2 emissions.
    Official formula: BPM = (CO2 - threshold) * rate + base
    Where threshold is "kolom 1" from the official Belastingdienst table.

    Args:
        co2_gkm: CO2 emissions in g/km

    Returns:
        Gross BPM amount in euros
    """
    # Find the correct bracket for this CO2 value
    for bracket in CO2_BRACKETS:
        if bracket["min"] <= co2_gkm <= bracket["max"]:
            # Formula: (CO2 - threshold) * rate + base
            # threshold is the official "kolom 1" value from Belastingdienst
            bpm = (co2_gkm - bracket["threshold"]) * bracket["rate"] + bracket["base"]
            return round(bpm, 2)

    # If beyond all brackets, use the last bracket
    last_bracket = CO2_BRACKETS[-1]
    bpm = (co2_gkm - last_bracket["threshold"]) * last_bracket["rate"] + last_bracket["base"]
    return round(bpm, 2)


def calculate_diesel_surcharge(co2_gkm: int, fuel_type: str) -> float:
    """
    Calculate diesel surcharge if applicable.
    Official formula: (CO2 - 69) × €114,83 for diesel cars with CO2 > 70 g/km

    Args:
        co2_gkm: CO2 emissions in g/km
        fuel_type: Normalized fuel type

    Returns:
        Diesel surcharge amount in euros
    """
    if fuel_type != "diesel":
        return 0

    if co2_gkm <= DIESEL_SURCHARGE_THRESHOLD:
        return 0

    # Official formula subtracts 69, not the threshold (70)
    excess_grams = co2_gkm - DIESEL_SURCHARGE_SUBTRACT
    return round(excess_grams * DIESEL_SURCHARGE_RATE, 2)


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
            # Calculate months within this bracket
            months_in_bracket = age_months - bracket["min_months"]

            # Calculate depreciation: base + (months * monthly_addition)
            depreciation = bracket["base_percentage"] + (months_in_bracket * bracket["monthly_addition"])

            # Cap at 100%
            return min(depreciation, 100.0)

    # If beyond all brackets, return maximum from last bracket
    last_bracket = DEPRECIATION_TABLE[-1]
    return min(last_bracket["base_percentage"] + (12 * last_bracket["monthly_addition"]), 100.0)


def calculate_bpm(
    co2_gkm: int,
    fuel_type: str,
    first_registration_date: datetime
) -> BPMResult:
    """
    Calculate complete BPM for a vehicle.

    Args:
        co2_gkm: CO2 emissions in g/km
        fuel_type: Fuel type string
        first_registration_date: Date of first registration

    Returns:
        BPMResult with all calculation details
    """
    # Normalize fuel type
    normalized_fuel = normalize_fuel_type(fuel_type)

    # Calculate vehicle age
    age_months = calculate_vehicle_age_months(first_registration_date)

    # Calculate gross BPM
    gross_bpm = calculate_gross_bpm(co2_gkm)

    # Calculate diesel surcharge
    diesel_surcharge = calculate_diesel_surcharge(co2_gkm, normalized_fuel)

    # Total gross BPM including surcharge
    total_gross = gross_bpm + diesel_surcharge

    # Get depreciation percentage
    depreciation = get_depreciation_percentage(age_months)

    # Calculate rest BPM (what you actually pay)
    rest_bpm = total_gross * (1 - depreciation / 100)

    return BPMResult(
        gross_bpm=round(gross_bpm, 2),
        rest_bpm=round(rest_bpm, 2),
        depreciation_percentage=depreciation,
        diesel_surcharge=round(diesel_surcharge, 2),
        vehicle_age_months=age_months,
        co2_gkm=co2_gkm,
        fuel_type=normalized_fuel,
    )


def bpm_to_dict(result: BPMResult) -> dict:
    """Convert BPMResult to dictionary for JSON serialization."""
    return {
        "grossBPM": result.gross_bpm,
        "restBPM": result.rest_bpm,
        "depreciationPercentage": result.depreciation_percentage,
        "dieselSurcharge": result.diesel_surcharge,
        "vehicleAgeMonths": result.vehicle_age_months,
        "co2_gkm": result.co2_gkm,
        "fuelType": result.fuel_type,
    }
