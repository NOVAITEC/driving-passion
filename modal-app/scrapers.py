"""
Vehicle scrapers for German car listing sites.
Uses Apify actors for mobile.de and AutoScout24.
"""

import httpx
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any
import asyncio
import re
import json

from constants import APIFY_ACTORS
from utils import normalize_fuel_type, normalize_transmission
from user_agents import get_random_headers


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
    # AutoScout24 - ONLY support German version (.de)
    # Dutch version (.nl) is used for searching comparable cars, not as import source
    if any(domain in url_lower for domain in [
        "autoscout24.de",
        "autoscout24.com/de",  # International site, German section
        "www.autoscout24.de",
    ]):
        return "autoscout24"
    # Reject Dutch AutoScout24 URLs explicitly
    if any(domain in url_lower for domain in [
        "autoscout24.nl",
        "autoscout24.be",
        "autoscout24.com/nl",
        "www.autoscout24.nl",
    ]):
        return "autoscout24.nl"  # Mark as Dutch to handle separately
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


async def scrape_autoscout24_de_direct(url: str) -> ScrapeResult:
    """
    Scrape AutoScout24.de listing directly via HTTP (no Apify).

    Uses __NEXT_DATA__ JSON extraction pattern proven in AutoScout24 NL scraper.

    Args:
        url: AutoScout24.de listing URL

    Returns:
        ScrapeResult with vehicle data or error
    """
    print(f"[AUTOSCOUT24.DE DIRECT] Scraping: {url}")

    # Clean URL - remove tracking parameters
    clean_url = clean_autoscout24_url(url)

    try:
        # HTTP GET with randomized realistic headers
        headers = get_random_headers()
        headers["Referer"] = "https://www.autoscout24.de/"

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(clean_url, headers=headers, timeout=30.0)

            # Check for error status codes
            if response.status_code == 404:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_OFFLINE",
                    error_message="Listing not found (404).",
                )
            elif response.status_code == 410:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_OFFLINE",
                    error_message="Listing no longer available (410 Gone).",
                )
            elif response.status_code == 403:
                return ScrapeResult(
                    success=False,
                    error_type="SCRAPER_BLOCKED",
                    error_message="Access blocked (403). Use Apify fallback.",
                )
            elif response.status_code == 429:
                return ScrapeResult(
                    success=False,
                    error_type="RATE_LIMITED",
                    error_message="Rate limited (429). Use Apify fallback.",
                )

            response.raise_for_status()
            html = response.text

        print(f"[AUTOSCOUT24.DE DIRECT] HTTP {response.status_code}, HTML length: {len(html)}")

        # Extract __NEXT_DATA__ JSON (proven pattern from AutoScout24 NL)
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html,
            re.DOTALL
        )

        if not match:
            # Try alternative: window.__INITIAL_STATE__
            match = re.search(
                r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
                html,
                re.DOTALL
            )
            if not match:
                print("[AUTOSCOUT24.DE DIRECT] No __NEXT_DATA__ or __INITIAL_STATE__ found")
                return ScrapeResult(
                    success=False,
                    error_type="PARSE_ERROR",
                    error_message="Could not extract vehicle data from page.",
                    error_details="Tried __NEXT_DATA__ and __INITIAL_STATE__ patterns",
                )

        try:
            json_data = json.loads(match.group(1))
            print("[AUTOSCOUT24.DE DIRECT] Extracted JSON data successfully")

            # Navigate JSON structure to find vehicle data
            # AutoScout24 typically stores listing data in props.pageProps.listingDetails
            listing_data = None

            # Try multiple paths in the JSON structure
            if "props" in json_data:
                page_props = json_data.get("props", {}).get("pageProps", {})

                # Try different property names
                for key in ["listingDetails", "listing", "vehicleDetails", "vehicle", "data"]:
                    if key in page_props:
                        listing_data = page_props[key]
                        print(f"[AUTOSCOUT24.DE DIRECT] Found listing data in props.pageProps.{key}")
                        break

            if not listing_data:
                # Try top-level keys
                for key in ["listing", "vehicle", "data", "pageProps"]:
                    if key in json_data:
                        listing_data = json_data[key]
                        print(f"[AUTOSCOUT24.DE DIRECT] Found listing data in top-level {key}")
                        break

            if not listing_data:
                print(f"[AUTOSCOUT24.DE DIRECT] Available keys: {list(json_data.keys())}")
                return ScrapeResult(
                    success=False,
                    error_type="PARSE_ERROR",
                    error_message="Could not find listing data in JSON structure.",
                    error_details=f"Available top-level keys: {list(json_data.keys())}",
                )

            # Parse using existing AutoScout24 parser
            vehicle = parse_autoscout24_result(listing_data, clean_url)

            # Validate we got real data
            if vehicle.price_eur == 0:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_SOLD",
                    error_message="Listing appears to be sold or price not available.",
                )

            print(f"[AUTOSCOUT24.DE DIRECT] SUCCESS: {vehicle.make} {vehicle.model}, €{vehicle.price_eur}")
            return ScrapeResult(success=True, data=vehicle)

        except json.JSONDecodeError as e:
            print(f"[AUTOSCOUT24.DE DIRECT] JSON decode error: {e}")
            return ScrapeResult(
                success=False,
                error_type="PARSE_ERROR",
                error_message="Failed to parse JSON data.",
                error_details=str(e),
            )

    except httpx.TimeoutException:
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_TIMEOUT",
            error_message="Request timed out after 30s.",
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[AUTOSCOUT24.DE DIRECT] Exception: {e}")
        print(f"[AUTOSCOUT24.DE DIRECT] Traceback: {error_trace}")
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_ERROR",
            error_message="Direct scraping failed.",
            error_details=f"{str(e)} | {error_trace[:500]}",
        )


