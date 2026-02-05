"""
Advanced pricing model with depreciation calculation and equipment valuation.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import statistics


@dataclass
class ComparableWithScore:
    """Comparable vehicle with relevance score and normalized price."""
    price_eur: int
    mileage_km: int
    year: int
    title: str
    listing_url: str
    source: str
    location: str
    # Derived fields
    normalized_price: int  # Price adjusted to target year
    relevance_score: float  # 0-1, how relevant this comparable is
    equipment_score: float  # 0-1, how well-equipped compared to target
    year_delta: int  # Years difference from target
    annual_depreciation: Optional[float] = None  # Calculated depreciation per year


def calculate_annual_depreciation_rate(comparables: List[dict]) -> float:
    """
    Calculate average annual depreciation rate from comparables.

    Uses comparables of different years to estimate how much value
    a car loses per year.

    Args:
        comparables: List of comparable vehicles with year and price

    Returns:
        Annual depreciation rate (e.g., 0.15 = 15% per year)
    """
    if len(comparables) < 2:
        # Default depreciation rates by age bracket
        # Older cars depreciate slower
        return 0.08  # 8% per year default for 10+ year old cars

    # Calculate price per year for each comparable
    price_per_year = []
    for comp in comparables:
        if comp.get("year") and comp.get("price_eur", 0) > 0:
            # Rough estimation: newer = higher price
            price_per_year.append({
                "year": comp["year"],
                "price": comp["price_eur"],
                "mileage": comp.get("mileage_km", 0),
            })

    if len(price_per_year) < 2:
        return 0.08

    # Sort by year
    price_per_year.sort(key=lambda x: x["year"])

    # Calculate year-over-year depreciation rates
    depreciation_rates = []
    for i in range(len(price_per_year) - 1):
        newer = price_per_year[i + 1]
        older = price_per_year[i]

        year_diff = newer["year"] - older["year"]
        if year_diff == 0:
            continue

        price_diff = newer["price"] - older["price"]

        # Adjust for mileage difference (rough estimate: €0.02/km value)
        mileage_diff = newer["mileage"] - older["mileage"]
        mileage_adjustment = mileage_diff * 0.02
        adjusted_price_diff = price_diff + mileage_adjustment

        # Calculate annual rate
        if newer["price"] > 0:
            annual_rate = (adjusted_price_diff / newer["price"]) / year_diff
            # Sanity check: depreciation between -30% and +5% per year
            if -0.30 <= annual_rate <= 0.05:
                depreciation_rates.append(abs(annual_rate))

    if depreciation_rates:
        # Use median to avoid outliers
        return statistics.median(depreciation_rates)

    return 0.08  # Default


def normalize_price_to_year(
    price: int,
    from_year: int,
    to_year: int,
    depreciation_rate: float,
) -> int:
    """
    Adjust a car's price from one year to another using depreciation rate.

    Args:
        price: Original price
        from_year: Year of the comparable
        to_year: Target year to normalize to
        depreciation_rate: Annual depreciation rate (e.g., 0.10 = 10%/year)

    Returns:
        Normalized price for target year
    """
    year_delta = to_year - from_year

    if year_delta == 0:
        return price

    # If target is newer (e.g., 2010 vs 2008), car was worth MORE back then
    # If target is older (e.g., 2010 vs 2012), car is worth LESS now
    if year_delta > 0:
        # Target year is newer - depreciate backwards
        # A 2012 car at €5000 was worth more in 2010
        factor = (1 + depreciation_rate) ** abs(year_delta)
        normalized = int(price * factor)
    else:
        # Target year is older - appreciate forwards
        # A 2008 car at €5000 would be worth less in 2010
        factor = (1 - depreciation_rate) ** abs(year_delta)
        normalized = int(price * factor)

    return normalized


def calculate_equipment_score(
    target_equipment: List[str],
    comparable_equipment: List[str],
) -> float:
    """
    Calculate how well-equipped a comparable is vs target.

    Args:
        target_equipment: List of equipment/features on target vehicle
        comparable_equipment: List of equipment on comparable

    Returns:
        Score from 0-1 (1.0 = same or better equipped)
    """
    if not target_equipment:
        return 1.0  # No basis for comparison

    # Count matching features
    target_set = set(feat.lower() for feat in target_equipment)
    comp_set = set(feat.lower() for feat in comparable_equipment)

    # Features in common
    common = target_set.intersection(comp_set)

    # Features target has that comparable doesn't
    missing_in_comp = target_set - comp_set

    # Features comparable has that target doesn't (bonus)
    extra_in_comp = comp_set - target_set

    # Base score: how many target features are matched
    base_score = len(common) / len(target_set) if target_set else 1.0

    # Penalty for missing features
    penalty = len(missing_in_comp) * 0.05  # -5% per missing feature

    # Bonus for extra features
    bonus = len(extra_in_comp) * 0.02  # +2% per extra feature

    final_score = base_score - penalty + bonus

    # Clamp between 0 and 1.2 (allow 20% bonus for well-equipped cars)
    return max(0.0, min(1.2, final_score))


def calculate_relevance_score(
    target_year: int,
    target_mileage: int,
    target_equipment: List[str],
    comparable: dict,
    depreciation_rate: float,
) -> Tuple[float, int, float]:
    """
    Calculate how relevant a comparable is for valuation.

    Args:
        target_year: Year of target vehicle
        target_mileage: Mileage of target vehicle
        target_equipment: Equipment list of target
        comparable: Comparable vehicle dict
        depreciation_rate: Annual depreciation rate

    Returns:
        Tuple of (relevance_score, normalized_price, equipment_score)
    """
    comp_year = comparable.get("year", target_year)
    comp_mileage = comparable.get("mileage_km", target_mileage)
    comp_price = comparable.get("price_eur", 0)
    comp_equipment = comparable.get("equipment", [])

    # Year proximity score (closer = better)
    year_delta = abs(comp_year - target_year)
    year_score = 1.0 / (1.0 + year_delta * 0.3)  # Decay as years differ

    # Mileage proximity score
    mileage_delta = abs(comp_mileage - target_mileage)
    mileage_score = 1.0 / (1.0 + mileage_delta / 50000)  # Decay per 50k km

    # Equipment score
    equipment_score = calculate_equipment_score(target_equipment, comp_equipment)

    # Normalize price to target year
    normalized_price = normalize_price_to_year(
        comp_price,
        comp_year,
        target_year,
        depreciation_rate,
    )

    # Overall relevance (weighted combination)
    relevance = (
        year_score * 0.4 +
        mileage_score * 0.4 +
        equipment_score * 0.2
    )

    return relevance, normalized_price, equipment_score


def score_and_normalize_comparables(
    target_year: int,
    target_mileage: int,
    target_equipment: List[str],
    comparables: List[dict],
    min_comparables: int = 3,
) -> List[ComparableWithScore]:
    """
    Score and normalize all comparables for better valuation.

    Args:
        target_year: Year of target vehicle
        target_mileage: Mileage of target vehicle
        target_equipment: Equipment list of target
        comparables: List of comparable vehicles
        min_comparables: Minimum number of comparables desired

    Returns:
        List of scored and normalized comparables, sorted by relevance
    """
    if not comparables:
        return []

    # Calculate depreciation rate from comparables
    depreciation_rate = calculate_annual_depreciation_rate(comparables)

    # Score each comparable
    scored_comparables = []
    for comp in comparables:
        relevance, normalized_price, equipment_score = calculate_relevance_score(
            target_year,
            target_mileage,
            target_equipment,
            comp,
            depreciation_rate,
        )

        scored_comp = ComparableWithScore(
            price_eur=comp.get("price_eur", 0),
            mileage_km=comp.get("mileage_km", 0),
            year=comp.get("year", target_year),
            title=comp.get("title", ""),
            listing_url=comp.get("listing_url", ""),
            source=comp.get("source", ""),
            location=comp.get("location", ""),
            normalized_price=normalized_price,
            relevance_score=relevance,
            equipment_score=equipment_score,
            year_delta=comp.get("year", target_year) - target_year,
            annual_depreciation=depreciation_rate,
        )
        scored_comparables.append(scored_comp)

    # Sort by relevance (best first)
    scored_comparables.sort(key=lambda x: x.relevance_score, reverse=True)

    return scored_comparables


def calculate_market_value(
    scored_comparables: List[ComparableWithScore],
    confidence_threshold: float = 0.5,
) -> Dict:
    """
    Calculate market value from scored comparables.

    Args:
        scored_comparables: List of scored and normalized comparables
        confidence_threshold: Minimum relevance score to include

    Returns:
        Dict with estimated value, range, confidence, etc.
    """
    if not scored_comparables:
        return {
            "estimated_value": 0,
            "value_range": {"low": 0, "high": 0},
            "confidence": 0.0,
            "comparables_used": 0,
            "depreciation_rate": 0.0,
        }

    # Filter by confidence threshold
    relevant_comps = [
        c for c in scored_comparables
        if c.relevance_score >= confidence_threshold
    ]

    # If not enough relevant comparables, lower threshold
    if len(relevant_comps) < 3:
        relevant_comps = scored_comparables[:5]  # Take top 5

    if not relevant_comps:
        return {
            "estimated_value": 0,
            "value_range": {"low": 0, "high": 0},
            "confidence": 0.0,
            "comparables_used": 0,
            "depreciation_rate": 0.0,
        }

    # Calculate weighted average of normalized prices
    total_weight = sum(c.relevance_score for c in relevant_comps)
    weighted_value = sum(
        c.normalized_price * c.relevance_score
        for c in relevant_comps
    ) / total_weight if total_weight > 0 else 0

    # Calculate equipment-adjusted value
    avg_equipment_score = statistics.mean(c.equipment_score for c in relevant_comps)
    equipment_adjustment = (avg_equipment_score - 1.0) * weighted_value * 0.1  # ±10% for equipment

    estimated_value = int(weighted_value + equipment_adjustment)

    # Value range (±15% or based on actual spread)
    normalized_prices = [c.normalized_price for c in relevant_comps]
    if len(normalized_prices) >= 3:
        low = int(min(normalized_prices))
        high = int(max(normalized_prices))
    else:
        low = int(estimated_value * 0.85)
        high = int(estimated_value * 1.15)

    # Confidence based on number and quality of comparables
    confidence = min(1.0, (
        len(relevant_comps) / 5.0 * 0.5 +  # More comparables = higher confidence
        statistics.mean(c.relevance_score for c in relevant_comps) * 0.5
    ))

    depreciation_rate = relevant_comps[0].annual_depreciation if relevant_comps else 0.0

    return {
        "estimated_value": estimated_value,
        "value_range": {"low": low, "high": high},
        "confidence": round(confidence, 2),
        "comparables_used": len(relevant_comps),
        "depreciation_rate": round(depreciation_rate * 100, 1),  # As percentage
        "equipment_adjustment": int(equipment_adjustment),
        "avg_equipment_score": round(avg_equipment_score, 2),
    }
