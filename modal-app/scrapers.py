"""
Vehicle scrapers for German car listing sites.
Uses Apify actors for mobile.de and AutoScout24.
"""

import httpx
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any
import asyncio

from constants import APIFY_ACTORS
from utils import normalize_fuel_type, normalize_transmission


@dataclass
class VehicleData:
    """Parsed vehicle data from a listing."""
    make: str
    model: str
    year: int
    mileage_km: int
    price_eur: int
    fuel_type: str
    transmission: str
    co2_gkm: int
    first_registration_date: datetime
    listing_url: str = ""
    source: str = ""
    title: str = ""
    features: list = None
    attributes: dict = None
    original_url: str = ""  # Original URL before normalization

    def __post_init__(self):
        if self.features is None:
            self.features = []
        if self.attributes is None:
            self.attributes = {}


@dataclass
class ScrapeResult:
    """Result of a scrape operation."""
    success: bool
    data: Optional[VehicleData] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[str] = None


def detect_source(url: str) -> str:
    """Detect the source website from URL."""
    url_lower = url.lower()
    if "mobile.de" in url_lower or "suchen.mobile.de" in url_lower:
        return "mobile.de"
    # AutoScout24 - support both German (.de) and Dutch (.nl) versions
    if any(domain in url_lower for domain in [
        "autoscout24.de",
        "autoscout24.nl",
        "autoscout24.com/de",  # International site, German section
        "autoscout24.com/nl",  # International site, Dutch section
        "www.autoscout24.de",
        "www.autoscout24.nl",
    ]):
        return "autoscout24"
    return "unknown"


def extract_listing_id(url: str, source: str) -> Optional[str]:
    """Extract listing ID from URL."""
    # Remove query parameters first
    clean_url = url.split("?")[0].rstrip("/")

    if source == "mobile.de":
        # https://suchen.mobile.de/fahrzeuge/details.html?id=446136631
        if "id=" in url:
            return url.split("id=")[1].split("&")[0]
    elif source == "autoscout24":
        # https://www.autoscout24.de/angebote/citroen-berlingo-...-479363a0-1413-4b65-8903-e38f1ec02db8
        parts = clean_url.split("/")
        if parts:
            return parts[-1]
    return None


def clean_autoscout24_url(url: str) -> str:
    """Clean AutoScout24 URL by removing tracking parameters."""
    # Remove query parameters - they're just tracking info
    return url.split("?")[0]


def normalize_mobile_de_url(url: str) -> str:
    """
    Normalize mobile.de URL to the standard German format.

    Converts various URL formats to the standard German version that Apify expects:
    - https://www.mobile.de/nl/voertuigen/details.html?id=123 -> https://suchen.mobile.de/fahrzeuge/details.html?id=123
    - https://www.mobile.de/fr/vehicules/details.html?id=123 -> https://suchen.mobile.de/fahrzeuge/details.html?id=123
    - https://www.mobile.de/en/vehicles/details.html?id=123 -> https://suchen.mobile.de/fahrzeuge/details.html?id=123
    """
    import re

    # Extract the listing ID from the URL
    listing_id = None
    if "id=" in url:
        listing_id = url.split("id=")[1].split("&")[0]

    if not listing_id:
        # If we can't extract the ID, return original URL
        return url

    # Check if this is a localized URL (contains language code like /nl/, /fr/, /en/, etc.)
    # Pattern matches: mobile.de/xx/ where xx is a 2-letter language code
    localized_pattern = r'mobile\.de/([a-z]{2})/'
    if re.search(localized_pattern, url):
        # Convert to standard German URL format
        normalized_url = f"https://suchen.mobile.de/fahrzeuge/details.html?id={listing_id}"
        print(f"[MOBILE.DE] Normalized URL from localized version: {url} -> {normalized_url}")
        return normalized_url

    # Already in correct format or standard format
    return url


