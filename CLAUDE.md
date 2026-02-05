# Driving Passion - Auto Import Calculator

## Project Overzicht

Dit is een auto import calculator die berekent of het winstgevend is om een auto uit Duitsland te importeren naar Nederland. De tool analyseert Duitse advertenties (mobile.de en autoscout24.de), berekent BPM, zoekt vergelijkbare auto's in Nederland, en geeft een AI-gestuurde taxatie.

## Architectuur

### Backend: Modal (PRIMAIR)

De backend draait op **Modal** (modal.com). Dit is de primaire en enige actieve backend.

**Endpoints:**
- `POST /analyze` - Analyseer een Duitse advertentie
- `GET /health` - Health check
- `POST /bpm` - BPM berekening alleen

**Modal App URL:** https://modal.com/apps/novaitec/main/deployed/driving-passion

**Belangrijke bestanden:**
- `modal-app/app.py` - Hoofdapplicatie en endpoints
- `modal-app/constants.py` - Configuratie (BPM tarieven, Apify actors, AI model)
- `modal-app/scrapers.py` - Scraping logica voor mobile.de en autoscout24.de
- `modal-app/bpm_calculator.py` - BPM berekening (2026 tarieven)
- `modal-app/dutch_market.py` - Nederlandse markt zoeken
- `modal-app/valuation.py` - AI taxatie via OpenRouter

### Frontend: Next.js (Vercel)

- Directory: `web/`
- Draait op Vercel
- Roept de Modal API aan

## Secrets & Credentials

Secrets worden beheerd via Modal:

```bash
# Apify secret (voor scraping)
modal secret create apify-secret APIFY_TOKEN=<token>

# OpenRouter secret (voor AI taxatie)
modal secret create openrouter-secret OPENROUTER_API_KEY=<key>
```

**Apify Account:**
- User ID: n7wcUu8LR7TshyTQO

## Deployment

### Modal App deployen:
```bash
cd modal-app
python3 -m modal deploy app.py
```

### Vercel (frontend):
Push naar main branch, Vercel deployed automatisch.

## Ondersteunde Bronnen

### Duitse advertenties (input):
- **mobile.de** - ❌ **NIET WERKEND** (Apify actor discontinued)
- **AutoScout24** (alle domeinen) - ✅ Direct HTTP scraping
  - **autoscout24.de** (Duits)
  - **autoscout24.nl** (Nederlands)
  - **autoscout24.be** (Belgisch)
  - **autoscout24.com** (Internationaal)

**Scraping Strategy:**
- **AutoScout24 (alle domeinen)**: Direct HTTP + JSON extraction (__NEXT_DATA__) - **WERKT**
  - Ondersteunt .de, .nl, .be, .com en alle andere AutoScout24 domeinen
  - Automatische detectie van domain-specifieke structuren (direct scraping vs Apify format)
  - Multilingual support (Duits, Nederlands, etc.) via genormaliseerde parsing
- **Mobile.de**: Apify fallback beschikbaar maar actor discontinued - **WERKT NIET**
- **Alternative voor mobile.de**: Selenium scraper beschikbaar in `selenium_scrapers.py` (niet geactiveerd)
  - Gebruikt undetected-chromedriver om Akamai Bot Manager te omzeilen
  - Vereist Xvfb virtual display voor Modal deployment
  - Lokaal getest en werkend
  - Activatie vereist: Xvfb setup + integratie in app.py
- **Cost Savings**: ~€120-180/year (AutoScout24 direct scraping)
- **Configuration**: `USE_DIRECT_SCRAPING = True` in [constants.py](modal-app/constants.py:72)
- **Performance**: Direct scraping ~10-15s vs Apify ~30s

### Nederlandse markt (vergelijking):
- **AutoScout24 NL** - Direct scraping via httpx
- **AutoTrack.nl** - Direct scraping via httpx (eigendom AutoScout24, Dec 2025)
- **Gaspedaal.nl** - Direct scraping via httpx (meta-aggregator, eigendom AutoScout24)
- **Occasions.nl** - Direct scraping via httpx (WordPress platform)
- **Marktplaats.nl** - Via Apify actor `ivanvs~marktplaats-scraper`

