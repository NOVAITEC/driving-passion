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
- mobile.de
- autoscout24.de

### Nederlandse markt (vergelijking):
- AutoScout24 NL (direct scraping)
- Marktplaats.nl (via Apify actor)

Beide bronnen worden parallel doorzocht voor betere marktdekking.

## Apify Actors

### Duitse bronnen (input):
- **mobile.de:** `3x1t~mobile-de-scraper-ppr` (Pay-per-result)
- **autoscout24.de:** `3x1t~autoscout24-scraper-ppr` (Pay-per-result)

Beide actors zijn van dezelfde ontwikkelaar (3x1t).

### Nederlandse bronnen (vergelijking):
- **marktplaats.nl:** `ivanvs~marktplaats-scraper` (Pay-per-event)

Om de Marktplaats actor te gebruiken, ga naar https://apify.com/ivanvs/marktplaats-scraper en klik "Try for free".

## AI Model

- Provider: OpenRouter
- Model: `anthropic/claude-sonnet-4`

## BPM Tarieven

Gebaseerd op 2026 Belastingdienst forfaitaire tabel. Zie `modal-app/constants.py` voor alle tarieven.

## Veelvoorkomende Problemen

### AI taxatie fout "model not found"
- Controleer of `DEFAULT_AI_MODEL` in constants.py correct is
- Moet zijn: `anthropic/claude-sonnet-4` (zonder datum suffix)

### AutoScout24 scraping faalt
- Controleer of de Apify actor `3x1t~autoscout24-scraper-ppr` beschikbaar is in je account
- Ga naar https://apify.com/3x1t/autoscout24-scraper-ppr en klik "Try for free"

### Marktplaats resultaten ontbreken
- Controleer of de actor `ivanvs~marktplaats-scraper` is toegevoegd aan je Apify account
- Ga naar https://apify.com/ivanvs/marktplaats-scraper en klik "Try for free"
- Check Modal logs: `modal logs driving-passion`

### Apify fout
- Controleer of de Modal secret `apify-secret` correct is ingesteld
- Controleer Apify account credits

## Flow Diagram

```
Duitse advertentie (mobile.de / autoscout24.de)
                    │
                    ▼
            ┌───────────────┐
            │ Scrape vehicle│
            │   via Apify   │
            └───────┬───────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│ AutoScout24 NL│       │  Marktplaats  │
│   (direct)    │       │  (via Apify)  │
└───────┬───────┘       └───────┬───────┘
        │                       │
        └───────────┬───────────┘
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
```
