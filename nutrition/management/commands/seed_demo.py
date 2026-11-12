"""Create a demo account with clearly labelled example data.

    python manage.py seed_demo                 # user "demo" / password "arabnutrivision-demo"
    python manage.py seed_demo --clear         # remove the demo user and everything it owns

The validation samples it creates are SIMULATED (session ids start with DEMO) so the Validation Lab
can be explored before the ArabFood-N weighing sessions; never report them as results.
"""
import datetime as dt
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from nutrition.models import Dish, IntakeItem, IntakeRecord, Participant, Supplement, SupplementIntake, ValidationSample
from nutrition.services.composition import all_profiles


class Command(BaseCommand):
    help = "Seed a demo account with example (simulated) data"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true")

    def handle(self, *args, **o):
        User = get_user_model()
        if o["clear"]:
            User.objects.filter(username="demo").delete()
            self.stdout.write("demo data removed")
            return
        user, created = User.objects.get_or_create(username="demo", defaults={"first_name": "Demo", "last_name": "Researcher"})
        if created:
            user.set_password("arabnutrivision-demo")
            user.save()
        p1, _ = Participant.objects.get_or_create(owner=user, code="P001", defaults={"sex": "F", "age_years": 34, "energy_target_kcal": 1900, "notes": "Example participant"})
        p2, _ = Participant.objects.get_or_create(owner=user, code="P002", defaults={"sex": "M", "age_years": 46, "energy_target_kcal": 2400, "notes": "Example participant"})
        d = {x.code: x for x in Dish.objects.all()}
        today = dt.date.today()
        if not p1.records.exists():
            r = IntakeRecord.objects.create(participant=p1, date=today - dt.timedelta(days=1), method="recall", notes="Example 24-h recall")
            for meal, code, g, style in [("breakfast", "foul", 200, "home"), ("breakfast", "manakish_zaatar", 120, "home"),
                                         ("lunch", "maqluba", 420, "restaurant"), ("lunch", "fattoush", 150, "home"),
                                         ("snack", "knafeh", 120, "restaurant"), ("dinner", "hummus", 150, "home"), ("dinner", "falafel", 100, "restaurant")]:
                IntakeItem.objects.create(record=r, meal=meal, dish=d[code], grams=g, style=style)
            SupplementIntake.objects.create(record=r, supplement=Supplement.objects.get(name__startswith="Iron"), doses=1)
            r2 = IntakeRecord.objects.create(participant=p1, date=today, method="record", notes="Example food record")
            for meal, code, g, style in [("breakfast", "fattet_hummus", 250, "home"), ("lunch", "mansaf", 450, "home"),
                                         ("dinner", "tabbouleh", 200, "light"), ("snack", "basbousa", 80, "home")]:
                IntakeItem.objects.create(record=r2, meal=meal, dish=d[code], grams=g, style=style)
        if not p2.records.exists():
            r = IntakeRecord.objects.create(participant=p2, date=today, method="recall", notes="Example 24-h recall")
            for meal, code, g, style in [("breakfast", "foul", 250, "restaurant"), ("lunch", "musakhan", 350, "restaurant"),
                                         ("lunch", "ruz_shaariyeh", 200, "home"), ("dinner", "chicken_shawarma_wrap", 300, "restaurant")]:
                IntakeItem.objects.create(record=r, meal=meal, dish=d[code], grams=g, style=style)
        if not ValidationSample.objects.filter(owner=user).exists():
            rng = random.Random(7)
            prof = all_profiles()
            codes = ["maqluba", "mansaf", "musakhan", "kabsa", "mujaddara", "hummus", "falafel", "tabbouleh", "fattoush", "knafeh", "warak_enab", "mulukhiyah"]
            for s in range(1, 5):
                for code in codes:
                    p = prof[code]
                    style = rng.choice(["home", "restaurant", "light"])
                    w = round(p.serving_g * rng.lognormvariate(0, 0.25))
                    true_k = w * p.variants[style]["kcal"] / 100
                    ai_d = d[code] if rng.random() < 0.85 else d[rng.choice(codes)]
                    ai_g = round(w * rng.lognormvariate(0, 0.22))
                    ai_style = style if rng.random() < 0.6 else rng.choice(["home", "restaurant", "light"])
                    # Simulated zero-shot model: sees the food but not the hidden fat (closer to the light recipe).
                    light = p.variants["light"]
                    ValidationSample.objects.create(
                        owner=user, session_id=f"DEMO{s:02d}", plate_no=codes.index(code) + 1, dish=d[code], variant=style, weight_g=w,
                        view=rng.choice(["top", "45deg"]), reference_card=rng.random() < 0.5, phone="simulated", split="test",
                        ai_dish=ai_d, ai_grams=ai_g, ai_style=ai_style,
                        ai_direct_kcal=round(ai_g * light["kcal"] / 100 * rng.lognormvariate(0, 0.18)),
                        ai_direct_fat_g=round(ai_g * light["fat_g"] / 100 * rng.lognormvariate(0, 0.30), 1))
        self.stdout.write(self.style.SUCCESS("Demo account ready: demo / arabnutrivision-demo (all data are examples)"))