async def scrape_mobile_de_direct(url: str) -> ScrapeResult:
    """
    Scrape mobile.de listing directly via HTTP (no Apify).

    Tries multiple JSON extraction patterns: __NEXT_DATA__, __INITIAL_STATE__, JSON-LD.

    Args:
        url: mobile.de listing URL

    Returns:
        ScrapeResult with vehicle data or error
    """
    print(f"[MOBILE.DE DIRECT] Scraping: {url}")

    # Normalize URL to standard German format
    normalized_url = normalize_mobile_de_url(url)

    try:
        # HTTP GET with randomized realistic headers
        headers = get_random_headers()
        headers["Referer"] = "https://suchen.mobile.de/"

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(normalized_url, headers=headers, timeout=30.0)

            # Check for error status codes
            if response.status_code == 404:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_OFFLINE",
                    error_message="Listing not found (404).",
                )
            elif response.status_code == 410:
                return ScrapeResult(
                    success=False,
                    error_type="LISTING_OFFLINE",
                    error_message="Listing no longer available (410 Gone).",
                )
            elif response.status_code == 403:
                return ScrapeResult(
                    success=False,
                    error_type="SCRAPER_BLOCKED",
                    error_message="Access blocked (403). Use Apify fallback.",
                )
            elif response.status_code == 429:
                return ScrapeResult(
                    success=False,
                    error_type="RATE_LIMITED",
                    error_message="Rate limited (429). Use Apify fallback.",
                )

            response.raise_for_status()
            html = response.text

        print(f"[MOBILE.DE DIRECT] HTTP {response.status_code}, HTML length: {len(html)}")

        # Try Pattern 1: __NEXT_DATA__
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html,
            re.DOTALL
        )

        json_data = None
        extraction_method = None

        if match:
            try:
                json_data = json.loads(match.group(1))
                extraction_method = "__NEXT_DATA__"
                print("[MOBILE.DE DIRECT] Extracted __NEXT_DATA__")
            except json.JSONDecodeError:
                pass

        # Try Pattern 2: window.__INITIAL_STATE__
        if not json_data:
            match = re.search(
                r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
                html,
                re.DOTALL
            )
            if match:
                try:
                    json_data = json.loads(match.group(1))
                    extraction_method = "__INITIAL_STATE__"
                    print("[MOBILE.DE DIRECT] Extracted __INITIAL_STATE__")
                except json.JSONDecodeError:
                    pass

        # Try Pattern 3: JSON-LD structured data (may have multiple blocks)
        if not json_data:
            # Find ALL JSON-LD blocks
            matches = re.finditer(
                r'<script type="application/ld\+json">(.*?)</script>',
                html,
                re.DOTALL
            )
            for match in matches:
                try:
                    data = json.loads(match.group(1))
                    # Look for Car/Vehicle/Product types (not Organization)
                    if data.get("@type") in ["Car", "Vehicle", "Product", "Offer"]:
                        json_data = data
                        extraction_method = "JSON-LD"
                        print(f"[MOBILE.DE DIRECT] Extracted JSON-LD with @type: {data.get('@type')}")
                        break
                except json.JSONDecodeError:
                    continue

        if not json_data:
            print("[MOBILE.DE DIRECT] No JSON data found with any pattern")
            return ScrapeResult(
                success=False,
                error_type="PARSE_ERROR",
                error_message="Could not extract vehicle data from page.",
                error_details="Tried __NEXT_DATA__, __INITIAL_STATE__, and JSON-LD patterns",
            )

        # Navigate JSON structure to find vehicle/listing data
        listing_data = None

        if extraction_method == "__NEXT_DATA__":
            # Try Next.js structure: props.pageProps.*
            if "props" in json_data:
                page_props = json_data.get("props", {}).get("pageProps", {})
                for key in ["ad", "listing", "vehicle", "data", "adDetails", "classifiedAd"]:
                    if key in page_props:
                        listing_data = page_props[key]
                        print(f"[MOBILE.DE DIRECT] Found data in props.pageProps.{key}")
                        break

        if not listing_data and extraction_method == "__INITIAL_STATE__":
            # Try common state keys
            for key in ["ad", "listing", "vehicle", "classified", "data"]:
                if key in json_data:
                    listing_data = json_data[key]
                    print(f"[MOBILE.DE DIRECT] Found data in {key}")
                    break

        if not listing_data and extraction_method == "JSON-LD":
            # JSON-LD is already the listing data for Car/Vehicle types
            if json_data.get("@type") in ["Car", "Vehicle", "Product"]:
                listing_data = json_data
                print("[MOBILE.DE DIRECT] Using JSON-LD data directly")

        if not listing_data:
            # Try top-level keys as fallback
            for key in ["ad", "listing", "vehicle", "data"]:
                if key in json_data:
                    listing_data = json_data[key]
                    print(f"[MOBILE.DE DIRECT] Found data in top-level {key}")
                    break

        if not listing_data:
            print(f"[MOBILE.DE DIRECT] Available keys: {list(json_data.keys())}")
            return ScrapeResult(
                success=False,
                error_type="PARSE_ERROR",
                error_message="Could not find listing data in JSON structure.",
                error_details=f"Method: {extraction_method}, Keys: {list(json_data.keys())}",
            )

        # Parse using existing mobile.de parser
        vehicle = parse_mobile_de_result(listing_data, normalized_url)

        # Store original URL if it was normalized
        if normalized_url != url:
            vehicle.original_url = url

        # Validate we got real data
        if vehicle.price_eur == 0:
            return ScrapeResult(
                success=False,
                error_type="LISTING_SOLD",
                error_message="Listing appears to be sold or price not available.",
            )

        print(f"[MOBILE.DE DIRECT] SUCCESS: {vehicle.make} {vehicle.model}, €{vehicle.price_eur}")
        return ScrapeResult(success=True, data=vehicle)

    except httpx.TimeoutException:
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_TIMEOUT",
            error_message="Request timed out after 30s.",
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[MOBILE.DE DIRECT] Exception: {e}")
        print(f"[MOBILE.DE DIRECT] Traceback: {error_trace}")
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_ERROR",
            error_message="Direct scraping failed.",
            error_details=f"{str(e)} | {error_trace[:500]}",
        )


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
                # Extract model with engine variant (e.g., "Golf 2.0 TDI" not just "Golf")
                # Include more words to capture engine size and type
                # Stop at common descriptive words that come after the core model
                stop_words = ["cabrio", "cabriolet", "limousine", "sedan", "wagon",
                             "kombi", "estate", "touring", "avant", "sportback",
                             "coupe", "suv", "roadster", "convertible", "van",
                             "panorama", "xenon", "navi", "automatik", "dsg",
                             "schalter", "benzin", "diesel", "hybrid"]
                model_words = []
                for word in model_part.split():
                    if word.lower() in stop_words:
                        break
                    model_words.append(word)
                    # Take up to 5 words to capture variants like "Golf VII 2.0 TDI"
                    if len(model_words) >= 5:
                        break
                model = " ".join(model_words) if model_words else model_part.split()[0] if model_part.split() else "Unknown"
                break

        if make == "Unknown":
            # Fallback: first word is make, next words are model
            parts = title.split()
            if len(parts) >= 1:
                make = parts[0]
            if len(parts) >= 2:
                # Take up to 4 words for model
                model = " ".join(parts[1:min(5, len(parts))])

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

    # Get price - this one is tricky, the actor may return various formats
    # European format uses . as thousands separator and , as decimal
    # E.g., "28.480,20" or "€ 28.480" or "28480.2"
    price_raw = item.get("price")

    price = 0
    if price_raw is not None:
        price_str = str(price_raw).strip()
        print(f"[MOBILE.DE] Raw price value: {repr(price_raw)}")

        # Remove currency symbols and whitespace
        price_str = price_str.replace("€", "").replace("EUR", "").strip()

        # Handle European number format:
        # "28.480,20" -> thousands separator is ., decimal is ,
        # "28.480" -> could be 28480 or 28.480 (ambiguous, assume thousands sep)
        # "28480.20" -> decimal point format (28480.20 euros)
        # "28480" -> plain integer

        if "," in price_str and "." in price_str:
            # European format: "28.480,20" - dot is thousands, comma is decimal
            # Remove thousands separator, replace decimal comma with dot
            price_str = price_str.replace(".", "").replace(",", ".")
        elif "," in price_str:
            # Only comma: could be "28,480" (European) or "28480,20" (decimal)
            parts = price_str.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Decimal: "28480,20" -> "28480.20"
                price_str = price_str.replace(",", ".")
            else:
                # Thousands separator: "28,480" -> "28480"
                price_str = price_str.replace(",", "")
        elif "." in price_str:
            # Only dot: could be "28.480" (thousands) or "28480.20" (decimal)
            parts = price_str.split(".")
            if len(parts) == 2:
                if len(parts[1]) <= 2:
                    # Decimal: "28480.20" -> keep as is (will truncate)
                    pass
                elif len(parts[1]) == 3:
                    # Thousands separator: "28.480" -> "28480"
                    price_str = price_str.replace(".", "")

        # Now extract the integer part (ignore decimals)
        # Split on decimal point and take first part
        if "." in price_str:
            price_str = price_str.split(".")[0]

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

        print(f"[MOBILE.DE] Parsed price: {price}")

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
    print(f"[MOBILE.DE] Fuel raw: {fuel_raw} → normalized: {fuel_type}")

    # Get transmission from attributes - key is "Transmission"
    trans_raw = (
        get_attr(["Transmission", "transmission", "gearbox"]) or
        item.get("transmission") or
        "automatic"
    )
    transmission = normalize_transmission(str(trans_raw))

    # ENHANCEMENT: If model is too generic (just 1-2 words like "Golf" or "3 Series"),
    # try to enrich it with engine info from attributes
    # This helps find more accurate market comparables
    if len(model.split()) <= 2 and not any(char.isdigit() for char in model):
        # Model is generic (e.g., "Golf", "3 Series") without engine size
        # First try to get actual engine displacement from attributes
        engine_size = None
        cubic_capacity = get_attr([
            "Cubic Capacity", "Cubic capacity", "cubic capacity",
            "Hubraum", "hubraum", "Engine Size", "engine size",
            "Displacement", "displacement", "ccm", "cc"
        ])

        if cubic_capacity:
            print(f"[MOBILE.DE] Cubic capacity attribute: {cubic_capacity}")
            # Parse values like "1,984 cc", "1984 ccm", "2.0 L", "1984"
            cc_str = str(cubic_capacity).lower().replace(",", "").replace(".", "")
            cc_digits = "".join(filter(str.isdigit, cc_str))
            if cc_digits:
                cc = int(cc_digits)
                # Convert cc to liters (e.g., 1984 cc = 2.0 L)
                if cc > 100:  # It's in cc, not liters
                    liters = cc / 1000
                else:
                    liters = cc  # Already in liters (rare)
                # Round to common engine sizes
                if liters < 1.1:
                    engine_size = "1.0"
                elif liters < 1.3:
                    engine_size = "1.2"
                elif liters < 1.5:
                    engine_size = "1.4"
                elif liters < 1.7:
                    engine_size = "1.6"
                elif liters < 1.9:
                    engine_size = "1.8"
                elif liters < 2.1:
                    engine_size = "2.0"
                elif liters < 2.3:
                    engine_size = "2.2"
                elif liters < 2.6:
                    engine_size = "2.5"
                elif liters < 2.9:
                    engine_size = "2.8"
                elif liters < 3.1:
                    engine_size = "3.0"
                elif liters < 3.3:
                    engine_size = "3.2"
                elif liters < 3.6:
                    engine_size = "3.5"
                elif liters < 4.1:
                    engine_size = "4.0"
                else:
                    engine_size = f"{liters:.1f}"
                print(f"[MOBILE.DE] Parsed engine size: {cc} cc → {engine_size} L")

        # Build engine designation with fuel type suffix
        if engine_size:
            if fuel_type == "diesel":
                engine_suffix = "TDI"  # VW/Audi diesel
            elif fuel_type == "petrol":
                engine_suffix = "TSI"  # VW/Audi petrol
            else:
                engine_suffix = ""

            original_model = model
            if engine_suffix:
                model = f"{model} {engine_size} {engine_suffix}"
            else:
                model = f"{model} {engine_size}"
            print(f"[MOBILE.DE] Enriched model from '{original_model}' to '{model}' based on actual displacement")
        else:
            # Fallback: No displacement found, log available attributes for debugging
            print(f"[MOBILE.DE] No cubic capacity found. Available attributes: {list(attrs.keys())}")

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
    """
    Parse AutoScout24 scraper result into VehicleData.

    Supports two formats:
    1. Apify format: flat structure with brand/model at top level
    2. Direct scraping format: nested structure with vehicle.* and prices.*
    """
    # Check if this is direct scraping format (has 'vehicle' key)
    if "vehicle" in item and isinstance(item["vehicle"], dict):
        return _parse_autoscout24_direct(item, url)

    # Otherwise, use the old Apify format parser
    return _parse_autoscout24_apify(item, url)


