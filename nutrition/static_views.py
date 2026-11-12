"""Static edition (GitHub Pages + Supabase).

These views only render page shells at build time (`manage.py build_site`). Everything that belongs to a
signed-in researcher (participants, records, validation plates) is read and written by
`static/nutrition/js/workspace.js` directly in Supabase, protected by row-level security.
All nutrient arithmetic uses the same composition table, exported here as JSON.
"""
import json

from django.shortcuts import render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from .models import Ingredient, IntakeItem, IntakeRecord, Participant, Supplement, ValidationSample
from .nutrients import KEYS, MEALS, NUTRIENTS, STYLES
from .templatetags.anv import is_ar
from .views import _profiles_json


def reference_data() -> dict:
    ar = is_ar()
    return {
        "keys": KEYS,
        "dishes": _profiles_json(),
        "ingredients": [{"code": i.code, "name": i.name, "n": [round(getattr(i, k), 4) for k in KEYS], "gi": i.gi}
                        for i in Ingredient.objects.order_by("name")],
        "supplements": [{"name": s.name, "dose": s.dose_label, "n": [round(getattr(s, k), 4) for k in KEYS]}
                        for s in Supplement.objects.order_by("name")],
        "nutrients": [{"key": n.key, "label": n.label_ar if ar else n.label, "unit": n.unit, "group": n.group,
                       "ref": n.reference, "upper": n.upper} for n in NUTRIENTS],
        "meals": [[k, str(v)] for k, v in MEALS],
        "variants": [[k, str(v)] for k, v in STYLES],
        "styles": [["mean", _("Average of recipes")]] + [[k, str(v)] for k, v in STYLES],
        "methods": [[k, str(v)] for k, v in IntakeRecord.METHODS],
        "sexes": [[k, str(v)] for k, v in Participant.SEX],
        "sources": [[k, str(v)] for k, v in IntakeItem.SOURCES],
        "views": [[k, str(v)] for k, v in ValidationSample.VIEWS],
    }


