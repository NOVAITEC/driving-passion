# Import Margin Calculator - Driving Passion

Cross-Border Vehicle Arbitrage Tool for calculating import margins on vehicles purchased in Germany and sold in the Netherlands.

## Features

- Parse vehicle listings from Mobile.de and AutoScout24.de
- Search Dutch marketplaces (AutoScout24 NL, Marktplaats) for comparable vehicles
- Calculate Dutch BPM tax using 2026 forfaitaire tabel method
- AI-powered valuation via OpenRouter
- Determine import profitability with Go/Consider/No-Go recommendations

## Project Structure

```
driving-passion/
├── modal-app/           # Backend (Modal)
│   ├── app.py           # Main API endpoints
│   ├── scrapers.py      # German listing scrapers
│   ├── dutch_market.py  # Dutch market search
│   ├── bpm_calculator.py
│   ├── valuation.py     # AI valuation
│   └── constants.py     # Configuration
├── web/                 # Frontend (Next.js)
│   └── app/
├── CLAUDE.md            # Development documentation
└── README.md
```

## Setup

### Backend (Modal)

1. Install Modal CLI:
   ```bash
   pip install modal
   modal token new
   ```

2. Set up secrets:
   ```bash
   modal secret create apify-secret APIFY_TOKEN=<your_token>
   modal secret create openrouter-secret OPENROUTER_API_KEY=<your_key>
   ```

3. Deploy:
   ```bash
   cd modal-app
   python3 -m modal deploy app.py
   ```

### Frontend (Next.js)

1. Install dependencies:
   ```bash
   cd web
   npm install
   ```

2. Configure environment:
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your Modal API URL
   ```

3. Run locally:
   ```bash
   npm run dev
   ```

Production deployment is handled automatically via Vercel.

## API Reference

### POST /analyze

Analyze a German vehicle listing and calculate import margin.

**Request:**
```json
{
  "url": "https://www.mobile.de/..."
}
```

**Response:**
```json
{
  "vehicle": {
    "description": "2021 BMW 320d",
    "ageMonths": 46,
    "co2_gkm": 118
  },
  "pricing": {
    "germanPrice": 28500,
    "dutchMarketValue": 35000,
    "comparablesCount": 8
  },
  "bpm": {
    "grossBPM": 6245,
    "depreciationPercentage": 63,
    "restBPM": 2311
  },
  "result": {
    "margin": 3391,
    "recommendation": "GO"
  }
}
```

## BPM Calculation (2026)

### CO2 Tariffs
| CO2 Range (g/km) | Rate |
|------------------|------|
| 0 (Electric) | €667 fixed |
| 1-79 | €667 base |
| 80-124 | €6.68/g |
| 125-169 | €67.40/g |
| 170-199 | €159.61/g |
| 200+ | €490.91/g |

### Diesel Surcharge
€109.87 per g/km above 70 g/km

## Recommendation Thresholds

- **GO** (Green): Margin >= €2,500
- **CONSIDER** (Yellow): Margin €1,000 - €2,499
- **NO-GO** (Red): Margin < €1,000

## License

Private - Driving Passion B.V.