def _parse_autoscout24_direct(item: dict, url: str) -> VehicleData:
    """Parse AutoScout24 direct scraping format (nested structure)."""
    vehicle = item.get("vehicle", {})
    prices = item.get("prices", {})

    # Make and Model - direct from vehicle.*
    make = vehicle.get("make", "Unknown")
    model = vehicle.get("model", "Unknown")

    # If model is too short, try to get variant for more specific matching
    variant = vehicle.get("variant", "")
    if variant and len(model.split()) <= 2:
        # Avoid duplication: don't add variant if it already starts with model
        # E.g., model="A3", variant="A3 Sportback" -> use "A3 Sportback"
        if variant.lower().startswith(model.lower()):
            model = variant.strip()
        else:
            model = f"{model} {variant}".strip()

    # Price - from prices.public.priceRaw (clean integer)
    price = prices.get("public", {}).get("priceRaw", 0) or 0
    if not price:
        price = prices.get("dealer", {}).get("priceRaw", 0) or 0

    # Mileage - parse from "184.555 km" format
    mileage_str = str(vehicle.get("mileageInKm", "0"))
    mileage = int("".join(filter(str.isdigit, mileage_str)) or 0)

    # First Registration - parse "11/2010" format
    first_reg_str = str(vehicle.get("firstRegistrationDate", ""))
    first_reg = datetime.now()
    year = datetime.now().year

    if first_reg_str and first_reg_str != "None":
        try:
            if "/" in first_reg_str:
                # Format: MM/YYYY
                parts = first_reg_str.split("/")
                if len(parts) == 2:
                    month = int(parts[0])
                    year = int(parts[1])
                    first_reg = datetime(year, month, 1)
            elif "-" in first_reg_str:
                # Format: YYYY-MM or YYYY-MM-DD
                parts = first_reg_str.split("-")
                year = int(parts[0])
                month = int(parts[1]) if len(parts) > 1 else 1
                first_reg = datetime(year, month, 1)
        except:
            pass

    # Override with production year if available
    if vehicle.get("productionYear"):
        try:
            year = int(vehicle.get("productionYear"))
        except:
            pass

    # Fuel type - from fuelCategory.formatted (handles dict or string)
    fuel_category = vehicle.get("fuelCategory", "petrol")
    if isinstance(fuel_category, dict):
        fuel_raw = fuel_category.get("formatted", fuel_category.get("raw", "petrol"))
    else:
        fuel_raw = fuel_category
    fuel_type = normalize_fuel_type(str(fuel_raw))

    # Transmission - from transmissionType (can be Dutch: "Handgeschakeld", "Automaat")
    trans_raw = vehicle.get("transmissionType", "automatic")
    transmission = normalize_transmission(str(trans_raw))

    # CO2 - from co2emissionInGramPerKmWithFallback
    co2 = 150 if fuel_type == "petrol" else 130  # Default
    co2_data = vehicle.get("co2emissionInGramPerKmWithFallback", {})
    if isinstance(co2_data, dict):
        co2_raw = co2_data.get("raw")
        if co2_raw and co2_raw != "None":
            try:
                co2 = int(co2_raw)
                # Sanity check
                if co2 < 50 or co2 > 400:
                    co2 = 150 if fuel_type == "petrol" else 130
            except:
                pass

    # If CO2 not available, estimate from power
    if co2 in [130, 150]:
        power_kw_str = str(vehicle.get("powerInKw", ""))
        kw_digits = "".join(filter(str.isdigit, power_kw_str.split()[0] if power_kw_str.split() else power_kw_str))
        if kw_digits:
            kw = int(kw_digits)
            if fuel_type == "diesel":
                co2 = min(250, max(100, int(kw * 1.0)))
            elif fuel_type == "electric":
                co2 = 0
            else:
                co2 = min(300, max(100, int(kw * 1.3)))

    # Title - from imgAltText or construct from make/model
    title = item.get("imgAltText", f"{make} {model}")

    # Equipment/features - from vehicle.equipment
    equipment = vehicle.get("equipment", [])
    if isinstance(equipment, list):
        features = equipment
    else:
        features = []

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
        features=features,
        attributes=vehicle,  # Store full vehicle dict as attributes
    )