# Strings used by workspace.js. Most msgids are shared with the server edition, so one translation serves both.
JS_MSGIDS = {
    "totalFood": gettext_noop("Total (food)"), "kcal": gettext_noop("kcal"), "g": gettext_noop("g"), "mg": gettext_noop("mg"), "saveFail": gettext_noop("Could not save."), "saved": gettext_noop("Saved."), "deleted": gettext_noop("Deleted."),
    "confirmDel": gettext_noop("Press again to delete"), "loading": gettext_noop("Loading…"), "signInFail": gettext_noop("Email or password is incorrect."),
    "notConfigured": gettext_noop("The online database is not configured yet. See the README (GitHub Pages + Supabase)."),
    "noParticipants": gettext_noop("No participants yet. Add one with a pseudonymous code such as P001."),
    "noRecords": gettext_noop("No records yet."), "noRecordsYet": gettext_noop("No records yet. Create the first one with the form."),
    "noItems": gettext_noop("No foods yet. Add the first item with the form below, or from a photo."),
    "noPlates": gettext_noop("No plates yet."), "noSystems": gettext_noop("No plates with recognition outputs yet. Add a plate with the form, or from the Analyze page after weighing."),
    "dupCode": gettext_noop("You already have a participant with this code."), "chooseFood": gettext_noop("Choose a dish or an ingredient."),
    "portionRange": gettext_noop("Enter a portion between 1 and 3000 g."), "required": gettext_noop("Fill in the required fields."),
    "added": gettext_noop("Added %(food)s (%(g).0f g)."), "addedTo": gettext_noop("Added %(food)s (%(g).0f g) to the record of %(p)s, %(d)s."),
    "openRecord": gettext_noop("Open record"), "plateSaved": gettext_noop("Plate %(f)s saved."), "partAdded": gettext_noop("Participant %(code)s added."),
    "ffqDone": gettext_noop("Imported %(n)d FFQ items as average daily intake."), "ffqFix": gettext_noop("Fix these rows and upload again:"),
    "ffqUnknownFood": gettext_noop("Row %(n)s: food '%(f)s' is not in the composition table"),
    "ffqBadFreq": gettext_noop("Row %(n)s: cannot read frequency '%(f)s'"), "ffqEmpty": gettext_noop("The file has no readable rows."),
    "ffqNote": gettext_noop("FFQ import: %(f)s"),
    "years": gettext_noop("%(a)s years"), "y": gettext_noop("%(a)s y"), "target": gettext_noop("target %(t)s kcal/day"), "participantTitle": gettext_noop("Participant %(c)s"),
    "nRecords": gettext_noop("%(n)s records"), "nItems": gettext_noop("%(n)s items"), "nDays": gettext_noop("%(n)s recall/record days"),
    "usual": gettext_noop("Usual intake · mean of %(n)s days incl. supplements"),
    "kcalTarget": gettext_noop("kcal · target %(t)s"), "protPct": gettext_noop("protein · %(p)s%% of energy"),
    "fatPct": gettext_noop("fat · %(p)s%% of energy · SFA %(f)s%%"), "glLine": gettext_noop("glycaemic load · carbohydrate %(c)s g"),
    "imageOnly": gettext_noop("image-only estimate: %(k)s kcal"), "supplement": gettext_noop("Supplement"), "remove": gettext_noop("Remove"),
    "energyKcal": gettext_noop("Energy (kcal)"), "fatG": gettext_noop("Fat (g)"), "protein": gettext_noop("Protein"), "fat": gettext_noop("Fat"), "carb": gettext_noop("Carbohydrate"),
    "ofEnergy": gettext_noop("of energy"), "plates": gettext_noop("Plates"), "bias": gettext_noop("Bias"), "meanAxis": gettext_noop("Mean of estimate and truth (kcal)"),
    "diffAxis": gettext_noop("Estimate − truth (kcal)"), "platesSessions": gettext_noop("plates · %(n)s cooking sessions"), "demo": gettext_noop("demo"),
    "sysImage": gettext_noop("Image-only AI (zero-shot)"), "sysImageD": gettext_noop("An external model's own kcal estimate from pixels"),
    "sysRecipe": gettext_noop("Recipe-aware (AI dish + grams + style)"), "sysRecipeD": gettext_noop("ArabNutriVision pipeline"),
    "sysOracle": gettext_noop("Recipe-aware, true dish"), "sysOracleD": gettext_noop("Upper bound for recognition errors"),
    "welcome": gettext_noop("Welcome, %(n)s"), "signedInAs": gettext_noop("Signed in as %(n)s"),
    # insights (same msgids as services/estimate.py)
    "inFat": gettext_noop("Fat supplies %(p).0f%% of energy, above the 20–35%% range."),
    "inSfa": gettext_noop("Saturated fat is %(p).1f%% of energy; the WHO recommends less than 10%%."),
    "inNa": gettext_noop("Sodium is %(v).0f mg, above the 2,300 mg upper limit."),
    "inFib": gettext_noop("Fibre is %(v).0f g; adults are advised 25–30 g a day."),
    "inGl": gettext_noop("Daily glycaemic load is %(v).0f (above 120 is considered high)."),
    "inHidden": gettext_noop("%(n)d dish(es) are recorded as restaurant or unknown preparation (%(k).0f kcal). Confirming the preparation narrows the hidden-fat range most."),
    "inTop": gettext_noop("Largest energy sources: %(names)s."),
    "inMin": gettext_noop("%(label)s is %(v).0f mg (%(p).0f%% of the reference value)."), "iron": gettext_noop("Iron"), "calcium": gettext_noop("Calcium"),
    "inOk": gettext_noop("No nutrient exceeded the limits checked here."),
}


def js_strings() -> dict:
    return {k: _(v) for k, v in JS_MSGIDS.items()}


def _page(request, template, page, **extra):
    ctx = {"ref_json": reference_data(), "js_json": js_strings(),
           "ws_page": page, **extra}
    return render(request, template, ctx)


def login(request):
    return render(request, "static_site/login.html", {"js_json": js_strings()})


def dashboard(request):
    return _page(request, "static_site/dashboard.html", "dashboard")


def participants(request):
    return _page(request, "static_site/participants.html", "participants")


def participant_view(request):
    return _page(request, "static_site/participant.html", "participant")


def record_view(request):
    return _page(request, "static_site/record.html", "record")


def ffq(request):
    return _page(request, "static_site/ffq.html", "ffq")


def validation(request):
    return _page(request, "static_site/validation.html", "validation")


def recipe_builder(request):
    """Static edition: the recipe calculator works in the browser; saving new dishes needs the server edition."""
    from .views import recipe_builder as server_view
    return server_view.__wrapped__(request)
