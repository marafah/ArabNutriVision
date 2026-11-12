/* ArabNutriVision · Analyze page: photo -> AI recognition -> recipe-aware estimate with interval. */
(function () {
  const DISHES = JSON.parse(JSON.parse(document.getElementById("anv-dishes").textContent));
  const NUT = JSON.parse(JSON.parse(document.getElementById("anv-nutrients").textContent));
  const KEY = Object.fromEntries(NUT.map((n, i) => [n.key, i]));
  const byCode = Object.fromEntries(DISHES.map(d => [d.code, d]));
  const $ = s => document.querySelector(s);
  const C = window.ANV_COLORS;
  const fmt = (x, u) => (u === "g" ? (Math.round(x * 10) / 10) : Math.round(x)).toLocaleString();
  const state = {dish: byCode.maqluba ? "maqluba" : DISHES[0].code, grams: 400, style: "mean", example: true, ai: null, source: "example"};

  // dish select grouped by category
  const sel = $("#dishSel");
  [...new Set(DISHES.map(d => d.cat))].forEach(c => {
    const g = document.createElement("optgroup"); g.label = c;
    DISHES.filter(d => d.cat === c).forEach(d => { const o = new Option(`${d.en.split(" (")[0]} · ${d.ar}`, d.code); g.append(o); });
    sel.append(g);
  });
  sel.value = state.dish;
  sel.onchange = () => { state.dish = sel.value; if (!state.ai) state.grams = byCode[state.dish].srv; state.example = false;
    state.source = state.ai ? "photo_corrected" : "manual"; syncGrams(); render(); };

  const gr = $("#grams"), grN = $("#gramsN");
  function syncGrams() { gr.value = Math.min(900, state.grams); grN.value = Math.round(state.grams); }
  gr.oninput = () => { state.grams = +gr.value; touched(); syncGrams(); render(); };
  grN.oninput = () => { const v = +grN.value; if (v > 0) { state.grams = v; touched(); gr.value = Math.min(900, v); render(); } };
  function touched() { state.example = false; if (state.source === "example") state.source = "manual"; if (state.source === "photo") state.source = "photo_corrected"; }
  document.querySelectorAll("#styles button").forEach(b => b.onclick = () => { state.style = b.dataset.style; setStyleBtns(); touched(); render(); });
  function setStyleBtns() { document.querySelectorAll("#styles button").forEach(x => x.classList.toggle("active", x.dataset.style === state.style)); }

  function compute(d, g, style) {
    const base = style === "mean" ? d.m : (d.v[style] || d.m);
    const lo = state.ai && state.ai.portion_low ? Math.min(g, state.ai.portion_low) : g * 0.8;
    const hi = state.ai && state.ai.portion_high ? Math.max(g, state.ai.portion_high) : g * 1.2;
    return {pt: base.map(x => x * g / 100), lo: d.lo.map(x => x * lo / 100), hi: d.hi.map(x => x * hi / 100), base};
  }

  let donut;
  function drawDonut(p, f, c) {
    const e = [p * 4, f * 9, c * 4], tot = e.reduce((a, b) => a + b, 0) || 1;
    const data = {labels: ["Protein", "Fat", "Carbohydrate"], datasets: [{data: e.map(v => Math.round(v)), backgroundColor: [C.blue, C.gold, C.olive], borderWidth: 2, borderColor: "#fff"}]};
    if (!window.Chart) return;
    if (donut) { donut.data = data; donut.update(); }
    else donut = new Chart($("#donut"), {type: "doughnut", data, options: {cutout: "62%", plugins: {legend: {display: false}, tooltip: {callbacks: {label: c => `${c.label}: ${c.raw} kcal`}}}}});
    $("#legend").innerHTML = [["Protein", e[0], p, C.blue], ["Fat", e[1], f, C.gold], ["Carbohydrate", e[2], c, C.olive]]
      .map(([n, en, g, col]) => `<div class="d-flex align-items-center gap-2 my-1"><i style="width:10px;height:10px;border-radius:3px;background:${col};display:inline-block"></i>${n}: <b>${fmt(g, "g")} g</b> · ${Math.round(en / tot * 100)}% of energy</div>`).join("");
  }

  function render() {
    const d = byCode[state.dish], r = compute(d, state.grams, state.style), i = KEY;
    $("#resEn").textContent = d.en; $("#resAr").textContent = d.ar;
    const tag = $("#resTag"), eb = $("#resEyebrow");
    const tags = {example: ["Example", "pill pill-demo", "Example result · not your photo"], photo: ["From photo", "pill pill-good", `Recognised · ${Math.round((state.ai?.confidence || 0) * 100)}% confidence`],
      photo_corrected: ["Corrected", "pill pill-good", "AI result, corrected by you"], manual: ["Manual", "pill pill-good", "Manual entry"]};
    const t = tags[state.example ? "example" : state.source] || tags.manual;
    tag.textContent = t[0]; tag.className = t[1] + " align-self-start"; eb.textContent = t[2];
    $("#kcal").textContent = fmt(r.pt[i.kcal], "kcal");
    $("#kcalRange").textContent = `Likely range ${fmt(r.lo[i.kcal], "kcal")}–${fmt(r.hi[i.kcal], "kcal")} kcal · ${Math.round(state.grams)} g · ${state.style === "mean" ? "average of 3 recipes" : state.style + " recipe"}`;
    drawDonut(r.pt[i.protein_g], r.pt[i.fat_g], r.pt[i.carb_g]);
    if (d.gi) {
      const avail = Math.max(r.base[i.carb_g] - r.base[i.fiber_g], 0) * state.grams / 100, gl = d.gi * avail / 100;
      $("#glLine").innerHTML = `<span class="pill ${gl >= 20 ? "pill-rose" : "pill-good"}">GL ${gl.toFixed(0)}</span> estimated glycaemic load (dish GI ≈ ${d.gi}, carbohydrate-weighted)`;
    } else $("#glLine").textContent = "";
    const sub = new Set(["sfa_g", "mufa_g", "pufa_g", "cholesterol_mg"]);
    $("#labelBox").innerHTML = `<div class="ln head"><span>Nutrient</span><span class="v">This portion</span><span class="r">Range</span></div>` +
      NUT.map(n => `<div class="ln ${sub.has(n.key) ? "sub" : ""}"><span>${n.label} <span class="text-secondary small" lang="ar">${n.ar}</span></span><span class="v">${fmt(r.pt[i[n.key]], n.unit)} ${n.unit}</span><span class="r">${fmt(r.lo[i[n.key]], n.unit)}–${fmt(r.hi[i[n.key]], n.unit)}</span></div>`).join("");
    $("#cmpRecipe").textContent = `${fmt(r.pt[i.kcal], "kcal")} kcal`; $("#cmpRecipeFat").textContent = `${fmt(r.pt[i.fat_g], "g")} g fat`;
    const de = state.ai && state.ai.direct_estimate;
    $("#cmpAI").textContent = de && de.kcal ? `${fmt(de.kcal, "kcal")} kcal` : "–";
    $("#cmpAIFat").textContent = de && de.fat_g != null ? `${fmt(de.fat_g, "g")} g fat` : "Shown after a photo is analysed";
    $("#hidden").innerHTML = `<i class="bi bi-eye-slash text-rose me-1"></i><b>Hidden-fat sources in this recipe:</b> ${d.fat.join(", ") || "none listed"}.` + (state.ai && state.ai.notes ? ` <span class="text-secondary">AI note: ${escapeHtml(state.ai.notes)}</span>` : "");
    fillValidation();
  }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])); }

  function renderAlts() {
    const box = $("#alts"); box.innerHTML = "";
    if (!state.ai || !state.ai.top3) return;
    state.ai.top3.filter(t => byCode[t.dish_id]).forEach(t => {
      const b = document.createElement("button"); b.type = "button";
      b.className = "btn btn-sm rounded-pill " + (t.dish_id === state.dish ? "btn-primary" : "btn-outline-secondary");
      b.textContent = `${byCode[t.dish_id].en.split(" (")[0]} ${Math.round((t.confidence || 0) * 100)}%`;
      b.onclick = () => { state.dish = t.dish_id; sel.value = t.dish_id; state.source = "photo_corrected"; renderAlts(); render(); };
      box.append(b);
    });
  }

  // photo input
  let photo = null;
  const drop = $("#drop"), file = $("#file");
  drop.onclick = () => file.click();
  drop.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); file.click(); } };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files[0]) setPhoto(e.dataTransfer.files[0]); };
  file.onchange = () => { if (file.files[0]) setPhoto(file.files[0]); };
  function setPhoto(f) {
    photo = f; const p = $("#preview"); p.src = URL.createObjectURL(f); p.hidden = false; $("#dropHint").hidden = true;
    $("#analyzeBtn").disabled = !window.ANV.ai;
    status(window.ANV.ai ? "Photo ready. Press Analyze." : "AI recognition is not configured on this server, so pick the dish and grams by hand.");
  }
  function status(t, err) { const s = $("#status"); s.textContent = t; s.className = "small mt-2 " + (err ? "text-danger" : "text-secondary"); }

  $("#analyzeBtn").onclick = async () => {
    if (!photo) return;
    $("#analyzeBtn").disabled = true; $("#spin").hidden = false; status("Looking at the photo… this can take up to a minute.");
    const fd = new FormData(); fd.append("photo", photo);
    try {
      const res = await fetch(window.ANV.recogniseUrl, {method: "POST", body: fd, headers: {"X-CSRFToken": window.ANV.csrf}});
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || "Analysis failed.");
      if (r.is_food === false) { status("No food found in this photo. Try a clearer top-down shot.", true); return; }
      state.ai = r; state.example = false;
      if (byCode[r.dish_id]) { state.dish = r.dish_id; state.source = "photo"; }
      else { state.source = "photo_corrected"; status(`Looks like "${r.other_name || "an unlisted dish"}", which is not in the table yet. Pick the closest dish.`, true); }
      sel.value = state.dish;
      state.grams = Math.max(30, Math.min(1500, +r.portion_g || byCode[state.dish].srv)); syncGrams();
      if (["home", "restaurant", "light"].includes(r.style)) { state.style = r.style; setStyleBtns(); }
      if (byCode[r.dish_id]) status(`Done. Check the dish and portion, then save.${r.reference_object && r.reference_object !== "none" ? " Scale from: " + r.reference_object + "." : ""}`);
      renderAlts(); render();
    } catch (e) { status(e.message || "Analysis failed. Try again.", true); }
    finally { $("#analyzeBtn").disabled = false; $("#spin").hidden = true; }
  };

  const addBtn = $("#addBtn");
  if (addBtn) addBtn.onclick = async () => {
    const fd = new FormData();
    fd.append("record", $("#recSel").value); fd.append("meal", $("#mealSel").value); fd.append("dish", state.dish);
    fd.append("grams", Math.round(state.grams)); fd.append("style", state.style); fd.append("source", state.example ? "manual" : state.source);
    if (state.ai && state.ai.direct_estimate && state.ai.direct_estimate.kcal) fd.append("ai_kcal", state.ai.direct_estimate.kcal);
    const s = $("#saveStatus");
    try {
      const res = await fetch(window.ANV.addUrl, {method: "POST", body: fd, headers: {"X-CSRFToken": window.ANV.csrf}});
      const r = await res.json(); if (!res.ok) throw new Error(r.error || "Could not save.");
      s.innerHTML = `<i class="bi bi-check-circle text-success me-1"></i>${escapeHtml(r.message)} <a href="${r.url}">Open record</a>`;
    } catch (e) { s.innerHTML = `<span class="text-danger">${escapeHtml(e.message)}</span>`; }
  };

  function fillValidation() {
    const f = $("#valForm"); if (!f) return;
    const d = byCode[state.dish];
    const set = (name, v) => { const el = f.querySelector(`[name="${name}"]`); if (el && v != null) el.value = v; };
    const dishOpt = [...f.querySelector('[name="dish"]').options].find(o => o.textContent.startsWith(d.en));
    if (dishOpt && !f.dataset.touched) f.querySelector('[name="dish"]').value = dishOpt.value;
    if (state.ai) {
      const aiOpt = [...f.querySelector('[name="ai_dish"]').options].find(o => byCode[state.ai.dish_id] && o.textContent.startsWith(byCode[state.ai.dish_id].en));
      if (aiOpt) f.querySelector('[name="ai_dish"]').value = aiOpt.value;
      set("ai_grams", Math.round(state.ai.portion_g || 0) || ""); set("ai_style", state.ai.style || "");
      if (state.ai.direct_estimate) { set("ai_direct_kcal", state.ai.direct_estimate.kcal); set("ai_direct_fat_g", state.ai.direct_estimate.fat_g); }
    }
  }
  const vf = $("#valForm"); if (vf) vf.addEventListener("change", () => vf.dataset.touched = "1");

  syncGrams(); render();
})();