Alle 5 bronnen worden parallel doorzocht. Resultaten worden gededupliceerd op basis van URL (belangrijk voor Gaspedaal die aggregeert van andere sites) en gesorteerd op prijs.

## Apify Actors

### Duitse bronnen (input):
- **mobile.de:** `3x1t~mobile-de-scraper` - ❌ **DISCONTINUED** (niet meer beschikbaar)
- **autoscout24.de:** `3x1t~autoscout24-scraper-ppr` (Pay-per-result, fallback only)

**Status:**
- **Mobile.de**: Apify actor discontinued, niet werkend. Selenium alternative beschikbaar in `selenium_scrapers.py`
- **AutoScout24.de**: Direct HTTP scraping werkt (primary). Apify als fallback.

**Fallback Strategy (AutoScout24 only):**
Apify wordt alleen gebruikt als:
- Direct scraping is blocked (403)
- Rate limited (429)
- Parse errors occur
- `USE_DIRECT_SCRAPING` is set to `False`

Beide actors zijn/waren van ontwikkelaar (3x1t).

### Nederlandse bronnen (vergelijking):
- **marktplaats.nl:** `ivanvs~marktplaats-scraper` (Pay-per-event)

Om de Marktplaats actor te gebruiken, ga naar https://apify.com/ivanvs/marktplaats-scraper en klik "Try for free".

## AI Model

- Provider: OpenRouter
- Model: `anthropic/claude-sonnet-4`

## BPM Tarieven

Gebaseerd op 2026 Belastingdienst forfaitaire tabel. Zie `modal-app/constants.py` voor alle tarieven.

## Veelvoorkomende Problemen

### Direct scraping wordt geblokkeerd (403/429)
- Het systeem valt automatisch terug op Apify actors
- Check Modal logs: `modal logs driving-passion` voor details
- Als dit vaak gebeurt, overweeg `USE_DIRECT_SCRAPING = False` in constants.py

### Direct scraping werkt niet (parse errors)
- Het systeem valt automatisch terug op Apify actors
- Website structuur kan gewijzigd zijn (JSON paden)
- Check Modal logs voor "PARSE_ERROR" berichten
- Tijdelijk disablen: `USE_DIRECT_SCRAPING = False` in constants.py

### AI taxatie fout "model not found"
- Controleer of `DEFAULT_AI_MODEL` in constants.py correct is
- Moet zijn: `anthropic/claude-sonnet-4` (zonder datum suffix)

### AutoScout24 scraping faalt (alle domeinen: .de, .nl, .be, .com)
- **Ondersteunde domeinen**: autoscout24.de, autoscout24.nl, autoscout24.be, autoscout24.com
- Direct scraping: Check Modal logs voor "AUTOSCOUT24.DE DIRECT" errors
- De scraper detecteert automatisch het domain en gebruikt de juiste parsing strategie
- Apify fallback (alleen .de): Controleer of de Apify actor `3x1t~autoscout24-scraper-ppr` beschikbaar is
- Ga naar https://apify.com/3x1t/autoscout24-scraper-ppr en klik "Try for free" (indien Apify nodig)

### Mobile.de scraping faalt
- **Status**: Apify actor `3x1t~mobile-de-scraper` is DISCONTINUED
- **Huidige situatie**: Mobile.de scraping werkt NIET
- **Oplossing beschikbaar**: Selenium scraper in `selenium_scrapers.py`
  - Gebruikt undetected-chromedriver om Akamai Bot Manager te omzeilen
  - Lokaal getest en werkend
  - **Vereist voor Modal deployment:**
    1. Xvfb virtual display in Modal image
    2. Chrome/Chromium + ChromeDriver dependencies
    3. Integratie in `app.py`
  - **Setup instructies**: Zie "Mobile.de Selenium Scraper Activeren" sectie hieronder

### Marktplaats resultaten ontbreken
- Controleer of de actor `ivanvs~marktplaats-scraper` is toegevoegd aan je Apify account
- Ga naar https://apify.com/ivanvs/marktplaats-scraper en klik "Try for free"
- Check Modal logs: `modal logs driving-passion`

