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


def extract_base_model_name(model: str) -> str:
    """
    Extract just the base model name without engine specs for URL paths.

    E.g., "Golf 2.0 TSI" -> "Golf"
          "3 Series 320d" -> "3 Series"
          "RS Q3" -> "RS Q3"

    Args:
        model: Full model string including engine specs

    Returns:
        Base model name only
    """
    parts = model.split()
    if not parts:
        return model

    # Keep collecting parts until we hit a number (engine size) or fuel type indicator
    engine_indicators = ['tdi', 'tsi', 'tfsi', 'fsi', 'cdi', 'cgi', 'hdi', 'dci',
                        'cdti', 'jtd', 'mjet', 'bluehdi', 'crdi']
    base_parts = []
    for part in parts:
        part_lower = part.lower()
        # Stop if we see engine size like "2.0" or "1.6"
        if '.' in part and any(c.isdigit() for c in part):
            break
        # Stop if we see fuel type indicators
        if part_lower in engine_indicators:
            break
        # Stop if it looks like just a number (displacement without dot)
        if part.isdigit() and len(part) <= 2:
            break
        base_parts.append(part)

    return " ".join(base_parts) if base_parts else parts[0]


def build_autoscout24_search_url(vehicle: VehicleData) -> str:
    """
    Build AutoScout24 NL search URL for comparable vehicles.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        Search URL string
    """
    base_url = "https://www.autoscout24.nl/lst"

    # Normalize make for URL
    make = vehicle.make.lower().replace(" ", "-")

    # Get full model with engine info for search query
    full_model, variant = extract_model_variant(vehicle.model)

    # Extract just base model name for URL path (AutoScout24 doesn't accept engine specs in path)
    base_model_name = extract_base_model_name(vehicle.model)
    model_path = base_model_name.lower().replace(" ", "-")

    # Build path with base model only
    path = f"/{make}/{model_path}"

    # Build query parameters
    params = []

    # Add search query with full model including engine variant for better matching
    # This helps filter results to the specific engine size
    if full_model != base_model_name:
        # Include engine specs in search query
        params.append(f"search={full_model.replace(' ', '+')}")

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
    url = f"{base_url}{path}?{query}"
    print(f"[AUTOSCOUT24 NL] Search URL: {url}")
    return url


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
        print("AutoScout24 NL: No __NEXT_DATA__ found in HTML")
        return comparables

    try:
        data = json.loads(match.group(1))
        listings = data.get("props", {}).get("pageProps", {}).get("listings", [])

        for listing in listings:
            try:
                # Price is in tracking.price or parse from price.priceFormatted
                tracking = listing.get("tracking", {})
                price = 0
                if tracking.get("price"):
                    price = int(tracking["price"])
                else:
                    # Fallback: parse from priceFormatted like "€ 29.750"
                    price_str = listing.get("price", {}).get("priceFormatted", "")
                    if price_str:
                        price_clean = re.sub(r'[^\d]', '', price_str)
                        price = int(price_clean) if price_clean else 0

                # Mileage is in tracking.mileage or vehicle.mileageInKm
                mileage = 0
                if tracking.get("mileage"):
                    mileage = int(tracking["mileage"])
                else:
                    mileage_str = listing.get("vehicle", {}).get("mileageInKm", "0")
                    mileage_clean = re.sub(r'[^\d]', '', str(mileage_str))
                    mileage = int(mileage_clean) if mileage_clean else 0

                # Year is in tracking.firstRegistration like "06-2022"
                year = 0
                first_reg = tracking.get("firstRegistration", "")
                if first_reg:
                    year_match = re.search(r'(\d{4})', first_reg)
                    if year_match:
                        year = int(year_match.group(1))

                # Build title from vehicle info
                vehicle_info = listing.get("vehicle", {})
                make = vehicle_info.get("make", "")
                model = vehicle_info.get("model", "")
                variant = vehicle_info.get("modelVersionInput", "")
                title = f"{make} {model} {variant}".strip()

                # Get listing ID and URL
                listing_id = listing.get("id", "")
                listing_url = listing.get("url", "")
                if listing_url and not listing_url.startswith("http"):
                    listing_url = f"https://www.autoscout24.nl{listing_url}"
                elif listing_id and not listing_url:
                    listing_url = f"https://www.autoscout24.nl/aanbod/{listing_id}"

                # Location
                location = listing.get("location", {}).get("city", "")

                if price > 0:
                    comparables.append(DutchComparable(
                        price_eur=price,
                        mileage_km=mileage,
                        year=year,
                        title=title,
                        listing_url=listing_url,
                        source="autoscout24",
                        location=location,
                    ))
            except (KeyError, TypeError, ValueError) as e:
                print(f"Error parsing AutoScout24 NL listing: {e}")
                continue

    except json.JSONDecodeError as e:
        print(f"AutoScout24 NL: JSON decode error: {e}")

    return comparables


