# Import Margin Calculator - Driving Passion

Cross-Border Vehicle Arbitrage Tool for calculating import margins on vehicles purchased in Germany and sold in the Netherlands.

## Features

- Parse vehicle listings from Mobile.de and AutoScout24
- Search Dutch marketplaces (Marktplaats) for comparable vehicles
- Calculate Dutch BPM tax using 2026 forfaitaire tabel method
- Determine import profitability with Go/Consider/No-Go recommendations

## Project Structure

```
driving-passion/
├── public/
│   └── index.html          # Frontend interface
├── src/
│   └── lib/
│       ├── bpm-calculator.ts      # BPM calculation logic
│       └── margin-calculator.ts   # Margin calculation logic
├── workflows/
│   ├── german-parser.json         # n8n: Parse German listings
│   ├── dutch-market-search.json   # n8n: Search Dutch market
│   └── main-orchestrator.json     # n8n: Main workflow
├── package.json
└── README.md
```

## Setup Instructions

### 1. Install n8n on your VPS

```bash
# Using Docker (recommended)
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  -e N8N_WEBHOOK_URL=https://your-domain.com \
  n8nio/n8n

# Or using npm
npm install -g n8n
n8n start
```

### 2. Configure n8n

1. Access n8n at `http://your-server:5678`
2. Set up credentials:
   - **Apify API**: Get token from https://apify.com/account/integrations
3. Import workflows:
   - Go to Workflows → Import
   - Import each JSON file from the `workflows/` folder
4. Activate all three workflows

### 3. Configure Environment Variables

Set these in n8n:
```
N8N_WEBHOOK_URL=https://your-domain.com
```

### 4. Start the Frontend

```bash
# Install dependencies
npm install

# Start local server
npm run dev
```

Then open http://localhost:3000

### 5. Update API URL

Edit `public/index.html` and update the `API_URL` variable:
```javascript
const API_URL = 'https://your-domain.com/webhook/calculate-margin';
```

## Usage

### Via URL Input

1. Copy a vehicle listing URL from Mobile.de or AutoScout24
2. Paste it in the URL input field
3. Click "Calculate Margin"

### Via Manual Input

1. Switch to "Manual Input" tab
2. Fill in vehicle details:
   - Make, Model, Year
   - Mileage, Price
   - Fuel type, Transmission
   - CO2 emissions (WLTP)
   - First registration date
3. Click "Calculate Margin"

## BPM Calculation

The tool uses the **Forfaitaire Tabel** method for BPM calculation:

### 2026 CO2 Tariffs
| CO2 Range (g/km) | Rate |
|------------------|------|
| 0 (Electric) | €667 fixed |
| 1-79 | €667 base only |
| 80-124 | €6.68/g |
| 125-169 | €67.40/g |
| 170-199 | €159.61/g |
| 200+ | €490.91/g |

### Diesel Surcharge
€109.87 per g/km above 70 g/km

### Depreciation Table
| Age (months) | Depreciation |
|--------------|-------------|
| 0-3 | 0% |
| 4-6 | 24% |
| 7-9 | 33% |
| 10-18 | 42% |
| 19-24 | 49% |
| 25-36 | 56% |
| 37-48 | 63% |
| 49-60 | 70% |
| 61-72 | 76% |
| 73-84 | 81% |
| 85-96 | 85% |
| 97-108 | 88% |
| 109-120 | 90% |
| 120+ | 92% |

## Default Import Costs

| Item | Amount |
|------|--------|
| Transport | €450 |
| RDW Inspection | €85 |
| License Plates | €50 |
| Handling Fee | €200 |
| NAP Check | €12.95 |
| **Total** | **€797.95** |

## Recommendation Thresholds

- **GO** (Green): Margin ≥ €2,500
- **CONSIDER** (Yellow): Margin €1,000 - €2,499
- **NO-GO** (Red): Margin < €1,000

## API Reference

### POST /webhook/calculate-margin

#### Request (URL mode)
```json
{
  "url": "https://www.mobile.de/..."
}
```

#### Request (Manual mode)
```json
{
  "make": "BMW",
  "model": "320d",
  "year": 2021,
  "mileage_km": 45000,
  "price_eur": 28500,
  "fuelType": "diesel",
  "transmission": "automatic",
  "co2_gkm": 118,
  "firstRegistrationDate": "2021-03-01"
}
```

#### Response
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
  "costs": {
    "totalCost": 31609
  },
  "result": {
    "margin": 3391,
    "marginPercentage": 10.7,
    "recommendation": "GO"
  }
}
```

## Future Improvements

- [ ] Autotelex B2B integration for koerslijst method
- [ ] Historical price tracking
- [ ] Batch processing for multiple vehicles
- [ ] Mobile app for on-the-go calculations
- [ ] Alert system when margin thresholds are met

## Support

For issues or questions, contact Driving Passion.

## License

Private - Driving Passion B.V.
