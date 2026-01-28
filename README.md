# Import Margin Calculator - Driving Passion

Een tool voor auto-importeurs om snel te berekenen of het winstgevend is om een specifieke auto uit Duitsland te importeren naar Nederland.

## Wat doet deze tool?

De Import Margin Calculator analyseert een Duitse auto-advertentie en berekent automatisch:

1. **De totale importkosten** - inclusief aankoopprijs, BPM, transport en administratie
2. **De Nederlandse marktwaarde** - gebaseerd op vergelijkbare auto's op Marktplaats en AutoScout24 NL
3. **De verwachte winstmarge** - met een duidelijk GO / CONSIDER / NO-GO advies

### Het probleem dat het oplost

Auto's zijn in Duitsland vaak goedkoper dan in Nederland. Maar door de BPM (Belasting van Personenauto's en Motorrijwielen) en andere importkosten is het niet altijd winstgevend om te importeren. Deze tool maakt binnen seconden duidelijk of een specifieke deal de moeite waard is.

## Hoe werkt het?

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. INVOER                                                                  │
│     Gebruiker plakt een URL van Mobile.de of AutoScout24.de                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. SCRAPING                                                                │
│     De tool haalt automatisch alle voertuiggegevens op:                     │
│     • Merk, model, uitvoering                                               │
│     • Bouwjaar en kilometerstand                                            │
│     • Brandstoftype en transmissie                                          │
│     • CO2-uitstoot (WLTP)                                                   │
│     • Vraagprijs in Euro                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. BPM BEREKENING                                                          │
│     Berekent de Rest-BPM volgens de forfaitaire tabel 2026:                 │
│     • Bruto BPM op basis van CO2-uitstoot                                   │
│     • Diesel toeslag (indien van toepassing)                                │
│     • Afschrijving op basis van leeftijd voertuig                           │
│     • Resulteert in de te betalen Rest-BPM                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. NEDERLANDSE MARKT ANALYSE                                               │
│     Zoekt parallel op twee platforms naar vergelijkbare auto's:             │
│                                                                             │
│     AutoScout24 NL          Marktplaats.nl                                  │
│     ┌───────────┐           ┌───────────┐                                   │
│     │ Direct    │           │ Via Apify │                                   │
│     │ scraping  │           │ actor     │                                   │
│     └─────┬─────┘           └─────┬─────┘                                   │
│           │                       │                                         │
│           └───────────┬───────────┘                                         │
│                       ▼                                                     │
│              Vergelijkbare auto's met:                                      │
│              • Zelfde merk en model                                         │
│              • Vergelijkbaar bouwjaar (±1 jaar)                             │
│              • Vergelijkbare kilometerstand (±20%)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. AI TAXATIE                                                              │
│     Claude analyseert de gevonden vergelijkbare auto's en bepaalt:          │
│     • Realistische Nederlandse marktwaarde                                  │
│     • Betrouwbaarheid van de schatting                                      │
│     • Factoren die de prijs beïnvloeden                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. MARGE BEREKENING                                                        │
│                                                                             │
│     Totale kosten =  Duitse prijs                                           │
│                    + Rest-BPM                                               │
│                    + Transport (€450)                                       │
│                    + RDW keuring (€85)                                      │
│                    + Kentekenplaten (€50)                                   │
│                    + Handelingskosten (€200)                                │
│                    + NAP check (€12,95)                                     │
│                    ─────────────────────                                    │
│                    = Totale investering                                     │
│                                                                             │
│     Marge = Nederlandse marktwaarde - Totale investering                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7. ADVIES                                                                  │
│                                                                             │
│     🟢 GO        Marge ≥ €2.500    "Deze deal is winstgevend"               │
│     🟡 CONSIDER  Marge €1.000-2.499 "Overweeg, maar let op risico's"        │
│     🔴 NO-GO     Marge < €1.000    "Niet winstgevend genoeg"                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## BPM Berekening in Detail

### Wat is BPM?

BPM is een eenmalige belasting die betaald moet worden bij de eerste registratie van een auto in Nederland. Voor geïmporteerde auto's wordt de "Rest-BPM" berekend: de BPM die nog "over" is na afschrijving.

### CO2-tarieven 2026

De bruto BPM wordt berekend op basis van de CO2-uitstoot:

