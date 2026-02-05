'use client'

import { useState, FormEvent } from 'react'

interface VehicleData {
  make: string
  model: string
  year: number
  mileage_km: number
  price_eur: number
  fuelType: string
  transmission: string
  co2_gkm: number
  firstRegistrationDate: string
  title?: string
  features?: string[]
  listingUrl?: string
  originalUrl?: string
  urlWasNormalized?: boolean
}

interface BPMData {
  grossBPM: number
  restBPM: number
  depreciationPercentage: number
  dieselSurcharge: number
  vehicleAgeMonths: number
}

interface CostsData {
  germanPrice: number
  bpm: number
  transport: number
  rdwInspection: number
  licensePlates: number
  handlingFee: number
  napCheck: number
  totalImportCosts: number
  totalCost: number
}

interface ResultData {
  margin: number
  marginPercentage: number
  safeMargin: number
  recommendation: 'GO' | 'CONSIDER' | 'NO_GO'
}

interface PriceBreakdown {
  baseValue: number
  mileageAdjustment: number
  optionsAdjustment: number
  conditionAdjustment: number
  marketAdjustment: number
  calculatedTotal: number
  explanation: string
}

interface AIValuation {
  estimatedRetailPrice: number
  estimatedQuickSalePrice: number
  confidence: number
  reasoning?: string
  pros?: string[]
  cons?: string[]
  priceBreakdown?: PriceBreakdown
}

interface ComparableVehicle {
  title: string
  price_eur: number
  mileage_km: number
  year?: number
  listingUrl?: string
  location?: string
  source?: string
}

interface AdvancedPricing {
  estimatedValue: number
  valueRange: { low: number; high: number }
  confidence: number
  comparablesUsed: number
  depreciationRate: number
  equipmentAdjustment: number
}

interface AnalysisResult {
  success: boolean
  requestId?: string
  data?: {
    vehicle: VehicleData
    pricing: {
      germanPrice: number
      dutchMarketValue: number
      dutchMarketValueRange: { low: number; high: number }
      comparablesCount: number
      sources: string[]
    }
    bpm: BPMData
    costs: CostsData
    result: ResultData
    aiValuation: AIValuation
    comparables: ComparableVehicle[]
    marketStats: { count: number; avgPrice: number; minPrice: number; maxPrice: number }
    advancedPricing?: AdvancedPricing
  }
  error?: { type: string; message: string; details?: string }
  meta?: { calculatedAt: string; processingTimeMs: number }
}

const LOADING_STEPS = [
  { id: 1, label: 'Advertentie ophalen...' },
  { id: 2, label: 'Voertuiggegevens analyseren...' },
  { id: 3, label: 'BPM berekenen...' },
  { id: 4, label: 'Nederlandse markt doorzoeken...' },
  { id: 5, label: 'AI taxatie uitvoeren...' },
  { id: 6, label: 'Marge berekenen...' },
]

