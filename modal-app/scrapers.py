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
    if "autoscout24.de" in url_lower or "autoscout24.com" in url_lower:
        return "autoscout24"
    return "unknown"


def extract_listing_id(url: str, source: str) -> Optional[str]:
    """Extract listing ID from URL."""
    if source == "mobile.de":
        # https://suchen.mobile.de/fahrzeuge/details.html?id=446136631
        if "id=" in url:
            return url.split("id=")[1].split("&")[0]
    elif source == "autoscout24":
        # https://www.autoscout24.de/angebote/xxx-xxx-xxx-guid
        parts = url.rstrip("/").split("/")
        if parts:
            return parts[-1]
    return None


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
    async with httpx.AsyncClient() as client:
        # Start the actor run
        start_url = f"https://api.apify.com/v2/acts/{actor_id}/runs"

        response = await client.post(
            start_url,
            params={"token": token},
            json=input_data,
            timeout=30,
        )
        response.raise_for_status()
        run_data = response.json()
        run_id = run_data["data"]["id"]

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

            if status == "SUCCEEDED":
                break
            elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
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
        source="mobile.de",
        title=title or f"{make} {model}",
        features=item.get("features", item.get("equipment", [])),
        attributes=attrs,
    )


def parse_autoscout24_result(item: dict, url: str) -> VehicleData:
    """Parse AutoScout24 scraper result into VehicleData."""
    # Handle different output formats from various AutoScout24 scrapers
    attrs = item.get("vehicleDetails", item.get("attributes", item.get("vehicle", {})))

    # Try multiple field names for make/model (different scrapers use different names)
    make = (
        item.get("make") or
        item.get("brand") or
        attrs.get("make") or
        attrs.get("brand") or
        "Unknown"
    )
    model = (
        item.get("model") or
        item.get("modelLine") or
        attrs.get("model") or
        "Unknown"
    )

    # Get first registration - handle multiple formats
    first_reg_str = (
        item.get("firstRegistration") or
        item.get("registration") or
        attrs.get("firstRegistration") or
        item.get("year") or
        ""
    )
    first_reg = datetime.now()
    year = datetime.now().year

    if first_reg_str:
        try:
            first_reg_str = str(first_reg_str)
            if "/" in first_reg_str:
                # Format: MM/YYYY
                month, yr = first_reg_str.split("/")
                first_reg = datetime(int(yr), int(month), 1)
                year = int(yr)
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
    if item.get("year"):
        try:
            year = int(item.get("year"))
        except:
            pass

    # Get mileage - try multiple field names
    mileage_str = str(
        item.get("mileage") or
        item.get("km") or
        item.get("mileageInKm") or
        attrs.get("mileage") or
        "0"
    )
    mileage = int("".join(filter(str.isdigit, mileage_str)) or 0)

    # Get price - try multiple field names
    price_val = (
        item.get("price") or
        item.get("priceInEur") or
        item.get("priceNumeric") or
        attrs.get("price") or
        "0"
    )
    price_str = str(price_val)
    price = int("".join(filter(str.isdigit, price_str.split(".")[0].split(",")[0])) or 0)

    # Get fuel type
    fuel_raw = (
        item.get("fuelType") or
        item.get("fuel") or
        attrs.get("fuelType") or
        attrs.get("fuel") or
        "petrol"
    )
    fuel_type = normalize_fuel_type(fuel_raw)

    # Get transmission
    trans_raw = (
        item.get("transmission") or
        item.get("gearbox") or
        attrs.get("transmission") or
        "automatic"
    )
    transmission = normalize_transmission(trans_raw)

    # Get CO2 - try multiple field names
    co2_val = (
        item.get("co2Emission") or
        item.get("co2") or
        item.get("emissionsCO2") or
        attrs.get("co2Emission") or
        attrs.get("co2") or
        ""
    )
    co2_str = str(co2_val)
    if co2_str and co2_str != "None":
        co2 = int("".join(filter(str.isdigit, co2_str)) or 0)
        if co2 == 0:
            co2 = 150 if fuel_type == "petrol" else 130
    else:
        co2 = 150 if fuel_type == "petrol" else 130

    # Get title
    title = (
        item.get("title") or
        item.get("name") or
        f"{make} {model}"
    )

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
        attributes=attrs,
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
            input_data = {
                "startUrls": [{"url": url}],
                "maxItems": 1,
            }
            results = await run_apify_actor(actor_id, input_data, apify_token)

            if not results:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_OFFLINE",
                    error_message="Listing not found or no longer available.",
                )

            vehicle = parse_mobile_de_result(results[0], url)

        else:  # autoscout24
            actor_id = APIFY_ACTORS["autoscout24"]
            # dtrungtin~autoscout24-scraper expects this input format
            input_data = {
                "startUrls": [{"url": url}],
                "maxItems": 1,
                "proxy": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["RESIDENTIAL"]
                }
            }
            results = await run_apify_actor(actor_id, input_data, apify_token)

            if not results:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_OFFLINE",
                    error_message="Listing not found or no longer available.",
                )

            vehicle = parse_autoscout24_result(results[0], url)

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
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_ERROR",
            error_message="Failed to scrape listing.",
            error_details=str(e),
        )


def vehicle_to_dict(vehicle: VehicleData) -> dict:
    """Convert VehicleData to dictionary for JSON serialization."""
    return {
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
