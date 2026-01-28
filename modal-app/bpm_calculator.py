"""
BPM Calculator for Dutch vehicle import tax.
Based on 2026 Belastingdienst forfaitaire tabel.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from constants import CO2_BRACKETS, DIESEL_SURCHARGE_RATE, DIESEL_SURCHARGE_THRESHOLD, DEPRECIATION_TABLE
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

    Args:
        co2_gkm: CO2 emissions in g/km

    Returns:
        Gross BPM amount in euros
    """
    total_bpm = 0

    for bracket in CO2_BRACKETS:
        if co2_gkm >= bracket["min"]:
            # Calculate grams in this bracket
            bracket_max = min(co2_gkm, bracket["max"])
            grams_in_bracket = bracket_max - bracket["min"] + 1

            if bracket["min"] == 0:
                # First bracket is flat base amount
                total_bpm = bracket["base"]
            else:
                # Add rate * grams for this bracket
                total_bpm += grams_in_bracket * bracket["rate"]

    return round(total_bpm, 2)


def calculate_diesel_surcharge(co2_gkm: int, fuel_type: str) -> float:
    """
    Calculate diesel surcharge if applicable.

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

    excess_grams = co2_gkm - DIESEL_SURCHARGE_THRESHOLD
    return round(excess_grams * DIESEL_SURCHARGE_RATE, 2)


def get_depreciation_percentage(age_months: int) -> float:
    """
    Get depreciation percentage from forfaitaire tabel.

    Args:
        age_months: Vehicle age in months

    Returns:
        Depreciation percentage (0-92)
    """
    for bracket in DEPRECIATION_TABLE:
        if bracket["min_months"] <= age_months <= bracket["max_months"]:
            return bracket["percentage"]

    return 92  # Maximum depreciation


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