| CO2-uitstoot | Tarief | Toelichting |
|--------------|--------|-------------|
| 0 g/km | €667 vast | Elektrische voertuigen |
| 1-79 g/km | €667 basis | Zuinige auto's (hybride) |
| 80-124 g/km | €667 + €6,68 per g/km boven 79 | Gemiddeld zuinig |
| 125-169 g/km | €968 + €67,40 per g/km boven 124 | Gemiddeld |
| 170-199 g/km | €4.001 + €159,61 per g/km boven 169 | Minder zuinig |
| 200+ g/km | €8.789 + €490,91 per g/km boven 199 | Onzuinig |

### Diesel toeslag

Dieselauto's betalen een extra toeslag van **€109,87 per g/km** boven de 70 g/km grens.

*Voorbeeld: Een diesel met 120 g/km CO2 betaalt €109,87 × (120-70) = €5.493,50 extra.*

### Afschrijvingstabel

De bruto BPM wordt verminderd met een afschrijvingspercentage op basis van de leeftijd:

| Leeftijd | Afschrijving | Leeftijd | Afschrijving |
|----------|--------------|----------|--------------|
| 0-3 maanden | 0% | 49-60 maanden | 70% |
| 4-6 maanden | 24% | 61-72 maanden | 76% |
| 7-9 maanden | 33% | 73-84 maanden | 81% |
| 10-18 maanden | 42% | 85-96 maanden | 85% |
| 19-24 maanden | 49% | 97-108 maanden | 88% |
| 25-36 maanden | 56% | 109-120 maanden | 90% |
| 37-48 maanden | 63% | 120+ maanden | 92% |

### Rekenvoorbeeld

**BMW 320d uit 2021, 118 g/km CO2, diesel:**

1. Bruto BPM (CO2): €667 + (118-79) × €6,68 = €667 + €260 = **€927**
2. Diesel toeslag: (118-70) × €109,87 = **€5.274**
3. Totaal bruto: €927 + €5.274 = **€6.201**
4. Auto is 46 maanden oud → 63% afschrijving
5. Rest-BPM: €6.201 × (100% - 63%) = €6.201 × 37% = **€2.294**

## Vaste importkosten

| Kostenpost | Bedrag | Toelichting |
|------------|--------|-------------|
| Transport | €450 | Autotransport Duitsland → Nederland |
| RDW keuring | €85 | Verplichte invoerkeuring |
| Kentekenplaten | €50 | Nederlands kenteken |
| Handelingskosten | €200 | Administratie en afhandeling |
| NAP check | €12,95 | Kilometerstandcontrole |
| **Totaal** | **€797,95** | |

## Ondersteunde platforms

### Duitse bronnen (input)
- **Mobile.de** - Grootste Duitse automarktplaats
- **AutoScout24.de** - Pan-Europese automarktplaats

### Nederlandse bronnen (vergelijking)
- **AutoScout24.nl** - Direct scraping
- **Marktplaats.nl** - Via Apify scraper

## Technische architectuur

| Component | Technologie | Hosting |
|-----------|-------------|---------|
| Backend API | Python + FastAPI | Modal.com |
| Frontend | Next.js + TailwindCSS | Vercel |
| Scraping | Apify actors | Apify.com |
| AI Taxatie | Claude (Anthropic) | OpenRouter |

## Project structuur

```
driving-passion/
├── modal-app/              # Backend
│   ├── app.py              # API endpoints (/analyze, /health, /bpm)
│   ├── scrapers.py         # Mobile.de & AutoScout24.de scrapers
│   ├── dutch_market.py     # Marktplaats & AutoScout24.nl zoeken
│   ├── bpm_calculator.py   # BPM berekening
│   ├── valuation.py        # AI taxatie via OpenRouter
│   └── constants.py        # Tarieven en configuratie
├── web/                    # Frontend
│   └── app/
│       └── page.tsx        # Hoofdpagina
└── CLAUDE.md               # Ontwikkelaarsdocumentatie
```

## Snelle setup

```bash
# Backend deployen
cd modal-app
modal secret create apify-secret APIFY_TOKEN=<token>
modal secret create openrouter-secret OPENROUTER_API_KEY=<key>
python3 -m modal deploy app.py

# Frontend lokaal draaien
cd web
npm install
npm run dev
```

## Licentie

Private - Driving Passion B.V.
