# Test Checklist - Import Margin Calculator

## Pre-Test Setup

- [ ] n8n is gestart op VPS (poort 5678)
- [ ] Apify API credentials geconfigureerd in n8n
- [ ] Alle 3 workflows geïmporteerd en ACTIVE
- [ ] Webhook URLs genoteerd

## Test 1: BPM Berekening (Offline)

```bash
node test-bpm-quick.js
```

**Expected:**
- 4 test cases slagen
- BMW 320d Rest-BPM: ~€2.294
- Tesla Model 3 Rest-BPM: ~€341 (electric)

## Test 2: Manual Input via Webhook

```bash
curl -X POST http://YOUR_VPS_IP:5678/webhook/calculate-margin \
  -H "Content-Type: application/json" \
  -d '{
    "make": "BMW",
    "model": "320d",
    "year": 2021,
    "mileage_km": 45000,
    "price_eur": 28500,
    "fuelType": "diesel",
    "transmission": "automatic",
    "co2_gkm": 118,
    "firstRegistrationDate": "2021-03-01"
  }'
```

**Expected Response:**
```json
{
  "vehicle": {
    "description": "2021 BMW 320d",
    "ageMonths": 46
  },
  "bpm": {
    "restBPM": 2294
  },
  "result": {
    "margin": 3000-4000,
    "recommendation": "GO" or "CONSIDER"
  }
}
```

**Check:**
- [ ] Response status: 200 OK
- [ ] BPM restBPM is ~€2.294
- [ ] Dutch market value > 0
- [ ] Margin is calculated
- [ ] Recommendation is GO/CONSIDER/NO_GO

## Test 3: German Listing Parser (Sub-workflow)

```bash
curl -X POST http://YOUR_VPS_IP:5678/webhook/parse-german-listing \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.mobile.de/auto/bmw-3er/318d-sedan-sport-line-navi-led-pdc-17/366956789.html"
  }'
```

**Expected:**
- [ ] Apify scraper wordt gestart
- [ ] Data wordt geparset (make, model, year, mileage, price, co2)
- [ ] Response bevat vehicle data

**Troubleshooting:**
- Als dit faalt: Check Apify credentials in n8n
- Als Apify quota overschreden: Wacht tot volgende maand of upgrade

## Test 4: Dutch Market Search (Sub-workflow)

```bash
curl -X POST http://YOUR_VPS_IP:5678/webhook/search-dutch-market \
  -H "Content-Type: application/json" \
  -d '{
    "make": "BMW",
    "model": "320d",
    "year": 2021,
    "mileage_km": 45000,
    "fuelType": "diesel",
    "transmission": "automatic"
  }'
```

**Expected:**
- [ ] Marktplaats wordt doorzocht
- [ ] 5-20 comparables gevonden
- [ ] Average price berekend
- [ ] Response bevat { comparables: [...], statistics: {...} }

**Troubleshooting:**
- Als geen comparables: Probeer populairder model (VW Golf, BMW 3-serie)
- Als Marktplaats blokkeert: Gebruik Apify scraper fallback

## Test 5: Frontend Interface

1. Start lokale server:
```bash
python3 -m http.server 3000 --directory public
```

2. Open: http://localhost:3000

3. Test Manual Input tab:
   - [ ] Vul BMW 320d in (zie Test 2 data)
   - [ ] Klik "Calculate Margin"
   - [ ] Loading spinner verschijnt
   - [ ] Results tonen:
     - Recommendation (kleur groen/geel/rood)
     - Margin bedrag
     - BPM breakdown
     - Comparables lijst

4. Test URL Input tab (optioneel, vereist Apify):
   - [ ] Plak Mobile.de URL
   - [ ] Klik "Calculate Margin"
   - [ ] Results tonen

## Test 6: End-to-End Test Cases

### Test Case A: Profitable Import (GO)
```json
{
  "make": "BMW",
  "model": "320d",
  "year": 2020,
  "mileage_km": 60000,
  "price_eur": 22000,
  "fuelType": "diesel",
  "transmission": "automatic",
  "co2_gkm": 118,
  "firstRegistrationDate": "2020-01-01"
}
```
**Expected:** Margin >€2.500, Recommendation: GO

### Test Case B: Marginal Import (CONSIDER)
```json
{
  "make": "Volkswagen",
  "model": "Golf",
  "year": 2019,
  "mileage_km": 80000,
  "price_eur": 16000,
  "fuelType": "petrol",
  "transmission": "manual",
  "co2_gkm": 110,
  "firstRegistrationDate": "2019-06-01"
}
```
**Expected:** Margin €1.000-2.500, Recommendation: CONSIDER

### Test Case C: Unprofitable Import (NO-GO)
```json
{
  "make": "Mercedes-Benz",
  "model": "C-Class",
  "year": 2018,
  "mileage_km": 120000,
  "price_eur": 24000,
  "fuelType": "diesel",
  "transmission": "automatic",
  "co2_gkm": 145,
  "firstRegistrationDate": "2018-03-01"
}
```
**Expected:** Margin <€1.000, Recommendation: NO-GO

## Troubleshooting

### Error: "Workflow not found"
- Check dat alle workflows ACTIVE staan in n8n
- Verifieer webhook paths: `/webhook/calculate-margin`, etc.

### Error: "Apify quota exceeded"
- Wacht tot volgende maand (free tier reset)
- Of upgrade naar Apify paid plan
- Of gebruik alleen manual input (werkt zonder Apify)

### Error: "No comparables found"
- Kies populairder merk/model (BMW, VW, Audi, Mercedes)
- Verbreed zoekbereik (±20% mileage in plaats van ±10%)
- Check Marktplaats API toegang

### Error: "CORS blocked"
- Voeg CORS headers toe aan n8n webhook response
- Of gebruik reverse proxy (nginx/Caddy) met CORS

### BPM calculation lijkt incorrect
- Verifieer CO2 waarde (moet WLTP zijn, niet NEDC)
- Check vehicle age calculation
- Vergelijk met officiele BPM calculator: https://www.belastingdienst.nl/

## Performance Benchmarks

- Manual input calculation: **5-15 seconden**
- URL parsing + calculation: **20-40 seconden** (door Apify)
- Dutch market search: **10-20 seconden**

## Sign-Off

- [ ] Alle unit tests slagen
- [ ] Manual input workflow werkt
- [ ] Frontend toont correcte results
- [ ] BPM berekeningen kloppen (±5%)
- [ ] Recommendations zijn logisch

---

**Ready for Production:** ✅ / ❌

**Notes:**
_Voeg hier je testnotities toe_
