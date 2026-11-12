from django import forms

from .models import Dish, IntakeItem, IntakeRecord, Participant, Supplement, SupplementIntake, ValidationSample
from .nutrients import MEALS, STYLES

STYLE_CHOICES = [("mean", "Average of recipes")] + STYLES


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
        labels = {"code": "Participant code", "age_years": "Age (years)", "energy_target_kcal": "Energy target (kcal/day)"}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["code"].widget.attrs["placeholder"] = "P003"


class RecordForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = IntakeRecord
        fields = ["date", "method", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["method"].choices = [c for c in IntakeRecord.METHODS if c[0] != "ffq"]


class ItemForm(BootstrapMixin, forms.ModelForm):
    style = forms.ChoiceField(choices=STYLE_CHOICES, initial="mean", label="Preparation")

    class Meta:
        model = IntakeItem
        fields = ["meal", "dish", "ingredient", "grams", "style"]
        labels = {"grams": "Portion (g)", "ingredient": "…or single ingredient"}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["dish"].required = False
        self.fields["ingredient"].required = False
        self.fields["dish"].queryset = Dish.objects.order_by("name_en")

    def clean(self):
        c = super().clean()
        if not c.get("dish") and not c.get("ingredient"):
            raise forms.ValidationError("Choose a dish or an ingredient.")
        if c.get("grams") is not None and not (1 <= c["grams"] <= 3000):
            self.add_error("grams", "Enter a portion between 1 and 3000 g.")
        return c


class SupplementIntakeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = SupplementIntake
        fields = ["supplement", "doses"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["supplement"].queryset = Supplement.objects.order_by("name")


class FFQUploadForm(BootstrapMixin, forms.Form):
    participant = forms.ModelChoiceField(queryset=Participant.objects.none())
    file = forms.FileField(help_text="CSV or Excel (.xlsx) with columns: food, frequency, portion_g")

    def __init__(self, user, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["participant"].queryset = Participant.objects.filter(owner=user)
        self._bs()

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith((".csv", ".xlsx", ".xlsm")):
            raise forms.ValidationError("Upload a .csv or .xlsx file.")
        return f


class ValidationSampleForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ValidationSample
        fields = ["session_id", "plate_no", "dish", "variant", "weight_g", "view", "reference_card", "phone", "split",
                  "ai_dish", "ai_grams", "ai_style", "ai_direct_kcal", "ai_direct_fat_g"]
        labels = {"dish": "True dish", "variant": "True recipe variant", "weight_g": "Weighed portion (g)",
                  "ai_dish": "AI dish", "ai_grams": "AI portion (g)", "ai_style": "AI style",
                  "ai_direct_kcal": "AI image-only kcal", "ai_direct_fat_g": "AI image-only fat (g)"}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()
        self.fields["dish"].queryset = Dish.objects.order_by("name_en")
        self.fields["ai_dish"].queryset = Dish.objects.order_by("name_en")
        self.fields["ai_style"] = forms.ChoiceField(choices=[("", "—")] + STYLES, required=False, label="AI style",
                                                    widget=forms.Select(attrs={"class": "form-select"}))


class CustomDishForm(BootstrapMixin, forms.Form):
    name_en = forms.CharField(max_length=160, label="Dish name (English)")
    name_ar = forms.CharField(max_length=160, required=False, label="Dish name (Arabic)")
    category = forms.ChoiceField(choices=Dish.CATEGORIES, initial="Custom")
    serving_g = forms.IntegerField(min_value=10, max_value=2000, initial=300, label="Typical serving (g)")
    cooked_g = forms.FloatField(min_value=10, label="Cooked batch weight (g)", help_text="Weigh the whole pot after cooking")
    is_raw = forms.BooleanField(required=False, label="Served raw (no cooking losses)")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._bs()


MEAL_CHOICES = MEALS