def build_marktplaats_search_url(vehicle: VehicleData) -> str:
    """
    Build Marktplaats search URL for comparable vehicles.

    Uses Marktplaats brand subcategory for more precise results.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        Search URL string for Marktplaats auto's
    """
    # Marktplaats uses brand as subcategory: /l/auto-s/bmw/
    # Normalize make for URL path
    make_url = vehicle.make.lower().replace(" ", "-").replace("ë", "e").replace("ö", "o")

    # Handle special brand names
    brand_mapping = {
        "mercedes-benz": "mercedes-benz",
        "volkswagen": "volkswagen",
        "vw": "volkswagen",
        "alfa romeo": "alfa-romeo",
        "land rover": "land-rover",
    }
    make_url = brand_mapping.get(make_url, make_url)

    base_url = f"https://www.marktplaats.nl/l/auto-s/{make_url}/"

    # Get base model for search query - use full model for better matching
    base_model, variant = extract_model_variant(vehicle.model)

    # Build query parameters
    params = []

    # Search query - include make + model for precision since Marktplaats
    # search can be imprecise with just model name
    search_query = f"{vehicle.make} {base_model}"
    params.append(f"q={search_query.replace(' ', '+')}")

    query = "&".join(params)
    return f"{base_url}?{query}"


async def search_marktplaats_via_apify(
    vehicle: VehicleData,
    apify_token: str,
    max_results: int = 5
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
            # Note: ivanvs~marktplaats-scraper expects "urls" with objects and "maxRecords"
            run_response = await client.post(
                f"https://api.apify.com/v2/acts/{actor_id}/runs",
                params={"token": apify_token},
                json={
                    "maxRecords": max_results,
                    "urls": [{"url": search_url}],
                },
                timeout=30,
            )
            run_response.raise_for_status()
            run_data = run_response.json()
            run_id = run_data["data"]["id"]

            # Wait for completion (max 90 seconds - Marktplaats actor can be slow)
            for _ in range(45):
                await asyncio.sleep(2)

                status_response = await client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": apify_token},
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
                params={"token": apify_token, "format": "json"},
                timeout=30,
            )
            results_response.raise_for_status()
            results = results_response.json()

            # Parse and filter results to match vehicle make/model
            comparables = parse_marktplaats_results(results)

            # Filter by make (case insensitive)
            make_lower = vehicle.make.lower()
            # Get base model for matching
            base_model, _ = extract_model_variant(vehicle.model)
            model_lower = base_model.lower()

            filtered = []
            for comp in comparables:
                title_lower = comp.title.lower()
                # Must contain the make
                if make_lower not in title_lower:
                    continue
                # Should contain model or model number (e.g., "320" from "320i")
                model_num = ''.join(c for c in model_lower if c.isdigit())
                if model_lower in title_lower or (model_num and model_num in title_lower):
                    filtered.append(comp)

            print(f"Marktplaats: {len(comparables)} results, {len(filtered)} after filtering for {vehicle.make} {base_model}")
            return filtered

        except Exception as e:
            print(f"Error searching Marktplaats via Apify: {e}")
            return []


def parse_marktplaats_results(results: list) -> list[DutchComparable]:
    """
    Parse Marktplaats results from ivanvs~marktplaats-scraper Apify actor.

    Args:
        results: Raw results from Apify actor

    Returns:
        List of comparable vehicles
    """
    comparables = []

    for item in results:
        try:
            # Skip non-car ads
            if not item.get("isCarAd", False):
                continue

            # Extract price from price.priceCents (in cents, divide by 100)
            price_obj = item.get("price", {})
            if isinstance(price_obj, dict):
                price_cents = price_obj.get("priceCents", 0)
                price = int(price_cents) // 100 if price_cents else 0
            else:
                # Fallback for other formats
                price_clean = re.sub(r'[^\d]', '', str(price_obj))
                price = int(price_clean) if price_clean else 0

            # Skip if no valid price
            if price <= 0 or price > 500000:
                continue

            # Extract mileage from attributes.mileage (string like "216.000")
            attrs = item.get("attributes", {})
            mileage_raw = attrs.get("mileage", "0")
            if isinstance(mileage_raw, str):
                # Remove dots and other non-digits (e.g., "216.000" -> 216000)
                mileage_clean = re.sub(r'[^\d]', '', mileage_raw)
                mileage = int(mileage_clean) if mileage_clean else 0
            else:
                mileage = int(mileage_raw or 0)

            # Extract year from constructionYear at top level
            year_raw = item.get("constructionYear") or attrs.get("constructionYear", "0")
            if isinstance(year_raw, str):
                year_match = re.search(r'\d{4}', year_raw)
                year = int(year_match.group()) if year_match else 0
            else:
                year = int(year_raw or 0)

            # Extract title and URL
            title = item.get("title", "")
            listing_url = item.get("url", "")

            # Build title from brand/model if not available
            if not title:
                brand = item.get("brand", "")
                model = item.get("model", "")
                title = f"{brand} {model}".strip()

            # Location is not directly available in seller info,
            # but we can try to extract from description or leave empty
            location = ""

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
