"""
Constants for the Driving Passion Auto Import Calculator.
BPM rates based on 2026 Belastingdienst forfaitaire tabel.
"""

# =============================================================================
# BPM 2026 TARIEVEN
# =============================================================================

# CO2 tarief schijven (g/km) - Officiële 2026 tarieven
# Bron: https://www.belastingdienst.nl/wps/wcm/connect/nl/bpm/content/personenauto-bpm-tarief-berekenen
# Formule: (CO2 - threshold) * rate + base
# threshold = "kolom 1" uit de officiële tabel (de aftrekwaarde)
CO2_BRACKETS = [
    {"min": 0, "max": 77, "threshold": 0, "rate": 2, "base": 687},
    {"min": 78, "max": 100, "threshold": 77, "rate": 82, "base": 841},
    {"min": 101, "max": 139, "threshold": 100, "rate": 181, "base": 2727},
    {"min": 140, "max": 155, "threshold": 139, "rate": 297, "base": 9786},
    {"min": 156, "max": float("inf"), "threshold": 155, "rate": 594, "base": 14538},
]

# Diesel toeslag - Officiële 2026 tarieven
# Bron: https://www.belastingdienst.nl/wps/wcm/connect/nl/bpm/content/personenauto-bpm-tarief-berekenen
# Formule: (CO2 - 69) × €114,83 voor auto's met CO2 > 70 g/km
# Let op: drempel is >70 (dus vanaf 71), maar aftrek is 69!
DIESEL_SURCHARGE_RATE = 114.83
DIESEL_SURCHARGE_THRESHOLD = 70  # Toeslag geldt bij CO2 > 70
DIESEL_SURCHARGE_SUBTRACT = 69   # Maar de formule trekt 69 af

# =============================================================================
# FORFAITAIRE AFSCHRIJVINGSTABEL 2026
# =============================================================================
# Officiële methode: Basispercentage + maandelijkse opslag
# Bron: https://www.belastingdienst.nl/wps/wcm/connect/nl/bpm/content/bpm-afschrijving-koerslijst-taxatierapport-forfaitaire-tabel
#
# Formule: afschrijving = base_percentage + (maanden_in_periode * monthly_addition)
# waarbij maanden_in_periode = maanden sinds start van de periode

DEPRECIATION_TABLE = [
    {"min_months": 0, "max_months": 1, "base_percentage": 0, "monthly_addition": 12},
    {"min_months": 1, "max_months": 3, "base_percentage": 12, "monthly_addition": 4},
    {"min_months": 3, "max_months": 5, "base_percentage": 20, "monthly_addition": 3.5},
    {"min_months": 5, "max_months": 9, "base_percentage": 27, "monthly_addition": 1.5},
    {"min_months": 9, "max_months": 18, "base_percentage": 33, "monthly_addition": 1},
    {"min_months": 18, "max_months": 30, "base_percentage": 42, "monthly_addition": 0.75},
    {"min_months": 30, "max_months": 42, "base_percentage": 51, "monthly_addition": 0.5},
    {"min_months": 42, "max_months": 54, "base_percentage": 57, "monthly_addition": 0.42},
    {"min_months": 54, "max_months": 66, "base_percentage": 62, "monthly_addition": 0.42},
    {"min_months": 66, "max_months": 78, "base_percentage": 67, "monthly_addition": 0.42},
    {"min_months": 78, "max_months": 90, "base_percentage": 72, "monthly_addition": 0.25},
    {"min_months": 90, "max_months": 102, "base_percentage": 75, "monthly_addition": 0.25},
    {"min_months": 102, "max_months": 114, "base_percentage": 78, "monthly_addition": 0.25},
    {"min_months": 114, "max_months": float("inf"), "base_percentage": 81, "monthly_addition": 0.19},
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

# Direct scraping toggle - set to False to disable direct HTTP scraping and use Apify only
USE_DIRECT_SCRAPING = True

APIFY_ACTORS = {
    "mobile_de": "3x1t~mobile-de-scraper",  # Rental version (not PPR) - supports detail pages
    "autoscout24": "3x1t~autoscout24-scraper-ppr",  # Same developer as mobile.de
    "marktplaats": "ivanvs~marktplaats-scraper",  # Dutch marketplace
}

# =============================================================================
# AI CONFIGURATIE
# =============================================================================

DEFAULT_AI_MODEL = "anthropic/claude-sonnet-4"
