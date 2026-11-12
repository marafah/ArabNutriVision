/* ArabNutriVision static edition: researcher workspace in the browser.
   Reads and writes the signed-in researcher's rows in Supabase (row-level security) and computes every
   nutrient total with the same recipe-aware composition table as the Django edition
   (ports of services/estimate.py and services/metrics.py). No external AI is used. */
(function () {
  const REF = JSON.parse(document.getElementById("anv-ref").textContent);
  const T = JSON.parse(document.getElementById("anv-t").textContent);
  const U = window.ANV_URLS, CL = window.ANVCloud, sb = CL && CL.sb, COL = window.ANV_COLORS;
  const AR = window.ANV_LANG === "ar", PAGE = window.ANV_PAGE;
  const K = REF.keys, I = Object.fromEntries(K.map((k, i) => [k, i]));
  const DISH = Object.fromEntries(REF.dishes.map(d => [d.code, d]));
  const ING = Object.fromEntries(REF.ingredients.map(x => [x.code, x]));
  const SUPP = Object.fromEntries(REF.supplements.map(x => [x.name, x]));
  const label = list => Object.fromEntries(REF[list]);
  const MEAL = label("meals"), METHOD = label("methods"), SEX = label("sexes"), SOURCE = label("sources"), STYLE = label("styles");
  const MEAL_ORDER = Object.fromEntries(REF.meals.map(([k], i) => [k, i]));
  const $ = (s, r = document) => r.querySelector(s);

  // ---------------------------------------------------------------- formatting helpers
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
  /** Python %-format (the msgids are shared with the server edition). */
  const pf = (s, o = {}) => s.replace(/%%|%\((\w+)\)(?:\.(\d+))?([sdf])/g, (m, k, nd, t) =>
    m === "%%" ? "%" : t === "f" ? Number(o[k]).toFixed(nd === undefined ? 6 : +nd) : t === "d" ? String(Math.round(o[k])) : String(o[k]));
  const n0 = x => (x == null || isNaN(x)) ? "–" : Math.round(x).toLocaleString("en-US");
  const n1 = x => (x == null || isNaN(x)) ? "–" : (Math.round(x * 10) / 10).toFixed(1);
  const LTR = s => "⁦" + s + "⁩";
  const dName = d => d ? (AR ? (d.ar || d.en) : d.en.split(" (")[0]) : "?";
  const dAlt = d => d ? (AR ? d.en.split(" (")[0] : d.ar) : "";
  const dateFmt = new Intl.DateTimeFormat(AR ? "ar-u-nu-latn" : "en-GB", {day: "2-digit", month: "short", year: "numeric"});
  const dateLong = new Intl.DateTimeFormat(AR ? "ar-u-nu-latn" : "en-GB", {weekday: "long", day: "2-digit", month: "short", year: "numeric"});
  const fdate = (s, long) => s ? (long ? dateLong : dateFmt).format(new Date(s + "T12:00:00")) : "";
  const qs = k => new URLSearchParams(location.search).get(k);
  const url = (base, id) => `${base}?id=${encodeURIComponent(id)}`;

  function notice(msg) {
    const n = $("#wsNotice"), l = $("#wsLoading");
    if (l) l.hidden = true;
    if (n) { n.innerHTML = msg; n.classList.remove("d-none"); }
  }
  function ready() { const l = $("#wsLoading"), b = $("#wsBody"); if (l) l.hidden = true; if (b) b.hidden = false; }
  function check({error, data, count}) { if (error) throw error; return count !== undefined && count !== null && data == null ? count : data; }
  function twice(btn, run) {        // destructive buttons need a second press
    btn.addEventListener("click", async e => {
      e.preventDefault();
      if (btn.dataset.ok !== "1") { btn.dataset.ok = "1"; btn.dataset.txt = btn.innerHTML; btn.textContent = T.confirmDel;
        setTimeout(() => { btn.dataset.ok = ""; btn.innerHTML = btn.dataset.txt; }, 4000); return; }
      btn.disabled = true; try { await run(); } catch (err) { btn.disabled = false; alert(err.message || T.saveFail); }
    });
  }
  function download(name, rows) {
    const csv = rows.map(r => r.map(v => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }).join(",")).join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + csv + "\r\n"], {type: "text/csv;charset=utf-8"}));
    a.download = name; document.body.append(a); a.click(); a.remove();
  }

  // ---------------------------------------------------------------- selects
  const OPTS = {
    dishes: () => REF.dishes.slice().sort((a, b) => dName(a).localeCompare(dName(b), AR ? "ar" : "en")).map(d => [d.code, `${dName(d)} · ${dAlt(d)}`]),
    ingredients: () => REF.ingredients.map(x => [x.code, x.name]),
    supplements: () => REF.supplements.map(x => [x.name, x.name]),
    meals: () => REF.meals, methods: () => REF.methods, sexes: () => REF.sexes, styles: () => REF.styles,
    variants: () => REF.variants, views: () => REF.views,
  };
  function fillSelects(root = document) {
    root.querySelectorAll("select[data-opts]").forEach(s => {
      if (s.options.length) return;
      if (s.dataset.blank) s.append(new Option("—", ""));
      OPTS[s.dataset.opts]().filter(([k]) => k !== s.dataset.exclude).forEach(([k, v]) => s.append(new Option(v, k)));
      if (s.dataset.default) s.value = s.dataset.default;
    });
  }
  const formData = f => Object.fromEntries([...f.elements].filter(e => e.name).map(e => [e.name, e.type === "checkbox" ? e.checked : e.value.trim()]));
  const num = v => (v === "" || v == null) ? null : +v;

  // ---------------------------------------------------------------- nutrient arithmetic (services/estimate.py)
  const zero = () => K.map(() => 0);
  const per100 = (d, style) => (style && style !== "mean" && d.v[style]) ? d.v[style] : d.m;
  function glDish(d, g, style) {
    if (d.gi == null) return null;
    const p = per100(d, style);
    return Math.round(d.gi * Math.max(p[I.carb_g] - p[I.fiber_g], 0) * g / 100 / 100 * 10) / 10;
  }
  function itemNut(it) {
    if (it.dish_code) { const d = DISH[it.dish_code]; return d ? per100(d, it.style).map(x => it.grams * x / 100) : zero(); }
    const g = ING[it.ingredient_code]; return g ? g.n.map(x => it.grams * x / 100) : zero();
  }
  function itemName(it) { return it.dish_code ? dName(DISH[it.dish_code]) : (ING[it.ingredient_code] || {}).name || "?"; }
  function summary(items, supps, target) {
    const rows = [], meals = {}, totals = zero(); let gl = 0;
    items.slice().sort((a, b) => (MEAL_ORDER[a.meal] ?? 9) - (MEAL_ORDER[b.meal] ?? 9) || a.created_at.localeCompare(b.created_at)).forEach(it => {
      const n = itemNut(it); let g = null;
      if (it.dish_code && DISH[it.dish_code]) g = glDish(DISH[it.dish_code], it.grams, it.style);
      else if (ING[it.ingredient_code] && ING[it.ingredient_code].gi != null) { const x = ING[it.ingredient_code]; g = x.gi * Math.max(x.n[I.carb_g] - x.n[I.fiber_g], 0) * it.grams / 10000; }
      gl += g || 0; rows.push({it, n, gl: g});
      const m = meals[MEAL[it.meal] || it.meal] = meals[MEAL[it.meal] || it.meal] || zero();
      n.forEach((v, i) => { m[i] += v; totals[i] += v; });
    });
    const suppTotals = zero(), suppRows = [];
    supps.forEach(s => { const x = SUPP[s.supplement_name]; const n = x ? x.n.map(v => v * s.doses) : zero(); suppRows.push({s, x, n}); n.forEach((v, i) => suppTotals[i] += v); });
    const withSupp = totals.map((v, i) => v + suppTotals[i]);
    const pct = REF.nutrients.map(nu => { const ref = nu.key === "kcal" ? (target || 2000) : nu.ref; return ref ? {nu, value: withSupp[I[nu.key]], pct: 100 * withSupp[I[nu.key]] / ref} : null; }).filter(Boolean);
    const e = totals[I.kcal] || 1;
    const macro = {Protein: 400 * totals[I.protein_g] / e, Fat: 900 * totals[I.fat_g] / e, Carbohydrate: 400 * totals[I.carb_g] / e};
    const fa = {SFA: 900 * totals[I.sfa_g] / e, MUFA: 900 * totals[I.mufa_g] / e, PUFA: 900 * totals[I.pufa_g] / e};
    const contributors = rows.slice().sort((a, b) => b.n[I.kcal] - a.n[I.kcal]).slice(0, 5);
    return {rows, meals, totals, suppRows, suppTotals, withSupp, pct, macro, fa, gl, contributors};
  }
  function insights(s) {
    const t = s.totals, w = s.withSupp, out = [], e = t[I.kcal];
    if (!s.rows.length) return out;
    if (s.macro.Fat > 35) out.push(["warn", "droplet-half", pf(T.inFat, {p: s.macro.Fat})]);
    if (s.fa.SFA > 10) out.push(["crit", "exclamation-octagon", pf(T.inSfa, {p: s.fa.SFA})]);
    if (w[I.sodium_mg] > 2300) out.push(["crit", "moisture", pf(T.inNa, {v: w[I.sodium_mg]})]);
    if (t[I.fiber_g] < 25 && e > 1000) out.push(["warn", "flower1", pf(T.inFib, {v: t[I.fiber_g]})]);
    if (s.gl > 120) out.push(["warn", "graph-up-arrow", pf(T.inGl, {v: s.gl})]);
    const hidden = s.rows.filter(r => r.it.dish_code && ["restaurant", "mean"].includes(r.it.style));
    if (hidden.length) out.push(["warn", "eye-slash", pf(T.inHidden, {n: hidden.length, k: hidden.reduce((a, r) => a + r.n[I.kcal], 0)})]);
    const top = s.contributors.slice(0, 3);
    if (top.length && e) out.push(["info", "pie-chart", pf(T.inTop, {names: top.map(r => `${itemName(r.it)} (${Math.round(100 * r.n[I.kcal] / e)}%)`).join(AR ? "، " : ", ")})]);
    [["iron_mg", T.iron, 18], ["calcium_mg", T.calcium, 1300]].forEach(([k, lab, ref]) => {
      if (w[I[k]] < 0.5 * ref) out.push(["warn", "capsule", pf(T.inMin, {label: lab, v: w[I[k]], p: 100 * w[I[k]] / ref})]);
    });
    if (!out.some(x => x[0] === "warn" || x[0] === "crit")) out.unshift(["good", "check-circle", T.inOk]);
    return out;
  }

  // ---------------------------------------------------------------- validation metrics (services/metrics.py)
  const mae = (p, t) => t.length ? p.reduce((a, x, i) => a + Math.abs(x - t[i]), 0) / t.length : null;
  function mape(p, t) { const pr = p.map((x, i) => [x, t[i]]).filter(([, y]) => y); return pr.length ? 100 * pr.reduce((a, [x, y]) => a + Math.abs(x - y) / y, 0) / pr.length : null; }
  function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function bootCI(p, t, nBoot = 1000) {
    if (t.length < 3) return null;
    const r = rng(0), n = t.length, vals = [];
    for (let b = 0; b < nBoot; b++) { const ps = [], ts = []; for (let j = 0; j < n; j++) { const k = Math.floor(r() * n); ps.push(p[k]); ts.push(t[k]); } vals.push(mape(ps, ts)); }
    vals.sort((a, b) => a - b); return [vals[Math.floor(0.025 * nBoot)], vals[Math.floor(0.975 * nBoot) - 1]];
  }
  function bland(p, t) {
    const d = p.map((x, i) => x - t[i]); if (d.length < 2) return null;
    const m = d.reduce((a, b) => a + b, 0) / d.length, sd = Math.sqrt(d.reduce((a, x) => a + (x - m) ** 2, 0) / (d.length - 1));
    return {bias: m, lo: m - 1.96 * sd, hi: m + 1.96 * sd, points: p.map((x, i) => ({x: (x + t[i]) / 2, y: x - t[i]}))};
  }
  const msum = (p, t) => t.length ? {n: t.length, mae: mae(p, t), mape: mape(p, t), ci: bootCI(p, t), ba: bland(p, t)} : null;
  function evaluate(samples) {
    const rows = [];
    samples.forEach(s => {
      const dt = DISH[s.dish_code]; if (!dt) return;
      const truthP = s.variant && dt.v[s.variant] ? dt.v[s.variant] : dt.m;
      const r = {s, truth: {kcal: s.weight_g * truthP[I.kcal] / 100, fat: s.weight_g * truthP[I.fat_g] / 100}};
      if (s.ai_dish_code && s.ai_grams) {
        const da = DISH[s.ai_dish_code] || dt, base = per100(da, s.ai_style || "mean");
        r.recipe = {kcal: s.ai_grams * base[I.kcal] / 100, fat: s.ai_grams * base[I.fat_g] / 100,
                    lo: 0.8 * s.ai_grams * da.lo[I.kcal] / 100, hi: 1.2 * s.ai_grams * da.hi[I.kcal] / 100};
        r.oracle = {kcal: s.ai_grams * dt.m[I.kcal] / 100, fat: s.ai_grams * dt.m[I.fat_g] / 100};
      }
      if (s.ai_direct_kcal != null) r.image = {kcal: s.ai_direct_kcal, fat: s.ai_direct_fat_g};
      rows.push(r);
    });
    const sys = (key, nut) => { const pr = rows.filter(r => r[key] && r[key][nut] != null); return pr.length ? msum(pr.map(r => r[key][nut]), pr.map(r => r.truth[nut])) : null; };
    const rec = rows.filter(r => r.s.ai_dish_code), port = rows.filter(r => r.s.ai_grams), cov = rows.filter(r => r.recipe);
    const res = {n: rows.length, sessions: new Set(rows.map(r => r.s.session_id)).size,
      top1: rec.length ? 100 * rec.filter(r => r.s.ai_dish_code === r.s.dish_code).length / rec.length : null,
      portion: port.length ? msum(port.map(r => r.s.ai_grams), port.map(r => r.s.weight_g)) : null,
      coverage: cov.length ? 100 * cov.filter(r => r.recipe.lo <= r.truth.kcal && r.truth.kcal <= r.recipe.hi).length / cov.length : null, systems: []};
    [["image", T.sysImage, T.sysImageD], ["recipe", T.sysRecipe, T.sysRecipeD], ["oracle", T.sysOracle, T.sysOracleD]].forEach(([key, lab, desc]) => {
      const e = sys(key, "kcal"), f = sys(key, "fat"); if (e) res.systems.push({key, lab, desc, e, f});
    });
    return {rows, res};
  }

  // ---------------------------------------------------------------- shared UI pieces
  function pctRows(list) {
    return list.map(p => { const cls = p.nu.upper && p.pct > 100 ? "bg-danger" : p.pct > 100 ? "bg-warning" : "bg-primary";
      return `<div class="dv-row"><span>${esc(p.nu.label)}</span><div class="progress progress-thin"><div class="progress-bar ${cls}" style="width:${Math.min(100, Math.round(p.pct))}%"></div></div><span class="pct">${Math.round(p.pct)}%</span></div>`; }).join("");
  }
  const charts = {};
  function chart(id, cfg) { const el = document.getElementById(id); if (!el || !window.Chart) return; if (charts[id]) charts[id].destroy(); charts[id] = new Chart(el, cfg); }
  const yPos = AR ? "right" : "left";

  async function loadItems(recordIds) {
    if (!recordIds.length) return {items: [], supps: []};
    const [items, supps] = await Promise.all([
      sb.from("items").select("*").in("record_id", recordIds).then(check),
      sb.from("supplement_intakes").select("*").in("record_id", recordIds).then(check)]);
    return {items, supps};
  }
  async function saveValidation(form) {
    const st = form.querySelector("[data-status]"), d = formData(form);
    if (!d.session_id || !d.dish_code || !(+d.weight_g > 0)) { st.innerHTML = `<span class="text-danger">${esc(T.required)}</span>`; return; }
    const row = {session_id: d.session_id, plate_no: num(d.plate_no) || 1, dish_code: d.dish_code, variant: d.variant || "home", weight_g: +d.weight_g,
      view: d.view || "top", reference_card: !!d.reference_card, phone: d.phone, split: d.split || "test", ai_dish_code: d.ai_dish_code || null,
      ai_grams: num(d.ai_grams), ai_style: d.ai_style || "", ai_direct_kcal: num(d.ai_direct_kcal), ai_direct_fat_g: num(d.ai_direct_fat_g)};
    row.image_file = `${row.dish_code}_${row.session_id}_p${String(row.plate_no).padStart(2, "0")}_${row.view}_${row.reference_card ? "card" : "nocard"}.jpg`;
    try { check(await sb.from("validation_samples").insert(row)); st.innerHTML = `<i class="bi bi-check-circle text-success me-1"></i>${esc(pf(T.plateSaved, {f: row.image_file}))}`; return true; }
    catch (e) { st.innerHTML = `<span class="text-danger">${esc(e.message || T.saveFail)}</span>`; }
  }

  // ---------------------------------------------------------------- pages
  const pages = {};

  pages.dashboard = async user => {
    const [parts, recs, nItems, nVal] = await Promise.all([
      sb.from("participants").select("id,code,sex,age_years").order("code").then(check),
      sb.from("records").select("id,participant_id,date,method").order("date", {ascending: false}).order("created_at", {ascending: false}).then(check),
      sb.from("items").select("id", {count: "exact", head: true}).then(r => { if (r.error) throw r.error; return r.count; }),
      sb.from("validation_samples").select("id", {count: "exact", head: true}).then(r => { if (r.error) throw r.error; return r.count; })]);
    $("#wsWelcome").textContent = pf(T.welcome, {n: user.email});
    $("#nPart").textContent = parts.length; $("#nRec").textContent = recs.length; $("#nItems").textContent = nItems; $("#nVal").textContent = nVal;
    const code = Object.fromEntries(parts.map(p => [p.id, p.code])), cnt = {};
    recs.forEach(r => cnt[r.participant_id] = (cnt[r.participant_id] || 0) + 1);
    $("#partList").innerHTML = parts.length ? parts.map(p => `<li class="list-group-item d-flex justify-content-between px-0"><a href="${url(U.participant, p.id)}" class="fw-semibold">${esc(p.code)}</a><span class="small text-secondary">${esc(SEX[p.sex] || "")}${p.age_years ? ", " + esc(pf(T.y, {a: p.age_years})) : ""} · ${esc(pf(T.nRecords, {n: cnt[p.id] || 0}))}</span></li>`).join("")
      : `<li class="list-group-item px-0 text-secondary">${esc(T.noParticipants)}</li>`;
    $("#recList").innerHTML = recs.length ? recs.slice(0, 6).map(r => `<li class="list-group-item d-flex justify-content-between px-0"><a href="${url(U.record, r.id)}">${esc(code[r.participant_id])} · ${esc(fdate(r.date))}</a><span class="small text-secondary">${esc(METHOD[r.method] || r.method)}</span></li>`).join("")
      : `<li class="list-group-item px-0 text-secondary">${esc(T.noRecords)}</li>`;
  };

  pages.participants = async () => {
    async function draw() {
      const [parts, recs] = await Promise.all([sb.from("participants").select("*").order("code").then(check), sb.from("records").select("participant_id").then(check)]);
      const cnt = {}; recs.forEach(r => cnt[r.participant_id] = (cnt[r.participant_id] || 0) + 1);
      $("#partRows").innerHTML = parts.length ? parts.map(p => `<tr style="cursor:pointer" data-href="${url(U.participant, p.id)}"><td class="ps-3"><a class="fw-semibold" href="${url(U.participant, p.id)}">${esc(p.code)}</a></td><td>${esc(SEX[p.sex] || "")}</td><td class="n">${p.age_years ?? "–"}</td><td class="n">${p.energy_target_kcal} ${esc(T.kcal)}</td><td class="n">${cnt[p.id] || 0}</td><td class="small text-secondary pe-3">${esc(p.notes || "")}</td></tr>`).join("")
        : `<tr><td colspan="6" class="text-center text-secondary py-4">${esc(T.noParticipants)}</td></tr>`;
      document.querySelectorAll("#partRows tr[data-href]").forEach(tr => tr.onclick = () => location.href = tr.dataset.href);
    }
    await draw();
    $("#partForm").onsubmit = async e => {
      e.preventDefault(); const d = formData(e.target), err = $("#partErr"); err.textContent = "";
      if (!d.code) { err.textContent = T.required; return; }
      const {data, error} = await sb.from("participants").insert({code: d.code, sex: d.sex || "X", age_years: num(d.age_years),
        energy_target_kcal: num(d.energy_target_kcal) || 2000, notes: d.notes}).select("id").single();
      if (error) { err.textContent = error.code === "23505" ? T.dupCode : (error.message || T.saveFail); return; }
      location.href = url(U.participant, data.id);
    };
  };

  pages.participant = async () => {
    const id = +qs("id");
    const part = check(await sb.from("participants").select("*").eq("id", id).maybeSingle());
    if (!part) { notice(esc(T.saveFail)); return false; }
    const recs = check(await sb.from("records").select("*").eq("participant_id", id).order("date", {ascending: false}).order("created_at", {ascending: false}));
    const {items, supps} = await loadItems(recs.map(r => r.id));
    document.title = part.code + " · ArabNutriVision";
    $("#bcCode").textContent = part.code; $("#pTitle").textContent = pf(T.participantTitle, {c: part.code});
    $("#pMeta").textContent = [SEX[part.sex], part.age_years ? pf(T.years, {a: part.age_years}) : null, pf(T.target, {t: part.energy_target_kcal})].filter(Boolean).join(" · ");
    $("#ffqLink").href += "?participant=" + id;
    const days = recs.map(r => ({r, s: summary(items.filter(x => x.record_id === r.id), supps.filter(x => x.record_id === r.id), part.energy_target_kcal)}));
    const food = days.filter(x => x.r.method !== "ffq");
    $("#nDays").textContent = pf(T.nDays, {n: food.length});
    $("#dayRows").innerHTML = days.map(({r, s}) => `<tr style="cursor:pointer" data-href="${url(U.record, r.id)}"><td class="ps-3"><a href="${url(U.record, r.id)}">${esc(fdate(r.date))}</a></td><td>${esc(METHOD[r.method] || r.method)}</td><td class="n">${s.rows.length}</td><td class="n fw-semibold">${n0(s.totals[I.kcal])}</td><td class="n">${n1(s.totals[I.protein_g])}</td><td class="n">${n1(s.totals[I.fat_g])}</td><td class="n"><span class="pill ${s.fa.SFA > 10 ? "pill-rose" : "pill-good"}">${n1(s.fa.SFA)}%</span></td><td class="n pe-3">${n0(s.totals[I.sodium_mg])}</td></tr>`).join("");
    document.querySelectorAll("#dayRows tr[data-href]").forEach(tr => tr.onclick = () => location.href = tr.dataset.href);
    if (!days.length) { $("#trendBox").hidden = true; $("#noDays").hidden = false; }
    else {
      const tr = days.slice().reverse();
      chart("trend", {type: "bar", data: {labels: tr.map(x => x.r.date + (x.r.method === "ffq" ? " (FFQ)" : "")), datasets: [
        {label: T.energyKcal, data: tr.map(x => Math.round(x.s.totals[I.kcal])), backgroundColor: COL.navy, yAxisID: "y"},
        {type: "line", label: T.fatG, data: tr.map(x => +x.s.totals[I.fat_g].toFixed(1)), borderColor: COL.rose, backgroundColor: COL.rose, yAxisID: "y1"}]},
        options: {maintainAspectRatio: false, plugins: {legend: {position: "bottom"}}, scales: {x: {reverse: AR}, y: {beginAtZero: true, position: yPos}, y1: {beginAtZero: true, position: AR ? "left" : "right", grid: {drawOnChartArea: false}}}}});
    }
    if (food.length) {
      const mean = K.map((_, i) => food.reduce((a, x) => a + x.s.withSupp[i], 0) / food.length);
      const pct = REF.nutrients.map(nu => { const ref = nu.key === "kcal" ? part.energy_target_kcal : nu.ref; return ref ? {nu, pct: 100 * mean[I[nu.key]] / ref} : null; }).filter(Boolean);
      $("#usualTitle").textContent = pf(T.usual, {n: food.length}); $("#usualRows").innerHTML = pctRows(pct); $("#usualBox").hidden = false;
    }
    $("#r_date").value = new Date().toISOString().slice(0, 10);
    $("#recForm").onsubmit = async e => {
      e.preventDefault(); const d = formData(e.target);
      if (!d.date) { $("#recErr").textContent = T.required; return; }
      const {data, error} = await sb.from("records").insert({participant_id: id, date: d.date, method: d.method, notes: d.notes}).select("id").single();
      if (error) { $("#recErr").textContent = error.message || T.saveFail; return; }
      location.href = url(U.record, data.id);
    };
    await bodyPanel(part);
    twice($("#delPart"), async () => { check(await sb.from("participants").delete().eq("id", id)); location.href = U.participants; });
  };

  pages.record = async () => {
    const id = +qs("id");
    const rec = check(await sb.from("records").select("*").eq("id", id).maybeSingle());
    if (!rec) { notice(esc(T.saveFail)); return false; }
    const part = check(await sb.from("participants").select("*").eq("id", rec.participant_id).single());
    $("#bcPart").textContent = part.code; $("#bcPart").href = url(U.participant, part.id); $("#bcDate").textContent = fdate(rec.date);
    $("#rMeta").textContent = (METHOD[rec.method] || rec.method) + (rec.notes ? " · " + rec.notes : "");
    $("#rTitle").textContent = `${part.code} · ${fdate(rec.date, true)}`;
    document.title = `${part.code} · ${rec.date} · ArabNutriVision`;
    let S;
    async function draw() {
      const {items, supps} = await loadItems([id]);
      const s = S = summary(items, supps, part.energy_target_kcal), w = s.withSupp;
      $("#stK").textContent = n0(w[I.kcal]); $("#stKl").textContent = pf(T.kcalTarget, {t: part.energy_target_kcal});
      $("#stP").textContent = `${n0(w[I.protein_g])} ${T.g}`; $("#stPl").textContent = pf(T.protPct, {p: Math.round(s.macro.Protein)});
      $("#stF").textContent = `${n0(w[I.fat_g])} ${T.g}`; $("#stFl").textContent = pf(T.fatPct, {p: Math.round(s.macro.Fat), f: s.fa.SFA.toFixed(1)});
      $("#stG").textContent = n0(s.gl); $("#stGl").textContent = pf(T.glLine, {c: Math.round(w[I.carb_g])});
      $("#nItemsLbl").textContent = pf(T.nItems, {n: s.rows.length});
      const rm = `<button class="btn btn-sm btn-link text-secondary p-0" aria-label="${esc(T.remove)}"><i class="bi bi-x-lg"></i></button>`;
      $("#itemRows").innerHTML = (s.rows.length ? s.rows.map(({it, n, gl}) => {
        const d = DISH[it.dish_code];
        const food = d ? `<a href="${U.dish}${it.dish_code}/">${esc(dName(d))}</a> <span class="small text-secondary">${esc(dAlt(d))}</span>` : esc(itemName(it));
        return `<tr><td class="ps-3 small">${esc(MEAL[it.meal] || it.meal)}</td><td>${food}${it.source !== "manual" ? ` <span class="pill pill-demo ms-1">${esc(SOURCE[it.source] || it.source)}</span>` : ""}${it.ai_image_only_kcal ? `<div class="small text-secondary">${esc(pf(T.imageOnly, {k: n0(it.ai_image_only_kcal)}))}</div>` : ""}</td>
          <td class="n">${n0(it.grams)}</td><td class="small">${esc(STYLE[it.style] || it.style)}</td><td class="n fw-semibold">${n0(n[I.kcal])}</td><td class="n">${n1(n[I.protein_g])}</td><td class="n">${n1(n[I.fat_g])}</td><td class="n">${n1(n[I.sfa_g])}</td><td class="n">${n1(n[I.carb_g])}</td><td class="n">${n0(n[I.sodium_mg])}</td><td class="n">${gl == null ? "–" : n0(gl)}</td><td class="pe-3" data-del-item="${it.id}">${rm}</td></tr>`;
      }).join("") : `<tr><td colspan="12" class="text-center text-secondary py-4">${esc(T.noItems)}</td></tr>`) +
        s.suppRows.map(({s: x, n}) => `<tr class="table-light"><td class="ps-3 small">${esc(T.supplement)}</td><td>${esc(x.supplement_name)}</td><td class="n">${x.doses}×</td><td class="small">${esc((SUPP[x.supplement_name] || {}).dose || "")}</td><td class="n">${n0(n[I.kcal])}</td><td colspan="6" class="small text-secondary">${[["Fe", "iron_mg"], ["Ca", "calcium_mg"], ["Vit C", "vitc_mg"], ["Zn", "zinc_mg"]].filter(([, k]) => n[I[k]]).map(([l, k]) => `${l} ${n0(n[I[k]])} mg`).join(" ")}</td><td class="pe-3" data-del-supp="${x.id}">${rm}</td></tr>`).join("");
      const t = s.totals;
      $("#totRow").innerHTML = `<td class="ps-3" colspan="4">${esc($("#totRow").dataset.lbl || "")}</td><td class="n">${n0(t[I.kcal])}</td><td class="n">${n1(t[I.protein_g])}</td><td class="n">${n1(t[I.fat_g])}</td><td class="n">${n1(t[I.sfa_g])}</td><td class="n">${n1(t[I.carb_g])}</td><td class="n">${n0(t[I.sodium_mg])}</td><td class="n">${n0(s.gl)}</td><td></td>`;
      document.querySelectorAll("[data-del-item]").forEach(td => td.querySelector("button").onclick = async () => { check(await sb.from("items").delete().eq("id", +td.dataset.delItem)); draw(); });
      document.querySelectorAll("[data-del-supp]").forEach(td => td.querySelector("button").onclick = async () => { check(await sb.from("supplement_intakes").delete().eq("id", +td.dataset.delSupp)); draw(); });
      const ins = insights(s), clr = {crit: "text-danger", warn: "text-warning", good: "text-success", info: "text-primary"};
      $("#insights").innerHTML = ins.length ? ins.map(([lv, ic, tx]) => `<li class="d-flex gap-2 align-items-start py-2 border-top"><i class="bi bi-${ic} fs-5 ${clr[lv]}"></i><span>${esc(tx)}</span></li>`).join("")
        : `<li class="text-secondary">${esc(T.noItems)}</li>`;
      $("#pctRows").innerHTML = pctRows(s.pct);
      const ML = {Protein: T.protein, Fat: T.fat, Carbohydrate: T.carb};
      chart("macro", {type: "doughnut", data: {labels: Object.keys(s.macro).map(k => ML[k]), datasets: [{data: Object.values(s.macro).map(v => +v.toFixed(1)), backgroundColor: [COL.blue, COL.gold, COL.olive], borderColor: "#fff"}]},
        options: {maintainAspectRatio: false, cutout: "60%", plugins: {legend: {position: AR ? "left" : "right"}, tooltip: {callbacks: {label: c => `${c.label}: ${c.raw}% ${T.ofEnergy}`}}}}});
      const limit = {id: "limit", afterDraw(ch) { const x = ch.scales.x.getPixelForValue(10), {top, bottom} = ch.chartArea, g = ch.ctx; g.save(); g.setLineDash([4, 3]); g.strokeStyle = COL.rose; g.beginPath(); g.moveTo(x, top); g.lineTo(x, bottom); g.stroke(); g.restore(); }};
      chart("fa", {type: "bar", data: {labels: Object.keys(s.fa), datasets: [{data: Object.values(s.fa).map(v => +v.toFixed(1)), backgroundColor: [COL.rose, COL.olive, COL.blue]}]},
        options: {indexAxis: "y", maintainAspectRatio: false, plugins: {legend: {display: false}}, scales: {x: {beginAtZero: true, suggestedMax: 15, reverse: AR}, y: {position: yPos}}}, plugins: [limit]});
      chart("meals", {type: "bar", data: {labels: Object.keys(s.meals), datasets: [{data: Object.values(s.meals).map(v => Math.round(v[I.kcal])), backgroundColor: COL.navy}]},
        options: {maintainAspectRatio: false, plugins: {legend: {display: false}}, scales: {x: {reverse: AR}, y: {beginAtZero: true, position: yPos}}}});
    }
    await draw();
    $("#itemForm").onsubmit = async e => {
      e.preventDefault(); const d = formData(e.target), err = $("#itemErr"); err.textContent = "";
      if (!d.dish && !d.ingredient) { err.textContent = T.chooseFood; return; }
      const g = +d.grams; if (!(g >= 1 && g <= 3000)) { err.textContent = T.portionRange; return; }
      const {error} = await sb.from("items").insert({record_id: id, meal: d.meal, dish_code: d.dish || null, ingredient_code: d.dish ? null : d.ingredient, grams: g, style: d.style || "mean", source: "manual"});
      if (error) { err.textContent = error.message || T.saveFail; return; }
      e.target.grams.value = ""; e.target.dish.value = ""; e.target.ingredient.value = ""; draw();
    };
    $("#i_dish").addEventListener("change", e => { const d = DISH[e.target.value]; if (d && !$("#i_grams").value) $("#i_grams").value = d.srv; });
    $("#suppForm").onsubmit = async e => {
      e.preventDefault(); const d = formData(e.target);
      check(await sb.from("supplement_intakes").insert({record_id: id, supplement_name: d.supplement, doses: +d.doses || 1})); draw();
    };
    $("#csvBtn").onclick = () => {
      const s = S, rows = [["participant", "date", "method", "meal", "food", "grams", "preparation", "source", ...K, "glycaemic_load"]];
      s.rows.forEach(({it, n, gl}) => rows.push([part.code, rec.date, rec.method, it.meal, it.dish_code ? DISH[it.dish_code].en.split(" (")[0] : itemName(it), Math.round(it.grams), it.style, it.source, ...n.map(v => v.toFixed(2)), gl == null ? "" : gl.toFixed(1)]));
      s.suppRows.forEach(({s: x, n}) => rows.push([part.code, rec.date, rec.method, "supplement", x.supplement_name, "", `${x.doses} dose`, "supplement", ...n.map(v => v.toFixed(2)), ""]));
      rows.push(["TOTAL incl. supplements", "", "", "", "", "", "", "", ...s.withSupp.map(v => v.toFixed(2)), s.gl.toFixed(1)]);
      download(`anv_${part.code}_${rec.date}.csv`, rows);
    };
    twice($("#delRec"), async () => { check(await sb.from("records").delete().eq("id", id)); location.href = url(U.participant, part.id); });
  };

  // ---- FFQ (services/ffq.py)
  const PER_DAY = [["day", 1], ["d", 1], ["يوم", 1], ["week", 1 / 7], ["wk", 1 / 7], ["w", 1 / 7], ["أسبوع", 1 / 7], ["month", 1 / 30.4], ["m", 1 / 30.4], ["شهر", 1 / 30.4]];
  function parseFreq(text) {
    const s = String(text ?? "").trim().toLowerCase();
    if (!s || s === "never" || s === "0" || s === "أبدا") return 0;
    const m = s.match(/^\s*([0-9]*\.?[0-9]+)\s*(?:x|times)?\s*(?:\/|per|في|بال)?\s*([a-zء-ي]+)?/);
    if (!m) throw new Error("freq");
    const unit = m[2] || "day", hit = PER_DAY.find(([k]) => unit.startsWith(k));
    if (!hit) throw new Error("freq");
    return +m[1] * hit[1];
  }
  function matchFood(tok) {
    const t = String(tok ?? "").trim(), tl = t.toLowerCase(); if (!t) return {};
    const ds = REF.dishes;
    const d = ds.find(x => x.code.toLowerCase() === tl) || ds.find(x => x.en.toLowerCase() === tl) || ds.find(x => x.ar === t) || ds.find(x => x.en.toLowerCase().startsWith(tl));
    if (d) return {dish: d};
    const g = REF.ingredients.find(x => x.code.toLowerCase() === tl) || REF.ingredients.find(x => x.name.toLowerCase().startsWith(tl));
    return g ? {ing: g} : {};
  }
  function parseCSV(text) {
    const rows = []; let row = [], cur = "", q = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) { if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += c; }
      else if (c === '"') q = true; else if (c === ",") { row.push(cur); cur = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cur); rows.push(row); row = []; cur = ""; }
      else cur += c;
    }
    if (cur || row.length) { row.push(cur); rows.push(row); }
    return rows.filter(r => r.some(v => String(v).trim() !== ""));
  }
  async function readTable(file) {
    if (/\.(xlsx|xlsm)$/i.test(file.name)) {
      const wb = XLSX.read(await file.arrayBuffer(), {type: "array"});
      return XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], {header: 1, defval: ""}).filter(r => r.some(v => String(v).trim() !== ""));
    }
    return parseCSV((await file.text()).replace(/^﻿/, ""));
  }
  pages.ffq = async () => {
    const parts = check(await sb.from("participants").select("id,code").order("code"));
    const sel = $("#f_part"); parts.forEach(p => sel.append(new Option(p.code, p.id)));
    if (qs("participant")) sel.value = qs("participant");
    $("#ffqForm").onsubmit = async e => {
      e.preventDefault(); const box = $("#ffqErr"), file = $("#f_file").files[0]; box.classList.add("d-none");
      const fail = list => { box.innerHTML = `<b>${esc(T.ffqFix)}</b><ul class="mb-0">${list.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`; box.classList.remove("d-none"); };
      if (!file || !sel.value) { fail([T.required]); return; }
      let table; try { table = await readTable(file); } catch (err) { fail([err.message]); return; }
      if (table.length < 2) { fail([T.ffqEmpty]); return; }
      const head = table[0].map(h => String(h).trim().toLowerCase()), col = k => head.indexOf(k);
      const lines = [], errors = [];
      table.slice(1).forEach((r, i) => {
        const n = i + 2, food = r[col("food")], m = matchFood(food);
        if (!m.dish && !m.ing) { errors.push(pf(T.ffqUnknownFood, {n, f: food})); return; }
        let perDay; try { perDay = parseFreq(r[col("frequency")]); } catch { errors.push(pf(T.ffqBadFreq, {n, f: r[col("frequency")]})); return; }
        const portion = +(r[col("portion_g")] || (m.dish ? m.dish.srv : 100));
        if (perDay > 0) lines.push({m, g: perDay * portion});
      });
      if (errors.length) { fail(errors); return; }
      if (!lines.length) { fail([T.ffqEmpty]); return; }
      const rec = check(await sb.from("records").insert({participant_id: +sel.value, date: new Date().toISOString().slice(0, 10), method: "ffq", notes: pf(T.ffqNote, {f: file.name}).slice(0, 200)}).select("id").single());
      check(await sb.from("items").insert(lines.map(l => ({record_id: rec.id, dish_code: l.m.dish ? l.m.dish.code : null, ingredient_code: l.m.ing ? l.m.ing.code : null,
        grams: Math.min(3000, Math.max(1, Math.round(l.g * 10) / 10)), meal: "snack", style: "mean", source: "ffq"}))));
      location.href = url(U.record, rec.id);
    };
  };


  // ---- InBody import (Excel/CSV export from Lookin'Body or LookinBody Web; no API)
  const IB_FIELDS = [   // [db column, label key, header prefixes after removing spaces/punctuation]
    ["code", "ibCode", ["id", "userid", "memberid", "participant", "code", "idnumber"]],
    ["measured_at", "ibDate", ["testdatetime", "testdate", "datetime", "date", "measurementdate", "testtime"]],
    ["weight_kg", "ibWeight", ["weight", "bodyweight"]],
    ["height_cm", "ibHeight", ["height"]],
    ["bmi", "ibBmi", ["bmi", "bodymassindex"]],
    ["pbf_pct", "ibPbf", ["pbf", "percentbodyfat", "bodyfatpercent", "bodyfat%"]],
    ["bfm_kg", "ibBfm", ["bfm", "bodyfatmass"]],
    ["smm_kg", "ibSmm", ["smm", "skeletalmusclemass"]],
    ["ffm_kg", "ibFfm", ["ffm", "fatfreemass"]],
    ["tbw_l", "ibTbw", ["tbw", "totalbodywater"]],
    ["bmr_kcal", "ibBmr", ["bmr", "basalmetabolicrate"]],
    ["vfl", "ibVfl", ["vfl", "visceralfatlevel"]],
    ["whr", "ibWhr", ["whr", "waisthipratio"]],
  ];
  const normHead = h => String(h ?? "").toLowerCase().replace(/[\s_\-\.\/()\[\]:]+/g, "");
  function autoMap(head) {
    const used = new Set(), map = {};
    IB_FIELDS.forEach(([col, , keys]) => {
      const i = head.findIndex((h, j) => !used.has(j) && keys.some(k => normHead(h) === k || normHead(h).startsWith(k)));
      if (i >= 0) { map[col] = i; used.add(i); }
    });
    return map;
  }
  function parseIbDate(v) {
    if (v == null || v === "") return null;
    if (v instanceof Date && !isNaN(v)) return v;
    if (typeof v === "number" && v > 20000 && v < 80000) return new Date(Math.round((v - 25569) * 864e5));   // Excel serial date
    const s = String(v).trim();
    let m = s.match(/^(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?$/);                                     // 20261112143000
    if (!m) m = s.match(/^(\d{4})[.\-\/](\d{1,2})[.\-\/](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);       // 2026.11.12 14:30
    if (m) return new Date(+m[1], +m[2] - 1, +m[3], +(m[4] || 12), +(m[5] || 0), +(m[6] || 0));
    m = s.match(/^(\d{1,2})[.\-\/](\d{1,2})[.\-\/](\d{4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);               // 12/11/2026 (day first)
    if (m) return new Date(+m[3], +m[2] - 1, +m[1], +(m[4] || 12), +(m[5] || 0), +(m[6] || 0));
    return null;
  }
  const ibNum = v => { if (v === "" || v == null) return null; const x = parseFloat(String(v).replace(",", ".").replace(/[^\d.\-]/g, "")); return isNaN(x) ? null : x; };

  pages.inbody = async () => {
    let parts = check(await sb.from("participants").select("id,code").order("code"));
    const psel = $("#ib_part"); parts.forEach(p => psel.append(new Option(p.code, p.id)));
    if (qs("participant")) { psel.value = qs("participant"); $("#ib_mode_one").checked = true; }
    const syncMode = () => { const one = $("#ib_mode_one").checked; $("#ib_partBox").hidden = !one; $("#ib_create").closest(".form-check").hidden = one; };
    document.querySelectorAll("[name=mode]").forEach(r => r.onchange = () => { syncMode(); preview(); }); syncMode();
    let table = null, fileName = "";
    const mapSel = () => Object.fromEntries([...document.querySelectorAll("#ibMap select")].filter(s => s.value !== "").map(s => [s.dataset.col, +s.value]));
    function build() {
      const map = mapSel(), one = $("#ib_mode_one").checked, rows = [], errors = [];
      table.slice(1).forEach((r, i) => {
        const n = i + 2, at = parseIbDate(r[map.measured_at]);
        if (!at) { errors.push(pf(T.ibBadDate, {n, v: r[map.measured_at] ?? ""})); return; }
        const row = {measured_at: at.toISOString(), code: one ? null : String(r[map.code] ?? "").trim()};
        IB_FIELDS.slice(2).forEach(([col]) => { if (col in map) row[col] = ibNum(r[map[col]]); });
        rows.push(row);
      });
      return {rows, errors, map};
    }
    function preview() {
      if (!table) return;
      const {rows, map} = build(), cols = IB_FIELDS.filter(([c]) => c in map || (c === "code" && !$("#ib_mode_one").checked));
      $("#ibHead").innerHTML = `<tr>${cols.map(([, k]) => `<th class="small">${esc(T[k])}</th>`).join("")}</tr>`;
      $("#ibRows").innerHTML = rows.slice(0, 8).map(r => `<tr>${cols.map(([c]) => `<td class="small">${c === "measured_at" ? esc(new Date(r[c]).toLocaleString(AR ? "ar-u-nu-latn" : "en-GB")) : esc(r[c] ?? "–")}</td>`).join("")}</tr>`).join("");
    }
    $("#ib_file").onchange = async e => {
      const file = e.target.files[0]; if (!file) return; fileName = file.name; $("#ibErr").classList.add("d-none"); $("#ibStatus").textContent = "";
      try {
        if (/\.(xlsx|xls|xlsm)$/i.test(file.name)) { const wb = XLSX.read(await file.arrayBuffer(), {type: "array", cellDates: true}); table = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], {header: 1, defval: "", raw: true}); }
        else table = parseCSV((await file.text()).replace(/^﻿/, ""));
        table = table.filter(r => r.some(v => String(v).trim() !== ""));
      } catch (err) { $("#ibErr").textContent = err.message; $("#ibErr").classList.remove("d-none"); return; }
      if (!table || table.length < 2) { $("#ibErr").textContent = T.ffqEmpty; $("#ibErr").classList.remove("d-none"); return; }
      const head = table[0].map(h => String(h).trim()), auto = autoMap(head);
      $("#ibMap").innerHTML = IB_FIELDS.map(([col, k]) => `<div class="col-sm-6"><label class="form-label small d-block w-100">${esc(T[k])}<select class="form-select form-select-sm" data-col="${col}"><option value="">— ${esc(T.ibNotUsed)} —</option>${head.map((h, i) => `<option value="${i}" ${auto[col] === i ? "selected" : ""}>${esc(h || "#" + (i + 1))}</option>`).join("")}</select></label></div>`).join("");
      document.querySelectorAll("#ibMap select").forEach(s => s.onchange = preview);
      $("#ibMapPanel").hidden = false; preview();
    };
    $("#ibImport").onclick = async () => {
      const box = $("#ibErr"), fail = list => { box.innerHTML = `<b>${esc(T.ffqFix)}</b><ul class="mb-0">${list.slice(0, 15).map(x => `<li>${esc(x)}</li>`).join("")}</ul>`; box.classList.remove("d-none"); };
      box.classList.add("d-none");
      const {rows, errors, map} = build(), one = $("#ib_mode_one").checked;
      if (!("measured_at" in map) || !IB_FIELDS.slice(2).some(([c]) => c in map)) { fail([T.ibNeed]); return; }
      if (one ? !psel.value : !("code" in map)) { fail([T.ibNeedId]); return; }
      if (errors.length) { fail(errors); return; }
      const byCode = Object.fromEntries(parts.map(p => [p.code.toLowerCase(), p.id]));
      if (!one) {
        const missing = [...new Set(rows.map(r => r.code).filter(c => c && !byCode[c.toLowerCase()]))];
        if (missing.length && $("#ib_create").checked) {
          const made = check(await sb.from("participants").insert(missing.map(c => ({code: c.slice(0, 30)}))).select("id,code"));
          made.forEach(p => byCode[p.code.toLowerCase()] = p.id); parts = parts.concat(made);
        }
        const bad = rows.map((r, i) => (!r.code || !byCode[r.code.toLowerCase()]) ? pf(T.ibNoPart, {n: i + 2, v: r.code || ""}) : null).filter(Boolean);
        if (bad.length) { fail(bad); return; }
      }
      const out = rows.map(r => { const {code, ...x} = r; return {...x, participant_id: one ? +psel.value : byCode[code.toLowerCase()], source_file: fileName.slice(0, 120)}; });
      const ids = [...new Set(out.map(r => r.participant_id))];
      const have = new Set(check(await sb.from("body_measurements").select("participant_id,measured_at").in("participant_id", ids)).map(r => r.participant_id + "|" + new Date(r.measured_at).toISOString()));
      const seen = new Set(), fresh = out.filter(r => { const k = r.participant_id + "|" + r.measured_at; if (have.has(k) || seen.has(k)) return false; seen.add(k); return true; });
      if (fresh.length) { const {error} = await sb.from("body_measurements").insert(fresh); if (error) { fail([error.message || T.saveFail]); return; } }
      $("#ibStatus").innerHTML = `<i class="bi bi-check-circle text-success me-1"></i>${esc(pf(T.ibDone, {n: fresh.length, d: out.length - fresh.length}))}` + (ids.length === 1 ? ` <a href="${url(U.participant, ids[0])}">${esc(parts.find(p => p.id === ids[0]).code)}</a>` : "");
    };
  };

  async function bodyPanel(part) {
    $("#ibLink").href += "?participant=" + part.id;
    const rows = check(await sb.from("body_measurements").select("*").eq("participant_id", part.id).order("measured_at"));
    if (!rows.length) { $("#bodyEmpty").textContent = T.ibNoRows; return; }
    $("#bodyEmpty").hidden = true; $("#bodyBox").hidden = false;
    const last = rows[rows.length - 1], prev = rows.length > 1 ? rows[rows.length - 2] : null;
    $("#bodyDate").textContent = fdate(last.measured_at.slice(0, 10));
    const stat = (col, k, d = 1) => last[col] == null ? "" : `<div class="col-6 col-md-3"><div class="border rounded-3 p-2 h-100"><div class="small text-secondary">${esc(T[k])}</div><div class="fs-5 fw-semibold num">${(+last[col]).toFixed(d)}</div>${prev && prev[col] != null ? `<div class="small ${(last[col] - prev[col] > 0) === ["smm_kg", "tbw_l", "bmr_kcal", "ffm_kg"].includes(col) ? "text-success" : "text-rose"}">${LTR((last[col] - prev[col] > 0 ? "+" : "") + (last[col] - prev[col]).toFixed(d))}</div>` : ""}</div></div>`;
    $("#bodyStats").innerHTML = [["weight_kg", "ibWeight"], ["pbf_pct", "ibPbf"], ["smm_kg", "ibSmm"], ["bfm_kg", "ibBfm"], ["bmi", "ibBmi"], ["vfl", "ibVfl", 0], ["bmr_kcal", "ibBmr", 0], ["tbw_l", "ibTbw"]].map(a => stat(...a)).join("");
    if (rows.length > 1) {
      const lab = rows.map(r => r.measured_at.slice(0, 10)), ds = [];
      [["weight_kg", "ibWeight", COL.navy, "y"], ["smm_kg", "ibSmm", COL.olive, "y"], ["pbf_pct", "ibPbf", COL.rose, "y1"]].forEach(([c, k, col, ax]) => {
        if (rows.some(r => r[c] != null)) ds.push({type: "line", label: T[k], data: rows.map(r => r[c]), borderColor: col, backgroundColor: col, yAxisID: ax, tension: .2}); });
      chart("bodyTrend", {type: "line", data: {labels: lab, datasets: ds}, options: {maintainAspectRatio: false, layout: {padding: {left: 12, right: 12}}, plugins: {legend: {position: "bottom"}},
        scales: {x: {reverse: AR}, y: {position: yPos}, y1: {position: AR ? "left" : "right", grid: {drawOnChartArea: false}}}}});
    } else $("#bodyTrendBox").hidden = true;
    if (last.bmr_kcal) {
      $("#bmrBox").hidden = false;
      $("#bmrBtn").onclick = async () => {
        const f = +$("#actSel").value, k = Math.round(last.bmr_kcal * f / 10) * 10;
        const {error} = await sb.from("participants").update({energy_target_kcal: k}).eq("id", part.id);
        $("#bmrStatus").innerHTML = error ? `<span class="text-danger">${esc(error.message)}</span>` : `<i class="bi bi-check-circle text-success me-1"></i>${esc(pf(T.ibTarget, {k, f}))}`;
        if (!error) setTimeout(() => location.reload(), 1200);
      };
    }
  }

  // ---- validation lab
  pages.validation = async () => {
    let all = [], split = "";
    const ba = {};
    function draw() {
      const {rows, res} = evaluate(split ? all.filter(s => s.split === split) : all);
      $("#vN").textContent = res.n; $("#vNl").textContent = pf(T.platesSessions, {n: res.sessions});
      $("#vTop1").textContent = res.top1 == null ? "–" : res.top1.toFixed(1) + "%";
      $("#vPort").textContent = res.portion ? res.portion.mape.toFixed(1) + "%" : "–";
      $("#vPortMae").textContent = res.portion ? `· MAE ${n0(res.portion.mae)} ${T.g}` : "";
      $("#vCov").textContent = res.coverage == null ? "–" : Math.round(res.coverage) + "%";
      $("#sysRows").innerHTML = res.systems.length ? res.systems.map(x => `<tr><td class="ps-3"><div class="fw-semibold">${esc(x.lab)}</div><div class="small text-secondary">${esc(x.desc)}</div></td><td class="n">${x.e.n}</td><td class="n fw-semibold">${n1(x.e.mape)}%</td><td class="n small">${x.e.ci ? LTR(n1(x.e.ci[0]) + "–" + n1(x.e.ci[1])) : "–"}</td><td class="n">${x.e.ba ? LTR(n0(x.e.ba.bias)) : "–"}</td><td class="n small">${x.e.ba ? LTR(n0(x.e.ba.lo) + " … " + n0(x.e.ba.hi)) : "–"}</td><td class="n pe-3">${x.f && x.f.mape != null ? `<span class="pill ${x.f.mape > 30 ? "pill-rose" : "pill-good"}">${n1(x.f.mape)}%</span>` : "–"}</td></tr>`).join("")
        : `<tr><td colspan="7" class="text-center text-secondary py-4">${esc(T.noSystems)}</td></tr>`;
      $("#plateRows").innerHTML = rows.length ? rows.slice(0, 200).map(r => { const s = r.s, ok = s.ai_dish_code === s.dish_code;
        return `<tr><td class="ps-3 small mono">${esc(s.image_file.length > 30 ? s.image_file.slice(0, 29) + "…" : s.image_file)}</td><td class="small">${esc(s.session_id)}${s.session_id.startsWith("DEMO") ? ` <span class="pill pill-demo">${esc(T.demo)}</span>` : ""}</td><td>${esc(dName(DISH[s.dish_code]))} <span class="small text-secondary">${esc(STYLE[s.variant] || s.variant)}</span></td><td class="n">${n0(s.weight_g)}</td><td class="n">${n0(r.truth.kcal)}</td>
          <td class="small">${s.ai_dish_code ? `<i class="bi bi-${ok ? "check-circle text-success" : "x-circle text-danger"}"></i> ${esc(dName(DISH[s.ai_dish_code]))}` : "–"}</td><td class="n">${s.ai_grams ? n0(s.ai_grams) : "–"}</td><td class="n">${r.image ? n0(r.image.kcal) : "–"}</td><td class="n">${r.recipe ? n0(r.recipe.kcal) : "–"}</td>
          <td class="pe-3" data-del="${s.id}"><button class="btn btn-sm btn-link text-secondary p-0" aria-label="${esc(T.remove)}"><i class="bi bi-x-lg"></i></button></td></tr>`; }).join("")
        : `<tr><td colspan="10" class="text-center text-secondary py-4">${esc(T.noPlates)}</td></tr>`;
      document.querySelectorAll("#plateRows [data-del]").forEach(td => td.querySelector("button").onclick = async () => { check(await sb.from("validation_samples").delete().eq("id", +td.dataset.del)); await load(); });
      Object.keys(ba).forEach(k => delete ba[k]);
      res.systems.forEach(x => { if (x.e.ba) ba[x.key] = {label: x.lab, ...x.e.ba}; });
      const sel = $("#baSel"), keep = sel.value; sel.innerHTML = "";
      Object.entries(ba).forEach(([k, v]) => sel.append(new Option(v.label, k)));
      $("#baPanel").hidden = !Object.keys(ba).length;
      sel.value = ba[keep] ? keep : (ba.recipe ? "recipe" : Object.keys(ba)[0] || ""); drawBA();
      $("#csvBtn").onclick = () => {
        const out = [["image_file", "dish_id", "recipe_variant", "session_id", "split", "weight_g", "view", "reference_card", "phone", "kcal", "fat_g", "ai_dish_id", "ai_grams", "ai_style", "ai_direct_kcal", "ai_direct_fat_g", "recipe_aware_kcal"]];
        evaluate(all).rows.forEach(r => { const s = r.s; out.push([s.image_file, s.dish_code, s.variant, s.session_id, s.split, s.weight_g, s.view, s.reference_card ? "yes" : "no", s.phone, r.truth.kcal.toFixed(1), r.truth.fat.toFixed(1), s.ai_dish_code || "", s.ai_grams ?? "", s.ai_style || "", s.ai_direct_kcal ?? "", s.ai_direct_fat_g ?? "", r.recipe ? r.recipe.kcal.toFixed(1) : ""]); });
        download("annotations.csv", out);
      };
    }
    function drawBA() {
      const b = ba[$("#baSel").value]; if (!b) return;
      const xs = b.points.map(p => p.x), x0 = Math.min(...xs), x1 = Math.max(...xs);
      const line = (y, lab, dash) => ({type: "line", label: lab, data: [{x: x0, y}, {x: x1, y}], borderColor: dash ? COL.grey : COL.rose, borderDash: dash ? [5, 4] : [], pointRadius: 0, borderWidth: 1.5});
      chart("ba", {type: "scatter", data: {datasets: [{type: "scatter", label: T.plates, data: b.points, backgroundColor: "rgba(21,48,94,.55)"}, line(b.bias, `${T.bias} ${b.bias.toFixed(0)} ${T.kcal}`, false), line(b.lo, "−1.96 SD", true), line(b.hi, "+1.96 SD", true)]},
        options: {maintainAspectRatio: false, plugins: {legend: {position: "bottom"}}, scales: {x: {reverse: AR, title: {display: true, text: T.meanAxis}}, y: {position: yPos, title: {display: true, text: T.diffAxis}}}}});
    }
    async function load() { all = check(await sb.from("validation_samples").select("*").order("created_at", {ascending: false})); draw(); }
    $("#baSel").onchange = drawBA;
    document.querySelectorAll("#splitBtns [data-split]").forEach(b => b.onclick = () => { split = b.dataset.split; document.querySelectorAll("#splitBtns button").forEach(x => x.classList.toggle("active", x === b)); draw(); });
    $("#valForm").onsubmit = async e => { e.preventDefault(); if (await saveValidation(e.target)) { e.target.weight_g.value = ""; await load(); } };
    await load();
  };

  // ---- Analyze page (public; saving needs a signed-in researcher)
  async function analyze() {
    fillSelects();
    const vf = $("#valFormAnalyze");
    if (vf) vf.addEventListener("change", () => vf.dataset.touched = "1");
    window.ANV.onResult = st => {
      if (!vf) return;
      if (!vf.dataset.touched) vf.dish_code.value = st.dish;
      if (st.ai) { vf.ai_dish_code.value = st.ai.dish_id; vf.ai_grams.value = Math.round(st.grams); vf.ai_style.value = st.ai.style || ""; }
    };
    if (window.ANV.state) window.ANV.onResult(window.ANV.state);
    if (!CL || !CL.configured) return;
    const user = await CL.ready; if (!user) return;
    const recs = check(await sb.from("records").select("id,date,method,participant_id,participants(code)").order("date", {ascending: false}).limit(30));
    const recSel = $("#recSel");
    recs.forEach(r => recSel.append(new Option(`${r.participants ? r.participants.code : "?"} · ${fdate(r.date)} · ${METHOD[r.method] || r.method}`, r.id)));
    if (!recs.length) { $("#noRecHint").hidden = false; $("#addBtn").disabled = true; }
    $("#addBtn").onclick = async () => {
      const st = window.ANV.state, s = $("#saveStatus"), r = recs.find(x => x.id === +recSel.value);
      const {data, error} = await sb.from("items").insert({record_id: r.id, meal: $("#mealSel").value, dish_code: st.dish, grams: Math.round(st.grams),
        style: st.style, source: st.example ? "manual" : st.source}).select("id").single();
      if (error) { s.innerHTML = `<span class="text-danger">${esc(error.message || T.saveFail)}</span>`; return; }
      s.innerHTML = `<i class="bi bi-check-circle text-success me-1"></i>${esc(pf(T.addedTo, {food: dName(DISH[st.dish]), g: st.grams, p: r.participants.code, d: fdate(r.date)}))} <a href="${url(U.record, r.id)}">${esc(T.openRecord)}</a>`;
      return data;
    };
    if (vf) vf.onsubmit = async e => { e.preventDefault(); await saveValidation(vf); };
  }

  // ---------------------------------------------------------------- boot
  (async function () {
    fillSelects();
    const tot = $("#totRow"); if (tot) tot.dataset.lbl = T.totalFood;
    if (PAGE === "analyze") { try { await analyze(); } catch (e) { console.error(e); } return; }
    if (!CL || !CL.configured) { notice(esc(T.notConfigured)); return; }
    let user; try { user = await CL.requireUser(); } catch { return; }
    try { if (await pages[PAGE](user) !== false) ready(); }
    catch (e) { console.error(e); notice(esc(e.message || T.saveFail)); }
  })();
})();
