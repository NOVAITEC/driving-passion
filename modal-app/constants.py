"""
Constants for the Driving Passion Auto Import Calculator.
BPM rates based on 2026 Belastingdienst forfaitaire tabel.
Includes historical regimes for keuzerecht (optimaal regime) berekening.
"""

# =============================================================================
# BPM 2026 TARIEVEN (huidige regime)
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
# HISTORISCHE BPM REGIMES (voor keuzerecht)
# =============================================================================
# Bij import mag de importeur kiezen welk belastingregime wordt toegepast:
# - Het regime van de Datum Eerste Toelating (DET)
# - Het regime van de Datum Aangifte (2026)
# - Elk tussenliggend regime
# Het laagste tarief mag worden gekozen (Artikel 110 VWEU).
#
# Formule per regime: (CO2 - threshold) * rate + base
# base = cumulatieve BPM aan einde vorige schijf (= vaste voet voor schijf 1)
#
# Bronnen:
# - 2026: Belastingdienst officieel (GEVERIFIEERD)
# - 2025: Belastingdienst/Promovendum (GEVERIFIEERD)
# - 2024: Belastingdienst/AutoRAI (GEVERIFIEERD)
# - 2023: Geschat via autonome vergroening (GESCHAT)
# - 2022: Geschat, gecorrigeerd met rijksfinancien data punt (GESCHAT)
# - 2021: Geschat via interpolatie (GESCHAT)
# - 2020: MrWheelson/Rijksoverheid - eerste WLTP jaar H2 (GEVERIFIEERD)

HISTORICAL_BPM_REGIMES = [
    {
        "year": 2020,
        "label": "2020 H2 (WLTP)",
        "measurement": "WLTP",
        "verified": True,
        "ev_exempt": True,
        "co2_brackets": [
            {"min": 0, "max": 90, "threshold": 0, "rate": 1, "base": 366},
            {"min": 91, "max": 116, "threshold": 90, "rate": 57, "base": 456},
            {"min": 117, "max": 162, "threshold": 116, "rate": 124, "base": 1938},
            {"min": 163, "max": 180, "threshold": 162, "rate": 204, "base": 7642},
            {"min": 181, "max": float("inf"), "threshold": 180, "rate": 408, "base": 11314},
        ],
        "diesel_threshold": 59,
        "diesel_subtract": 59,
        "diesel_rate": 89.95,
    },
    {
        "year": 2021,
        "label": "2021 (WLTP)",
        "measurement": "WLTP",
        "verified": False,
        "ev_exempt": True,
        "co2_brackets": [
            {"min": 0, "max": 88, "threshold": 0, "rate": 1, "base": 366},
            {"min": 89, "max": 113, "threshold": 88, "rate": 59, "base": 454},
            {"min": 114, "max": 158, "threshold": 113, "rate": 131, "base": 1929},
            {"min": 159, "max": 175, "threshold": 158, "rate": 222, "base": 7824},
            {"min": 176, "max": float("inf"), "threshold": 175, "rate": 443, "base": 11598},
        ],
        "diesel_threshold": 62,
        "diesel_subtract": 62,
        "diesel_rate": 93.0,
    },
    {
        "year": 2022,
        "label": "2022 (WLTP)",
        "measurement": "WLTP",
        "verified": False,
        "ev_exempt": True,
        "co2_brackets": [
            {"min": 0, "max": 85, "threshold": 0, "rate": 2, "base": 366},
            {"min": 86, "max": 109, "threshold": 85, "rate": 61, "base": 536},
            {"min": 110, "max": 154, "threshold": 109, "rate": 137, "base": 2000},
            {"min": 155, "max": 171, "threshold": 154, "rate": 239, "base": 8165},
            {"min": 172, "max": float("inf"), "threshold": 171, "rate": 479, "base": 12228},
        ],
        "diesel_threshold": 65,
        "diesel_subtract": 65,
        "diesel_rate": 98.0,
    },
    {
        "year": 2023,
        "label": "2023 (WLTP)",
        "measurement": "WLTP",
        "verified": False,
        "ev_exempt": True,
        "co2_brackets": [
            {"min": 0, "max": 83, "threshold": 0, "rate": 2, "base": 400},
            {"min": 84, "max": 107, "threshold": 83, "rate": 71, "base": 566},
            {"min": 108, "max": 149, "threshold": 107, "rate": 152, "base": 2270},
            {"min": 150, "max": 166, "threshold": 149, "rate": 257, "base": 8654},
            {"min": 167, "max": float("inf"), "threshold": 166, "rate": 514, "base": 13023},
        ],
        "diesel_threshold": 67,
        "diesel_subtract": 67,
        "diesel_rate": 102.0,
    },
    {
        "year": 2024,
        "label": "2024 (WLTP)",
        "measurement": "WLTP",
        "verified": True,
        "ev_exempt": True,
        "co2_brackets": [
            {"min": 0, "max": 80, "threshold": 0, "rate": 2, "base": 440},
            {"min": 81, "max": 104, "threshold": 80, "rate": 76, "base": 600},
            {"min": 105, "max": 145, "threshold": 104, "rate": 167, "base": 2424},
            {"min": 146, "max": 161, "threshold": 145, "rate": 274, "base": 9271},
            {"min": 162, "max": float("inf"), "threshold": 161, "rate": 549, "base": 13655},
        ],
        "diesel_threshold": 70,
        "diesel_subtract": 69,
        "diesel_rate": 106.07,
    },
    {
        "year": 2025,
        "label": "2025 (WLTP)",
        "measurement": "WLTP",
        "verified": True,
        "ev_exempt": False,
        "co2_brackets": [
            {"min": 0, "max": 79, "threshold": 0, "rate": 2, "base": 667},
            {"min": 80, "max": 101, "threshold": 79, "rate": 79, "base": 825},
            {"min": 102, "max": 141, "threshold": 101, "rate": 173, "base": 2563},
            {"min": 142, "max": 157, "threshold": 141, "rate": 284, "base": 9483},
            {"min": 158, "max": float("inf"), "threshold": 157, "rate": 568, "base": 14027},
        ],
        "diesel_threshold": 70,
        "diesel_subtract": 69,
        "diesel_rate": 109.87,
    },
    {
        "year": 2026,
        "label": "2026 (WLTP)",
        "measurement": "WLTP",
        "verified": True,
        "ev_exempt": False,
        "co2_brackets": [
            {"min": 0, "max": 77, "threshold": 0, "rate": 2, "base": 687},
            {"min": 78, "max": 100, "threshold": 77, "rate": 82, "base": 841},
            {"min": 101, "max": 139, "threshold": 100, "rate": 181, "base": 2727},
            {"min": 140, "max": 155, "threshold": 139, "rate": 297, "base": 9786},
            {"min": 156, "max": float("inf"), "threshold": 155, "rate": 594, "base": 14538},
        ],
        "diesel_threshold": 70,
        "diesel_subtract": 69,
        "diesel_rate": 114.83,
    },
]

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
