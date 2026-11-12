/* ArabNutriVision · Analyze page: photo -> AI recognition -> recipe-aware estimate with interval. */
(function () {
  const DISHES = JSON.parse(JSON.parse(document.getElementById("anv-dishes").textContent));
  const NUT = JSON.parse(JSON.parse(document.getElementById("anv-nutrients").textContent));
  const KEY = Object.fromEntries(NUT.map((n, i) => [n.key, i]));
  const byCode = Object.fromEntries(DISHES.map(d => [d.code, d]));
  const $ = s => document.querySelector(s);
  const C = window.ANV_COLORS;
  const T = window.ANV.T, AR = window.ANV_LANG === "ar";
  const fmt = (x, u) => (u === "g" ? (Math.round(x * 10) / 10) : Math.round(x)).toLocaleString("en-US");
  const fill = (s, v, c) => s.replace("{v}", v).replace("{c}", c);
  const nm = d => AR ? d.ar : d.en.split(" (")[0];       // primary name in the interface language
  const alt = d => AR ? d.en.split(" (")[0] : d.ar;      // secondary name
  const unit = u => ({kcal: T.kcal, g: T.g, mg: T.mg, "µg": T.ug})[u] || u;
  const rng = (a, b) => "\u2066" + a + "–" + b + "\u2069";   // keep numeric ranges left-to-right inside Arabic text
  const state = {dish: byCode.maqluba ? "maqluba" : DISHES[0].code, grams: 400, style: "mean", example: true, ai: null, source: "example"};

  // dish select grouped by category
  const sel = $("#dishSel");
  [...new Set(DISHES.map(d => d.cat))].forEach(c => {
    const g = document.createElement("optgroup"); g.label = c;
    DISHES.filter(d => d.cat === c).forEach(d => { const o = new Option(`${nm(d)} · ${alt(d)}`, d.code); g.append(o); });
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
    const data = {labels: [T.protein, T.fatName, T.carb], datasets: [{data: e.map(v => Math.round(v)), backgroundColor: [C.blue, C.gold, C.olive], borderWidth: 2, borderColor: "#fff"}]};
    if (!window.Chart) return;
    if (donut) { donut.data = data; donut.update(); }
    else donut = new Chart($("#donut"), {type: "doughnut", data, options: {cutout: "62%", plugins: {legend: {display: false}, tooltip: {callbacks: {label: c => `${c.label}: ${c.raw} ${T.kcal}`}}}}});
    $("#legend").innerHTML = [[T.protein, e[0], p, C.blue], [T.fatName, e[1], f, C.gold], [T.carb, e[2], c, C.olive]]
      .map(([n, en, g, col]) => `<div class="d-flex align-items-center gap-2 my-1"><i style="width:10px;height:10px;border-radius:3px;background:${col};display:inline-block"></i>${n}: <b>${fmt(g, "g")} ${T.g}</b> · ${Math.round(en / tot * 100)}% ${T.ofEnergy}</div>`).join("");
  }

  function render() {
    const d = byCode[state.dish], r = compute(d, state.grams, state.style), i = KEY;
    $("#resEn").textContent = AR ? d.ar : d.en; $("#resAr").textContent = alt(d);
    const tag = $("#resTag"), eb = $("#resEyebrow");
    const tags = {example: [T.example, "pill pill-demo", T.exampleEyebrow], photo: [T.fromPhoto, "pill pill-good", fill(T.recognised, "", Math.round((state.ai?.confidence || 0) * 100))],
      photo_corrected: [T.corrected, "pill pill-good", T.correctedEyebrow], manual: [T.manual, "pill pill-good", T.manualEyebrow]};
    const t = tags[state.example ? "example" : state.source] || tags.manual;
    tag.textContent = t[0]; tag.className = t[1] + " align-self-start"; eb.textContent = t[2];
    $("#kcal").textContent = fmt(r.pt[i.kcal], "kcal");
    $("#kcalRange").textContent = `${T.likely} ${rng(fmt(r.lo[i.kcal], "kcal"), fmt(r.hi[i.kcal], "kcal"))} ${T.kcal} · ${Math.round(state.grams)} ${T.g} · ${state.style === "mean" ? T.avg3 : T.styleRecipe[state.style]}`;
    drawDonut(r.pt[i.protein_g], r.pt[i.fat_g], r.pt[i.carb_g]);
    if (d.gi) {
      const avail = Math.max(r.base[i.carb_g] - r.base[i.fiber_g], 0) * state.grams / 100, gl = d.gi * avail / 100;
      $("#glLine").innerHTML = `<span class="pill ${gl >= 20 ? "pill-rose" : "pill-good"}">GL ${gl.toFixed(0)}</span> ${fill(T.gl, d.gi, "")}`;
    } else $("#glLine").textContent = "";
    const sub = new Set(["sfa_g", "mufa_g", "pufa_g", "cholesterol_mg"]);
    $("#labelBox").innerHTML = `<div class="ln head"><span>${T.nutrient}</span><span class="v">${T.portion}</span><span class="r">${T.range}</span></div>` +
      NUT.map(n => `<div class="ln ${sub.has(n.key) ? "sub" : ""}"><span>${n.label}</span><span class="v">${fmt(r.pt[i[n.key]], n.unit)} ${unit(n.unit)}</span><span class="r">${fmt(r.lo[i[n.key]], n.unit)}–${fmt(r.hi[i[n.key]], n.unit)}</span></div>`).join("");
    $("#cmpRecipe").textContent = `${fmt(r.pt[i.kcal], "kcal")} ${T.kcal}`; $("#cmpRecipeFat").textContent = `${fmt(r.pt[i.fat_g], "g")} ${T.g} ${T.fat}`;
    const avg = d.m.map(x => x * state.grams / 100);
    $("#cmpAI").textContent = `${fmt(avg[i.kcal], "kcal")} ${T.kcal}`;
    $("#cmpAIFat").textContent = `${fmt(avg[i.fat_g], "g")} ${T.g} ${T.fat} · ${T.range} ${rng(fmt(r.lo[i.kcal], "kcal"), fmt(r.hi[i.kcal], "kcal"))} ${T.kcal}`;
    $("#hidden").innerHTML = `<i class="bi bi-eye-slash text-rose me-1"></i><b>${T.hidden}</b> ${d.fat.join(AR ? "، " : ", ") || T.none}.` + (state.ai && state.ai.notes ? ` <span class="text-secondary">${T.note} ${escapeHtml(state.ai.notes)}</span>` : "");
    fillValidation();
  }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])); }

  function renderAlts() {
    const box = $("#alts"); box.innerHTML = "";
    if (!state.ai || !state.ai.top3) return;
    state.ai.top3.filter(t => byCode[t.dish_id]).forEach(t => {
      const b = document.createElement("button"); b.type = "button";
      b.className = "btn btn-sm rounded-pill " + (t.dish_id === state.dish ? "btn-primary" : "btn-outline-secondary");
      b.textContent = `${nm(byCode[t.dish_id])} ${Math.round((t.confidence || 0) * 100)}%`;
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
    $("#analyzeBtn").disabled = false;
    status(T.ready);
    // recognise automatically as soon as the photo is shown (the button stays for re-runs)
    p.decode().catch(() => {}).then(() => $("#analyzeBtn").click());
  }
  // start fetching the on-device model as soon as the visitor opens the photo picker
  drop.addEventListener("pointerdown", () => classifier().catch(() => {}), {once: true});
  function status(t, err) { const s = $("#status"); s.textContent = t; s.className = "small mt-2 " + (err ? "text-danger" : "text-secondary"); }

  // ---- on-device recognition: CLIP zero-shot (open-source, runs in the browser; no API) ----
  // Several visual descriptions per dish (prompt ensemble); a dish's score is the sum over its prompts.
  const LOOKS = {
    maqluba: ["an upside-down rice cake turned out on a platter, layered with fried eggplant, cauliflower and chicken",
              "a dome of rice with fried eggplant slices and chicken on top, Palestinian maqluba",
              "a large tray of rice with fried vegetables and chicken pieces, garnished with nuts"],
    mansaf: ["a large round platter of yellow rice topped with big chunks of lamb on the bone, pine nuts and almonds",
             "Jordanian mansaf: lamb meat with bones on yellow rice garnished with toasted pine nuts and parsley",
             "a festive tray of rice and boiled lamb pieces with fried nuts, served with white yogurt sauce"],
    musakhan: ["roasted chicken on flatbread covered with purple sumac onions",
               "musakhan: taboon bread topped with caramelised red onions, sumac and roast chicken"],
    mulukhiyah: ["a bowl of dark green jute leaf stew", "mulukhiyah: a glossy green leafy stew served with rice and chicken"],
    kabsa: ["orange spiced rice with roasted chicken quarters, raisins and nuts", "Gulf kabsa: reddish-orange rice with a whole roasted chicken on top"],
    mujaddara: ["brown lentils and rice topped with crispy dark fried onions", "a plate of mujaddara, beige lentil rice with caramelised onions"],
    warak_enab: ["rolled stuffed grape vine leaves arranged in rows", "dark green cylinders of stuffed vine leaves with lemon"],
    kofta_tahini: ["kofta meat fingers baked in a tray with white tahini sauce and potatoes", "minced meat patties baked under a creamy tahini sauce"],
    chicken_shawarma_wrap: ["a chicken shawarma wrap sandwich rolled in thin bread", "a toasted pita wrap filled with sliced chicken, garlic sauce and pickles"],
    ruz_shaariyeh: ["a plate of plain white rice with toasted vermicelli noodles", "fluffy white rice mixed with golden brown vermicelli"],
    hummus: ["a plate of smooth creamy beige chickpea dip with olive oil and paprika", "hummus spread in a shallow bowl with a swirl of olive oil"],
    mutabbal: ["a bowl of smoky grey eggplant dip with tahini", "baba ghanoush, a pale grey-beige mashed eggplant dip with pomegranate seeds"],
    tabbouleh: ["a finely chopped green parsley salad with tomato and bulgur", "tabbouleh, a bright green herb salad with diced tomatoes"],
    fattoush: ["a mixed green salad with fried pita bread chips and sumac", "fattoush salad with lettuce, tomato, cucumber, radish and crispy bread"],
    falafel: ["fried brown chickpea balls", "a plate of crispy round falafel with tahini"],
    foul: ["mashed brown fava beans with olive oil in a bowl", "foul mudammas, a brown bean stew topped with olive oil, tomato and parsley"],
    manakish_zaatar: ["a round flatbread topped with green za'atar and olive oil", "manakish, a baked pizza-like bread covered with dark green thyme mix"],
    fatayer_spinach: ["triangular baked pastries filled with spinach", "small golden triangle pies stuffed with spinach"],
    knafeh: ["an orange shredded pastry dessert with melted white cheese and syrup", "knafeh, a bright orange cheese dessert topped with crushed green pistachios"],
    basbousa: ["semolina cake squares soaked in syrup with almonds", "golden yellow diamond-cut semolina cake pieces"],
    freekeh_chicken: ["green smoked cracked wheat with chicken", "a plate of freekeh, greenish-brown grain with chicken and nuts"],
    fattet_hummus: ["chickpeas and toasted bread under white yogurt tahini sauce with pine nuts", "fatteh in a bowl: creamy white yogurt topping with chickpeas, fried bread and pine nuts"],
  };
  const NOT_FOOD = "something that is not food";
  const STYLE_PROMPTS = {light: "a light, lean home-made plate with very little oil",
    home: "an ordinary home-cooked plate of food", restaurant: "a rich restaurant plate glistening with oil, ghee and fried nuts"};
  let clfPromise = null;
  async function classifier() {
    if (!clfPromise) clfPromise = (async () => {
      const TF = await import(window.ANV.vendor + "transformers.min.js");
      TF.env.allowLocalModels = false;
      TF.env.backends.onnx.wasm.wasmPaths = window.ANV.vendor;
      TF.env.backends.onnx.wasm.numThreads = 1;
      const bar = $("#dlBar"), barFill = bar.querySelector(".progress-bar"); bar.hidden = false;
      const files = {};
      const clf = await TF.pipeline("zero-shot-image-classification", "Xenova/clip-vit-base-patch32", {
        progress_callback: p => {
          if (p.status !== "progress" || !p.file) return;
          files[p.file] = p.progress || 0;
          const v = Object.values(files), pct = Math.round(v.reduce((a, b) => a + b, 0) / v.length);
          barFill.style.width = pct + "%";
          status(fill(T.download, pct, ""));
        } });
      bar.hidden = true; return clf;
    })().catch(e => { clfPromise = null; throw e; });
    return clfPromise;
  }

  $("#analyzeBtn").onclick = async () => {
    if (!photo) return;
    $("#analyzeBtn").disabled = true; $("#spin").hidden = false; status(T.loading);
    try {
      const clf = await classifier();
      status(T.recognising);
      const url = $("#preview").src;
      const codes = DISHES.map(d => d.code), labels = [], owner = [];
      codes.forEach(c => (LOOKS[c] || [byCode[c].en]).forEach(t => { labels.push(t); owner.push(c); }));
      labels.push(NOT_FOOD); owner.push(null);
      const res = await clf(url, labels, {hypothesis_template: "a photo of {}."});
      const score = {}; let notFood = 0;
      res.forEach(r => { const c = owner[labels.indexOf(r.label)]; if (c) score[c] = (score[c] || 0) + r.score; else notFood = r.score; });
      if (notFood > 0.5) { status(T.notFood, true); return; }
      const ranked = codes.map(c => ({dish_id: c, confidence: score[c] || 0})).sort((a, b) => b.confidence - a.confidence);
      const norm = ranked.reduce((a, r) => a + r.confidence, 0) || 1;
      ranked.forEach(r => r.confidence /= norm);
      const st = await clf(url, Object.values(STYLE_PROMPTS), {hypothesis_template: "{}."});
      const sbest = st[0], style = Object.keys(STYLE_PROMPTS).find(k => STYLE_PROMPTS[k] === sbest.label);
      state.ai = {dish_id: ranked[0].dish_id, confidence: ranked[0].confidence, top3: ranked.slice(0, 3),
                  style: sbest.score > 0.5 ? style : null, notes: fill(T.styleNote, T.styleName[style], Math.round(sbest.score * 100))};
      state.example = false; state.dish = state.ai.dish_id; state.source = "photo"; sel.value = state.dish;
      state.grams = byCode[state.dish].srv; syncGrams();
      if (state.ai.style) { state.style = state.ai.style; setStyleBtns(); }
      status(fill(T.done, nm(byCode[state.dish]), Math.round(ranked[0].confidence * 100)));
      renderAlts(); render();
    } catch (e) { console.error(e); status(T.failed, true); }
    finally { $("#analyzeBtn").disabled = false; $("#spin").hidden = true; }
  };

  const addBtn = $("#addBtn");
  if (addBtn && !window.ANV_CFG) addBtn.onclick = async () => {
    const fd = new FormData();
    fd.append("record", $("#recSel").value); fd.append("meal", $("#mealSel").value); fd.append("dish", state.dish);
    fd.append("grams", Math.round(state.grams)); fd.append("style", state.style); fd.append("source", state.example ? "manual" : state.source);
    const s = $("#saveStatus");
    try {
      const res = await fetch(window.ANV.addUrl, {method: "POST", body: fd, headers: {"X-CSRFToken": window.ANV.csrf}});
      const r = await res.json(); if (!res.ok) throw new Error(r.error || T.saveFail);
      s.innerHTML = `<i class="bi bi-check-circle text-success me-1"></i>${escapeHtml(r.message)} <a href="${r.url}">${T.openRecord}</a>`;
    } catch (e) { s.innerHTML = `<span class="text-danger">${escapeHtml(e.message)}</span>`; }
  };

  function fillValidation() {
    if (window.ANV.onResult) window.ANV.onResult(state);   // static edition (workspace.js) fills its own form
    const f = $("#valForm"); if (!f) return;
    const d = byCode[state.dish];
    const set = (name, v) => { const el = f.querySelector(`[name="${name}"]`); if (el && v != null) el.value = v; };
    const dishOpt = [...f.querySelector('[name="dish"]').options].find(o => o.textContent.startsWith(d.en));  // admin form lists English names
    if (dishOpt && !f.dataset.touched) f.querySelector('[name="dish"]').value = dishOpt.value;
    if (state.ai) {
      const aiOpt = [...f.querySelector('[name="ai_dish"]').options].find(o => byCode[state.ai.dish_id] && o.textContent.startsWith(byCode[state.ai.dish_id].en));
      if (aiOpt) f.querySelector('[name="ai_dish"]').value = aiOpt.value;
      set("ai_grams", Math.round(state.grams)); set("ai_style", state.ai.style || "");
    }
  }
  const vf = $("#valForm"); if (vf) vf.addEventListener("change", () => vf.dataset.touched = "1");

  window.ANV.state = state;
  syncGrams(); render();
})();