async def run_apify_actor(
    actor_id: str,
    input_data: dict,
    token: str,
    timeout: int = 120
) -> dict:
    """
    Run an Apify actor and wait for results.

    Args:
        actor_id: Apify actor ID
        input_data: Input for the actor
        token: Apify API token
        timeout: Timeout in seconds

    Returns:
        Actor run results
    """
    print(f"[APIFY] Starting actor: {actor_id}")
    print(f"[APIFY] Input data: {input_data}")

    async with httpx.AsyncClient() as client:
        # Start the actor run
        start_url = f"https://api.apify.com/v2/acts/{actor_id}/runs"

        response = await client.post(
            start_url,
            params={"token": token},
            json=input_data,
            timeout=30,
        )
        print(f"[APIFY] Start response status: {response.status_code}")
        if response.status_code != 200 and response.status_code != 201:
            print(f"[APIFY] Start response body: {response.text}")
        response.raise_for_status()
        run_data = response.json()
        run_id = run_data["data"]["id"]
        print(f"[APIFY] Actor run started with ID: {run_id}")

        # Poll for completion
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}"
        start_time = asyncio.get_event_loop().time()

        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Actor run timed out after {timeout}s")

            response = await client.get(
                status_url,
                params={"token": token},
                timeout=10,
            )
            response.raise_for_status()
            status_data = response.json()
            status = status_data["data"]["status"]
            print(f"[APIFY] Actor run status: {status}")

            if status == "SUCCEEDED":
                break
            elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                print(f"[APIFY] Actor run failed! Full response: {status_data}")
                raise Exception(f"Actor run failed with status: {status}")

            await asyncio.sleep(2)

        # Get results from default dataset
        dataset_id = status_data["data"]["defaultDatasetId"]
        results_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"

        response = await client.get(
            results_url,
            params={"token": token},
            timeout=30,
        )
        response.raise_for_status()

        return response.json()


