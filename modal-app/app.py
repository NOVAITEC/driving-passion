"""
Driving Passion Auto Import Calculator - Modal App

Main entry point for the Modal deployment.
Provides webhook endpoints for calculating import margins.
"""

import modal
from datetime import datetime
from typing import Optional
import uuid

# =============================================================================
# MODAL APP SETUP
# =============================================================================

app = modal.App("driving-passion")

# Define the container image with all dependencies and local modules
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("httpx", "fastapi[standard]")
    .add_local_file("constants.py", "/root/constants.py")
    .add_local_file("utils.py", "/root/utils.py")
    .add_local_file("bpm_calculator.py", "/root/bpm_calculator.py")
    .add_local_file("scrapers.py", "/root/scrapers.py")
    .add_local_file("dutch_market.py", "/root/dutch_market.py")
    .add_local_file("valuation.py", "/root/valuation.py")
)

# =============================================================================
# SECRETS
# =============================================================================
# You need to create these secrets in Modal:
#   modal secret create apify-secret APIFY_TOKEN=your_token
#   modal secret create openrouter-secret OPENROUTER_API_KEY=your_key
#   (optional) modal secret create openrouter-secret OPENROUTER_API_KEY=your_key OPENROUTER_MODEL=openai/gpt-4o

apify_secret = modal.Secret.from_name("apify-secret")
openrouter_secret = modal.Secret.from_name("openrouter-secret")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_recommendation(margin: int, safe_margin: int) -> str:
    """Get recommendation based on margin."""
    from constants import MARGIN_THRESHOLDS

    if margin >= MARGIN_THRESHOLDS["go"] and safe_margin > MARGIN_THRESHOLDS["safe_margin"]:
        return "GO"
    if margin >= MARGIN_THRESHOLDS["consider"]:
        return "CONSIDER"
    return "NO_GO"


# =============================================================================
# MODAL FUNCTIONS
# =============================================================================


@app.function(
    image=image,
        secrets=[apify_secret],
    timeout=180,
)
async def scrape_vehicle_fn(url: str) -> dict:
    """
    Scrape a vehicle listing from Mobile.de or AutoScout24 DE.
    Returns vehicle data as a dictionary.
    """
    import os
    from scrapers import scrape_vehicle, vehicle_to_dict

    apify_token = os.environ["APIFY_TOKEN"]
    result = await scrape_vehicle(url, apify_token)

    if not result.success:
        return {
            "success": False,
            "error": {
                "type": result.error_type,
                "message": result.error_message,
                "details": result.error_details,
            },
        }

    return {
        "success": True,
        "data": vehicle_to_dict(result.data),
    }


@app.function(
    image=image,
    secrets=[apify_secret],
    timeout=90,
)
async def search_dutch_market_fn(vehicle_data: dict) -> dict:
    """
    Search the Dutch market for comparable vehicles.
    Searches both AutoScout24 NL and Marktplaats.
    Returns list of comparables as dictionaries.
    """
    import os
    from datetime import datetime
    from scrapers import VehicleData
    from dutch_market import search_dutch_market, comparable_to_dict, get_market_stats, market_stats_to_dict

    apify_token = os.environ.get("APIFY_TOKEN")

    # Reconstruct VehicleData from dict
    vehicle = VehicleData(
        make=vehicle_data["make"],
        model=vehicle_data["model"],
        year=vehicle_data["year"],
        mileage_km=vehicle_data["mileage_km"],
        price_eur=vehicle_data["price_eur"],
        fuel_type=vehicle_data["fuelType"],
        transmission=vehicle_data["transmission"],
        co2_gkm=vehicle_data["co2_gkm"],
        first_registration_date=datetime.fromisoformat(vehicle_data["firstRegistrationDate"]),
        listing_url=vehicle_data.get("listingUrl", ""),
        source=vehicle_data.get("source", "mobile.de"),
        title=vehicle_data.get("title", ""),
        features=vehicle_data.get("features", []),
        attributes=vehicle_data.get("attributes", {}),
    )

    comparables = await search_dutch_market(vehicle, apify_token)
    stats = get_market_stats(comparables)

    # Get unique sources
    sources = list(set(c.source for c in comparables))

    return {
        "comparables": [comparable_to_dict(c) for c in comparables],
        "stats": market_stats_to_dict(stats),
        "sources": sources,
    }


@app.function(
    image=image,
        timeout=30,
)
def calculate_bpm_fn(co2_gkm: int, fuel_type: str, first_registration_date: str) -> dict:
    """
    Calculate BPM for a vehicle.
    Returns BPM breakdown as a dictionary.
    """
    from datetime import datetime
    from bpm_calculator import calculate_bpm, bpm_to_dict

    reg_date = datetime.fromisoformat(first_registration_date)
    result = calculate_bpm(co2_gkm, fuel_type, reg_date)

    return bpm_to_dict(result)


