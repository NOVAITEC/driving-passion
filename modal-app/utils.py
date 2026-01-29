"""
Utility functions for the Driving Passion Auto Import Calculator.
"""

from datetime import datetime
from typing import Optional


def calculate_vehicle_age_months(first_registration_date: datetime) -> int:
    """
    Calculate the age of a vehicle in months.

    Args:
        first_registration_date: The date of first registration

    Returns:
        Age in months (rounded down)
    """
    now = datetime.now()
    months = (now.year - first_registration_date.year) * 12
    months += now.month - first_registration_date.month

    # Adjust if we haven't reached the day of month yet
    if now.day < first_registration_date.day:
        months -= 1

    return max(0, months)


def normalize_fuel_type(fuel_type: str) -> str:
    """
    Normalize fuel type strings to standard values.

    Args:
        fuel_type: Raw fuel type string

    Returns:
        Normalized fuel type: 'petrol', 'diesel', 'electric', 'hybrid', 'lpg'
    """
    fuel_lower = fuel_type.lower().strip()

    diesel_terms = ['diesel', 'diesel (diesel)']
    petrol_terms = ['petrol', 'benzine', 'gasoline', 'petrol (gasoline)']
    electric_terms = ['electric', 'elektrisch', 'elektro', 'ev']
    hybrid_terms = ['hybrid', 'hybride', 'plug-in hybrid', 'phev']
    lpg_terms = ['lpg', 'gas', 'autogas']

    if any(term in fuel_lower for term in diesel_terms):
        return 'diesel'
    if any(term in fuel_lower for term in petrol_terms):
        return 'petrol'
    if any(term in fuel_lower for term in electric_terms):
        return 'electric'
    if any(term in fuel_lower for term in hybrid_terms):
        return 'hybrid'
    if any(term in fuel_lower for term in lpg_terms):
        return 'lpg'

    return 'petrol'  # Default to petrol if unknown


def normalize_transmission(transmission: str) -> str:
    """
    Normalize transmission strings to standard values.

    Args:
        transmission: Raw transmission string

    Returns:
        Normalized transmission: 'automatic' or 'manual'
    """
    trans_lower = transmission.lower().strip()

    auto_terms = ['automatic', 'automatik', 'automaat', 'auto', 'dsg', 'tiptronic', 's tronic']
    manual_terms = ['manual', 'manuell', 'handgeschakeld', 'schaltgetriebe']

    if any(term in trans_lower for term in auto_terms):
        return 'automatic'
    if any(term in trans_lower for term in manual_terms):
        return 'manual'

    return 'automatic'  # Default to automatic if unknown


def format_currency(amount: float, currency: str = "EUR") -> str:
    """
    Format a number as currency.

    Args:
        amount: The amount to format
        currency: Currency code (default: EUR)

    Returns:
        Formatted currency string
    """
    if currency == "EUR":
        return f"€{amount:,.0f}".replace(",", ".")
    return f"{amount:,.0f} {currency}"


def extract_model_variant(model: str) -> tuple[str, Optional[str]]:
    """
    Extract base model and variant from model string.

    E.g., "RSQ3" -> ("RS Q3", None)
          "320d xDrive" -> ("320d xDrive", None)
          "Golf 2.0 TDI Highline" -> ("Golf 2.0 TDI", "Highline")

    IMPORTANT: Engine variants (numbers + fuel type) are kept in base_model
    for better market comparisons. Only trim levels are separated as variant.

    Args:
        model: Raw model string

    Returns:
        Tuple of (base_model, variant)
    """
    # RS model corrections for Audi
    rs_models = {
        'rsq3': 'RS Q3',
        'rsq5': 'RS Q5',
        'rsq7': 'RS Q7',
        'rsq8': 'RS Q8',
        'rs3': 'RS3',
        'rs4': 'RS4',
        'rs5': 'RS5',
        'rs6': 'RS6',
        'rs7': 'RS7',
    }

    model_lower = model.lower().replace(" ", "")

    for key, corrected in rs_models.items():
        if key in model_lower:
            return corrected, None

    # Split model into parts
    parts = model.split()
    if len(parts) <= 1:
        return model, None

    # Identify engine-related parts (should stay in base_model)
    # vs trim/equipment parts (can be separated as variant)
    engine_indicators = ['tdi', 'tsi', 'tfsi', 'fsi', 'gti', 'gtd', 'rs', 'amg',
                        'xdrive', '4matic', 'quattro', 'e-tron', 'phev', 'hybrid',
                        'd', 'i', 'e', 's', 'm']  # Common suffixes like "320d", "118i"
    trim_levels = ['highline', 'comfortline', 'trendline', 'style', 'sport',
                   'business', 'executive', 'luxury', 'premium', 'edition',
                   'line', 'pack', 'plus', 'comfort', 'elegance', 'dynamic']

    # Find where trim level starts (if any)
    trim_start_idx = None
    for i, part in enumerate(parts):
        part_lower = part.lower()
        # Check if this is a trim level word
        if part_lower in trim_levels:
            trim_start_idx = i
            break
        # If we see engine indicators, keep going
        is_engine_part = False
        for indicator in engine_indicators:
            if indicator in part_lower or part_lower.endswith(indicator):
                is_engine_part = True
                break
        # If it's a number (engine size like "2.0" or "320"), keep it
        if any(c.isdigit() for c in part):
            is_engine_part = True
        # If not an engine part and not the first few words, might be trim
        if not is_engine_part and i > 2:
            trim_start_idx = i
            break

    if trim_start_idx is None:
        # No clear trim level found, keep everything as base model
        return model, None

    # Split at trim level
    base_model = " ".join(parts[:trim_start_idx])
    variant = " ".join(parts[trim_start_idx:])

    return base_model, variant if variant else None