def parse_mobile_de_result(item: dict, url: str) -> VehicleData:
    """Parse mobile.de scraper result into VehicleData."""
    # The 3x1t~mobile-de-scraper-ppr actor returns attributes with keys like
    # "First Registration", "Mileage", "Fuel" (with spaces and capitals)

    # Extract attributes dict if present
    attrs = item.get("attributes", {})
    if isinstance(attrs, str):
        attrs = {}

    # Helper function to get value from attrs with flexible key matching
    def get_attr(keys):
        """Try multiple key variations to find a value in attrs."""
        for key in keys:
            if key in attrs:
                return attrs[key]
            # Try lowercase
            key_lower = key.lower()
            for attr_key, attr_val in attrs.items():
                if attr_key.lower() == key_lower:
                    return attr_val
        return None

    # Parse title first - it contains make and model
    title = item.get("title", "") or item.get("name", "") or ""

    # Extract make/model from title like "Mercedes-Benz C 180 Cabrio Verdeck..."
    make = "Unknown"
    model = "Unknown"
    if title:
        # Common German car brands
        brands = ["Mercedes-Benz", "BMW", "Audi", "Volkswagen", "VW", "Porsche",
                  "Ford", "Opel", "Skoda", "Seat", "Renault", "Peugeot", "Citroën",
                  "Fiat", "Alfa Romeo", "Volvo", "Toyota", "Honda", "Mazda",
                  "Nissan", "Hyundai", "Kia", "Lexus", "Mini", "Land Rover",
                  "Jaguar", "Jeep", "Tesla", "Chevrolet", "Dodge"]
        for brand in brands:
            if title.lower().startswith(brand.lower()):
                make = brand
                # Model is what comes after the brand
                model_part = title[len(brand):].strip()
                # Take first 2-3 words as model
                model_words = model_part.split()[:3]
                model = " ".join(model_words)
                break

        if make == "Unknown":
            # Fallback: first word is make, next words are model
            parts = title.split()
            if len(parts) >= 1:
                make = parts[0]
            if len(parts) >= 2:
                model = " ".join(parts[1:3])

    # Override with explicit make/model if available
    if item.get("brand"):
        make = item.get("brand")
    if item.get("model"):
        model = item.get("model")

    # Get first registration from attributes - key is "First Registration"
    first_reg_str = (
        get_attr(["First Registration", "firstRegistration", "registration"]) or
        item.get("firstRegistration") or
        ""
    )

    first_reg = datetime.now()
    year = datetime.now().year

    if first_reg_str:
        first_reg_str = str(first_reg_str).strip()
        try:
            if "/" in first_reg_str:
                # Format: "09/2016"
                parts = first_reg_str.split("/")
                if len(parts) == 2:
                    if len(parts[0]) == 4:  # YYYY/MM
                        year = int(parts[0])
                        month = int(parts[1])
                    else:  # MM/YYYY
                        month = int(parts[0])
                        year = int(parts[1])
                    first_reg = datetime(year, month, 1)
            elif "-" in first_reg_str:
                parts = first_reg_str.split("-")
                year = int(parts[0])
                month = int(parts[1]) if len(parts) > 1 else 1
                first_reg = datetime(year, month, 1)
        except:
            pass

    # Get mileage from attributes - key is "Mileage"
    mileage_str = (
        get_attr(["Mileage", "mileage", "km"]) or
        item.get("mileage") or
        "0"
    )
    # Parse "75,948 km" -> 75948
    mileage = int("".join(filter(str.isdigit, str(mileage_str))) or 0)

    # Get price - this one is tricky, the actor seems to have issues
    # Try to get from item.price first, but validate it
    price_raw = item.get("price")

    # The price field might be duplicated or corrupted
    # A normal car price is 4-6 digits (1000 - 999999 EUR)
    price = 0
    if price_raw is not None:
        price_str = str(price_raw)
        # Extract all digits
        digits = "".join(filter(str.isdigit, price_str))

        if digits:
            # Check if digits are duplicated (e.g., "2360023600" = "23600" twice)
            if len(digits) >= 8:
                half_len = len(digits) // 2
                first_half = digits[:half_len]
                second_half = digits[half_len:half_len*2]
                if first_half == second_half:
                    # Duplicated! Use just the first half
                    price = int(first_half)
                else:
                    # Not duplicated, take first 5-6 digits
                    price = int(digits[:min(6, len(digits))])
            else:
                price = int(digits)

    # Sanity check
    if price < 100 or price > 500000:
        price = 0  # Will trigger error downstream

    # Get fuel type from attributes - key is "Fuel"
    fuel_raw = (
        get_attr(["Fuel", "fuel", "fuelType", "Drive type"]) or
        item.get("fuel") or
        "petrol"
    )
    fuel_type = normalize_fuel_type(str(fuel_raw))

    # Get transmission from attributes - key is "Transmission"
    trans_raw = (
        get_attr(["Transmission", "transmission", "gearbox"]) or
        item.get("transmission") or
        "automatic"
    )
    transmission = normalize_transmission(str(trans_raw))

    # Get CO2 - often not available, estimate based on engine
    co2 = 150  # Default
    power_str = get_attr(["Power", "power", "kW"])
    if power_str:
        # Parse "115 kW (156 hp)" -> estimate CO2 based on power
        kw_match = "".join(filter(str.isdigit, str(power_str).split("kW")[0]))
        if kw_match:
            kw = int(kw_match)
            # Rough estimate: ~1.2-1.5 g/km per kW for petrol
            if fuel_type == "diesel":
                co2 = min(250, max(100, int(kw * 1.0)))
            elif fuel_type == "electric":
                co2 = 0
            else:
                co2 = min(300, max(100, int(kw * 1.3)))

    # Use the URL returned by Apify if available, otherwise use the provided URL
    actual_url = item.get("url", item.get("listingUrl", url))

    return VehicleData(
        make=make,
        model=model,
        year=year,
        mileage_km=mileage,
        price_eur=price,
        fuel_type=fuel_type,
        transmission=transmission,
        co2_gkm=co2,
        first_registration_date=first_reg,
        listing_url=actual_url,
        source="mobile.de",
        title=title or f"{make} {model}",
        features=item.get("features", item.get("equipment", [])),
        attributes=attrs,
    )


