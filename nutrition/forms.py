from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Dish, IntakeItem, IntakeRecord, Participant, Supplement, SupplementIntake, ValidationSample
from .nutrients import MEALS, STYLES

STYLE_CHOICES = [("mean", _("Average of recipes"))] + STYLES


class BootstrapMixin:
    def _bs(self):
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")


class ParticipantForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["code", "sex", "age_years", "energy_target_kcal", "notes"]
        labels = {"code": _("Participant code"), "sex": _("Sex"), "age_years": _("Age (years)"), "energy_target_kcal": _("Energy target (kcal/day)"), "notes": _("Notes")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["code"].widget.attrs["placeholder"] = "P003"


class RecordForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = IntakeRecord
        fields = ["date", "method", "notes"]
        labels = {"date": _("Date"), "method": _("Method"), "notes": _("Notes")}
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["method"].choices = [c for c in IntakeRecord.METHODS if c[0] != "ffq"]


class ItemForm(BootstrapMixin, forms.ModelForm):
    style = forms.ChoiceField(choices=STYLE_CHOICES, initial="mean", label=_("Preparation"))

    class Meta:
        model = IntakeItem
        fields = ["meal", "dish", "ingredient", "grams", "style"]
        labels = {"grams": _("Portion (g)"), "ingredient": _("…or single ingredient"), "meal": _("Meal"), "dish": _("Dish")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["dish"].required = False
        self.fields["ingredient"].required = False
        self.fields["dish"].queryset = Dish.objects.order_by("name_en")

    def clean(self):
        c = super().clean()
        if not c.get("dish") and not c.get("ingredient"):
            raise forms.ValidationError(_("Choose a dish or an ingredient."))
        if c.get("grams") is not None and not (1 <= c["grams"] <= 3000):
            self.add_error("grams", _("Enter a portion between 1 and 3000 g."))
        return c


class SupplementIntakeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = SupplementIntake
        fields = ["supplement", "doses"]
        labels = {"supplement": _("Supplement"), "doses": _("Doses")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["supplement"].queryset = Supplement.objects.order_by("name")


class FFQUploadForm(BootstrapMixin, forms.Form):
    participant = forms.ModelChoiceField(queryset=Participant.objects.none(), label=_("Participant"))
    file = forms.FileField(label=_("File"), help_text=_("CSV or Excel (.xlsx) with columns: food, frequency, portion_g"))

    def __init__(self, user, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["participant"].queryset = Participant.objects.filter(owner=user)
        self._bs()

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith((".csv", ".xlsx", ".xlsm")):
            raise forms.ValidationError(_("Upload a .csv or .xlsx file."))
        return f


class ValidationSampleForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ValidationSample
        fields = ["session_id", "plate_no", "dish", "variant", "weight_g", "view", "reference_card", "phone", "split",
                  "ai_dish", "ai_grams", "ai_style", "ai_direct_kcal", "ai_direct_fat_g"]
        labels = {"session_id": _("Session id"), "plate_no": _("Plate no."), "dish": _("True dish"), "variant": _("True recipe variant"),
                  "weight_g": _("Weighed portion (g)"), "view": _("View"), "reference_card": _("Reference card in photo"),
                  "phone": _("Phone"), "split": _("Split"), "ai_dish": _("AI dish"), "ai_grams": _("AI portion (g)"), "ai_style": _("AI style"),
                  "ai_direct_kcal": _("Image-only kcal (external model)"), "ai_direct_fat_g": _("Image-only fat g (external model)")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["dish"].queryset = Dish.objects.order_by("name_en")
        self.fields["ai_dish"].queryset = Dish.objects.order_by("name_en")
        self.fields["ai_style"] = forms.ChoiceField(choices=[("", "—")] + STYLES, required=False, label=_("AI style"),
                                                    widget=forms.Select(attrs={"class": "form-select"}))


class CustomDishForm(BootstrapMixin, forms.Form):
    name_en = forms.CharField(max_length=160, label=_("Dish name (English)"))
    name_ar = forms.CharField(max_length=160, required=False, label=_("Dish name (Arabic)"))
    category = forms.ChoiceField(choices=Dish.CATEGORIES, initial="Custom", label=_("Category"))
    serving_g = forms.IntegerField(min_value=10, max_value=2000, initial=300, label=_("Typical serving (g)"))
    cooked_g = forms.FloatField(min_value=10, label=_("Cooked batch weight (g)"), help_text=_("Weigh the whole pot after cooking"))
    is_raw = forms.BooleanField(required=False, label=_("Served raw (no cooking losses)"))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()


MEAL_CHOICES = MEALS
