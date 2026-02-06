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
from user_agents import get_random_headers, get_random_user_agent


def _get_dutch_headers(referer: str = "") -> dict:
    """Get randomized browser headers with Dutch language preference."""
    headers = get_random_headers()
    headers["Accept-Language"] = "nl-NL,nl;q=0.9,en;q=0.8"
    if referer:
        headers["Referer"] = referer
    return headers


async def _curl_cffi_get(url: str, referer: str = "") -> str:
    """
    Fetch URL using curl_cffi which impersonates Chrome's TLS fingerprint.
    Used for sites that block httpx via TLS fingerprinting (AutoTrack, Gaspedaal).
    Returns response text or raises an exception.
    """
    from curl_cffi.requests import AsyncSession

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer

    async with AsyncSession(impersonate="chrome") as session:
        response = await session.get(url, headers=headers, allow_redirects=True, timeout=30)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code} for {url}")
        return response.text


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
    equipment: list = None  # List of equipment/features
    fuel_type: str = ""  # For better matching
    transmission: str = ""  # For better matching

    def __post_init__(self):
        if self.equipment is None:
            self.equipment = []


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
    Extract just the base model name without engine specs or body styles for URL paths.

    E.g., "Golf 2.0 TSI" -> "Golf"
          "A3 Sportback" -> "A3"
          "3 Series 320d" -> "3 Series"
          "RS Q3" -> "RS Q3"

    Args:
        model: Full model string including engine specs and variants

    Returns:
        Base model name only
    """
    parts = model.split()
    if not parts:
        return model

    # Keep collecting parts until we hit engine specs, fuel type, or body style indicators
    engine_indicators = ['tdi', 'tsi', 'tfsi', 'fsi', 'cdi', 'cgi', 'hdi', 'dci',
                        'cdti', 'jtd', 'mjet', 'bluehdi', 'crdi']

    # Body style variants that should be excluded from base model name
    body_styles = ['sportback', 'sedan', 'saloon', 'wagon', 'estate', 'touring',
                   'avant', 'kombi', 'coupe', 'cabrio', 'cabriolet', 'convertible',
                   'roadster', 'limousine', 'hatchback', 'suv', 'van']

    base_parts = []
    for part in parts:
        part_lower = part.lower()
        # Stop if we see engine size like "2.0" or "1.6"
        if '.' in part and any(c.isdigit() for c in part):
            break
        # Stop if we see fuel type indicators
        if part_lower in engine_indicators:
            break
        # Stop if we see body style variants
        if part_lower in body_styles:
            break
        # Stop if it looks like just a number (displacement without dot)
        if part.isdigit() and len(part) <= 2:
            break
        base_parts.append(part)

    return " ".join(base_parts) if base_parts else parts[0]


def build_autoscout24_search_url(
    vehicle: VehicleData,
    year_delta: int = 1,
    km_percent: float = 0.2,
    include_fuel: bool = True,
    include_transmission: bool = True
) -> str:
    """
    Build AutoScout24 NL search URL for comparable vehicles.

    Args:
        vehicle: The target vehicle to find comparables for
        year_delta: Year range (±N years)
        km_percent: Mileage range as percentage (0.2 = ±20%)
        include_fuel: Whether to filter by fuel type
        include_transmission: Whether to filter by transmission

    Returns:
        Search URL string
    """
    base_url = "https://www.autoscout24.nl/lst"

    # Normalize make for URL
    make = vehicle.make.lower().replace(" ", "-")

    # Extract just base model name for URL path (AutoScout24 doesn't accept engine specs in path)
    base_model_name = extract_base_model_name(vehicle.model)
    model_path = base_model_name.lower().replace(" ", "-")

    # Build path with base model only
    path = f"/{make}/{model_path}"

    # Build query parameters
    params = []

    # Year range
    params.append(f"fregfrom={vehicle.year - year_delta}")
    params.append(f"fregto={vehicle.year + year_delta}")

    # Mileage range
    min_km = int(vehicle.mileage_km * (1 - km_percent))
    max_km = int(vehicle.mileage_km * (1 + km_percent))
    params.append(f"kmfrom={min_km}")
    params.append(f"kmto={max_km}")

    # Fuel type mapping (optional)
    if include_fuel:
        fuel_map = {
            "petrol": "B",
            "diesel": "D",
            "electric": "E",
            "hybrid": "2",
            "lpg": "L",
        }
        if vehicle.fuel_type in fuel_map:
            params.append(f"fuel={fuel_map[vehicle.fuel_type]}")

    # Transmission mapping (optional)
    if include_transmission:
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

    # Get base model for search query (without body styles)
    base_model = extract_base_model_name(vehicle.model)

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
            # Get base model for matching (without body styles like "Sedan", "Wagon", etc.)
            base_model = extract_base_model_name(vehicle.model)
            model_lower = base_model.lower()

            filtered = []
            for comp in comparables:
                title_lower = comp.title.lower()
                # Must contain the make
                if make_lower not in title_lower:
                    continue

                # More lenient model matching to avoid filtering out valid matches
                # For BMW 330, accept: 330, 330i, 330d, 330e, 330xi, 330xd, etc.
                # Strategy: Match base model number, allow engine/drivetrain suffixes

                matched = False

                # Extract just the numeric part of the model (e.g., "330" from "330 Sedan")
                model_numeric = re.search(r'\d+', model_lower)

                if model_numeric:
                    base_number = model_numeric.group()

                    # Check if base number appears in title with word boundary
                    # This matches "330", "330i", "330d", "330xi" but not "3300" or "1330"
                    pattern = r'\b' + re.escape(base_number) + r'[a-z]{0,3}\b'
                    if re.search(pattern, title_lower):
                        matched = True
                    elif len(base_number) == 3:
                        # Fallback: match series designation (e.g., "440" -> "4 serie")
                        # BMW uses 3-digit numbers where first digit = series: 320->3, 440->4, 520->5
                        series_digit = base_number[0]
                        series_pattern = r'\b' + re.escape(series_digit) + r'[\s-]?(?:serie[s]?|reeks)\b'
                        if re.search(series_pattern, title_lower):
                            matched = True
                else:
                    # No numeric model (e.g., "A3" or "Golf"), use exact/prefix matching
                    model_tokens = model_lower.split()
                    if model_tokens:
                        first_token = model_tokens[0]
                        pattern = r'\b' + re.escape(first_token) + r'\b'
                        if re.search(pattern, title_lower):
                            matched = True

                if matched:
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


def _model_to_series(make: str, model: str) -> str:
    """
    Convert specific model variants to series names for platforms like AutoTrack/Gaspedaal.

    BMW 440 -> 4-serie, BMW 320 -> 3-serie, Mercedes C200 -> C-klasse, etc.
    Returns the original model if no series mapping applies.
    """
    make_lower = make.lower()
    model_lower = model.lower().strip()

    if make_lower == "bmw":
        # BMW 3-digit numeric models: 118->1-serie, 320->3-serie, 440->4-serie, etc.
        m = re.match(r'^(\d)\d{2}', model_lower)
        if m:
            return f"{m.group(1)}-serie"

    if make_lower in ("mercedes-benz", "mercedes"):
        # Mercedes letter+number models: C200->C-klasse, E220->E-klasse, etc.
        m = re.match(r'^([a-z])\s?\d', model_lower)
        if m:
            return f"{m.group(1).upper()}-klasse"

    return model


# =============================================================================
# AUTOTRACK.NL SCRAPER
# =============================================================================

def build_autotrack_search_url(vehicle: VehicleData) -> str:
    """
    Build AutoTrack.nl search URL for comparable vehicles.

    AutoTrack is owned by AutoScout24 (as of Dec 2025) and likely uses
    similar URL structure and parameters.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        Search URL string
    """
    base_url = "https://www.autotrack.nl/aanbod"

    # Normalize make for URL
    make = vehicle.make.lower().replace(" ", "-")

    # Extract base model and convert to series name for URL path
    base_model_name = extract_base_model_name(vehicle.model)
    series_name = _model_to_series(vehicle.make, base_model_name)
    model_path = series_name.lower().replace(" ", "-")

    # Build path: /aanbod/merk/{make}/model/{model}
    path = f"/merk/{make}/model/{model_path}"

    # AutoTrack doesn't support URL query parameters for filtering
    # We'll fetch all results and filter client-side in the parser
    url = f"{base_url}{path}"
    print(f"[AUTOTRACK] Search URL: {url}")
    print(f"[AUTOTRACK] Will filter client-side: year={vehicle.year}±1, km={vehicle.mileage_km}±20%, fuel={vehicle.fuel_type}, trans={vehicle.transmission}")
    return url


def parse_autotrack_search_results(html: str) -> list[DutchComparable]:
    """
    Parse AutoTrack search results from HTML.

    AutoTrack uses JSON-LD structured data with id="srp-item-list-schema"
    containing an ItemList of Car/Product items with schema.org format.

    Args:
        html: Raw HTML from search page

    Returns:
        List of comparable vehicles
    """
    comparables = []

    # Extract JSON-LD with id="srp-item-list-schema"
    match = re.search(
        r'<script type="application/ld\+json" id="srp-item-list-schema"[^>]*>(.*?)</script>',
        html,
        re.DOTALL
    )

    if not match:
        print("[AUTOTRACK] No JSON-LD srp-item-list-schema found in HTML")
        return comparables

    try:
        data = json.loads(match.group(1))
        items = data.get("itemListElement", [])

        for list_item in items:
            try:
                # Each list item has an 'item' key with the actual car data
                item = list_item.get("item", {})

                # Brand and Model
                brand = item.get("brand", "")
                model = item.get("model", "")

                # Title (includes all details)
                title = item.get("name", f"{brand} {model}").replace(" | AutoTrack", "").strip()

                # Year from vehicleModelDate or productionDate
                year = 0
                year_str = item.get("vehicleModelDate") or item.get("productionDate", "")
                if year_str:
                    year_match = re.search(r'(\d{4})', str(year_str))
                    if year_match:
                        year = int(year_match.group(1))

                # Mileage from mileageFromOdometer
                mileage = 0
                mileage_obj = item.get("mileageFromOdometer", {})
                if isinstance(mileage_obj, dict):
                    mileage = int(mileage_obj.get("value", 0))

                # Price from offers.price
                price = 0
                offers = item.get("offers", {})
                if isinstance(offers, dict):
                    price_str = offers.get("price", "0")
                    price = int(price_str) if price_str else 0

                # URL
                listing_url = item.get("url", "")
                if listing_url and not listing_url.startswith("http"):
                    listing_url = f"https://www.autotrack.nl{listing_url}"

                # Location from offers.seller.address
                location = ""
                seller = offers.get("seller", {})
                if isinstance(seller, dict):
                    address = seller.get("address", {})
                    if isinstance(address, dict):
                        location = address.get("addressLocality", "")

                # Validate and add
                if 0 < price < 500000:
                    comparables.append(DutchComparable(
                        price_eur=price,
                        mileage_km=mileage,
                        year=year,
                        title=title,
                        listing_url=listing_url,
                        source="autotrack",
                        location=location,
                    ))
            except (KeyError, TypeError, ValueError) as e:
                print(f"[AUTOTRACK] Error parsing listing: {e}")
                continue

        print(f"[AUTOTRACK] Found {len(comparables)} comparables from JSON-LD")

    except json.JSONDecodeError as e:
        print(f"[AUTOTRACK] JSON decode error: {e}")

    return comparables


async def search_autotrack_nl(vehicle: VehicleData) -> list[DutchComparable]:
    """
    Search AutoTrack.nl for comparable vehicles.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        List of comparable vehicles from AutoTrack
    """
    search_url = build_autotrack_search_url(vehicle)

    try:
        html = await _curl_cffi_get(search_url, referer="https://www.autotrack.nl/")

        # Parse all results
        all_results = parse_autotrack_search_results(html)

        # Filter client-side (AutoTrack doesn't support URL filters)
        filtered = []
        min_km = int(vehicle.mileage_km * 0.8)
        max_km = int(vehicle.mileage_km * 1.2)

        for comp in all_results:
            # Year filter: ±1 year
            if comp.year and abs(comp.year - vehicle.year) > 1:
                continue

            # Mileage filter: ±20%
            if comp.mileage_km and (comp.mileage_km < min_km or comp.mileage_km > max_km):
                continue

            filtered.append(comp)

        print(f"[AUTOTRACK] Filtered to {len(filtered)} results (from {len(all_results)} total) matching year={vehicle.year}±1, km={vehicle.mileage_km}±20%")
        return filtered

    except Exception as e:
        print(f"[AUTOTRACK] Error searching: {e}")
        return []


# =============================================================================
# GASPEDAAL.NL SCRAPER
# =============================================================================

def build_gaspedaal_search_url(vehicle: VehicleData) -> str:
    """
    Build Gaspedaal.nl search URL for comparable vehicles.

    Gaspedaal is a meta-search aggregator (owned by AutoScout24 as of Dec 2025)
    that combines results from multiple Dutch car platforms.

    Uses format: /make/model (e.g., /audi/a3)
    Filtering done client-side since URL parameters don't work.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        Search URL string
    """
    # Normalize make and convert model to series name for URL
    make = vehicle.make.lower().replace(" ", "-")
    base_model = extract_base_model_name(vehicle.model)
    series_name = _model_to_series(vehicle.make, base_model)
    model = series_name.lower().replace(" ", "-")

    # Build URL: /make/model
    url = f"https://www.gaspedaal.nl/{make}/{model}"
    print(f"[GASPEDAAL] Search URL: {url}")
    return url


def parse_gaspedaal_search_results(html: str) -> list[DutchComparable]:
    """
    Parse Gaspedaal search results from HTML.

    Gaspedaal uses JSON-LD structured data with ItemList containing Car/Product items.

    Args:
        html: Raw HTML from search page

    Returns:
        List of comparable vehicles
    """
    comparables = []

    # Try JSON-LD ItemList structure (similar to AutoTrack)
    json_ld_matches = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)

    for json_ld_str in json_ld_matches:
        try:
            data = json.loads(json_ld_str)

            # Check if this is an ItemList
            if data.get("@type") == "ItemList":
                items = data.get("itemListElement", [])
                print(f"[GASPEDAAL] Found ItemList with {len(items)} items")

                for list_item in items:
                    try:
                        # Get the actual item (Car/Product)
                        item = list_item.get("item", {})
                        item_type = item.get("@type", [])

                        # Check if it's a Car or Product
                        if not isinstance(item_type, list):
                            item_type = [item_type]

                        if "Car" not in item_type and "Product" not in item_type:
                            continue

                        # Extract brand and model
                        brand = item.get("brand", "")
                        if isinstance(brand, dict):
                            brand = brand.get("name", "")
                        model = item.get("model", "")
                        name = item.get("name", "")

                        # Build title
                        if name:
                            title = name
                        else:
                            title = f"{brand} {model}".strip()

                        # Extract mileage
                        mileage = 0
                        mileage_obj = item.get("mileageFromOdometer", {})
                        if isinstance(mileage_obj, dict):
                            mileage_value = mileage_obj.get("value", 0)
                            try:
                                mileage = int(float(str(mileage_value)))
                            except (ValueError, TypeError):
                                mileage = 0

                        # Extract year from productionDate
                        year = 0
                        prod_date = item.get("productionDate", "")
                        if prod_date:
                            year_match = re.search(r'(\d{4})', str(prod_date))
                            if year_match:
                                year = int(year_match.group(1))

                        # Extract price
                        price = 0
                        offers = item.get("offers", {})
                        if isinstance(offers, dict):
                            price_value = offers.get("price", "0")
                            try:
                                # Handle both string and numeric prices
                                price = int(float(str(price_value)))
                            except (ValueError, TypeError):
                                price = 0

                        # Extract URL
                        listing_url = item.get("url", "")
                        if listing_url and not listing_url.startswith("http"):
                            listing_url = f"https://www.gaspedaal.nl{listing_url}"

                        # Only add valid results
                        if title and 0 < price < 500000:
                            comparables.append(DutchComparable(
                                price_eur=price,
                                mileage_km=mileage,
                                year=year,
                                title=title,
                                listing_url=listing_url,
                                source="gaspedaal",
                                location="",
                            ))

                    except (KeyError, TypeError, ValueError) as e:
                        print(f"[GASPEDAAL] Error parsing item: {e}")
                        continue

                # If we found items, return them
                if comparables:
                    print(f"[GASPEDAAL] Parsed {len(comparables)} comparables from ItemList")
                    return comparables

        except json.JSONDecodeError as e:
            print(f"[GASPEDAAL] JSON decode error: {e}")
            continue

    print(f"[GASPEDAAL] Found {len(comparables)} comparables")
    return comparables


async def search_gaspedaal_nl(vehicle: VehicleData) -> list[DutchComparable]:
    """
    Search Gaspedaal.nl for comparable vehicles.

    Gaspedaal is a meta-aggregator that combines results from multiple sources,
    so results may include duplicates from AutoScout24/Marktplaats.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        List of comparable vehicles from Gaspedaal
    """
    search_url = build_gaspedaal_search_url(vehicle)

    try:
        html = await _curl_cffi_get(search_url, referer="https://www.gaspedaal.nl/")

        # Parse all results
        all_results = parse_gaspedaal_search_results(html)

        # Apply client-side filtering for better relevance
        filtered = []
        min_km = int(vehicle.mileage_km * 0.8)
        max_km = int(vehicle.mileage_km * 1.2)

        # Extract base model for matching (without body styles)
        base_model = extract_base_model_name(vehicle.model)
        make_lower = vehicle.make.lower()
        model_lower = base_model.lower()

        for comp in all_results:
            # Brand/model filter
            title_lower = comp.title.lower()
            if make_lower not in title_lower:
                continue

            # Check if model matches
            model_matched = False
            model_numeric = re.search(r'\d+', model_lower)
            if model_numeric:
                base_number = model_numeric.group()
                pattern = r'\b' + re.escape(base_number) + r'[a-z]{0,3}\b'
                if re.search(pattern, title_lower):
                    model_matched = True
                elif len(base_number) == 3:
                    # Fallback: match series designation (e.g., "440" -> "4 serie")
                    series_digit = base_number[0]
                    series_pattern = r'\b' + re.escape(series_digit) + r'[\s-]?(?:serie[s]?|reeks)\b'
                    if re.search(series_pattern, title_lower):
                        model_matched = True
            else:
                model_tokens = model_lower.split()
                if model_tokens:
                    first_token = model_tokens[0]
                    pattern = r'\b' + re.escape(first_token) + r'\b'
                    if re.search(pattern, title_lower):
                        model_matched = True
            if not model_matched:
                continue

            # Year filter: ±1 year
            if comp.year and abs(comp.year - vehicle.year) > 1:
                continue

            # Mileage filter: ±20%
            if comp.mileage_km and (comp.mileage_km < min_km or comp.mileage_km > max_km):
                continue

            filtered.append(comp)

        print(f"[GASPEDAAL] Filtered to {len(filtered)} results (from {len(all_results)} total) matching {vehicle.make} {base_model}, year={vehicle.year}±1, km={vehicle.mileage_km}±20%")
        return filtered

    except Exception as e:
        print(f"[GASPEDAAL] Error searching: {e}")
        return []


# =============================================================================
# OCCASIONS.NL SCRAPER
# =============================================================================

def build_occasions_search_url(vehicle: VehicleData) -> str:
    """
    Build Occasions.nl search URL for comparable vehicles.

    Occasions.nl is a WordPress-based car marketplace.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        Search URL string
    """
    # WordPress search uses /?s=query format
    base_url = "https://www.occasions.nl"

    # Get base model name for search (without body styles like "Sedan")
    base_model = extract_base_model_name(vehicle.model)

    # Build search query: "Make Model Year" for better WordPress search results
    # WordPress doesn't support advanced filters via URL, so we use general search
    search_query = f"{vehicle.make} {base_model} {vehicle.year}"

    # WordPress search parameter
    params = [f"s={search_query.replace(' ', '+')}"]

    # Note: WordPress doesn't support advanced filters via URL params
    # We'll filter results client-side in the parser

    query = "&".join(params)
    url = f"{base_url}?{query}"
    print(f"[OCCASIONS] Search URL: {url}")
    print(f"[OCCASIONS] Will filter client-side: year={vehicle.year}±1, km={vehicle.mileage_km}±20%, fuel={vehicle.fuel_type}")
    return url


def parse_occasions_search_results(html: str) -> list[DutchComparable]:
    """
    Parse Occasions.nl search results from HTML.

    WordPress sites can have varying HTML structures depending on theme/plugins.
    Try multiple parsing strategies.

    Args:
        html: Raw HTML from search page

    Returns:
        List of comparable vehicles
    """
    comparables = []

    # Strategy 1: JSON-LD structured data (most reliable for WordPress)
    json_ld_matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)

    for json_ld_str in json_ld_matches:
        try:
            json_ld = json.loads(json_ld_str)

            # Handle array or single item
            items = json_ld if isinstance(json_ld, list) else [json_ld]

            for item in items:
                if item.get("@type") in ["Car", "Vehicle", "Product"]:
                    try:
                        # Extract price
                        price = 0
                        offers = item.get("offers", {})
                        if isinstance(offers, dict):
                            price_str = str(offers.get("price", "0"))
                            price = int(float(price_str)) if price_str else 0

                        # Extract mileage
                        mileage = 0
                        mileage_value = item.get("mileageFromOdometer", {})
                        if isinstance(mileage_value, dict):
                            mileage_str = str(mileage_value.get("value", "0"))
                        else:
                            mileage_str = str(mileage_value)
                        mileage = int(float(mileage_str)) if mileage_str and mileage_str != "0" else 0

                        # Extract year
                        year = 0
                        prod_date = item.get("productionDate", "")
                        if prod_date:
                            year_match = re.search(r'(\d{4})', str(prod_date))
                            if year_match:
                                year = int(year_match.group(1))

                        # Extract title and URL
                        title = item.get("name", "")
                        listing_url = item.get("url", "")
                        if listing_url and not listing_url.startswith("http"):
                            listing_url = f"https://www.occasions.nl{listing_url}"

                        if 0 < price < 500000 and title:
                            comparables.append(DutchComparable(
                                price_eur=price,
                                mileage_km=mileage,
                                year=year,
                                title=title,
                                listing_url=listing_url,
                                source="occasions",
                                location="",
                            ))
                    except (KeyError, TypeError, ValueError) as e:
                        print(f"[OCCASIONS] Error parsing JSON-LD item: {e}")
                        continue
        except json.JSONDecodeError:
            continue

    if comparables:
        print(f"[OCCASIONS] Found {len(comparables)} comparables via JSON-LD")
        return comparables

    # Strategy 2: HTML parsing with regex (common WordPress patterns)
    # Look for common WordPress car plugin article/div patterns
    patterns = [
        r'<article[^>]*class="[^"]*occasion[^"]*"[^>]*>(.*?)</article>',
        r'<div[^>]*class="[^"]*vehicle-card[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*car-listing[^"]*"[^>]*>(.*?)</div>',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        if matches:
            for match in matches:
                try:
                    # Extract price: €45.000, €45000, etc.
                    price_match = re.search(r'€\s*(\d{1,3}(?:[.,]\d{3})*)', match)
                    price = 0
                    if price_match:
                        price_str = price_match.group(1).replace('.', '').replace(',', '')
                        price = int(price_str)

                    # Extract mileage: 50.000 km, 50000 km, etc.
                    mileage_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*)\s*km', match, re.IGNORECASE)
                    mileage = 0
                    if mileage_match:
                        mileage_str = mileage_match.group(1).replace('.', '').replace(',', '')
                        mileage = int(mileage_str)

                    # Extract year: 2021, 2022, etc.
                    year_match = re.search(r'\b(20\d{2})\b', match)
                    year = int(year_match.group(1)) if year_match else 0

                    # Extract title (from h2, h3, or strong tags)
                    title_match = re.search(r'<(?:h2|h3|strong)[^>]*>(.*?)</(?:h2|h3|strong)>', match, re.DOTALL)
                    title = ""
                    if title_match:
                        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

                    # Extract URL
                    url_match = re.search(r'href="([^"]*)"', match)
                    listing_url = ""
                    if url_match:
                        listing_url = url_match.group(1)
                        if listing_url and not listing_url.startswith("http"):
                            listing_url = f"https://www.occasions.nl{listing_url}"

                    if 0 < price < 500000 and title and listing_url:
                        comparables.append(DutchComparable(
                            price_eur=price,
                            mileage_km=mileage,
                            year=year,
                            title=title,
                            listing_url=listing_url,
                            source="occasions",
                            location="",
                        ))
                except (ValueError, AttributeError) as e:
                    print(f"[OCCASIONS] Error parsing HTML listing: {e}")
                    continue

            if comparables:
                break  # Found results with this pattern

    print(f"[OCCASIONS] Found {len(comparables)} comparables")
    return comparables


async def search_occasions_nl(vehicle: VehicleData) -> list[DutchComparable]:
    """
    Search Occasions.nl for comparable vehicles.

    WordPress-based platform with variable HTML structure.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        List of comparable vehicles from Occasions.nl
    """
    search_url = build_occasions_search_url(vehicle)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                search_url,
                headers=_get_dutch_headers(referer="https://www.occasions.nl/"),
                follow_redirects=True,
                timeout=30,
            )
            response.raise_for_status()

            return parse_occasions_search_results(response.text)

        except Exception as e:
            print(f"[OCCASIONS] Error searching: {e}")
            return []


async def search_autoscout24_nl(vehicle: VehicleData) -> list[DutchComparable]:
    """
    Search AutoScout24 NL for comparable vehicles with progressive parameter widening.

    Strategy: Start strict, progressively widen parameters until results found.

    Args:
        vehicle: The target vehicle to find comparables for

    Returns:
        List of comparable vehicles from AutoScout24 NL
    """
    async with httpx.AsyncClient() as client:
        # Try progressively wider search parameters
        search_attempts = [
            # Attempt 1: Strict (±1 year, ±20% km, fuel + transmission)
            {"year_delta": 1, "km_percent": 0.2, "include_fuel": True, "include_transmission": True},
            # Attempt 2: Remove transmission filter
            {"year_delta": 1, "km_percent": 0.2, "include_fuel": True, "include_transmission": False},
            # Attempt 3: Widen mileage ±30%
            {"year_delta": 1, "km_percent": 0.3, "include_fuel": True, "include_transmission": False},
            # Attempt 4: Widen year ±2
            {"year_delta": 2, "km_percent": 0.3, "include_fuel": True, "include_transmission": False},
            # Attempt 5: Remove fuel filter
            {"year_delta": 2, "km_percent": 0.3, "include_fuel": False, "include_transmission": False},
            # Attempt 6: Widen mileage ±50%
            {"year_delta": 2, "km_percent": 0.5, "include_fuel": False, "include_transmission": False},
        ]

        for i, params in enumerate(search_attempts, 1):
            search_url = build_autoscout24_search_url(
                vehicle,
                year_delta=params["year_delta"],
                km_percent=params["km_percent"],
                include_fuel=params["include_fuel"],
                include_transmission=params["include_transmission"]
            )

            print(f"[AUTOSCOUT24 NL] Attempt {i}/{len(search_attempts)}: year±{params['year_delta']}, km±{int(params['km_percent']*100)}%, fuel={params['include_fuel']}, trans={params['include_transmission']}")

            try:
                response = await client.get(
                    search_url,
                    headers=_get_dutch_headers(referer="https://www.autoscout24.nl/"),
                    follow_redirects=True,
                    timeout=30,
                )
                response.raise_for_status()

                results = parse_autoscout24_search_results(response.text)

                if results:
                    print(f"[AUTOSCOUT24 NL] SUCCESS: Found {len(results)} results on attempt {i}")
                    return results
                else:
                    print(f"[AUTOSCOUT24 NL] Attempt {i} returned 0 results, trying wider parameters...")

            except Exception as e:
                print(f"[AUTOSCOUT24 NL] Error on attempt {i}: {e}")
                continue

        print(f"[AUTOSCOUT24 NL] All {len(search_attempts)} attempts failed, returning empty list")
        return []


async def search_dutch_market(
    vehicle: VehicleData,
    apify_token: Optional[str] = None
) -> list[DutchComparable]:
    """
    Search the Dutch market for comparable vehicles.
    Combines results from 5 platforms: AutoScout24 NL, AutoTrack, Gaspedaal,
    Occasions.nl, and Marktplaats.

    Args:
        vehicle: The target vehicle to find comparables for
        apify_token: Apify API token for Marktplaats search (optional)

    Returns:
        List of comparable vehicles from multiple sources, deduplicated and sorted by price
    """
    all_comparables = []

    # Create all search tasks
    tasks = [
        search_autoscout24_nl(vehicle),       # Direct HTTP
        search_autotrack_nl(vehicle),         # Direct HTTP (AutoScout24 owned)
        search_gaspedaal_nl(vehicle),         # Direct HTTP (meta-aggregator)
        search_occasions_nl(vehicle),         # Direct HTTP (WordPress)
    ]

    source_names = ["AutoScout24 NL", "AutoTrack", "Gaspedaal", "Occasions"]

    # Add Marktplaats if token available
    if apify_token:
        tasks.append(search_marktplaats_via_apify(vehicle, apify_token))
        source_names.append("Marktplaats")

    # Run all searches in parallel with error handling
    print(f"[DUTCH MARKET] Searching {len(tasks)} platforms in parallel...")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results from each platform
    for i, result in enumerate(results):
        if isinstance(result, list):
            all_comparables.extend(result)
            print(f"[DUTCH MARKET] Found {len(result)} results from {source_names[i]}")
        else:
            print(f"[DUTCH MARKET] {source_names[i]} search failed: {result}")

    print(f"[DUTCH MARKET] Total results before deduplication: {len(all_comparables)}")

    # Deduplicate by URL (critical for Gaspedaal which aggregates from other sources)
    seen_urls = set()
    unique_comparables = []
    for comp in all_comparables:
        # Normalize URL for comparison (remove query params and trailing slash)
        url_normalized = comp.listing_url.lower().split('?')[0].rstrip('/')

        if url_normalized not in seen_urls and url_normalized:
            seen_urls.add(url_normalized)
            unique_comparables.append(comp)

    dedup_count = len(all_comparables) - len(unique_comparables)
    if dedup_count > 0:
        print(f"[DUTCH MARKET] Removed {dedup_count} duplicate listings")

    # Sort by price
    unique_comparables.sort(key=lambda x: x.price_eur)

    print(f"[DUTCH MARKET] Final unique results: {len(unique_comparables)}")

    return unique_comparables


async def search_dutch_market_progressive(
    vehicle: VehicleData,
    apify_token: Optional[str] = None,
    min_comparables: int = 5,
    max_year_delta: int = 5,
) -> list[DutchComparable]:
    """
    Progressively search Dutch market with expanding year ranges.

    Starts with ±1 year, then ±2, ±3, etc. until enough comparables found.
    This ensures we get enough data points for accurate valuation while
    prioritizing closer years.

    Args:
        vehicle: Target vehicle to find comparables for
        apify_token: Apify API token for Marktplaats
        min_comparables: Minimum number of comparables desired
        max_year_delta: Maximum year difference to search

    Returns:
        List of comparable vehicles from multiple year ranges
    """
    all_comparables = []
    year_delta = 1

    print(f"[PROGRESSIVE SEARCH] Target: {vehicle.make} {vehicle.model} ({vehicle.year})")
    print(f"[PROGRESSIVE SEARCH] Goal: Find at least {min_comparables} comparables")

    while year_delta <= max_year_delta:
        print(f"\n[PROGRESSIVE SEARCH] Searching year range: {vehicle.year}±{year_delta} ({vehicle.year - year_delta} - {vehicle.year + year_delta})")

        # Create modified vehicle with expanded year range for URL building
        search_vehicle = VehicleData(
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,  # Keep original year for targeting
            mileage_km=vehicle.mileage_km,
            price_eur=vehicle.price_eur,
            fuel_type=vehicle.fuel_type,
            transmission=vehicle.transmission,
            co2_gkm=vehicle.co2_gkm,
            first_registration_date=vehicle.first_registration_date,
            listing_url=vehicle.listing_url,
            source=vehicle.source,
            title=vehicle.title,
            features=vehicle.features,
            attributes=vehicle.attributes,
        )

        # Search all platforms
        round_comparables = await search_dutch_market(search_vehicle, apify_token)

        # Filter to this year range (client-side filtering)
        min_year = vehicle.year - year_delta
        max_year = vehicle.year + year_delta

        filtered_comparables = [
            comp for comp in round_comparables
            if comp.year and min_year <= comp.year <= max_year
        ]

        print(f"[PROGRESSIVE SEARCH] Found {len(filtered_comparables)} in year range ±{year_delta}")

        # Add new comparables (avoid duplicates)
        existing_urls = {c.listing_url for c in all_comparables}
        new_comparables = [
            comp for comp in filtered_comparables
            if comp.listing_url not in existing_urls
        ]

        all_comparables.extend(new_comparables)
        print(f"[PROGRESSIVE SEARCH] Total unique comparables: {len(all_comparables)}")

        # Check if we have enough
        if len(all_comparables) >= min_comparables:
            print(f"[PROGRESSIVE SEARCH] ✓ Target reached! Found {len(all_comparables)} comparables")
            break

        # Expand search range
        year_delta += 1

    if len(all_comparables) < min_comparables:
        print(f"[PROGRESSIVE SEARCH] ⚠ Only found {len(all_comparables)}/{min_comparables} comparables after searching ±{max_year_delta} years")

    # Sort by year proximity, then price
    all_comparables.sort(key=lambda x: (abs(x.year - vehicle.year), x.price_eur))

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
        "equipment": comp.equipment if hasattr(comp, 'equipment') else [],
        "fuelType": comp.fuel_type if hasattr(comp, 'fuel_type') else "",
        "transmission": comp.transmission if hasattr(comp, 'transmission') else "",
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
