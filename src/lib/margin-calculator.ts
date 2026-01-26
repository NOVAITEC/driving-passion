/**
 * Import Margin Calculator for Cross-Border Vehicle Arbitrage
 * Calculates profitability of importing vehicles from Germany to Netherlands
 */

import { calculateBPM, BPMResult, FuelType } from './bpm-calculator';

// Default import costs (in EUR)
export const DEFAULT_IMPORT_COSTS = {
  transport: 450, // Average DE → NL transport
  rdwInspection: 85, // RDW keuring
  licensePlates: 50, // Kenteken aanvraag
  handlingFee: 200, // Dealer handling
  napCheck: 12.95, // NAP kilometercheck
};

export type Recommendation = 'GO' | 'CONSIDER' | 'NO_GO';

export interface VehicleData {
  make: string;
  model: string;
  year: number;
  mileage_km: number;
  fuelType: FuelType;
  transmission: 'automatic' | 'manual';
  co2_gkm: number;
  firstRegistrationDate: Date;
}

export interface GermanListing extends VehicleData {
  price_eur: number;
  listingUrl?: string;
  source: 'mobile.de' | 'autoscout24' | 'manual';
}

export interface DutchComparable {
  price_eur: number;
  mileage_km: number;
  listingUrl?: string;
  source: 'marktplaats' | 'gaspedaal' | 'manual';
}

export interface ImportCosts {
  transport: number;
  rdwInspection: number;
  licensePlates: number;
  handlingFee: number;
  napCheck: number;
  other?: number;
}

export interface MarginInput {
  germanListing: GermanListing;
  dutchComparables: DutchComparable[];
  importCosts?: Partial<ImportCosts>;
  profitThresholds?: {
    go: number; // Minimum for GO recommendation
    consider: number; // Minimum for CONSIDER recommendation
  };
}

export interface MarginResult {
  // Input summary
  germanPrice: number;
  dutchMarketValue: number;
  comparablesCount: number;

  // BPM calculation
  bpm: BPMResult;

  // Cost breakdown
  costs: {
    germanPrice: number;
    bpm: number;
    transport: number;
    rdwInspection: number;
    licensePlates: number;
    handlingFee: number;
    napCheck: number;
    other: number;
    totalImportCosts: number;
    totalCost: number;
  };

  // Result
  margin: number;
  marginPercentage: number;
  recommendation: Recommendation;

  // Metadata
  calculatedAt: Date;
  vehicle: {
    description: string;
    ageMonths: number;
  };
}

/**
 * Calculate average price from comparable listings
 * Filters outliers using IQR method
 */
function calculateAverageMarketValue(comparables: DutchComparable[]): number {
  if (comparables.length === 0) {
    throw new Error('No comparable vehicles found');
  }

  if (comparables.length === 1) {
    return comparables[0].price_eur;
  }

  // Sort prices
  const prices = comparables.map((c) => c.price_eur).sort((a, b) => a - b);

  // For small sample sizes, use simple average
  if (prices.length < 4) {
    const sum = prices.reduce((acc, p) => acc + p, 0);
    return Math.round(sum / prices.length);
  }

  // Use IQR method to filter outliers
  const q1Index = Math.floor(prices.length * 0.25);
  const q3Index = Math.floor(prices.length * 0.75);
  const q1 = prices[q1Index];
  const q3 = prices[q3Index];
  const iqr = q3 - q1;

  const lowerBound = q1 - 1.5 * iqr;
  const upperBound = q3 + 1.5 * iqr;

  // Filter outliers
  const filteredPrices = prices.filter((p) => p >= lowerBound && p <= upperBound);

  // Calculate average of filtered prices
  const sum = filteredPrices.reduce((acc, p) => acc + p, 0);
  return Math.round(sum / filteredPrices.length);
}

/**
 * Get recommendation based on margin and thresholds
 */
function getRecommendation(
  margin: number,
  thresholds: { go: number; consider: number }
): Recommendation {
  if (margin >= thresholds.go) {
    return 'GO';
  }
  if (margin >= thresholds.consider) {
    return 'CONSIDER';
  }
  return 'NO_GO';
}

/**
 * Main margin calculation function
 */