def parse_autoscout24_result(item: dict, url: str) -> VehicleData:
    """Parse AutoScout24 scraper result into VehicleData."""
    # The 3x1t~autoscout24-scraper-ppr returns data with:
    # - brand, model at top level
    # - attributes dict with keys like "First Registration", "Mileage", "Fuel"
    # - price as nested object: price.total.amount
    attrs = item.get("attributes", {})
    if isinstance(attrs, str):
        attrs = {}


    # Helper function to get value from item or attrs with flexible key matching
    def get_field(keys):
        """Try multiple key variations to find a value."""
        for key in keys:
            # Try item first
            if key in item and item[key]:
                return item[key]
            # Try attrs
            if key in attrs and attrs[key]:
                return attrs[key]
            # Try lowercase/case-insensitive
            key_lower = key.lower()
            for d in [item, attrs]:
                for k, v in d.items():
                    if k.lower() == key_lower and v:
                        return v
        return None

    # Try multiple field names for make/model (different scrapers use different names)
    make = get_field(["make", "brand", "Brand", "Make", "manufacturer"]) or "Unknown"
    model = get_field(["model", "modelLine", "Model", "ModelLine"]) or "Unknown"

    # Parse make/model from title if needed
    title = get_field(["title", "name", "Title", "Name"]) or ""
    if (make == "Unknown" or model == "Unknown") and title:
        # Extract from title like "BMW 320d xDrive..."
        brands = ["Mercedes-Benz", "BMW", "Audi", "Volkswagen", "VW", "Porsche",
                  "Ford", "Opel", "Skoda", "Seat", "Renault", "Peugeot", "Citroën",
                  "Fiat", "Alfa Romeo", "Volvo", "Toyota", "Honda", "Mazda",
                  "Nissan", "Hyundai", "Kia", "Lexus", "Mini", "Land Rover",
                  "Jaguar", "Jeep", "Tesla", "Chevrolet", "Dodge"]
        for brand in brands:
            if title.lower().startswith(brand.lower()):
                if make == "Unknown":
                    make = brand
                if model == "Unknown":
                    model_part = title[len(brand):].strip()
                    model_words = model_part.split()[:3]
                    model = " ".join(model_words)
                break
        if make == "Unknown" and title:
            parts = title.split()
            if len(parts) >= 1:
                make = parts[0]
            if len(parts) >= 2 and model == "Unknown":
                model = " ".join(parts[1:3])

    # Get first registration - handle multiple formats
    first_reg_str = get_field([
        "firstRegistration", "registration", "firstReg",
        "First Registration", "Registration", "year"
    ]) or ""
    first_reg = datetime.now()
    year = datetime.now().year

    if first_reg_str:
        try:
            first_reg_str = str(first_reg_str).strip()
            if "/" in first_reg_str:
                # Format: MM/YYYY or YYYY/MM
                parts = first_reg_str.split("/")
                if len(parts) == 2:
                    if len(parts[0]) == 4:  # YYYY/MM
                        year = int(parts[0])
                        month = int(parts[1])
                    else:  # MM/YYYY
                        month = int(parts[0])
                        year = int(parts[1])
                    first_reg = datetime(year, month, 1)
            elif "-" in first_reg_str:
                # Format: YYYY-MM or YYYY-MM-DD
                parts = first_reg_str.split("-")
                if len(parts) >= 2:
                    first_reg = datetime(int(parts[0]), int(parts[1]), 1)
                    year = int(parts[0])
            elif first_reg_str.isdigit() and len(first_reg_str) == 4:
                # Format: YYYY
                year = int(first_reg_str)
                first_reg = datetime(year, 1, 1)
        except:
            pass

    # Override year if explicitly provided
    year_field = get_field(["year", "Year", "productionYear"])
    if year_field:
        try:
            year = int(str(year_field).strip())
        except:
            pass

    # Get mileage - try multiple field names
    mileage_val = get_field([
        "mileage", "km", "mileageInKm", "Mileage", "Km",
        "kilometerstand", "kilometers"
    ]) or "0"
    mileage_str = str(mileage_val)
    mileage = int("".join(filter(str.isdigit, mileage_str)) or 0)

    # Get price - handle nested structure from 3x1t scraper: price.total.amount
    price = 0
    price_obj = item.get("price")
    if isinstance(price_obj, dict):
        # Nested structure: price.total.amount
        total_obj = price_obj.get("total", {})
        if isinstance(total_obj, dict):
            price = total_obj.get("amount", 0)
            if price:
                price = int(price)
        # Also try price.value or price.amount directly
        if not price:
            price = price_obj.get("amount", price_obj.get("value", 0))
            if price:
                price = int(price)
    elif price_obj:
        # Direct price value
        price_str = str(price_obj)
        # Handle prices like "23.600" (European format) or "23600" or "€ 23.600"
        price_str = price_str.replace("€", "").replace(" ", "").strip()
        # Handle European decimal separator (. as thousands, , as decimal)
        if "." in price_str and "," not in price_str:
            parts = price_str.split(".")
            if len(parts) == 2 and len(parts[1]) == 3:
                price_str = price_str.replace(".", "")
        price_str = price_str.split(",")[0]
        price = int("".join(filter(str.isdigit, price_str)) or 0)

    # Fallback to other field names
    if not price:
        price_val = get_field([
            "priceInEur", "priceNumeric", "Price", "priceEur", "askingPrice"
        ]) or "0"
        price_str = str(price_val)
        price_str = price_str.replace("€", "").replace(" ", "").strip()
        if "." in price_str and "," not in price_str:
            parts = price_str.split(".")
            if len(parts) == 2 and len(parts[1]) == 3:
                price_str = price_str.replace(".", "")
        price_str = price_str.split(",")[0]
        price = int("".join(filter(str.isdigit, price_str)) or 0)


    # Sanity check - price should be reasonable
    if price < 100 or price > 500000:
        price = 0

    # Get fuel type
    fuel_raw = get_field([
        "fuelType", "fuel", "Fuel", "FuelType", "Kraftstoff"
    ]) or "petrol"
    fuel_type = normalize_fuel_type(str(fuel_raw))

    # Get transmission
    trans_raw = get_field([
        "transmission", "gearbox", "Transmission", "Gearbox", "Getriebe"
    ]) or "automatic"
    transmission = normalize_transmission(str(trans_raw))

    # Get CO2 - try multiple field names (including special characters)
    co2_val = get_field([
        "co2Emission", "co2", "emissionsCO2", "CO2", "Co2",
        "co2_gkm", "emissionCO2", "CO₂ emissions"
    ])
    # Also check attrs directly for special character keys
    if not co2_val and attrs:
        for key in attrs.keys():
            if "co2" in key.lower() or "co₂" in key.lower():
                co2_val = attrs[key]
                break
    co2 = 150 if fuel_type == "petrol" else 130  # Default
    if co2_val:
        co2_str = str(co2_val)
        if co2_str and co2_str != "None":
            # Extract just the number from strings like "231 g/km (comb.)"
            digits = "".join(filter(str.isdigit, co2_str.split()[0] if co2_str.split() else co2_str))
            if digits:
                co2 = int(digits)
                # Sanity check
                if co2 < 50 or co2 > 400:
                    co2 = 150 if fuel_type == "petrol" else 130

    # Estimate CO2 from power if not available
    if co2 in [130, 150]:  # Still default
        power_val = get_field(["power", "kw", "powerKw", "Power", "Kw"])
        if power_val:
            kw_str = str(power_val)
            kw_digits = "".join(filter(str.isdigit, kw_str.split("kW")[0]))
            if kw_digits:
                kw = int(kw_digits)
                if fuel_type == "diesel":
                    co2 = min(250, max(100, int(kw * 1.0)))
                elif fuel_type == "electric":
                    co2 = 0
                else:
                    co2 = min(300, max(100, int(kw * 1.3)))

    if not title:
        title = f"{make} {model}"

    return VehicleData(
        make=make,
        model=model,
        year=year,
        mileage_km=mileage,
        price_eur=price,
        fuel_type=fuel_type,
        transmission=transmission,
        co2_gkm=co2,
        first_registration_date=first_reg,
        listing_url=url,
        source="autoscout24.de",
        title=title,
        features=item.get("features", item.get("equipment", [])),
        attributes=attrs if isinstance(attrs, dict) else {},
    )


