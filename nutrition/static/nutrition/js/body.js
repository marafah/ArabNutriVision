/* ArabNutriVision · body-composition helpers (no device, no API).
   Reference ranges and prediction equations, each with its published source:
   - BMI classes: WHO, Obesity: preventing and managing the global epidemic, TRS 894 (2000).
   - Healthy % body fat by sex and age (20–79 y): Gallagher D. et al., Am J Clin Nutr 2000;72:694–701.
   - Waist–hip ratio cut-offs (men ≥ 0.90, women ≥ 0.85): WHO, Waist circumference and waist–hip ratio, expert consultation (2008).
   - Waist-to-height ratio ≥ 0.5: Ashwell M. et al., Obes Rev 2012;13:275–286.
   - Visceral fat level < 10: InBody result-sheet interpretation (device-specific scale).
   - % body fat from circumferences: Hodgdon J.A., Beckett M.B., US Naval Health Research Center reports 84-11 and 84-29 (1984).
   - % body fat from BMI: Deurenberg P. et al., Br J Nutr 1991;65:105–114.
   - BMR: Mifflin M.D. et al., Am J Clin Nutr 1990;51:241–247; Katch–McArdle: 370 + 21.6 × fat-free mass (kg).
   - Protein reference 0.8 g/kg/day: Institute of Medicine, Dietary Reference Intakes for Energy and Macronutrients (2005).
   Every equation result is an estimate and is labelled as such in the interface. */
(function () {
  const log10 = Math.log10, IN = 2.54;
  const GALLAGHER = {F: [[20, 39, 21, 32], [40, 59, 23, 33], [60, 79, 24, 35]], M: [[20, 39, 8, 19], [40, 59, 11, 21], [60, 79, 13, 24]]};
  const B = {
    bmi: (w, h) => (w && h) ? w / ((h / 100) ** 2) : null,
    bmiRange: () => [18.5, 24.9],
    bmiClass(b) { if (b == null) return null; return b < 18.5 ? "low" : b < 25 ? "ok" : b < 30 ? "high" : "obese"; },
    pbfRange(sex, age) {
      const t = GALLAGHER[sex]; if (!t || age == null) return null;
      const r = t.find(([a, b]) => age >= a && age <= b); return r ? [r[2], r[3]] : null;
    },
    classify(v, r) { if (v == null || !r) return null; return v < r[0] ? "low" : v > r[1] ? "high" : "ok"; },
    vflClass: v => v == null ? null : v < 10 ? "ok" : "high",
    whrCut: sex => sex === "M" ? 0.90 : sex === "F" ? 0.85 : null,
    whrClass(sex, v) { const c = B.whrCut(sex); return (v == null || c == null) ? null : v >= c ? "high" : "ok"; },
    whtr: (waist, h) => (waist && h) ? waist / h : null,
    whtrClass: v => v == null ? null : v >= 0.5 ? "high" : "ok",
    /** US Navy circumference method; inputs in cm, equations in inches. */
    navy(sex, h, waist, neck, hip) {
      if (!h || !waist || !neck) return null;
      const H = h / IN, W = waist / IN, N = neck / IN;
      if (sex === "M") return W - N > 0 ? 86.010 * log10(W - N) - 70.041 * log10(H) + 36.76 : null;
      if (sex === "F" && hip) { const P = hip / IN; return W + P - N > 0 ? 163.205 * log10(W + P - N) - 97.684 * log10(H) - 78.387 : null; }
      return null;
    },
    deurenberg(bmi, age, sex) { if (bmi == null || age == null || !["M", "F"].includes(sex)) return null; return 1.2 * bmi + 0.23 * age - 10.8 * (sex === "M" ? 1 : 0) - 5.4; },
    mifflin(sex, w, h, age) { if (!w || !h || age == null || !["M", "F"].includes(sex)) return null; return 10 * w + 6.25 * h - 5 * age + (sex === "M" ? 5 : -161); },
    katch: ffm => ffm ? 370 + 21.6 * ffm : null,
    /** Fill derived fields of a measurement (BMI, fat mass, fat-free mass) when the parts are known. */
    derive(m) {
      const o = {...m};
      if (o.bmi == null) o.bmi = B.bmi(o.weight_kg, o.height_cm);
      if (o.bfm_kg == null && o.weight_kg && o.pbf_pct != null) o.bfm_kg = o.weight_kg * o.pbf_pct / 100;
      if (o.ffm_kg == null && o.weight_kg && o.bfm_kg != null) o.ffm_kg = o.weight_kg - o.bfm_kg;
      if (o.whr == null && o.waist_cm && o.hip_cm) o.whr = o.waist_cm / o.hip_cm;
      return o;
    },
    /** Status of each indicator of one measurement for a participant (sex F/M/X, age in years). */
    assess(m, sex, age) {
      const d = B.derive(m), whtr = B.whtr(d.waist_cm, d.height_cm);
      return {d, whtr, rows: [
        {key: "bmi", v: d.bmi, range: B.bmiRange(), st: B.bmiClass(d.bmi), dec: 1},
        {key: "pbf_pct", v: d.pbf_pct, range: B.pbfRange(sex, age), st: B.classify(d.pbf_pct, B.pbfRange(sex, age)), dec: 1},
        {key: "vfl", v: d.vfl, range: [1, 9], st: B.vflClass(d.vfl), dec: 0},
        {key: "whr", v: d.whr, range: B.whrCut(sex) ? [null, B.whrCut(sex)] : null, st: B.whrClass(sex, d.whr), dec: 2},
        {key: "whtr", v: whtr, range: [null, 0.5], st: B.whtrClass(whtr), dec: 2},
      ]};
    },
    /** Link body composition with recorded intake (mean of food days). */
    nutritionLink(meanKcal, meanProtein, m, target) {
      const d = B.derive(m), out = {};
      if (meanProtein != null && d.weight_kg) out.protKg = meanProtein / d.weight_kg;
      if (meanProtein != null && d.ffm_kg) out.protFfm = meanProtein / d.ffm_kg;
      if (meanKcal != null && d.bmr_kcal) out.eiBmr = meanKcal / d.bmr_kcal;
      if (meanKcal != null && target) out.eiTarget = meanKcal - target;
      return out;
    },
    PROTEIN_RDA: 0.8,
  };
  window.ANVBody = B;
})();
