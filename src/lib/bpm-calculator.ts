/**
 * Dutch BPM (Belasting van Personenauto's en Motorrijwielen) Calculator
 * Based on 2026 rates from Belastingdienst
 * Uses Forfaitaire Tabel method for depreciation
 */

// 2026 BPM CO2 Tariff Brackets
const BPM_BRACKETS_2026 = [
  { minCO2: 0, maxCO2: 79, ratePerGram: 0, baseAmount: 667 },
  { minCO2: 80, maxCO2: 124, ratePerGram: 6.68, baseAmount: 0 },
  { minCO2: 125, maxCO2: 169, ratePerGram: 67.40, baseAmount: 0 },
  { minCO2: 170, maxCO2: 199, ratePerGram: 159.61, baseAmount: 0 },
  { minCO2: 200, maxCO2: Infinity, ratePerGram: 490.91, baseAmount: 0 },
];

// Diesel surcharge: €109.87 per g/km above 70 g/km
const DIESEL_SURCHARGE_THRESHOLD = 70;
const DIESEL_SURCHARGE_RATE = 109.87;

// Forfaitaire Depreciation Table (2026)
// Based on vehicle age in months
const DEPRECIATION_TABLE: { maxMonths: number; percentage: number }[] = [
  { maxMonths: 3, percentage: 0 },
  { maxMonths: 6, percentage: 24 },
  { maxMonths: 9, percentage: 33 },
  { maxMonths: 18, percentage: 42 },
  { maxMonths: 24, percentage: 49 },
  { maxMonths: 36, percentage: 56 },
  { maxMonths: 48, percentage: 63 },
  { maxMonths: 60, percentage: 70 },
  { maxMonths: 72, percentage: 76 },
  { maxMonths: 84, percentage: 81 },
  { maxMonths: 96, percentage: 85 },
  { maxMonths: 108, percentage: 88 },
  { maxMonths: 120, percentage: 90 },
  { maxMonths: Infinity, percentage: 92 },
];

export type FuelType = 'petrol' | 'diesel' | 'electric' | 'hybrid' | 'lpg';

export interface BPMInput {
  co2_gkm: number; // CO2 emissions in g/km (WLTP)
  fuelType: FuelType;
  firstRegistrationDate: Date; // First registration date (abroad)
  calculationDate?: Date; // Date of BPM calculation (defaults to now)
}

export interface BPMResult {
  grossBPM: number; // BPM before depreciation
  dieselSurcharge: number; // Additional diesel tax
  totalGrossBPM: number; // Gross + diesel surcharge
  vehicleAgeMonths: number;
  depreciationPercentage: number;
  restBPM: number; // Final BPM to pay
  breakdown: {
    baseBPM: number;
    co2BPM: number;
    dieselSurcharge: number;
  };
}

/**
 * Calculate the number of months between two dates
 */
function monthsBetween(startDate: Date, endDate: Date): number {
  const years = endDate.getFullYear() - startDate.getFullYear();
  const months = endDate.getMonth() - startDate.getMonth();
  return years * 12 + months;
}

/**
 * Get depreciation percentage from forfaitaire table based on vehicle age
 */
function getDepreciationPercentage(ageMonths: number): number {
  for (const bracket of DEPRECIATION_TABLE) {
    if (ageMonths <= bracket.maxMonths) {
      return bracket.percentage;
    }
  }
  return 92; // Maximum depreciation
}

/**
 * Calculate gross BPM based on CO2 emissions (before depreciation)
 */