def _parse_autoscout24_apify(item: dict, url: str) -> VehicleData:
    """Parse AutoScout24 Apify format (flat structure)."""
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


async def scrape_mobile_de_apify(url: str, apify_token: str) -> ScrapeResult:
    """
    Scrape mobile.de listing via Apify actor (fallback method).

    Args:
        url: mobile.de listing URL
        apify_token: Apify API token

    Returns:
        ScrapeResult with vehicle data or error
    """
    print(f"[MOBILE.DE APIFY] Scraping via Apify: {url}")

    actor_id = APIFY_ACTORS["mobile_de"]
    # Normalize the URL to standard German format (handles /nl/, /fr/, /en/ versions)
    normalized_url = normalize_mobile_de_url(url)
    url_was_normalized = normalized_url != url

    # The rental version (3x1t~mobile-de-scraper) requires searchPageURLs parameter
    input_data = {
        "automaticPaging": True,
        "searchCategory": "Car",
        "searchPageURLMaxItems": 1,
        "searchPageURLs": [normalized_url],
    }

    print(f"[MOBILE.DE APIFY] Using actor: {actor_id}")
    print(f"[MOBILE.DE APIFY] Normalized URL: {normalized_url}")

    try:
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
            error_message="Apify actor timed out. Please try again.",
            error_details=str(e),
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[MOBILE.DE APIFY] Exception: {e}")
        print(f"[MOBILE.DE APIFY] Traceback: {error_trace}")
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_ERROR",
            error_message="Apify scraping failed.",
            error_details=f"{str(e)} | {error_trace[:500]}",
        )


