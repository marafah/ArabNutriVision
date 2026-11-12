"""Template helpers for bilingual (English / Arabic) display."""
from django import template
from django.utils.translation import get_language, gettext

register = template.Library()

CATEGORIES = {"Main dish": "طبق رئيسي", "Stew": "يخنة", "Mezze": "مقبلات", "Salad": "سلطة", "Sandwich": "ساندويش",
              "Side": "طبق جانبي", "Breakfast": "فطور", "Bakery": "مخبوزات", "Dessert": "حلويات", "Custom": "وصفة خاصة"}
STYLES = {"mean": ("Average", "متوسط"), "home": ("Home", "بيتي"), "restaurant": ("Restaurant", "مطاعم"),
          "light": ("Light", "خفيف"), "custom": ("Custom", "خاص")}


def is_ar() -> bool:
    return (get_language() or "en").startswith("ar")


@register.filter
def dish_name(obj, full=False):
    """Localised dish name for a Dish, Profile or dict-like object."""
    ar = getattr(obj, "name_ar", "") or ""
    en = getattr(obj, "name_en", None) or getattr(obj, "name", "") or ""
    if is_ar() and ar:
        return ar
    return en if full else en.split(" (")[0]


@register.filter
def dish_name_full(obj):
    return dish_name(obj, True)


@register.filter
def dish_alt(obj):
    """The name in the other language, shown as a secondary line."""
    ar = getattr(obj, "name_ar", "") or ""
    en = getattr(obj, "name_en", None) or getattr(obj, "name", "") or ""
    return en.split(" (")[0] if is_ar() else ar


@register.filter
def cat(value):
    return CATEGORIES.get(value, value) if is_ar() else value


@register.filter
def style(value):
    en, ar = STYLES.get(value, (value, value))
    return ar if is_ar() else en


@register.filter
def nlabel(n):
    return n.label_ar if is_ar() else n.label


@register.simple_tag
def other_language():
    return ("en", "English") if is_ar() else ("ar", "العربية")


FAT_SOURCES = {"Almonds": "لوز", "Beef": "لحم بقري", "Butter": "زبدة", "Chicken": "دجاج بالجلد", "Chicken breast": "صدر دجاج",
               "Chicken thigh": "فخذ دجاج", "Coconut": "جوز الهند", "Ghee": "سمن", "Lamb": "لحم خروف",
               "Nabulsi/akkawi cheese": "جبنة نابلسية/عكاوي", "Olive oil": "زيت زيتون", "Pine nuts": "صنوبر",
               "Tahini": "طحينة", "Vegetable oil": "زيت نباتي"}


def fat_source(name: str) -> str:
    return FAT_SOURCES.get(name, name) if is_ar() else name
