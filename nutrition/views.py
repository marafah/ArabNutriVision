import csv
import json
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import (CustomDishForm, FFQUploadForm, ItemForm, ParticipantForm, RecordForm, SupplementIntakeForm,
                    ValidationSampleForm)
from .models import (Dish, Ingredient, IntakeItem, IntakeRecord, Participant, RecipeLine, RecipeVariant,
                     SupplementIntake, ValidationSample)
from .nutrients import BY_KEY, CORE, GROUP_LABELS, KEYS, MEALS, NUTRIENTS
from .services import ffq
from .services import metrics as M
from .services.composition import all_profiles, gap_decomposition, invalidate, profile_for
from .services.estimate import estimate, insights, record_summary
from .templatetags.anv import cat, dish_name, fat_source, is_ar

DATA = Path(__file__).resolve().parent / "data"


def _profiles_json():
    out = []
    for p in sorted(all_profiles().values(), key=lambda p: (p.category, p.name)):
        out.append({"code": p.code, "en": p.name, "ar": p.name_ar or p.name, "cat": cat(p.category), "srv": p.serving_g,
                    "m": [round(p.mean[k], 3) for k in KEYS], "lo": [round(p.low[k], 3) for k in KEYS],
                    "hi": [round(p.high[k], 3) for k in KEYS],
                    "v": {s: [round(v[k], 3) for k in KEYS] for s, v in p.variants.items()},
                    "gi": p.gi, "fat": [fat_source(f) for f in p.hidden_fat]})
    return out


def _nutrient_meta():
    ar = is_ar()
    return [{"key": n.key, "label": n.label_ar if ar else n.label, "ar": n.label if ar else n.label_ar, "unit": n.unit, "group": n.group} for n in NUTRIENTS]


def _analysis():
    try:
        return json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ public pages
