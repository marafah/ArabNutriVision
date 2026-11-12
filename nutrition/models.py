from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .nutrients import MEALS, STYLES


class NutrientFields(models.Model):
    """Per-100 g (ingredient) or per-dose (supplement) nutrient columns."""
    kcal = models.FloatField(default=0)
    protein_g = models.FloatField(default=0)
    fat_g = models.FloatField(default=0)
    carb_g = models.FloatField(default=0)
    fiber_g = models.FloatField(default=0)
    sfa_g = models.FloatField(default=0)
    mufa_g = models.FloatField(default=0)
    pufa_g = models.FloatField(default=0)
    cholesterol_mg = models.FloatField(default=0)
    sodium_mg = models.FloatField(default=0)
    potassium_mg = models.FloatField(default=0)
    calcium_mg = models.FloatField(default=0)
    iron_mg = models.FloatField(default=0)
    magnesium_mg = models.FloatField(default=0)
    zinc_mg = models.FloatField(default=0)
    vitc_mg = models.FloatField(default=0)
    vita_rae_ug = models.FloatField(default=0)

    class Meta:
        abstract = True

    def nutrient_dict(self) -> dict[str, float]:
        from .nutrients import KEYS
        return {k: getattr(self, k) for k in KEYS}


class Ingredient(NutrientFields):
    code = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=160)
    gi = models.FloatField(null=True, blank=True, help_text="Glycaemic index (glucose = 100); blank if not applicable")
    source_note = models.CharField(max_length=200, blank=True)
    is_estimate = models.BooleanField(default=False, help_text="Placeholder value awaiting reference-book or laboratory data")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Dish(models.Model):
    CATEGORIES = [(c, c) for c in ["Main dish", "Stew", "Mezze", "Salad", "Sandwich", "Side", "Breakfast", "Bakery", "Dessert", "Custom"]]
    code = models.SlugField(max_length=60, unique=True)
    name_en = models.CharField(max_length=160)
    name_ar = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORIES, default="Main dish")
    serving_g = models.PositiveIntegerField(default=300)
    is_raw = models.BooleanField(default=False, help_text="Uncooked dish (no vitamin C cooking loss)")
    is_custom = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name_en"]
        verbose_name_plural = "dishes"

    def __str__(self):
        return self.name_en

    @property
    def short_name(self):
        return self.name_en.split(" (")[0]

    def get_absolute_url(self):
        return reverse("nutrition:dish_detail", args=[self.code])


class RecipeVariant(models.Model):
    STYLE_CHOICES = STYLES + [("custom", _("Custom"))]
    dish = models.ForeignKey(Dish, related_name="variants", on_delete=models.CASCADE)
    style = models.CharField(max_length=20, choices=STYLE_CHOICES)
    cooked_g = models.FloatField(help_text="Weight of the whole cooked batch (g)")
    source = models.CharField(max_length=200, blank=True, default="Draft standard recipe (to be replaced by weighed recipe)")

    class Meta:
        unique_together = ("dish", "style")
        ordering = ["dish", "style"]

    def __str__(self):
        return f"{self.dish} · {self.style}"


class RecipeLine(models.Model):
    variant = models.ForeignKey(RecipeVariant, related_name="lines", on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    grams = models.FloatField(help_text="Raw edible weight in the batch (g)")

    class Meta:
        ordering = ["-grams"]


class Participant(models.Model):
    SEX = [("F", _("Female")), ("M", _("Male")), ("X", _("Not recorded"))]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participants")
    code = models.CharField(max_length=30, help_text=_("Pseudonymous code only (e.g. P001). Never store names."))
    sex = models.CharField(max_length=1, choices=SEX, default="X")
    age_years = models.PositiveIntegerField(null=True, blank=True)
    energy_target_kcal = models.PositiveIntegerField(default=2000)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("owner", "code")
        ordering = ["code"]

    def __str__(self):
        return self.code

    def get_absolute_url(self):
        return reverse("nutrition:participant_detail", args=[self.pk])


class IntakeRecord(models.Model):
    METHODS = [("recall", _("24-hour recall")), ("record", _("Food record (weighed/estimated)")), ("menu", _("Menu / meal plan")), ("ffq", _("FFQ (daily average)"))]
    participant = models.ForeignKey(Participant, related_name="records", on_delete=models.CASCADE)
    date = models.DateField()
    method = models.CharField(max_length=10, choices=METHODS, default="recall")
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.participant} · {self.date} · {self.get_method_display()}"

    def get_absolute_url(self):
        return reverse("nutrition:record_detail", args=[self.pk])


class IntakeItem(models.Model):
    SOURCES = [("manual", _("Manual")), ("photo", _("Photo + AI")), ("photo_corrected", _("Photo, corrected")), ("ffq", _("FFQ import"))]
    record = models.ForeignKey(IntakeRecord, related_name="items", on_delete=models.CASCADE)
    meal = models.CharField(max_length=12, choices=MEALS, default="lunch")
    dish = models.ForeignKey(Dish, null=True, blank=True, on_delete=models.PROTECT)
    ingredient = models.ForeignKey(Ingredient, null=True, blank=True, on_delete=models.PROTECT)
    grams = models.FloatField()
    style = models.CharField(max_length=12, default="mean")
    source = models.CharField(max_length=20, choices=SOURCES, default="manual")
    ai_image_only_kcal = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["meal", "created_at"]

    @property
    def food_name(self):
        return self.dish.short_name if self.dish else (self.ingredient.name if self.ingredient else "?")


class Supplement(NutrientFields):
    name = models.CharField(max_length=120, unique=True)
    dose_label = models.CharField(max_length=60, default="1 tablet")

    def __str__(self):
        return self.name


class SupplementIntake(models.Model):
    record = models.ForeignKey(IntakeRecord, related_name="supplements", on_delete=models.CASCADE)
    supplement = models.ForeignKey(Supplement, on_delete=models.PROTECT)
    doses = models.FloatField(default=1)


class ValidationSample(models.Model):
    """One weighed plate of the ArabFood-N validation set, with the AI system outputs for that photo."""
    VIEWS = [("top", _("Top-down")), ("45deg", "45°")]
    SPLITS = [("train", "train"), ("val", "val"), ("test", "test")]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=20, help_text="Cooking session (split unit; never split a session)")
    plate_no = models.PositiveIntegerField(default=1)
    dish = models.ForeignKey(Dish, on_delete=models.PROTECT, related_name="validation_samples")
    variant = models.CharField(max_length=12, choices=STYLES, default="home")
    weight_g = models.FloatField(help_text="Weighed edible portion (1 g scale)")
    view = models.CharField(max_length=6, choices=VIEWS, default="top")
    reference_card = models.BooleanField(default=False)
    phone = models.CharField(max_length=40, blank=True)
    split = models.CharField(max_length=6, choices=SPLITS, default="test")
    image_file = models.CharField(max_length=160, blank=True, help_text="File name in the image archive (photos are not stored here)")
    ai_dish = models.ForeignKey(Dish, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ai_grams = models.FloatField(null=True, blank=True)
    ai_style = models.CharField(max_length=12, blank=True)
    ai_direct_kcal = models.FloatField(null=True, blank=True)
    ai_direct_fat_g = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def default_image_name(self):
        return f"{self.dish.code}_{self.session_id}_p{self.plate_no:02d}_{self.view}_{'card' if self.reference_card else 'nocard'}.jpg"

    def save(self, *args, **kwargs):
        if not self.image_file and self.dish_id:
            self.image_file = self.default_image_name()
        super().save(*args, **kwargs)