export default function Home() {
  const [url, setUrl] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!url.trim()) {
      setError('Vul een advertentie URL in van mobile.de of AutoScout24')
      return
    }

    setIsLoading(true)
    setError(null)
    setResult(null)
    setCurrentStep(0)

    const stepInterval = setInterval(() => {
      setCurrentStep(prev => prev < LOADING_STEPS.length - 1 ? prev + 1 : prev)
    }, 2500)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_MODAL_API_URL
      if (!apiUrl) {
        throw new Error('API URL niet geconfigureerd. Stel NEXT_PUBLIC_MODAL_API_URL in.')
      }

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      })

      const data: AnalysisResult = await response.json()
      if (!data.success) {
        throw new Error(data.error?.message || 'Er ging iets mis bij de analyse')
      }
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Er ging iets mis')
    } finally {
      clearInterval(stepInterval)
      setIsLoading(false)
    }
  }

  const formatCurrency = (value: number) => new Intl.NumberFormat('nl-NL', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(value)

  const formatNumber = (value: number) => new Intl.NumberFormat('nl-NL').format(value)

  const getRecommendationStyle = (rec: string) => {
    switch (rec) {
      case 'GO': return 'recommendation-go'
      case 'CONSIDER': return 'recommendation-consider'
      default: return 'recommendation-no-go'
    }
  }

  const getRecommendationText = (rec: string) => {
    switch (rec) {
      case 'GO': return 'Kopen!'
      case 'CONSIDER': return 'Overwegen'
      default: return 'Niet doen'
    }
  }

  return (
    <main className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-slate-900 mb-3">Auto Import Calculator</h1>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Plak een link van een advertentie en ontdek binnen seconden of de auto winstgevend is om te importeren.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          <div className="card">
            <h2 className="text-xl font-semibold mb-6">Advertentie Analyseren</h2>
            <form onSubmit={handleSubmit}>
              <div className="mb-6">
                <label htmlFor="url" className="block text-sm font-medium text-slate-700 mb-2">
                  Advertentie URL
                </label>
                <input
                  type="url"
                  id="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://www.mobile.de/... of https://www.autoscout24.de/.../nl/..."
                  className="input-field"
                  disabled={isLoading}
                />
                <p className="mt-2 text-sm text-slate-500">
                  <strong>Let op:</strong> De auto moet in Duitsland staan om geïmporteerd te kunnen worden.
                  <br />AutoScout24 URLs (.de, .nl, .be) worden ondersteund.
                </p>
              </div>
              <button type="submit" disabled={isLoading || !url.trim()} className="btn-primary">
                {isLoading ? 'Analyseren...' : 'Analyseer Advertentie'}
              </button>
            </form>

            {error && (
              <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-xl">
                <p className="text-red-700 text-sm">{error}</p>
              </div>
            )}

            {isLoading && (
              <div className="mt-8 space-y-3">
                {LOADING_STEPS.map((step, index) => (
                  <div
                    key={step.id}
                    className={`flex items-center gap-3 p-3 rounded-lg transition-all duration-300 ${
                      index < currentStep ? 'bg-emerald-50 text-emerald-700'
                        : index === currentStep ? 'bg-primary-50 text-primary-700'
                        : 'bg-slate-50 text-slate-400'
                    }`}
                  >
                    {index < currentStep ? (
                      <svg className="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : index === currentStep ? (
                      <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <div className="w-5 h-5 border-2 border-slate-300 rounded-full" />
                    )}
                    <span className="text-sm font-medium">{step.label}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-8 pt-6 border-t border-slate-200">
              <h3 className="text-sm font-medium text-slate-700 mb-3">Voorbeeld URL's:</h3>
              <div className="flex flex-col gap-2">
                <button
                  type="button"
                  onClick={() => setUrl('https://suchen.mobile.de/fahrzeuge/details.html?id=446136631')}
                  className="text-sm text-primary-600 hover:text-primary-700 underline text-left"
                >
                  mobile.de - Test advertentie
                </button>
                <a
                  href="https://www.autoscout24.de/lst"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary-600 hover:text-primary-700 underline text-left"
                >
                  autoscout24.de - Zoek een advertentie
                </a>
                <a
                  href="https://www.autoscout24.nl/lst"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary-600 hover:text-primary-700 underline text-left"
                >
                  autoscout24.nl - Zoek een advertentie (ook auto's uit Duitsland)
                </a>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            {result?.data ? (
              <>
                <div className={`card ${
                  result.data.result.recommendation === 'GO' ? 'bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200'
                    : result.data.result.recommendation === 'CONSIDER' ? 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200'
                    : 'bg-gradient-to-br from-red-50 to-red-100 border-red-200'
                }`}>
                  <div className="text-center">
                    <span className={`recommendation-badge ${getRecommendationStyle(result.data.result.recommendation)}`}>
                      {getRecommendationText(result.data.result.recommendation)}
                    </span>
                    <div className="mt-4">
                      <p className="text-4xl font-bold text-slate-900">{formatCurrency(result.data.result.margin)}</p>
                      <p className="text-sm text-slate-600 mt-1">Verwachte winst ({result.data.result.marginPercentage}%)</p>
                    </div>
                    <div className="mt-4 pt-4 border-t border-slate-200/50">
                      <p className="text-sm text-slate-600">
                        Veilige marge: <span className="font-semibold">{formatCurrency(result.data.result.safeMargin)}</span>
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <h3 className="font-semibold text-lg mb-4">Voertuig</h3>
                  {result.data.vehicle.urlWasNormalized && (
                    <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-sm text-blue-700">
                        <span className="font-medium">URL automatisch geconverteerd:</span> De Nederlandse versie van mobile.de is omgezet naar de Duitse versie voor accurate scraping.
                      </p>
                    </div>
                  )}
                  <div className="space-y-3">
                    <div className="flex justify-between"><span className="text-slate-600">Auto</span><span className="font-medium">{result.data.vehicle.make} {result.data.vehicle.model}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Bouwjaar</span><span className="font-medium">{result.data.vehicle.year}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Kilometerstand</span><span className="font-medium">{formatNumber(result.data.vehicle.mileage_km)} km</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Brandstof</span><span className="font-medium capitalize">{result.data.vehicle.fuelType}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">CO2 uitstoot</span><span className="font-medium">{result.data.vehicle.co2_gkm} g/km</span></div>
                    {result.data.vehicle.listingUrl && (
                      <div className="pt-3 border-t border-slate-200">
                        <a
                          href={result.data.vehicle.listingUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-primary-600 hover:text-primary-700 underline"
                        >
                          Bekijk originele advertentie
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                <div className="card">
                  <h3 className="font-semibold text-lg mb-4">Kostenopbouw</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between"><span className="text-slate-600">Duitse prijs</span><span className="font-medium">{formatCurrency(result.data.costs.germanPrice)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">BPM</span><span className="font-medium">{formatCurrency(result.data.costs.bpm)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Transport</span><span className="font-medium">{formatCurrency(result.data.costs.transport)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">RDW + Kenteken</span><span className="font-medium">{formatCurrency(result.data.costs.rdwInspection + result.data.costs.licensePlates)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Overige kosten</span><span className="font-medium">{formatCurrency(result.data.costs.handlingFee + result.data.costs.napCheck)}</span></div>
                    <div className="flex justify-between pt-3 border-t border-slate-200">
                      <span className="font-semibold">Totale investering</span>
                      <span className="font-bold text-lg">{formatCurrency(result.data.costs.totalCost)}</span>
                    </div>
                  </div>
                </div>

                {result.data.advancedPricing && (
                  <div className="card bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
                    <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                      <span className="text-blue-600">🎯</span> Geavanceerde Marktanalyse
                    </h3>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-slate-600">Geschatte marktwaarde</span>
                        <span className="font-bold text-lg">{formatCurrency(result.data.advancedPricing.estimatedValue)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Waarderange</span>
                        <span className="font-medium">
                          {formatCurrency(result.data.advancedPricing.valueRange.low)} - {formatCurrency(result.data.advancedPricing.valueRange.high)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Betrouwbaarheid</span>
                        <span className="font-medium">
                          {(result.data.advancedPricing.confidence * 100).toFixed(0)}%
                          <span className="ml-2">
                            {result.data.advancedPricing.confidence >= 0.8 ? '🟢' : result.data.advancedPricing.confidence >= 0.6 ? '🟡' : '🟠'}
                          </span>
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Afschrijving per jaar</span>
                        <span className="font-medium">{result.data.advancedPricing.depreciationRate}%</span>
                      </div>
                      {result.data.advancedPricing.equipmentAdjustment !== 0 && (
                        <div className="flex justify-between">
                          <span className="text-slate-600">Uitrusting correctie</span>
                          <span className={`font-medium ${result.data.advancedPricing.equipmentAdjustment >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            {result.data.advancedPricing.equipmentAdjustment >= 0 ? '+' : ''}{formatCurrency(result.data.advancedPricing.equipmentAdjustment)}
                          </span>
                        </div>
                      )}
                      <div className="mt-3 pt-3 border-t border-blue-200">
                        <p className="text-xs text-slate-500">
                          Gebaseerd op {result.data.advancedPricing.comparablesUsed} vergelijkbare auto's met jaar- en kilometerstand normalisatie
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <div className="card">
                  <h3 className="font-semibold text-lg mb-4 flex items-center justify-between">
                    <span>Nederlandse Marktwaarde</span>
                    {result.data.advancedPricing && (
                      <span className="text-xs font-normal bg-blue-100 text-blue-700 px-2 py-1 rounded">Geavanceerd model</span>
                    )}
                    {!result.data.advancedPricing && result.data.aiValuation && (
                      <span className="text-xs font-normal bg-purple-100 text-purple-700 px-2 py-1 rounded">AI taxatie</span>
                    )}
                  </h3>
                  <div className="space-y-3">
                    <div className="flex justify-between"><span className="text-slate-600">Geschatte retailprijs</span><span className="font-medium">{formatCurrency(result.data.pricing.dutchMarketValue)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Snelle verkoop prijs</span><span className="font-medium">{formatCurrency(result.data.pricing.dutchMarketValueRange.low)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Vergelijkbare auto's</span><span className="font-medium">{result.data.pricing.comparablesCount}</span></div>
                  </div>
                  {result.data.aiValuation?.reasoning && (
                    <div className="mt-4 pt-4 border-t border-slate-200">
                      <p className="text-sm text-slate-600 mb-2 font-medium">AI Analyse:</p>
                      <p className="text-sm text-slate-700">{result.data.aiValuation.reasoning}</p>
                    </div>
                  )}
                </div>

                {result.data.aiValuation?.priceBreakdown && (
                  <div className="card">
                    <h3 className="font-semibold text-lg mb-4">💰 Prijsopbouw</h3>
                    <div className="space-y-3 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-600">Basiswaarde</span>
                        <span className="font-medium">{formatCurrency(result.data.aiValuation.priceBreakdown.baseValue)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Kilometerstand correctie</span>
                        <span className={`font-medium ${result.data.aiValuation.priceBreakdown.mileageAdjustment >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {result.data.aiValuation.priceBreakdown.mileageAdjustment >= 0 ? '+' : ''}{formatCurrency(result.data.aiValuation.priceBreakdown.mileageAdjustment)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Opties & uitrusting</span>
                        <span className={`font-medium ${result.data.aiValuation.priceBreakdown.optionsAdjustment >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {result.data.aiValuation.priceBreakdown.optionsAdjustment >= 0 ? '+' : ''}{formatCurrency(result.data.aiValuation.priceBreakdown.optionsAdjustment)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Staat & leeftijd</span>
                        <span className={`font-medium ${result.data.aiValuation.priceBreakdown.conditionAdjustment >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {result.data.aiValuation.priceBreakdown.conditionAdjustment >= 0 ? '+' : ''}{formatCurrency(result.data.aiValuation.priceBreakdown.conditionAdjustment)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Marktomstandigheden</span>
                        <span className={`font-medium ${result.data.aiValuation.priceBreakdown.marketAdjustment >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {result.data.aiValuation.priceBreakdown.marketAdjustment >= 0 ? '+' : ''}{formatCurrency(result.data.aiValuation.priceBreakdown.marketAdjustment)}
                        </span>
                      </div>
                      <div className="flex justify-between pt-3 border-t border-slate-200">
                        <span className="font-semibold">Berekende waarde</span>
                        <span className="font-bold">{formatCurrency(result.data.aiValuation.priceBreakdown.calculatedTotal)}</span>
                      </div>
                    </div>
                    {result.data.aiValuation.priceBreakdown.explanation && (
                      <div className="mt-4 pt-4 border-t border-slate-200">
                        <p className="text-xs text-slate-500">{result.data.aiValuation.priceBreakdown.explanation}</p>
                      </div>
                    )}
                  </div>
                )}

                {(result.data.aiValuation?.pros?.length || result.data.aiValuation?.cons?.length) && (
                  <div className="card">
                    <h3 className="font-semibold text-lg mb-4">📋 Beoordeling</h3>
                    <div className="grid md:grid-cols-2 gap-4">
                      {result.data.aiValuation.pros && result.data.aiValuation.pros.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-emerald-700 mb-2 flex items-center gap-1">
                            <span className="text-emerald-500">✓</span> Pluspunten
                          </h4>
                          <ul className="space-y-2">
                            {result.data.aiValuation.pros.map((pro: string, index: number) => (
                              <li key={index} className="text-sm text-slate-700 flex items-start gap-2">
                                <span className="text-emerald-500 mt-0.5">•</span>
                                <span>{pro}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {result.data.aiValuation.cons && result.data.aiValuation.cons.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-red-700 mb-2 flex items-center gap-1">
                            <span className="text-red-500">!</span> Aandachtspunten
                          </h4>
                          <ul className="space-y-2">
                            {result.data.aiValuation.cons.map((con: string, index: number) => (
                              <li key={index} className="text-sm text-slate-700 flex items-start gap-2">
                                <span className="text-red-500 mt-0.5">•</span>
                                <span>{con}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                <div className="card">
                  <h3 className="font-semibold text-lg mb-4">BPM Berekening</h3>
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between"><span className="text-slate-600">Bruto BPM (nieuw)</span><span className="font-medium">{formatCurrency(result.data.bpm.grossBPM)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Leeftijd voertuig</span><span className="font-medium">{result.data.bpm.vehicleAgeMonths} maanden</span></div>
                    <div className="flex justify-between"><span className="text-slate-600">Afschrijving</span><span className="font-medium">{result.data.bpm.depreciationPercentage}%</span></div>
                    {result.data.bpm.dieselSurcharge > 0 && (
                      <div className="flex justify-between"><span className="text-slate-600">Diesel toeslag</span><span className="font-medium">{formatCurrency(result.data.bpm.dieselSurcharge)}</span></div>
                    )}
                    <div className="flex justify-between pt-3 border-t border-slate-200">
                      <span className="font-semibold">Te betalen BPM</span>
                      <span className="font-bold">{formatCurrency(result.data.bpm.restBPM)}</span>
                    </div>
                  </div>
                </div>

                {result.data.comparables && result.data.comparables.length > 0 && (
                  <div className="card">
                    <h3 className="font-semibold text-lg mb-4">
                      Vergelijkbare auto's ({result.data.comparables.length})
                      {result.data.pricing.sources && result.data.pricing.sources.length > 0 && (
                        <span className="text-xs font-normal text-slate-500 ml-2">
                          via {result.data.pricing.sources.map(s =>
                            s === 'autoscout24' ? 'AutoScout24' :
                            s === 'marktplaats' ? 'Marktplaats' :
                            s === 'autotrack' ? 'AutoTrack' :
                            s === 'gaspedaal' ? 'Gaspedaal' :
                            s === 'occasions' ? 'Occasions.nl' :
                            s
                          ).join(' + ')}
                        </span>
                      )}
                    </h3>
                    <div className="space-y-3 max-h-64 overflow-y-auto">
                      {result.data.comparables.slice(0, 10).map((comp, index) => (
                        <div key={index} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">{comp.title}</p>
                            <p className="text-xs text-slate-500">
                              {comp.year && `${comp.year} • `}
                              {formatNumber(comp.mileage_km)} km
                              {comp.location && ` • ${comp.location}`}
                              <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                                comp.source === 'marktplaats' ? 'bg-orange-100 text-orange-700' :
                                comp.source === 'autotrack' ? 'bg-green-100 text-green-700' :
                                comp.source === 'gaspedaal' ? 'bg-purple-100 text-purple-700' :
                                comp.source === 'occasions' ? 'bg-yellow-100 text-yellow-700' :
                                'bg-blue-100 text-blue-700'
                              }`}>
                                {comp.source === 'marktplaats' ? 'MP' :
                                 comp.source === 'autotrack' ? 'AT' :
                                 comp.source === 'gaspedaal' ? 'GP' :
                                 comp.source === 'occasions' ? 'OC' :
                                 'AS24'}
                              </span>
                            </p>
                          </div>
                          <div className="text-right ml-3">
                            <p className="font-semibold">{formatCurrency(comp.price_eur)}</p>
                            {comp.listingUrl && (
                              <a href={comp.listingUrl} target="_blank" rel="noopener noreferrer" className="text-xs text-primary-600 hover:underline">Bekijk</a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {result.meta && (
                  <p className="text-xs text-slate-400 text-center">
                    Berekend op {new Date(result.meta.calculatedAt).toLocaleString('nl-NL')} • Verwerkingstijd: {(result.meta.processingTimeMs / 1000).toFixed(1)}s
                  </p>
                )}
              </>
            ) : !isLoading && (
              <div className="card text-center py-12">
                <div className="text-6xl mb-4">🚗</div>
                <h3 className="text-lg font-semibold text-slate-700 mb-2">Klaar om te analyseren</h3>
                <p className="text-slate-500 text-sm">
                  Plak een URL van een Duitse advertentie om te beginnen.
                  We berekenen automatisch de BPM, zoeken vergelijkbare auto's in Nederland,
                  en geven je een AI-gestuurde taxatie.
                </p>
              </div>
            )}
          </div>
        </div>

        <footer className="mt-12 text-center text-sm text-slate-500">
          <p>Driving Passion - Auto Import Calculator</p>
          <p className="text-xs mt-1">BPM tarieven 2026 • Powered by AI</p>
        </footer>
      </div>
    </main>
  )
}