async def scrape_autoscout24_de_apify(url: str, apify_token: str) -> ScrapeResult:
    """
    Scrape AutoScout24.de listing via Apify actor (fallback method).

    Args:
        url: AutoScout24.de listing URL
        apify_token: Apify API token

    Returns:
        ScrapeResult with vehicle data or error
    """
    print(f"[AUTOSCOUT24.DE APIFY] Scraping via Apify: {url}")

    actor_id = APIFY_ACTORS["autoscout24"]
    # Clean the URL - remove tracking parameters
    clean_url = clean_autoscout24_url(url)

    # 3x1t~autoscout24-scraper-ppr expects startUrls as array of STRINGS
    input_data = {
        "startUrls": [clean_url],
        "maxItems": 1,
    }

    print(f"[AUTOSCOUT24.DE APIFY] Using actor: {actor_id}")
    print(f"[AUTOSCOUT24.DE APIFY] Clean URL: {clean_url}")

    try:
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
            error_message="Apify actor timed out. Please try again.",
            error_details=str(e),
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[AUTOSCOUT24.DE APIFY] Exception: {e}")
        print(f"[AUTOSCOUT24.DE APIFY] Traceback: {error_trace}")
        return ScrapeResult(
            success=False,
            error_type="SCRAPER_ERROR",
            error_message="Apify scraping failed.",
            error_details=f"{str(e)} | {error_trace[:500]}",
        )


