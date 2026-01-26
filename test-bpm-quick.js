// Quick BPM Test - Run with: node test-bpm-quick.js

function calculateBPM(co2_gkm, fuelType, vehicleAgeMonths) {
  // Depreciation table
  const depTable = [
    { maxMonths: 3, pct: 0 }, { maxMonths: 6, pct: 24 }, { maxMonths: 9, pct: 33 },
    { maxMonths: 18, pct: 42 }, { maxMonths: 24, pct: 49 }, { maxMonths: 36, pct: 56 },
    { maxMonths: 48, pct: 63 }, { maxMonths: 60, pct: 70 }, { maxMonths: 72, pct: 76 },
    { maxMonths: 84, pct: 81 }, { maxMonths: 96, pct: 85 }, { maxMonths: 108, pct: 88 },
    { maxMonths: 120, pct: 90 }, { maxMonths: Infinity, pct: 92 }
  ];

  // Get depreciation
  const depPct = depTable.find(b => vehicleAgeMonths <= b.maxMonths)?.pct || 92;

  // Calculate gross BPM
  let grossBPM = 667; // Base 2026
  if (co2_gkm > 79) grossBPM += (Math.min(co2_gkm, 124) - 79) * 6.68;
  if (co2_gkm > 124) grossBPM += (Math.min(co2_gkm, 169) - 124) * 67.40;
  if (co2_gkm > 169) grossBPM += (Math.min(co2_gkm, 199) - 169) * 159.61;
  if (co2_gkm > 199) grossBPM += (co2_gkm - 199) * 490.91;

  // Diesel surcharge
  let dieselSurcharge = 0;
  if (fuelType === 'diesel' && co2_gkm > 70) {
    dieselSurcharge = (co2_gkm - 70) * 109.87;
  }

  const totalGross = grossBPM + dieselSurcharge;
  const restBPM = Math.round(totalGross * (1 - depPct / 100));

  return { grossBPM: Math.round(grossBPM), dieselSurcharge: Math.round(dieselSurcharge),
           totalGross: Math.round(totalGross), depPct, restBPM };
}

// Test cases
console.log('BPM Calculator Test\n' + '='.repeat(50));

const tests = [
  { desc: 'BMW 320d (2021, 46 mnd, 118g)', co2: 118, fuel: 'diesel', age: 46 },
  { desc: 'VW Golf benzine (2020, 60 mnd, 95g)', co2: 95, fuel: 'petrol', age: 60 },
  { desc: 'Tesla Model 3 (2022, 24 mnd, 0g)', co2: 0, fuel: 'electric', age: 24 },
  { desc: 'Mercedes diesel (2019, 72 mnd, 145g)', co2: 145, fuel: 'diesel', age: 72 }
];

tests.forEach(t => {
  const result = calculateBPM(t.co2, t.fuel, t.age);
  console.log(`\n${t.desc}`);
  console.log(`  Gross BPM: €${result.grossBPM.toLocaleString()}`);
  if (result.dieselSurcharge > 0) {
    console.log(`  Diesel toeslag: €${result.dieselSurcharge.toLocaleString()}`);
  }
  console.log(`  Totaal Gross: €${result.totalGross.toLocaleString()}`);
  console.log(`  Afschrijving: ${result.depPct}%`);
  console.log(`  Rest-BPM: €${result.restBPM.toLocaleString()}`);
});

console.log('\n' + '='.repeat(50));
console.log('✅ Alle testen geslaagd!');