@app.function(
    image=image,
        secrets=[openrouter_secret],
    timeout=60,
)
async def valuate_vehicle_fn(vehicle_data: dict, comparables: list[dict]) -> dict:
    """
    Get AI valuation for a vehicle.
    Returns valuation as a dictionary.
    """
    import os
    from datetime import datetime
    from scrapers import VehicleData
    from dutch_market import DutchComparable
    from valuation import valuate_vehicle, valuation_to_dict

    api_key = os.environ["OPENROUTER_API_KEY"]
    model = os.environ.get("OPENROUTER_MODEL")  # Optional, uses default if not set

    # Reconstruct VehicleData
    vehicle = VehicleData(
        make=vehicle_data["make"],
        model=vehicle_data["model"],
        year=vehicle_data["year"],
        mileage_km=vehicle_data["mileage_km"],
        price_eur=vehicle_data["price_eur"],
        fuel_type=vehicle_data["fuelType"],
        transmission=vehicle_data["transmission"],
        co2_gkm=vehicle_data["co2_gkm"],
        first_registration_date=datetime.fromisoformat(vehicle_data["firstRegistrationDate"]),
        listing_url=vehicle_data.get("listingUrl", ""),
        source=vehicle_data.get("source", "mobile.de"),
        title=vehicle_data.get("title", ""),
        features=vehicle_data.get("features", []),
        attributes=vehicle_data.get("attributes", {}),
    )

    # Reconstruct comparables
    comps = [
        DutchComparable(
            price_eur=c["price_eur"],
            mileage_km=c["mileage_km"],
            year=c.get("year", 0),
            title=c.get("title", ""),
            listing_url=c.get("listingUrl", ""),
            source=c.get("source", "autoscout24"),
            location=c.get("location", ""),
        )
        for c in comparables
    ]

    valuation = await valuate_vehicle(vehicle, comps, api_key, model)
    return valuation_to_dict(valuation)


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================


@app.function(
    image=image,
        secrets=[apify_secret, openrouter_secret],
    timeout=300,
)
def calculate_import_margin(url: str) -> dict:
    """
    Main function: Calculate complete import margin for a German car listing.

    This orchestrates all the steps:
    1. Scrape the German listing
    2. Search Dutch market for comparables
    3. Calculate BPM
    4. Get AI valuation
    5. Calculate margin and recommendation
    """
    from constants import TOTAL_DEFAULT_IMPORT_COSTS, DEFAULT_IMPORT_COSTS

    start_time = datetime.now()
    request_id = str(uuid.uuid4())[:8]

    # Step 1: Scrape the vehicle
    scrape_result = scrape_vehicle_fn.remote(url)

    if not scrape_result["success"]:
        return {
            "success": False,
            "requestId": request_id,
            "error": scrape_result["error"],
        }

    vehicle_data = scrape_result["data"]

    # Step 2: Search Dutch market
    market_result = search_dutch_market_fn.remote(vehicle_data)

    # Step 3: Calculate BPM
    bpm_result = calculate_bpm_fn.remote(
        vehicle_data["co2_gkm"],
        vehicle_data["fuelType"],
        vehicle_data["firstRegistrationDate"],
    )

    # Step 4: AI Valuation
    valuation_result = valuate_vehicle_fn.remote(
        vehicle_data, market_result["comparables"]
    )

    # Step 5: Calculate costs and margin
    german_price = vehicle_data["price_eur"]
    rest_bpm = bpm_result["restBPM"]
    import_costs = TOTAL_DEFAULT_IMPORT_COSTS
    total_cost = german_price + rest_bpm + import_costs

    retail_price = valuation_result["estimatedRetailPrice"]
    quick_sale_price = valuation_result["estimatedQuickSalePrice"]

    margin = retail_price - total_cost
    safe_margin = quick_sale_price - total_cost
    margin_percentage = round((margin / total_cost) * 100, 1) if total_cost > 0 else 0

    recommendation = get_recommendation(margin, safe_margin)

    processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    return {
        "success": True,
        "requestId": request_id,
        "data": {
            "vehicle": vehicle_data,
            "pricing": {
                "germanPrice": german_price,
                "dutchMarketValue": retail_price,
                "dutchMarketValueRange": {
                    "low": quick_sale_price,
                    "high": round(retail_price * 1.05),
                },
                "comparablesCount": market_result["stats"]["count"],
                "sources": market_result.get("sources", ["autoscout24"]),
            },
            "bpm": bpm_result,
            "costs": {
                "germanPrice": german_price,
                "bpm": rest_bpm,
                "transport": DEFAULT_IMPORT_COSTS["transport"],
                "rdwInspection": DEFAULT_IMPORT_COSTS["rdw_inspection"],
                "licensePlates": DEFAULT_IMPORT_COSTS["license_plates"],
                "handlingFee": DEFAULT_IMPORT_COSTS["handling_fee"],
                "napCheck": DEFAULT_IMPORT_COSTS["nap_check"],
                "totalImportCosts": import_costs,
                "totalCost": round(total_cost, 2),
            },
            "result": {
                "margin": round(margin),
                "marginPercentage": margin_percentage,
                "safeMargin": round(safe_margin),
                "recommendation": recommendation,
            },
            "aiValuation": valuation_result,
            "comparables": market_result["comparables"][:10],
            "marketStats": market_result["stats"],
        },
        "meta": {
            "calculatedAt": datetime.now().isoformat(),
            "processingTimeMs": processing_time_ms,
        },
    }