export function calculateMargin(input: MarginInput): MarginResult {
  const { germanListing, dutchComparables, importCosts, profitThresholds } = input;

  // Default thresholds
  const thresholds = {
    go: profitThresholds?.go ?? 2500,
    consider: profitThresholds?.consider ?? 1000,
  };

  // Merge import costs with defaults
  const costs: ImportCosts = {
    ...DEFAULT_IMPORT_COSTS,
    ...importCosts,
    other: importCosts?.other ?? 0,
  };

  // Calculate BPM
  const bpmResult = calculateBPM({
    co2_gkm: germanListing.co2_gkm,
    fuelType: germanListing.fuelType,
    firstRegistrationDate: germanListing.firstRegistrationDate,
    calculationDate: new Date(),
  });

  // Calculate Dutch market value
  const dutchMarketValue = calculateAverageMarketValue(dutchComparables);

  // Calculate total import costs
  const totalImportCosts =
    costs.transport +
    costs.rdwInspection +
    costs.licensePlates +
    costs.handlingFee +
    costs.napCheck +
    costs.other;

  // Calculate total cost
  const totalCost = germanListing.price_eur + bpmResult.restBPM + totalImportCosts;

  // Calculate margin
  const margin = dutchMarketValue - totalCost;
  const marginPercentage = (margin / totalCost) * 100;

  // Get recommendation
  const recommendation = getRecommendation(margin, thresholds);

  // Create vehicle description
  const vehicleDescription = `${germanListing.year} ${germanListing.make} ${germanListing.model}`;

  return {
    germanPrice: germanListing.price_eur,
    dutchMarketValue,
    comparablesCount: dutchComparables.length,

    bpm: bpmResult,

    costs: {
      germanPrice: germanListing.price_eur,
      bpm: bpmResult.restBPM,
      transport: costs.transport,
      rdwInspection: costs.rdwInspection,
      licensePlates: costs.licensePlates,
      handlingFee: costs.handlingFee,
      napCheck: costs.napCheck,
      other: costs.other,
      totalImportCosts,
      totalCost,
    },

    margin: Math.round(margin * 100) / 100,
    marginPercentage: Math.round(marginPercentage * 100) / 100,
    recommendation,

    calculatedAt: new Date(),
    vehicle: {
      description: vehicleDescription,
      ageMonths: bpmResult.vehicleAgeMonths,
    },
  };
}

/**
 * Format margin result for display
 */
export function formatMarginResult(result: MarginResult): string {
  const recommendationEmoji = {
    GO: '🟢',
    CONSIDER: '🟡',
    NO_GO: '🔴',
  };

  return `
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IMPORT MARGIN ANALYSIS
  ${result.vehicle.description}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 MARKET COMPARISON
  German asking price:    €${result.germanPrice.toLocaleString()}
  Dutch market value:     €${result.dutchMarketValue.toLocaleString()}
  (Based on ${result.comparablesCount} comparable listing${result.comparablesCount !== 1 ? 's' : ''})

💰 COST BREAKDOWN
  German price:           €${result.costs.germanPrice.toLocaleString()}
  BPM (Rest-BPM):         €${result.costs.bpm.toLocaleString()}
  Transport:              €${result.costs.transport.toLocaleString()}
  RDW Inspection:         €${result.costs.rdwInspection.toLocaleString()}
  License plates:         €${result.costs.licensePlates.toLocaleString()}
  Handling fee:           €${result.costs.handlingFee.toLocaleString()}
  NAP check:              €${result.costs.napCheck.toLocaleString()}
  ${result.costs.other > 0 ? `Other costs:            €${result.costs.other.toLocaleString()}\n` : ''}
  ─────────────────────────────────────────────
  TOTAL COST:             €${result.costs.totalCost.toLocaleString()}

📈 BPM DETAILS
  Vehicle age:            ${result.bpm.vehicleAgeMonths} months
  Gross BPM:              €${result.bpm.totalGrossBPM.toLocaleString()}
  Depreciation:           ${result.bpm.depreciationPercentage}%
  Rest-BPM:               €${result.bpm.restBPM.toLocaleString()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ${recommendationEmoji[result.recommendation]} RESULT: ${result.recommendation}

  Potential margin:       €${result.margin.toLocaleString()}
  ROI:                    ${result.marginPercentage.toFixed(1)}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`;
}

/**
 * Quick margin estimate helper
 */
export function quickMarginEstimate(
  germanPrice: number,
  dutchMarketValue: number,
  bpm: number,
  importCosts: number = 800
): { margin: number; recommendation: Recommendation } {
  const totalCost = germanPrice + bpm + importCosts;
  const margin = dutchMarketValue - totalCost;

  return {
    margin: Math.round(margin),
    recommendation: margin >= 2500 ? 'GO' : margin >= 1000 ? 'CONSIDER' : 'NO_GO',
  };
}

// For use in n8n Code nodes (CommonJS export)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    calculateMargin,
    formatMarginResult,
    quickMarginEstimate,
    DEFAULT_IMPORT_COSTS,
  };
}
