from django.utils.translation import gettext_lazy as _

TEAM = [
    {"name": "Dr. Mohammad Arafah", "name_ar": "د. محمد عرفه", "role": _("Principal investigator · computer vision, AI and software"),
     "affiliation": _("Faculty of Information Technology, University of Petra, Amman, Jordan"), "initials": "MA"},
    {"name": "Amna Zaytoun, MSc", "name_ar": "آمنة زيتون", "role": _("Clinical nutrition · recipes, weighing protocol and validation"),
     "affiliation": _("MSc in Nutrition (graduate)"), "initials": "AZ"},
]


def site(request):
    from django.conf import settings
    from django.utils.translation import get_language
    ctx = {"ANV_VERSION": "1.1.0", "TEAM": TEAM, "STATIC_SITE": settings.STATIC_SITE}
    if settings.STATIC_SITE:
        base = settings.ANV_BASE_PATH
        ar = (get_language() or "en").startswith("ar")
        ctx.update({"ALT_URL": base + ("" if ar else "/ar") + request.path_info, "SITE_ROOT": base,
                    "SUPABASE_URL": settings.SUPABASE_URL, "SUPABASE_ANON_KEY": settings.SUPABASE_ANON_KEY})
    return ctx
