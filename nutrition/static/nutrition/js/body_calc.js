/* Body-composition calculator page: equations from body.js, optional saving to Supabase (static edition). */
(function () {
  const B = window.ANVBody, T = JSON.parse(document.getElementById("anv-t").textContent), AR = window.ANV_LANG === "ar";
  const f = document.getElementById("bcForm"), $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
  const pf = (s, o = {}) => s.replace(/%%|%\((\w+)\)(?:\.(\d+))?([sdf])/g, (m, k, nd, t) => m === "%%" ? "%" : t === "f" ? Number(o[k]).toFixed(nd === undefined ? 6 : +nd) : String(o[k]));
  const fx = (v, d = 1) => v == null || isNaN(v) ? "–" : (+v).toFixed(d);
  const LTR = s => "⁦" + s + "⁩";
  const chip = st => st ? `<span class="range-chip range-${st === "obese" ? "high" : st}">${esc({low: T.stLow, ok: T.stOk, high: T.stHigh, obese: T.stObese}[st])}</span>` : `<span class="range-chip range-na">–</span>`;
  const num = n => { const v = f.elements[n].value; return v === "" ? null : +v; };
  let last = null;

  function card(title, value, unit, st, note, tag) {
    return `<div class="col-sm-6 col-xl-4"><div class="stat h-100"><div class="d-flex justify-content-between gap-2"><div class="l mb-1">${esc(title)}</div>${tag ? `<span class="pill pill-demo align-self-start">${esc(tag)}</span>` : ""}</div>
      <div class="v">${value}<small class="fs-6 fw-normal text-secondary ms-1">${esc(unit || "")}</small></div><div class="mt-1">${st === undefined ? "" : chip(st)}</div>${note ? `<div class="small text-secondary mt-1">${note}</div>` : ""}</div></div>`;
  }

  function compute() {
    const sex = f.sex.value, age = num("age"), h = num("height_cm"), w = num("weight_kg"), waist = num("waist_cm"), neck = num("neck_cm"), hip = num("hip_cm");
    const bmi = B.bmi(w, h), navy = B.navy(sex, h, waist, neck, hip), deur = B.deurenberg(bmi, age, sex), dev = num("pbf_pct");
    const range = B.pbfRange(sex, age), best = dev ?? navy ?? deur, method = dev != null ? "inbody" : navy != null ? "navy" : "deurenberg";
    const ffm = best != null && w ? w * (1 - best / 100) : null;
    const bmrM = B.mifflin(sex, w, h, age), bmrK = B.katch(ffm), bmrDev = num("bmr_kcal"), bmr = bmrDev ?? bmrM, pal = +f.pal.value;
    const whr = waist && hip ? waist / hip : null, whtr = B.whtr(waist, h), smm = num("smm_kg"), vfl = num("vfl");
    last = {sex, age, method, row: {weight_kg: w, height_cm: h, bmi, pbf_pct: best, bfm_kg: best != null && w ? w * best / 100 : null, ffm_kg: ffm,
      smm_kg: smm, bmr_kcal: bmr, vfl, whr, waist_cm: waist, hip_cm: hip, neck_cm: neck}};
    const est = T.estimate, meas = T.measured;
    $("#bcCards").innerHTML = [
      card(T.bmiLabel, fx(bmi), "kg/m²", B.bmiClass(bmi), LTR("18.5–24.9")),
      card(T.ibPbf, fx(best), "%", B.classify(best, range), range ? LTR(`${range[0]}–${range[1]}%`) : esc(T.rangeNA), dev != null ? meas : est),
      card(T.ffmLabel, fx(ffm), "kg", undefined, "", dev != null ? meas : est),
      card(T.whrLabel, fx(whr, 2), "", B.whrClass(sex, whr), B.whrCut(sex) ? LTR(`< ${B.whrCut(sex).toFixed(2)}`) : ""),
      card(T.whtrLabel, fx(whtr, 2), "", B.whtrClass(whtr), LTR("< 0.50")),
      vfl != null ? card(T.ibVfl, fx(vfl, 0), "", B.vflClass(vfl), LTR("< 10"), meas) : smm != null ? card(T.ibSmm, fx(smm), "kg", undefined, w ? pf(T.smmShare, {p: fx(100 * smm / w, 0)}) : "", meas) : "",
      card(bmrDev != null ? T.ibBmr : T.bmrMifflin, fx(bmr, 0), "kcal", undefined, bmrK ? esc(T.bmrKatch) + ": " + fx(bmrK, 0) : "", bmrDev != null ? meas : est),
      card(T.energyNeed, fx(bmr ? bmr * pal : null, 0), "kcal", undefined, LTR(`BMR × ${pal}`), est),
    ].join("");
    const rows = [[T.mInbody, dev, meas], [T.mNavy, navy, est], [T.mDeur, deur, est]];
    $("#bcMethods").innerHTML = rows.map(([lab, v, tag]) => `<tr><td>${esc(lab)} <span class="pill pill-demo ms-1">${esc(tag)}</span></td><td class="n fw-semibold">${fx(v)}</td><td class="n">${v != null && w ? fx(w * v / 100) : "–"}</td><td class="n">${v != null && w ? fx(w * (1 - v / 100)) : "–"}</td><td>${v == null ? (lab === T.mNavy && sex === "F" && !hip ? `<span class="small text-secondary">${esc(T.needHip)}</span>` : "–") : chip(B.classify(v, range))}</td></tr>`).join("");
    $("#bcRangeNote").textContent = range ? pf(T.rangeNote, {sex: sex === "M" ? T.male : T.female, age, lo: range[0], hi: range[1]}) : T.rangeNA;
  }
  f.addEventListener("input", compute); f.addEventListener("change", compute);

  // static edition: save to a participant
  (async function () {
    const C = window.ANVCloud; if (!C || !C.configured) return;
    const user = await C.ready; if (!user) return;
    const sb = C.sb, sel = $("#bcPart"), qs = new URLSearchParams(location.search).get("participant");
    const {data: parts} = await sb.from("participants").select("id,code,sex,age_years").order("code");
    (parts || []).forEach(p => sel.append(new Option(p.code, p.id)));
    const pick = () => { const p = (parts || []).find(x => x.id === +sel.value); if (!p) return;
      if (["F", "M"].includes(p.sex)) f.sex.value = p.sex; if (p.age_years) f.age.value = p.age_years; compute(); };
    if (qs) sel.value = qs; sel.onchange = pick; pick();
    $("#bcDate").value = new Date().toISOString().slice(0, 10);
    $("#bcSave").onclick = async () => {
      const st = $("#bcStatus"); if (!sel.value || !last) return;
      const r = Object.fromEntries(Object.entries(last.row).filter(([, v]) => v != null && !isNaN(v)).map(([k, v]) => [k, Math.round(v * 100) / 100]));
      const device = {inbody: "InBody (entered)", navy: "Estimate: US Navy", deurenberg: "Estimate: Deurenberg"}[last.method];
      const {error} = await sb.from("body_measurements").insert({...r, participant_id: +sel.value, measured_at: new Date($("#bcDate").value + "T12:00:00").toISOString(), device, source_file: "calculator"});
      st.innerHTML = error ? `<span class="text-danger">${esc(error.code === "23505" ? T.dupMeasure : error.message)}</span>` : `<i class="bi bi-check-circle text-success me-1"></i>${esc(pf(T.saveOk, {c: sel.selectedOptions[0].textContent}))}`;
    };
  })();
  compute();
})();