async def scrape_vehicle(url: str, apify_token: str) -> ScrapeResult:
    """
    Scrape a vehicle listing with direct HTTP (primary) and Apify fallback.

    Strategy:
    1. Try direct HTTP scraping first (fast, free)
    2. If direct fails (except LISTING_OFFLINE), fall back to Apify
    3. LISTING_OFFLINE errors don't trigger fallback (listing truly offline)

    Args:
        url: URL of the listing
        apify_token: Apify API token

    Returns:
        ScrapeResult with vehicle data or error
    """
    source = detect_source(url)

    if source == "autoscout24.nl":
        return ScrapeResult(
            success=False,
            error_type="INVALID_URL",
            error_message="Nederlandse AutoScout24 advertenties worden niet ondersteund. Deze calculator is alleen voor Duitse advertenties die je naar Nederland wilt importeren.",
            error_details="Ga naar autoscout24.de om Duitse advertenties te bekijken.",
        )

    if source == "unknown":
        return ScrapeResult(
            success=False,
            error_type="INVALID_URL",
            error_message="URL not supported. Use mobile.de or AutoScout24.de (German listings only).",
        )

    listing_id = extract_listing_id(url, source)

    if not listing_id:
        return ScrapeResult(
            success=False,
            error_type="INVALID_URL",
            error_message="Could not extract listing ID from URL.",
        )

    # Import USE_DIRECT_SCRAPING flag
    from constants import USE_DIRECT_SCRAPING

    if source == "mobile.de":
        # Try direct scraping first (if enabled)
        if USE_DIRECT_SCRAPING:
            print("[SCRAPER] Trying mobile.de direct HTTP scraping...")
            result = await scrape_mobile_de_direct(url)

            # If successful, return immediately
            if result.success:
                print("[SCRAPER] Direct scraping SUCCESS")
                return result

            # If listing is offline, don't fallback (it's truly gone)
            if result.error_type == "LISTING_OFFLINE":
                print("[SCRAPER] Listing offline, no fallback")
                return result

            # Otherwise, try Apify fallback
            print(f"[SCRAPER] Direct scraping failed ({result.error_type}), trying Apify fallback...")
        else:
            print("[SCRAPER] Direct scraping disabled, using Apify only")

        # Apify fallback
        result = await scrape_mobile_de_apify(url, apify_token)
        return result

    elif source == "autoscout24":
        # Try direct scraping first (if enabled)
        if USE_DIRECT_SCRAPING:
            print("[SCRAPER] Trying AutoScout24.de direct HTTP scraping...")
            result = await scrape_autoscout24_de_direct(url)

            # If successful, return immediately
            if result.success:
                print("[SCRAPER] Direct scraping SUCCESS")
                return result

            # If listing is offline, don't fallback (it's truly gone)
            if result.error_type == "LISTING_OFFLINE":
                print("[SCRAPER] Listing offline, no fallback")
                return result

            # Otherwise, try Apify fallback
            print(f"[SCRAPER] Direct scraping failed ({result.error_type}), trying Apify fallback...")
        else:
            print("[SCRAPER] Direct scraping disabled, using Apify only")

        # Apify fallback
        result = await scrape_autoscout24_de_apify(url, apify_token)
        return result

    else:
        return ScrapeResult(
            success=False,
            error_type="INVALID_URL",
            error_message=f"Unknown source: {source}",
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
