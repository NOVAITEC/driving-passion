"""
Dutch market search for comparable vehicles.
Searches AutoScout24 NL and Marktplaats for similar cars.
"""

import httpx
from dataclasses import dataclass
from typing import Optional
import json
import re
import asyncio

from scrapers import VehicleData
from utils import extract_model_variant
from constants import APIFY_ACTORS


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


def build_marktplaats_search_url(vehicle: VehicleData) -> str:
    """
    Build Marktplaats search URL for comparable vehicles.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        Search URL string for Marktplaats auto's
    """
    base_url = "https://www.marktplaats.nl/l/auto-s"

    # Normalize make for URL (marktplaats uses different format)
    make = vehicle.make.lower().replace(" ", "-")

    # Handle model
    base_model, variant = extract_model_variant(vehicle.model)
    model = base_model.lower().replace(" ", "-")

    # Build query parameters
    params = []

    # Search query with make and model
    params.append(f"q={vehicle.make}+{base_model}")

    # Year range: ±1 year
    params.append(f"attributesByKey[]=constructionYear%3A{vehicle.year - 1}%7C{vehicle.year + 1}")

    # Mileage range: ±20%
    min_km = int(vehicle.mileage_km * 0.8)
    max_km = int(vehicle.mileage_km * 1.2)
    # Marktplaats uses mileage ranges like 0|50000, 50000|100000, etc.
    # We'll use the closest ranges
    params.append(f"attributesByKey[]=mileage%3A{min_km}%7C{max_km}")

    # Fuel type mapping for Marktplaats
    fuel_map = {
        "petrol": "benzine",
        "diesel": "diesel",
        "electric": "elektrisch",
        "hybrid": "hybride",
        "lpg": "lpg",
    }
    if vehicle.fuel_type in fuel_map:
        params.append(f"attributesByKey[]=fuel%3A{fuel_map[vehicle.fuel_type]}")

    query = "&".join(params)
    return f"{base_url}/?{query}"


async def search_marktplaats_via_apify(
    vehicle: VehicleData,
    apify_token: str,
    max_results: int = 20
) -> list[DutchComparable]:
    """
    Search Marktplaats for comparable vehicles using Apify actor.

    Args:
        vehicle: The target vehicle to find comparables for
        apify_token: Apify API token
        max_results: Maximum number of results to return

    Returns:
        List of comparable vehicles from Marktplaats
    """
    actor_id = APIFY_ACTORS["marktplaats"]
    search_url = build_marktplaats_search_url(vehicle)

    async with httpx.AsyncClient() as client:
        try:
            # Start the actor run
            run_response = await client.post(
                f"https://api.apify.com/v2/acts/{actor_id}/runs",
                headers={"Authorization": f"Bearer {apify_token}"},
                json={
                    "startUrls": [{"url": search_url}],
                    "maxItems": max_results,
                },
                timeout=30,
            )
            run_response.raise_for_status()
            run_data = run_response.json()
            run_id = run_data["data"]["id"]

            # Wait for completion (max 60 seconds)
            for _ in range(30):
                await asyncio.sleep(2)

                status_response = await client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    headers={"Authorization": f"Bearer {apify_token}"},
                    timeout=10,
                )
                status_data = status_response.json()
                status = status_data["data"]["status"]

                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    print(f"Marktplaats scraper failed with status: {status}")
                    return []
            else:
                print("Marktplaats scraper timed out")
                return []

            # Get results
            dataset_id = status_data["data"]["defaultDatasetId"]
            results_response = await client.get(
                f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                headers={"Authorization": f"Bearer {apify_token}"},
                params={"format": "json"},
                timeout=30,
            )
            results_response.raise_for_status()
            results = results_response.json()

            return parse_marktplaats_results(results)

        except Exception as e:
            print(f"Error searching Marktplaats via Apify: {e}")
            return []