function calculateGrossBPM(co2_gkm: number): { baseBPM: number; co2BPM: number; total: number } {
  // Base amount (fixed rate for 2026)
  const baseBPM = 667;

  // Electric vehicles (0 CO2) only pay base rate
  if (co2_gkm === 0) {
    return { baseBPM, co2BPM: 0, total: baseBPM };
  }

  let co2BPM = 0;

  // Calculate CO2-based BPM using progressive brackets
  // Bracket 1: 0-79 g/km = €0 (only base rate)
  // Bracket 2: 80-124 g/km = €6.68 per gram
  if (co2_gkm > 79) {
    const gramsInBracket = Math.min(co2_gkm, 124) - 79;
    co2BPM += gramsInBracket * 6.68;
  }

  // Bracket 3: 125-169 g/km = €67.40 per gram
  if (co2_gkm > 124) {
    const gramsInBracket = Math.min(co2_gkm, 169) - 124;
    co2BPM += gramsInBracket * 67.40;
  }

  // Bracket 4: 170-199 g/km = €159.61 per gram
  if (co2_gkm > 169) {
    const gramsInBracket = Math.min(co2_gkm, 199) - 169;
    co2BPM += gramsInBracket * 159.61;
  }

  // Bracket 5: 200+ g/km = €490.91 per gram
  if (co2_gkm > 199) {
    const gramsInBracket = co2_gkm - 199;
    co2BPM += gramsInBracket * 490.91;
  }

  return {
    baseBPM,
    co2BPM: Math.round(co2BPM * 100) / 100,
    total: Math.round((baseBPM + co2BPM) * 100) / 100,
  };
}

/**
 * Calculate diesel surcharge
 * Applies when CO2 > 70 g/km for diesel vehicles
 */
function calculateDieselSurcharge(co2_gkm: number, fuelType: FuelType): number {
  if (fuelType !== 'diesel') {
    return 0;
  }

  if (co2_gkm <= DIESEL_SURCHARGE_THRESHOLD) {
    return 0;
  }

  const gramsAboveThreshold = co2_gkm - DIESEL_SURCHARGE_THRESHOLD;
  return Math.round(gramsAboveThreshold * DIESEL_SURCHARGE_RATE * 100) / 100;
}

/**
 * Main BPM calculation function
 * Implements the Forfaitaire Tabel method
 */
export function calculateBPM(input: BPMInput): BPMResult {
  const calculationDate = input.calculationDate || new Date();

  // Calculate vehicle age in months
  const vehicleAgeMonths = monthsBetween(input.firstRegistrationDate, calculationDate);

  // Get depreciation percentage from forfaitaire table
  const depreciationPercentage = getDepreciationPercentage(vehicleAgeMonths);

  // Calculate gross BPM components
  const grossBPMComponents = calculateGrossBPM(input.co2_gkm);

  // Calculate diesel surcharge
  const dieselSurcharge = calculateDieselSurcharge(input.co2_gkm, input.fuelType);

  // Total gross BPM (before depreciation)
  const totalGrossBPM = grossBPMComponents.total + dieselSurcharge;

  // Apply depreciation to get Rest-BPM
  const depreciationFactor = 1 - depreciationPercentage / 100;
  const restBPM = Math.round(totalGrossBPM * depreciationFactor * 100) / 100;

  return {
    grossBPM: grossBPMComponents.total,
    dieselSurcharge,
    totalGrossBPM,
    vehicleAgeMonths,
    depreciationPercentage,
    restBPM,
    breakdown: {
      baseBPM: grossBPMComponents.baseBPM,
      co2BPM: grossBPMComponents.co2BPM,
      dieselSurcharge,
    },
  };
}

/**
 * Quick calculation helper for common use case
 */
export function quickBPMEstimate(
  co2_gkm: number,
  fuelType: FuelType,
  vehicleAgeMonths: number
): number {
  // Create a synthetic first registration date based on age
  const now = new Date();
  const firstRegistrationDate = new Date(now);
  firstRegistrationDate.setMonth(now.getMonth() - vehicleAgeMonths);

  const result = calculateBPM({
    co2_gkm,
    fuelType,
    firstRegistrationDate,
    calculationDate: now,
  });

  return result.restBPM;
}

// For use in n8n Code nodes (CommonJS export)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { calculateBPM, quickBPMEstimate };
}