### Apify fout (fallback fails)
- Controleer of de Modal secret `apify-secret` correct is ingesteld
- Controleer Apify account credits
- Als credits op zijn, werkt alleen direct scraping (mobile.de en autoscout24.de)

## Flow Diagram

```
Duitse advertentie (mobile.de / autoscout24.de)
                    │
                    ▼
         ┌─────────────────────┐
         │   Scrape vehicle    │
         │  (Direct HTTP +     │
         │   Apify fallback)   │
         └──────────┬──────────┘
                    │
        ┌───────────┴───────────────────────────────┐
        │     Dutch Market Search (5 platforms)     │
        │         Parallel + Deduplication          │
        └───────────┬───────────────────────────────┘
                    │
        ┌───────────┼───────────┬──────────┬────────┐
        ▼           ▼           ▼          ▼        ▼
  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐ ┌────────┐
  │AutoScout│ │AutoTrack│ │Gaspedaal│ │Occas.│ │Markt-  │
  │24 NL    │ │ (HTTP)  │ │ (HTTP)  │ │(HTTP)│ │plaats  │
  │ (HTTP)  │ │         │ │  meta   │ │  WP  │ │(Apify) │
  └────┬────┘ └────┬────┘ └────┬────┘ └───┬──┘ └───┬────┘
       │           │           │          │        │
       └───────────┴───────────┴──────────┴────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  AI Taxatie   │
                   │ (OpenRouter)  │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │ BPM + Marge   │
                   │  berekening   │
                   └───────────────┘

Scraping Strategy Details:
┌──────────────────────────────────────────────────┐
│  German Sites (mobile.de / autoscout24.de)       │
├──────────────────────────────────────────────────┤
│  AutoScout24.de:                                 │
│  1. Try Direct HTTP Scraping (10-15s, FREE)      │
│     - Extract __NEXT_DATA__                      │
│     - If SUCCESS → Return data                   │
│     - If LISTING_OFFLINE → Return error          │
│     - If OTHER ERROR → Try Apify fallback        │
│                                                   │
│  2. Apify Fallback (30s, PAID)                   │
│     - 3x1t~autoscout24-scraper-ppr               │
│                                                   │
│  Mobile.de: ❌ NOT WORKING                       │
│  - Apify actor discontinued                      │
│  - Selenium alternative available (not active)   │
└──────────────────────────────────────────────────┘
```

## Mobile.de Selenium Scraper Activeren (Optioneel)

De Selenium scraper in `selenium_scrapers.py` is klaar maar niet geïntegreerd. Om te activeren:

### 1. Modal Image Dependencies
Update `app.py` image configuratie:
```python
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install([
        "chromium",
        "chromium-driver",
        "xvfb",  # Virtual display
        "fonts-liberation",
        "libnss3",
        "libatk-bridge2.0-0",
    ])
    .pip_install([
        "undetected-chromedriver",
        "selenium",
        "xvfbwrapper",  # Python wrapper voor Xvfb
    ])
)
```

### 2. Integratie in app.py
```python
from selenium_scrapers import scrape_mobile_de_selenium

# In scrape_vehicle() functie:
if "mobile.de" in url:
    result = scrape_mobile_de_selenium(url)
    return result
```

### 3. Xvfb Setup in selenium_scrapers.py
```python
from xvfbwrapper import Xvfb

def scrape_mobile_de_selenium(url: str) -> ScrapeResult:
    vdisplay = Xvfb(width=1920, height=1080)
    vdisplay.start()

    try:
        # Normal scraping code...
    finally:
        vdisplay.stop()
```

### 4. Test & Deploy
```bash
# Test lokaal (vereist Xvfb):
pip install xvfbwrapper
python3 modal-app/test_selenium_scraper.py

# Deploy naar Modal:
cd modal-app
python3 -m modal deploy app.py
```

**Verwachte kosten**: €0 (geen Apify), wel hogere Modal compute kosten door browser overhead