def home(request):
    profiles = all_profiles()
    a = _analysis()
    kcal = sorted(((p.mean["kcal"], p) for p in profiles.values()), key=lambda x: x[0])
    return render(request, "nutrition/home.html", {
        "n_dishes": len(profiles), "n_ingredients": Ingredient.objects.count(), "analysis": a,
        "featured": [p for _, p in kcal[::max(1, len(kcal) // 6)]][:6]})


def research(request):
    a = _analysis()
    grid = a["montecarlo"]["grid"] if a else []
    series = {}
    for r in grid:
        series.setdefault(r["estimator"], []).append({"x": r["sigma"] * 100, "e": r["energy_mape"], "f": r["fat_mape"]})
    gap = []
    try:
        gap = list(csv.DictReader(open(DATA / "table2_gap_decomposition.csv", encoding="utf-8")))
    except OSError:
        pass
    names = {p.code: dish_name(p) for p in all_profiles().values()}
    for g in gap:
        g["name"] = names.get(g["dish"], g["dish"])
    gap.sort(key=lambda g: -float(g["gap_kcal_per100"]))
    return render(request, "nutrition/research.html", {"a": a, "series_json": json.dumps(series), "gap": gap,
                                                       "gap_json": json.dumps(gap)})


def dish_list(request):
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("cat", "")
    profiles = list(all_profiles().values())
    if q:
        profiles = [p for p in profiles if q.lower() in p.name.lower() or q in p.name_ar or q.lower() in p.code]
    if cat:
        profiles = [p for p in profiles if p.category == cat]
    profiles.sort(key=lambda p: (p.category, p.name))
    cats = sorted({p.category for p in all_profiles().values()})
    return render(request, "nutrition/dish_list.html", {"profiles": profiles, "q": q, "cat": cat, "cats": cats})


def dish_detail(request, code):
    dish = get_object_or_404(Dish.objects.prefetch_related("variants__lines__ingredient"), code=code)
    p = profile_for(code)
    if p is None:
        messages.warning(request, _("This dish has no recipe yet."))
        return redirect("nutrition:dishes")
    groups = []
    for g, label in GROUP_LABELS.items():
        rows = [{"n": n, "mean": p.mean[n.key], "low": p.low[n.key], "high": p.high[n.key],
                 "variants": [p.variants[s][n.key] for s in ("light", "home", "restaurant") if s in p.variants]}
                for n in NUTRIENTS if n.group == g]
        groups.append((label, rows))
    variants = sorted(dish.variants.all(), key=lambda v: ["light", "home", "restaurant", "custom"].index(v.style))
    home_v = next((v for v in variants if v.style == "home"), variants[0])
    return render(request, "nutrition/dish_detail.html", {
        "dish": dish, "p": p, "groups": groups, "variants": variants, "styles": [s for s in ("light", "home", "restaurant") if s in p.variants],
        "gap": gap_decomposition(dish), "home_cooked_g": home_v.cooked_g,
        "chart_json": json.dumps({s: {k: round(p.variants[s][k], 2) for k in CORE + ["sfa_g", "mufa_g", "pufa_g"]} for s in p.variants}),
        "gl": p.gl_per_serving()})


def analyze(request):
    records = []
    if request.user.is_authenticated:
        records = IntakeRecord.objects.filter(participant__owner=request.user).select_related("participant")[:30]
    extra = {}
    from django.conf import settings
    if settings.STATIC_SITE:
        from .static_views import js_strings, reference_data
        extra = {"ref_json": reference_data(), "js_json": js_strings(), "ws_page": "analyze"}
    return render(request, "nutrition/analyze.html", {**extra, 
        "dishes_json": json.dumps(_profiles_json(), ensure_ascii=False), "nut_json": json.dumps(_nutrient_meta(), ensure_ascii=False),
        "records": records, "meals": MEALS, "vform": ValidationSampleForm() if request.user.is_authenticated and not settings.STATIC_SITE else None})


# ------------------------------------------------------------------ researcher workspace
@login_required
def dashboard(request):
    parts = Participant.objects.filter(owner=request.user).annotate(n=Count("records"))
    recs = IntakeRecord.objects.filter(participant__owner=request.user).select_related("participant")[:6]
    vs = ValidationSample.objects.filter(owner=request.user)
    return render(request, "nutrition/dashboard.html", {"participants": parts, "records": recs, "n_val": vs.count(),
                                                        "n_custom": Dish.objects.filter(is_custom=True, created_by=request.user).count()})


@login_required
def participant_list(request):
    form = ParticipantForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        if Participant.objects.filter(owner=request.user, code=obj.code).exists():
            form.add_error("code", _("You already have a participant with this code."))
        else:
            obj.save()
            messages.success(request, _("Participant %(code)s added.") % {"code": obj.code})
            return redirect(obj)
    parts = Participant.objects.filter(owner=request.user).annotate(n=Count("records"))
    return render(request, "nutrition/participant_list.html", {"participants": parts, "form": form})


@login_required
def participant_detail(request, pk):
    part = get_object_or_404(Participant, pk=pk, owner=request.user)
    form = RecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        rec = form.save(commit=False)
        rec.participant = part
        rec.save()
        messages.success(request, _("Record created. Add the foods eaten."))
        return redirect(rec)
    recs = list(part.records.all())
    days = [(r, record_summary(r)) for r in recs]
    mean = None
    food_days = [s for r, s in days if r.method != "ffq"]
    if food_days:
        mean = {k: sum(s["with_supp"][k] for s in food_days) / len(food_days) for k in KEYS}
    trend = [{"date": r.date.isoformat(), "kcal": round(s["totals"]["kcal"]), "fat": round(s["totals"]["fat_g"], 1),
              "method": r.get_method_display()} for r, s in reversed(days)]
    pct = []
    if mean:
        for n in NUTRIENTS:
            ref = part.energy_target_kcal if n.key == "kcal" else n.reference
            if ref:
                pct.append({"n": n, "value": mean[n.key], "pct": 100 * mean[n.key] / ref})
    return render(request, "nutrition/participant_detail.html", {"part": part, "days": days, "form": form, "mean": mean,
                                                                 "pct": pct, "trend_json": json.dumps(trend), "n_food_days": len(food_days)})


@login_required
def record_detail(request, pk):
    rec = get_object_or_404(IntakeRecord.objects.select_related("participant"), pk=pk, participant__owner=request.user)
    iform = ItemForm(request.POST if request.POST.get("action") == "item" else None, prefix="i")
    sform = SupplementIntakeForm(request.POST if request.POST.get("action") == "supp" else None, prefix="s")
    if request.method == "POST":
        if request.POST.get("action") == "item" and iform.is_valid():
            item = iform.save(commit=False)
            item.record = rec
            if item.ingredient_id and item.dish_id:
                item.ingredient = None
            item.save()
            messages.success(request, _("Added %(food)s (%(g).0f g).") % {"food": dish_name(item.dish) if item.dish else item.food_name, "g": item.grams})
            return redirect(rec)
        if request.POST.get("action") == "supp" and sform.is_valid():
            s = sform.save(commit=False)
            s.record = rec
            s.save()
            messages.success(request, _("Supplement added."))
            return redirect(rec)
    s = record_summary(rec)
    chart = {"macro": s["macro_pct"], "fa": s["fa_pct_energy"],
             "meals": {m: round(v["kcal"]) for m, v in s["meals"].items()}}
    return render(request, "nutrition/record_detail.html", {"rec": rec, "s": s, "iform": iform, "sform": sform, "insights": insights(s),
                                                            "chart_json": json.dumps(chart), "core": [BY_KEY[k] for k in CORE]})


@login_required
@require_POST
def item_delete(request, pk):
    item = get_object_or_404(IntakeItem, pk=pk, record__participant__owner=request.user)
    rec = item.record
    item.delete()
    messages.info(request, _("Item removed."))
    return redirect(rec)


@login_required
@require_POST
def supplement_delete(request, pk):
    s = get_object_or_404(SupplementIntake, pk=pk, record__participant__owner=request.user)
    rec = s.record
    s.delete()
    return redirect(rec)


@login_required
@require_POST
def record_delete(request, pk):
    rec = get_object_or_404(IntakeRecord, pk=pk, participant__owner=request.user)
    part = rec.participant
    rec.delete()
    messages.info(request, _("Record deleted."))
    return redirect(part)


@login_required
def record_csv(request, pk):
    rec = get_object_or_404(IntakeRecord, pk=pk, participant__owner=request.user)
    s = record_summary(rec)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="anv_{rec.participant.code}_{rec.date}.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    w.writerow(["participant", "date", "method", "meal", "food", "grams", "preparation", "source"] + KEYS + ["glycaemic_load"])
    for r in s["rows"]:
        it = r["item"]
        w.writerow([rec.participant.code, rec.date, rec.method, it.meal, it.food_name, round(it.grams), it.style, it.source]
                   + [round(r["n"][k], 2) for k in KEYS] + [round(r["gl"], 1) if r["gl"] is not None else ""])
    for r in s["supp_rows"]:
        w.writerow([rec.participant.code, rec.date, rec.method, "supplement", r["s"].supplement.name, "", f'{r["s"].doses} dose', "supplement"]
                   + [round(r["n"][k], 2) for k in KEYS] + [""])
    w.writerow(["TOTAL incl. supplements", "", "", "", "", "", "", ""] + [round(s["with_supp"][k], 2) for k in KEYS] + [round(s["gl_total"], 1)])
    return resp


@login_required
@require_POST
def api_add_item(request):
    """Add an analysed photo result to a record (called from the Analyze page)."""
    rec = get_object_or_404(IntakeRecord, pk=request.POST.get("record"), participant__owner=request.user)
    dish = get_object_or_404(Dish, code=request.POST.get("dish"))
    try:
        grams = float(request.POST.get("grams"))
        ai_kcal = float(request.POST["ai_kcal"]) if request.POST.get("ai_kcal") else None
    except (TypeError, ValueError):
        return JsonResponse({"error": _("Invalid portion.")}, status=400)
    style = request.POST.get("style", "mean")
    meal = request.POST.get("meal", "lunch")
    item = IntakeItem.objects.create(record=rec, dish=dish, grams=grams, style=style if style in ("mean", "home", "restaurant", "light") else "mean",
                                     meal=meal if meal in dict(MEALS) else "lunch", source=request.POST.get("source", "manual")[:20],
                                     ai_image_only_kcal=ai_kcal)
    return JsonResponse({"ok": True, "message": _("Added %(food)s (%(g).0f g) to the record of %(p)s, %(d)s.") % {"food": dish_name(dish), "g": grams, "p": rec.participant.code, "d": rec.date}, "url": reverse("nutrition:record_detail", args=[rec.pk]), "id": item.pk})


@login_required
def ffq_import(request):
    form = FFQUploadForm(request.user, request.POST or None, request.FILES or None)
    preview = errors = None
    if request.method == "POST" and form.is_valid():
        lines, errors = ffq.parse(form.cleaned_data["file"])
        if lines and not errors:
            part = form.cleaned_data["participant"]
            with transaction.atomic():
                import datetime as dt
                rec = IntakeRecord.objects.create(participant=part, date=dt.date.today(), method="ffq",
                                                  notes=f"FFQ import: {form.cleaned_data['file'].name}")
                for ln in lines:
                    IntakeItem.objects.create(record=rec, dish=ln["dish"], ingredient=ln["ingredient"], grams=ln["grams_per_day"],
                                              meal="snack", style="mean", source="ffq")
            messages.success(request, _("Imported %(n)d FFQ items as average daily intake.") % {"n": len(lines)})
            return redirect(rec)
        preview = lines
    return render(request, "nutrition/ffq_import.html", {"form": form, "errors": errors, "preview": preview})


def ffq_template(request):
    resp = HttpResponse(ffq.TEMPLATE, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="arabnutrivision_ffq_template.csv"'
    return resp


@login_required
def recipe_builder(request):
    form = CustomDishForm(request.POST or None)
    ings = Ingredient.objects.order_by("name")
    if request.method == "POST" and form.is_valid():
        codes = request.POST.getlist("ing")
        grams = request.POST.getlist("grams")
        pairs = [(c, float(g)) for c, g in zip(codes, grams) if c and g and float(g) > 0]
        if not pairs:
            form.add_error(None, _("Add at least one ingredient with a weight."))
        else:
            from django.utils.text import slugify
            base = slugify(form.cleaned_data["name_en"])[:40] or "dish"
            code, n = f"custom-{base}", 1
            while Dish.objects.filter(code=code).exists():
                n += 1
                code = f"custom-{base}-{n}"
            with transaction.atomic():
                d = Dish.objects.create(code=code, name_en=form.cleaned_data["name_en"], name_ar=form.cleaned_data["name_ar"],
                                        category=form.cleaned_data["category"], serving_g=form.cleaned_data["serving_g"],
                                        is_raw=form.cleaned_data["is_raw"], is_custom=True, created_by=request.user)
                v = RecipeVariant.objects.create(dish=d, style="home", cooked_g=form.cleaned_data["cooked_g"], source="User recipe")
                lookup = {i.code: i for i in Ingredient.objects.filter(code__in=[c for c, _ in pairs])}
                RecipeLine.objects.bulk_create([RecipeLine(variant=v, ingredient=lookup[c], grams=g) for c, g in pairs if c in lookup])
            invalidate()
            messages.success(request, _("%(name)s added to the composition table.") % {"name": dish_name(d)})
            return redirect(d)
    ing_json = json.dumps([{"code": i.code, "name": i.name, "kcal": i.kcal, "fat": i.fat_g, "protein": i.protein_g, "carb": i.carb_g}
                           for i in ings], ensure_ascii=False)
    return render(request, "nutrition/recipe_builder.html", {"form": form, "ings": ings, "ing_json": ing_json})


# ------------------------------------------------------------------ validation lab (ArabFood-N)
def _evaluate(samples):
    prof = all_profiles()
    rows = []
    for s in samples:
        p_true = prof.get(s.dish.code)
        if not p_true:
            continue
        truth = {k: s.weight_g * p_true.variants.get(s.variant, p_true.mean)[k] / 100 for k in ("kcal", "fat_g")}
        r = {"s": s, "truth": truth}
        if s.ai_dish_id and s.ai_grams:
            p_ai = prof.get(s.ai_dish.code) or p_true
            est = estimate(p_ai, s.ai_grams, s.ai_style or "mean")
            r["recipe"] = {"kcal": est.point["kcal"], "fat_g": est.point["fat_g"], "lo": est.low["kcal"], "hi": est.high["kcal"]}
            r["oracle_dish"] = {"kcal": s.ai_grams * p_true.mean["kcal"] / 100, "fat_g": s.ai_grams * p_true.mean["fat_g"] / 100}
        if s.ai_direct_kcal is not None:
            r["image_only"] = {"kcal": s.ai_direct_kcal, "fat_g": s.ai_direct_fat_g}
        rows.append(r)

    def sys_metrics(key, nut):
        pairs = [(r[key][nut], r["truth"][nut]) for r in rows if key in r and r[key].get(nut) is not None]
        if not pairs:
            return None
        return M.summary([a for a, _ in pairs], [b for _, b in pairs])

    rec = [r for r in rows if r["s"].ai_dish_id]
    portion = [(r["s"].ai_grams, r["s"].weight_g) for r in rows if r["s"].ai_grams]
    res = {
        "n": len(rows),
        "sessions": len({r["s"].session_id for r in rows}),
        "top1": 100 * sum(r["s"].ai_dish_id == r["s"].dish_id for r in rec) / len(rec) if rec else None,
        "portion": M.summary([a for a, _ in portion], [b for _, b in portion]) if portion else None,
        "systems": [],
        "coverage": M.coverage([r["recipe"]["lo"] for r in rows if "recipe" in r], [r["recipe"]["hi"] for r in rows if "recipe" in r],
                               [r["truth"]["kcal"] for r in rows if "recipe" in r]),
    }
    for key, label, desc in [("image_only", _("Image-only AI (zero-shot)"), _("An external model's own kcal estimate from pixels")),
                             ("recipe", _("Recipe-aware (AI dish + grams + style)"), _("ArabNutriVision pipeline")),
                             ("oracle_dish", _("Recipe-aware, true dish"), _("Upper bound for recognition errors"))]:
        e, f = sys_metrics(key, "kcal"), sys_metrics(key, "fat_g")
        if e:
            res["systems"].append({"key": key, "label": label, "desc": desc, "e": e, "f": f})
    return rows, res


@login_required
def validation_lab(request):
    samples = ValidationSample.objects.filter(owner=request.user).select_related("dish", "ai_dish")
    form = ValidationSampleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        v = form.save(commit=False)
        v.owner = request.user
        v.save()
        messages.success(request, _("Plate %(f)s saved.") % {"f": v.image_file})
        return redirect("nutrition:validation")
    split = request.GET.get("split", "")
    if split:
        samples = samples.filter(split=split)
    rows, res = _evaluate(list(samples))
    ba = {}
    for sysm in res["systems"]:
        if sysm["e"]["ba"]:
            ba[sysm["key"]] = {"label": sysm["label"], **{k: sysm["e"]["ba"][k] for k in ("bias", "loa_low", "loa_high", "points")}}
    demo = samples.filter(session_id__startswith="DEMO").exists()
    return render(request, "nutrition/validation.html", {"rows": rows[:200], "res": res, "form": form, "ba_json": json.dumps(ba),
                                                         "split": split, "demo": demo})


@login_required
def validation_csv(request):
    samples = ValidationSample.objects.filter(owner=request.user).select_related("dish", "ai_dish")
    rows, _ = _evaluate(list(samples))
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="annotations.csv"'
    w = csv.writer(resp)
    w.writerow(["image_file", "dish_id", "recipe_variant", "session_id", "split", "weight_g", "view", "reference_card", "phone",
                "kcal", "fat_g", "ai_dish_id", "ai_grams", "ai_style", "ai_direct_kcal", "ai_direct_fat_g", "recipe_aware_kcal"])
    for r in rows:
        s = r["s"]
        w.writerow([s.image_file, s.dish.code, s.variant, s.session_id, s.split, s.weight_g, s.view, "yes" if s.reference_card else "no",
                    s.phone, round(r["truth"]["kcal"], 1), round(r["truth"]["fat_g"], 1), s.ai_dish.code if s.ai_dish else "",
                    s.ai_grams or "", s.ai_style, s.ai_direct_kcal or "", s.ai_direct_fat_g or "",
                    round(r["recipe"]["kcal"], 1) if "recipe" in r else ""])
    return resp


@login_required
@require_POST
def validation_delete(request, pk):
    get_object_or_404(ValidationSample, pk=pk, owner=request.user).delete()
    return redirect("nutrition:validation")
