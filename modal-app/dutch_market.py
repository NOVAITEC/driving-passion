"""
Dutch market search for comparable vehicles.
Searches AutoScout24 NL for similar cars.
"""

import httpx
from dataclasses import dataclass
from typing import Optional
import json
import re

from scrapers import VehicleData
from utils import extract_model_variant


@dataclass
class DutchComparable:
    """A comparable vehicle found on the Dutch market."""
    price_eur: int
    mileage_km: int
    year: int = 0
    title: str = ""
    listing_url: str = ""
    source: str = "autoscout24"
    location: str = ""


@dataclass
class MarketStats:
    """Statistics about the Dutch market for this vehicle."""
    count: int
    avg_price: float
    min_price: int
    max_price: int
    median_price: float


def build_autoscout24_search_url(vehicle: VehicleData) -> str:
    """
    Build AutoScout24 NL search URL for comparable vehicles.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        Search URL string
    """
    base_url = "https://www.autoscout24.nl/lst"

    # Normalize make/model for URL
    make = vehicle.make.lower().replace(" ", "-")

    # Handle RS models and other variants
    base_model, variant = extract_model_variant(vehicle.model)
    model = base_model.lower().replace(" ", "-")

    # Build path
    path = f"/{make}/{model}"

    # Build query parameters
    params = []

    # Year range: ±1 year
    params.append(f"fregfrom={vehicle.year - 1}")
    params.append(f"fregto={vehicle.year + 1}")

    # Mileage range: ±20%
    min_km = int(vehicle.mileage_km * 0.8)
    max_km = int(vehicle.mileage_km * 1.2)
    params.append(f"kmfrom={min_km}")
    params.append(f"kmto={max_km}")

    # Fuel type mapping
    fuel_map = {
        "petrol": "B",
        "diesel": "D",
        "electric": "E",
        "hybrid": "2",  # All hybrids
        "lpg": "L",
    }
    if vehicle.fuel_type in fuel_map:
        params.append(f"fuel={fuel_map[vehicle.fuel_type]}")

    # Transmission mapping
    trans_map = {
        "automatic": "A",
        "manual": "M",
    }
    if vehicle.transmission in trans_map:
        params.append(f"gear={trans_map[vehicle.transmission]}")

    # Sort by price
    params.append("sort=price")
    params.append("desc=0")

    # Country: Netherlands
    params.append("cy=NL")

    query = "&".join(params)
    return f"{base_url}{path}?{query}"


def parse_autoscout24_search_results(html: str) -> list[DutchComparable]:
    """
    Parse AutoScout24 search results from HTML.

    The data is embedded in __NEXT_DATA__ JSON.

    Args:
        html: Raw HTML from search page

    Returns:
        List of comparable vehicles
    """
    comparables = []

    # Find __NEXT_DATA__ script
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)

    if not match:
        return comparables

    try:
        data = json.loads(match.group(1))
        listings = data.get("props", {}).get("pageProps", {}).get("listings", [])

        for listing in listings:
            try:
                price = int(listing.get("price", {}).get("value", 0) or 0)
                mileage = int(listing.get("mileage", 0) or 0)
                year = int(listing.get("year", 0) or 0)
                title = listing.get("title", "")
                listing_id = listing.get("id", "")
                location = listing.get("location", {}).get("city", "")

                if price > 0:
                    comparables.append(DutchComparable(
                        price_eur=price,
                        mileage_km=mileage,
                        year=year,
                        title=title,
                        listing_url=f"https://www.autoscout24.nl/aanbod/{listing_id}" if listing_id else "",
                        source="autoscout24",
                        location=location,
                    ))
            except (KeyError, TypeError, ValueError):
                continue

    except json.JSONDecodeError:
        pass

    return comparables


async def search_dutch_market(vehicle: VehicleData) -> list[DutchComparable]:
    """
    Search the Dutch market for comparable vehicles.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        List of comparable vehicles
    """
    search_url = build_autoscout24_search_url(vehicle)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "nl-NL,nl;q=0.9",
                },
                follow_redirects=True,
                timeout=30,
            )
            response.raise_for_status()

            return parse_autoscout24_search_results(response.text)

        except Exception as e:
            print(f"Error searching Dutch market: {e}")
            return []


def get_market_stats(comparables: list[DutchComparable]) -> MarketStats:
    """
    Calculate market statistics from comparables.

    Uses IQR method to filter outliers.

    Args:
        comparables: List of comparable vehicles

    Returns:
        Market statistics
    """
    if not comparables:
        return MarketStats(
            count=0,
            avg_price=0,
            min_price=0,
            max_price=0,
            median_price=0,
        )

    prices = sorted([c.price_eur for c in comparables])

    # Filter outliers using IQR
    if len(prices) >= 4:
        q1_idx = len(prices) // 4
        q3_idx = (3 * len(prices)) // 4
        q1 = prices[q1_idx]
        q3 = prices[q3_idx]
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        filtered_prices = [p for p in prices if lower_bound <= p <= upper_bound]
    else:
        filtered_prices = prices

    if not filtered_prices:
        filtered_prices = prices

    avg_price = sum(filtered_prices) / len(filtered_prices)
    median_idx = len(filtered_prices) // 2
    median_price = filtered_prices[median_idx]

    return MarketStats(
        count=len(comparables),
        avg_price=round(avg_price, 2),
        min_price=min(filtered_prices),
        max_price=max(filtered_prices),
        median_price=median_price,
    )


def comparable_to_dict(comp: DutchComparable) -> dict:
    """Convert DutchComparable to dictionary for JSON serialization."""
    return {
        "price_eur": comp.price_eur,
        "mileage_km": comp.mileage_km,
        "year": comp.year,
        "title": comp.title,
        "listingUrl": comp.listing_url,
        "source": comp.source,
        "location": comp.location,
    }


def market_stats_to_dict(stats: MarketStats) -> dict:
    """Convert MarketStats to dictionary for JSON serialization."""
    return {
        "count": stats.count,
        "avgPrice": stats.avg_price,
        "minPrice": stats.min_price,
        "maxPrice": stats.max_price,
        "medianPrice": stats.median_price,
    }