def parse_marktplaats_results(results: list) -> list[DutchComparable]:
    """
    Parse Marktplaats results from Apify actor.

    Args:
        results: Raw results from Apify actor

    Returns:
        List of comparable vehicles
    """
    comparables = []

    for item in results:
        try:
            # Extract price - Marktplaats uses various formats
            price_raw = item.get("price") or item.get("priceInfo", {}).get("priceCents", 0)
            if isinstance(price_raw, str):
                # Parse price string like "€ 15.000" or "15000"
                price_clean = re.sub(r'[^\d]', '', price_raw)
                price = int(price_clean) if price_clean else 0
            elif isinstance(price_raw, dict):
                price = int(price_raw.get("priceCents", 0)) // 100
            else:
                price = int(price_raw or 0)

            # Skip if no valid price
            if price <= 0 or price > 500000:
                continue

            # Extract mileage
            mileage_raw = item.get("mileage") or item.get("attributes", {}).get("mileage", "0")
            if isinstance(mileage_raw, str):
                mileage_clean = re.sub(r'[^\d]', '', mileage_raw)
                mileage = int(mileage_clean) if mileage_clean else 0
            else:
                mileage = int(mileage_raw or 0)

            # Extract year
            year_raw = item.get("year") or item.get("attributes", {}).get("constructionYear", "0")
            if isinstance(year_raw, str):
                year_match = re.search(r'\d{4}', year_raw)
                year = int(year_match.group()) if year_match else 0
            else:
                year = int(year_raw or 0)

            # Extract title and URL
            title = item.get("title", "") or item.get("name", "")
            listing_url = item.get("url", "") or item.get("link", "")

            # Extract location
            location = item.get("location", "") or item.get("sellerLocation", "")
            if isinstance(location, dict):
                location = location.get("cityName", "") or location.get("city", "")

            comparables.append(DutchComparable(
                price_eur=price,
                mileage_km=mileage,
                year=year,
                title=title,
                listing_url=listing_url,
                source="marktplaats",
                location=location,
            ))

        except (KeyError, TypeError, ValueError) as e:
            print(f"Error parsing Marktplaats item: {e}")
            continue

    return comparables


async def search_autoscout24_nl(vehicle: VehicleData) -> list[DutchComparable]:
    """
    Search AutoScout24 NL for comparable vehicles.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        List of comparable vehicles from AutoScout24 NL
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
            print(f"Error searching AutoScout24 NL: {e}")
            return []


async def search_dutch_market(
    vehicle: VehicleData,
    apify_token: Optional[str] = None
) -> list[DutchComparable]:
    """
    Search the Dutch market for comparable vehicles.
    Combines results from AutoScout24 NL and Marktplaats.

    Args:
        vehicle: The target vehicle to find comparables for
        apify_token: Apify API token for Marktplaats search (optional)

    Returns:
        List of comparable vehicles from multiple sources
    """
    all_comparables = []

    # Search AutoScout24 NL (always)
    autoscout_task = search_autoscout24_nl(vehicle)

    # Search Marktplaats (if token available)
    if apify_token:
        marktplaats_task = search_marktplaats_via_apify(vehicle, apify_token)
        autoscout_results, marktplaats_results = await asyncio.gather(
            autoscout_task,
            marktplaats_task,
            return_exceptions=True
        )

        # Handle AutoScout24 results
        if isinstance(autoscout_results, list):
            all_comparables.extend(autoscout_results)
            print(f"Found {len(autoscout_results)} results from AutoScout24 NL")
        else:
            print(f"AutoScout24 search failed: {autoscout_results}")

        # Handle Marktplaats results
        if isinstance(marktplaats_results, list):
            all_comparables.extend(marktplaats_results)
            print(f"Found {len(marktplaats_results)} results from Marktplaats")
        else:
            print(f"Marktplaats search failed: {marktplaats_results}")
    else:
        # Only AutoScout24 if no Apify token
        autoscout_results = await autoscout_task
        if isinstance(autoscout_results, list):
            all_comparables.extend(autoscout_results)
            print(f"Found {len(autoscout_results)} results from AutoScout24 NL")

    # Sort by price
    all_comparables.sort(key=lambda x: x.price_eur)

    return all_comparables


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
