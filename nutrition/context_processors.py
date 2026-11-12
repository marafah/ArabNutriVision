from django.utils.translation import gettext_lazy as _

TEAM = [
    {"name": "Dr. Mohammad Arafah", "name_ar": "د. محمد عرفه", "role": _("Principal investigator · computer vision, AI and software"),
     "affiliation": _("Faculty of Information Technology, University of Petra, Amman, Jordan"), "initials": "MA"},
    {"name": "Amna Zaytoun, MSc", "name_ar": "آمنة زيتون", "role": _("Clinical nutrition · recipes, weighing protocol and validation"),
     "affiliation": _("MSc in Nutrition (graduate)"), "initials": "AZ"},
]


def site(request):
    return {"ANV_VERSION": "1.0.0", "TEAM": TEAM}
