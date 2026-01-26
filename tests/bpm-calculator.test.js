/**
 * BPM Calculator Tests
 * Verifies BPM calculations against known examples
 */

// BPM Calculation Logic (copied from bpm-calculator.ts for testing)
const DEPRECIATION_TABLE = [
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

function getDepreciationPercentage(ageMonths) {
  for (const bracket of DEPRECIATION_TABLE) {
    if (ageMonths <= bracket.maxMonths) {
      return bracket.percentage;
    }
  }
  return 92;
}

function calculateGrossBPM(co2_gkm) {
  const baseBPM = 667;
  if (co2_gkm === 0) return { baseBPM, co2BPM: 0, total: baseBPM };

  let co2BPM = 0;
  if (co2_gkm > 79) co2BPM += (Math.min(co2_gkm, 124) - 79) * 6.68;
  if (co2_gkm > 124) co2BPM += (Math.min(co2_gkm, 169) - 124) * 67.40;
  if (co2_gkm > 169) co2BPM += (Math.min(co2_gkm, 199) - 169) * 159.61;
  if (co2_gkm > 199) co2BPM += (co2_gkm - 199) * 490.91;

  return {
    baseBPM,
    co2BPM: Math.round(co2BPM * 100) / 100,
    total: Math.round((baseBPM + co2BPM) * 100) / 100,
  };
}

function calculateDieselSurcharge(co2_gkm, fuelType) {
  if (fuelType !== 'diesel' || co2_gkm <= 70) return 0;
  return Math.round((co2_gkm - 70) * 109.87 * 100) / 100;
}

function calculateBPM(co2_gkm, fuelType, vehicleAgeMonths) {
  const depreciationPct = getDepreciationPercentage(vehicleAgeMonths);
  const grossBPM = calculateGrossBPM(co2_gkm);
  const dieselSurcharge = calculateDieselSurcharge(co2_gkm, fuelType);
  const totalGrossBPM = grossBPM.total + dieselSurcharge;
  const restBPM = Math.round(totalGrossBPM * (1 - depreciationPct / 100) * 100) / 100;

  return {
    grossBPM: grossBPM.total,
    dieselSurcharge,
    totalGrossBPM,
    vehicleAgeMonths,
    depreciationPercentage: depreciationPct,
    restBPM
  };
}

// Test Cases
const tests = [
  {
    name: 'Electric vehicle (0 CO2)',
    input: { co2: 0, fuel: 'electric', ageMonths: 24 },
    expected: { grossBPM: 667, restBPM: 340.17 } // 667 * (1 - 0.49)
  },
  {
    name: 'New petrol car (95 g/km, 6 months)',
    input: { co2: 95, fuel: 'petrol', ageMonths: 6 },
    expected: { grossBPM: 773.88, restBPM: 588.15 } // 667 + (95-79)*6.68 = 773.88, * 0.76
  },
  {
    name: 'Diesel car with surcharge (118 g/km, 46 months)',
    input: { co2: 118, fuel: 'diesel', ageMonths: 46 },
    // Gross: 667 + (118-79)*6.68 = 667 + 260.52 = 927.52
    // Diesel surcharge: (118-70)*109.87 = 5273.76
    // Total: 6201.28
    // Depreciation: 63% for 37-48 months
    // Rest: 6201.28 * 0.37 = 2294.47
    expected: { grossBPM: 927.52, dieselSurcharge: 5273.76, totalGross: 6201.28, restBPM: 2294.47 }
  },
  {
    name: 'High CO2 diesel (200 g/km, 60 months)',
    input: { co2: 200, fuel: 'diesel', ageMonths: 60 },
    // Base: 667
    // 80-124: 45 * 6.68 = 300.60
    // 125-169: 45 * 67.40 = 3033.00
    // 170-199: 30 * 159.61 = 4788.30
    // 200: 1 * 490.91 = 490.91
    // Total CO2 BPM: 8612.81
    // Gross: 667 + 8612.81 = 9279.81
    // Diesel surcharge: (200-70)*109.87 = 14283.10
    // Total: 23562.91
    // Depreciation: 70% for 49-60 months
    // Rest: 23562.91 * 0.30 = 7068.87
    expected: { totalGross: 23562.91, restBPM: 7068.87 }
  },
  {
    name: 'Old vehicle (10+ years)',
    input: { co2: 150, fuel: 'petrol', ageMonths: 130 },
    // Gross: 667 + (124-79)*6.68 + (150-124)*67.40 = 667 + 300.60 + 1752.40 = 2720
    // Depreciation: 92% for 120+ months
    // Rest: 2720 * 0.08 = 217.60
    expected: { grossBPM: 2720, restBPM: 217.60 }
  }
];

// Run tests
console.log('BPM Calculator Tests\n' + '='.repeat(50));

let passed = 0;
let failed = 0;

for (const test of tests) {
  const result = calculateBPM(test.input.co2, test.input.fuel, test.input.ageMonths);

  console.log(`\n${test.name}`);
  console.log(`  Input: CO2=${test.input.co2}g/km, Fuel=${test.input.fuel}, Age=${test.input.ageMonths} months`);
  console.log(`  Result:`);
  console.log(`    Gross BPM: €${result.grossBPM.toFixed(2)}`);
  if (result.dieselSurcharge > 0) {
    console.log(`    Diesel Surcharge: €${result.dieselSurcharge.toFixed(2)}`);
    console.log(`    Total Gross: €${result.totalGrossBPM.toFixed(2)}`);
  }
  console.log(`    Depreciation: ${result.depreciationPercentage}%`);
  console.log(`    Rest-BPM: €${result.restBPM.toFixed(2)}`);

  // Check expected values
  let testPassed = true;

  if (test.expected.grossBPM !== undefined) {
    const diff = Math.abs(result.grossBPM - test.expected.grossBPM);
    if (diff > 1) {
      console.log(`    ❌ Gross BPM mismatch: expected €${test.expected.grossBPM}, got €${result.grossBPM}`);
      testPassed = false;
    }
  }

  if (test.expected.restBPM !== undefined) {
    const diff = Math.abs(result.restBPM - test.expected.restBPM);
    if (diff > 1) {
      console.log(`    ❌ Rest-BPM mismatch: expected €${test.expected.restBPM}, got €${result.restBPM}`);
      testPassed = false;
    }
  }

  if (test.expected.totalGross !== undefined) {
    const diff = Math.abs(result.totalGrossBPM - test.expected.totalGross);
    if (diff > 1) {
      console.log(`    ❌ Total Gross mismatch: expected €${test.expected.totalGross}, got €${result.totalGrossBPM}`);
      testPassed = false;
    }
  }

  if (testPassed) {
    console.log('  ✅ PASSED');
    passed++;
  } else {
    failed++;
  }
}

console.log('\n' + '='.repeat(50));
console.log(`Results: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  process.exit(1);
}
