"""
Constants for the Driving Passion Auto Import Calculator.
BPM rates based on 2026 Belastingdienst forfaitaire tabel.
"""

# =============================================================================
# BPM 2026 TARIEVEN
# =============================================================================

# CO2 tarief schijven (g/km)
CO2_BRACKETS = [
    {"min": 0, "max": 79, "rate": 0, "base": 667},
    {"min": 80, "max": 124, "rate": 6.68, "base": 667},
    {"min": 125, "max": 169, "rate": 67.40, "base": 968},
    {"min": 170, "max": 199, "rate": 159.61, "base": 4001},
    {"min": 200, "max": float("inf"), "rate": 490.91, "base": 8789},
]

# Diesel toeslag per g/km boven 70 g/km
DIESEL_SURCHARGE_RATE = 109.87
DIESEL_SURCHARGE_THRESHOLD = 70

# =============================================================================
# FORFAITAIRE AFSCHRIJVINGSTABEL 2026
# =============================================================================

DEPRECIATION_TABLE = [
    {"min_months": 0, "max_months": 3, "percentage": 0},
    {"min_months": 4, "max_months": 6, "percentage": 24},
    {"min_months": 7, "max_months": 9, "percentage": 33},
    {"min_months": 10, "max_months": 18, "percentage": 42},
    {"min_months": 19, "max_months": 24, "percentage": 49},
    {"min_months": 25, "max_months": 36, "percentage": 56},
    {"min_months": 37, "max_months": 48, "percentage": 63},
    {"min_months": 49, "max_months": 60, "percentage": 70},
    {"min_months": 61, "max_months": 72, "percentage": 76},
    {"min_months": 73, "max_months": 84, "percentage": 81},
    {"min_months": 85, "max_months": 96, "percentage": 85},
    {"min_months": 97, "max_months": 108, "percentage": 88},
    {"min_months": 109, "max_months": 120, "percentage": 90},
    {"min_months": 121, "max_months": float("inf"), "percentage": 92},
]

# =============================================================================
# IMPORT KOSTEN
# =============================================================================

DEFAULT_IMPORT_COSTS = {
    "transport": 450,
    "rdw_inspection": 85,
    "license_plates": 50,
    "handling_fee": 200,
    "nap_check": 12.95,
}

TOTAL_DEFAULT_IMPORT_COSTS = sum(DEFAULT_IMPORT_COSTS.values())

# =============================================================================
# MARGE DREMPELS
# =============================================================================

MARGIN_THRESHOLDS = {
    "go": 2500,        # Minimale marge voor GO advies
    "consider": 1000,  # Minimale marge voor CONSIDER advies
    "safe_margin": 500,  # Minimale veilige marge voor GO advies
}

# =============================================================================
# SCRAPER CONFIGURATIE
# =============================================================================

APIFY_ACTORS = {
    "mobile_de": "3x1t~mobile-de-scraper-ppr",
    "autoscout24": "3x1t~autoscout24-scraper-ppr",  # Same developer as mobile.de
    "marktplaats": "ivanvs~marktplaats-scraper",  # Dutch marketplace
}

# =============================================================================
# AI CONFIGURATIE
# =============================================================================

DEFAULT_AI_MODEL = "anthropic/claude-sonnet-4"