async def scrape_vehicle(url: str, apify_token: str) -> ScrapeResult:
    """
    Scrape a vehicle listing.

    Args:
        url: URL of the listing
        apify_token: Apify API token

    Returns:
        ScrapeResult with vehicle data or error
    """
    source = detect_source(url)

    if source == "unknown":
        return ScrapeResult(
            success=False,
            error_type="INVALID_URL",
            error_message="URL not supported. Use mobile.de or AutoScout24.",
        )

    listing_id = extract_listing_id(url, source)

    if not listing_id:
        return ScrapeResult(
            success=False,
            error_type="INVALID_URL",
            error_message="Could not extract listing ID from URL.",
        )

    try:
        if source == "mobile.de":
            actor_id = APIFY_ACTORS["mobile_de"]
            # Normalize the URL to standard German format (handles /nl/, /fr/, /en/ versions)
            normalized_url = normalize_mobile_de_url(url)
            url_was_normalized = normalized_url != url
            # The rental version (3x1t~mobile-de-scraper) requires searchPageURLs parameter
            # and works best with auto-inserat URL format
            input_data = {
                "automaticPaging": True,
                "searchCategory": "Car",
                "searchPageURLMaxItems": 1,
                "searchPageURLs": [normalized_url],
            }
            print(f"[MOBILE.DE] Using actor: {actor_id}")
            print(f"[MOBILE.DE] Original URL: {url}")
            print(f"[MOBILE.DE] Normalized URL: {normalized_url}")
            print(f"[MOBILE.DE] URL was normalized: {url_was_normalized}")
            print(f"[MOBILE.DE] Input data: {input_data}")
            results = await run_apify_actor(actor_id, input_data, apify_token)

            if not results:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_OFFLINE",
                    error_message="Listing not found or no longer available.",
                )

            vehicle = parse_mobile_de_result(results[0], normalized_url)
            # Store original URL if it was normalized
            if url_was_normalized:
                vehicle.original_url = url

        else:  # autoscout24
            actor_id = APIFY_ACTORS["autoscout24"]
            # Clean the URL - remove tracking parameters
            clean_url = clean_autoscout24_url(url)
            # 3x1t~autoscout24-scraper-ppr expects startUrls as array of STRINGS (not objects!)
            input_data = {
                "startUrls": [clean_url],
                "maxItems": 1,
            }
            print(f"[AUTOSCOUT24] Using actor: {actor_id}")
            print(f"[AUTOSCOUT24] Clean URL: {clean_url}")
            print(f"[AUTOSCOUT24] Input data: {input_data}")
            results = await run_apify_actor(actor_id, input_data, apify_token)

            if not results:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_OFFLINE",
                    error_message="Listing not found or no longer available.",
                )

            vehicle = parse_autoscout24_result(results[0], clean_url)

        # Validate we got real data
        if vehicle.price_eur == 0:
            return ScrapeResult(
                success=False,
                error_type="LISTING_SOLD",
                error_message="Listing appears to be sold or price not available.",
            )

        return ScrapeResult(success=True, data=vehicle)

    except TimeoutError as e:
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_TIMEOUT",
            error_message="Scraper timed out. Please try again.",
            error_details=str(e),
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[SCRAPER_ERROR] Source: {source}, URL: {url}")
        print(f"[SCRAPER_ERROR] Exception: {e}")
        print(f"[SCRAPER_ERROR] Traceback: {error_trace}")
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_ERROR",
            error_message=f"Failed to scrape listing from {source}.",
            error_details=f"{str(e)} | {error_trace[:500]}",
        )


def vehicle_to_dict(vehicle: VehicleData) -> dict:
    """Convert VehicleData to dictionary for JSON serialization."""
    result = {
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "mileage_km": vehicle.mileage_km,
        "price_eur": vehicle.price_eur,
        "fuelType": vehicle.fuel_type,
        "transmission": vehicle.transmission,
        "co2_gkm": vehicle.co2_gkm,
        "firstRegistrationDate": vehicle.first_registration_date.isoformat(),
        "listingUrl": vehicle.listing_url,
        "source": vehicle.source,
        "title": vehicle.title,
        "features": vehicle.features,
        "attributes": vehicle.attributes,
    }
    # Include original URL if the URL was normalized
    if vehicle.original_url:
        result["originalUrl"] = vehicle.original_url
        result["urlWasNormalized"] = True
    return result