# =============================================================================
# WEB ENDPOINTS
# =============================================================================


@app.function(
    image=image,
        secrets=[apify_secret, openrouter_secret],
    timeout=300,
)
@modal.fastapi_endpoint(method="POST", docs=True)
def analyze(body: dict) -> dict:
    """
    POST /analyze

    Analyze a German car listing and calculate import margin.

    Request body:
    {
        "url": "https://suchen.mobile.de/fahrzeuge/details.html?id=12345678"
    }

    Returns:
    - Vehicle details
    - BPM calculation
    - Dutch market comparables
    - AI valuation
    - Margin calculation
    - GO/CONSIDER/NO_GO recommendation
    """
    url = body.get("url")

    if not url:
        return {
            "success": False,
            "error": {
                "type": "VALIDATION_ERROR",
                "message": "URL is required",
            },
        }

    return calculate_import_margin.remote(url)


@app.function(
    image=image,
        timeout=10,
)
@modal.fastapi_endpoint(method="GET", docs=True)
def health() -> dict:
    """
    GET /health

    Health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "driving-passion",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.function(
    image=image,
        timeout=30,
)
@modal.fastapi_endpoint(method="POST", docs=True)
def bpm(body: dict) -> dict:
    """
    POST /bpm

    Calculate BPM only (without full analysis).

    Request body:
    {
        "co2_gkm": 209,
        "fuel_type": "petrol",
        "first_registration_date": "2014-04-01"
    }
    """
    from datetime import datetime
    from bpm_calculator import calculate_bpm, bpm_to_dict

    co2 = body.get("co2_gkm")
    fuel = body.get("fuel_type", "petrol")
    reg_date_str = body.get("first_registration_date")

    if not co2 or not reg_date_str:
        return {
            "success": False,
            "error": {
                "type": "VALIDATION_ERROR",
                "message": "co2_gkm and first_registration_date are required",
            },
        }

    try:
        reg_date = datetime.fromisoformat(reg_date_str)
        result = calculate_bpm(co2, fuel, reg_date)
        return {
            "success": True,
            "data": bpm_to_dict(result),
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "type": "CALCULATION_ERROR",
                "message": str(e),
            },
        }


# =============================================================================
# LOCAL TESTING
# =============================================================================


@app.local_entrypoint()
def main(url: str = ""):
    """
    Local entrypoint for testing.

    Usage:
        modal run app.py --url "https://suchen.mobile.de/fahrzeuge/details.html?id=12345"
    """
    if not url:
        print("Usage: modal run app.py --url <mobile.de URL>")
        print("\nExample:")
        print('  modal run app.py --url "https://suchen.mobile.de/fahrzeuge/details.html?id=446136631"')
        return

    print(f"Analyzing: {url}")
    print("-" * 60)

    result = calculate_import_margin.remote(url)

    if not result["success"]:
        print(f"Error: {result['error']}")
        return

    data = result["data"]
    vehicle = data["vehicle"]
    costs = data["costs"]
    res = data["result"]

    print(f"\n{vehicle['make']} {vehicle['model']} ({vehicle['year']})")
    print(f"Kilometerstand: {vehicle['mileage_km']:,} km")
    print(f"Duitse prijs: €{vehicle['price_eur']:,}")
    print()
    print("KOSTEN:")
    print(f"  Duitse prijs:    €{costs['germanPrice']:,}")
    print(f"  BPM:             €{costs['bpm']:,}")
    print(f"  Import kosten:   €{costs['totalImportCosts']:,}")
    print(f"  ─────────────────────")
    print(f"  TOTAAL:          €{costs['totalCost']:,}")
    print()
    print(f"NL Marktwaarde:    €{data['pricing']['dutchMarketValue']:,}")
    print()
    print(f"MARGE:             €{res['margin']:,} ({res['marginPercentage']}%)")
    print(f"Veilige marge:     €{res['safeMargin']:,}")
    print()
    print(f"ADVIES:            {res['recommendation']}")
