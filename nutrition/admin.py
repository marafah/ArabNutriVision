from django.contrib import admin

from .models import (Dish, Ingredient, IntakeItem, IntakeRecord, Participant, RecipeLine, RecipeVariant, Supplement,
                     SupplementIntake, ValidationSample)
from .services.composition import invalidate


class InvalidatingAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate()


@admin.register(Ingredient)
class IngredientAdmin(InvalidatingAdmin):
    list_display = ("name", "code", "kcal", "protein_g", "fat_g", "carb_g", "sfa_g", "gi", "is_estimate")
    list_filter = ("is_estimate",)
    search_fields = ("name", "code")


class RecipeLineInline(admin.TabularInline):
    model = RecipeLine
    extra = 1
    autocomplete_fields = ("ingredient",)


@admin.register(RecipeVariant)
class RecipeVariantAdmin(InvalidatingAdmin):
    list_display = ("dish", "style", "cooked_g", "source")
    list_filter = ("style",)
    inlines = [RecipeLineInline]


class VariantInline(admin.TabularInline):
    model = RecipeVariant
    extra = 0
    show_change_link = True


@admin.register(Dish)
class DishAdmin(InvalidatingAdmin):
    list_display = ("name_en", "name_ar", "category", "serving_g", "is_custom")
    list_filter = ("category", "is_custom")
    search_fields = ("name_en", "name_ar", "code")
    inlines = [VariantInline]


class ItemInline(admin.TabularInline):
    model = IntakeItem
    extra = 0


@admin.register(IntakeRecord)
class IntakeRecordAdmin(admin.ModelAdmin):
    list_display = ("participant", "date", "method")
    list_filter = ("method",)
    inlines = [ItemInline]


admin.site.register(Participant)
admin.site.register(Supplement)
admin.site.register(SupplementIntake)


@admin.register(ValidationSample)
class ValidationSampleAdmin(admin.ModelAdmin):
    list_display = ("image_file", "session_id", "dish", "variant", "weight_g", "split", "ai_dish", "ai_grams", "ai_direct_kcal")
    list_filter = ("split", "dish")
