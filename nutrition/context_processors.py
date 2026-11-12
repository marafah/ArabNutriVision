TEAM = [
    {"name": "Dr. Mohammad Arafah", "name_ar": "د. محمد عرفه", "role": "Principal investigator · computer vision, AI and software",
     "affiliation": "Faculty of Information Technology, University of Petra, Amman, Jordan", "initials": "MA"},
    {"name": "Amna Zaytoun, MSc", "name_ar": "آمنة زيتون", "role": "Clinical nutrition · recipes, weighing protocol and validation",
     "affiliation": "MSc in Nutrition (graduate)", "initials": "AZ"},
]


def site(request):
    return {"ANV_VERSION": "1.0.0", "TEAM": TEAM}
