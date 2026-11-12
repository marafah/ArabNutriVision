import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Dish, IntakeItem, IntakeRecord, Participant, ValidationSample
from .services import ffq, metrics
from .services.composition import all_profiles, gap_decomposition
from .services.estimate import estimate, insights, record_summary


class ReferenceDataMixin:
    @classmethod
    def setUpTestData(cls):
        call_command("load_reference_data", stdout=io.StringIO())
        call_command("seed_demo", stdout=io.StringIO())
        cls.user = get_user_model().objects.get(username="demo")


class CompositionTests(ReferenceDataMixin, TestCase):
    def test_table_is_plausible_and_passes_atwater(self):
        profiles = all_profiles(refresh=True)
        self.assertGreaterEqual(len(profiles), 20)
        for p in profiles.values():
            self.assertTrue(30 < p.mean["kcal"] < 500, p.code)
            self.assertLessEqual(p.low["kcal"], p.mean["kcal"])
            self.assertLessEqual(p.mean["kcal"], p.high["kcal"])
            atw = 4 * p.mean["protein_g"] + 9 * p.mean["fat_g"] + 4 * p.mean["carb_g"]
            self.assertLess(abs(atw - p.mean["kcal"]) / p.mean["kcal"], 0.15, p.code)
            fa = p.mean["sfa_g"] + p.mean["mufa_g"] + p.mean["pufa_g"]
            self.assertLessEqual(fa, p.mean["fat_g"] * 1.05, p.code)

    def test_maqluba_matches_python_pipeline(self):
        p = all_profiles()["maqluba"]
        self.assertAlmostEqual(p.mean["kcal"], 176.78, delta=0.1)   # same value as scripts/build_table.py
        self.assertAlmostEqual(p.variants["light"]["kcal"], 127.05, delta=0.1)

    def test_interval_contains_point(self):
        e = estimate(all_profiles()["mansaf"], 450)
        self.assertLessEqual(e.low["kcal"], e.point["kcal"])
        self.assertLessEqual(e.point["kcal"], e.high["kcal"])

    def test_gap_decomposition_sums_to_variant_difference(self):
        d = Dish.objects.get(code="musakhan")
        gap = gap_decomposition(d)
        p = all_profiles()["musakhan"]
        self.assertAlmostEqual(sum(gap.values()), p.variants["restaurant"]["kcal"] - p.variants["light"]["kcal"], delta=0.5)


class MetricsAndFFQTests(TestCase):
    def test_metrics(self):
        self.assertEqual(metrics.mae([110, 90], [100, 100]), 10)
        self.assertEqual(metrics.mape([110, 90], [100, 100]), 10)
        self.assertEqual(metrics.coverage([0, 0], [5, 1], [3, 3]), 50)
        ba = metrics.bland_altman([110, 90, 100], [100, 100, 100])
        self.assertAlmostEqual(ba["bias"], 0)

    def test_frequency_parser(self):
        self.assertEqual(ffq.parse_frequency("2/day"), 2)
        self.assertAlmostEqual(ffq.parse_frequency("7/week"), 1)
        self.assertAlmostEqual(ffq.parse_frequency("1 per month"), 1 / 30.4)
        self.assertEqual(ffq.parse_frequency("never"), 0)
        with self.assertRaises(ValueError):
            ffq.parse_frequency("often")


class RecordTests(ReferenceDataMixin, TestCase):
    def test_summary_and_insights(self):
        rec = IntakeRecord.objects.filter(participant__owner=self.user).first()
        s = record_summary(rec)
        self.assertGreater(s["totals"]["kcal"], 0)
        ins = insights(s)
        self.assertTrue(ins)
        self.assertTrue(all(i["level"] in ("good", "warn", "crit", "info") for i in ins))


class ViewTests(ReferenceDataMixin, TestCase):
    def test_public_pages(self):
        for name, args in [("home", []), ("research", []), ("analyze", []), ("dishes", []), ("dish_detail", ["maqluba"])]:
            r = self.client.get(reverse(f"nutrition:{name}", args=args))
            self.assertEqual(r.status_code, 200, name)
        self.assertContains(self.client.get(reverse("nutrition:home")), "University of Petra")

    def test_private_pages_require_login(self):
        r = self.client.get(reverse("nutrition:dashboard"))
        self.assertEqual(r.status_code, 302)

    def test_workspace_flow(self):
        self.client.force_login(self.user)
        for name in ["dashboard", "participants", "ffq", "validation", "recipe_builder"]:
            self.assertEqual(self.client.get(reverse(f"nutrition:{name}")).status_code, 200, name)
        part = Participant.objects.filter(owner=self.user).first()
        self.assertEqual(self.client.get(part.get_absolute_url()).status_code, 200)
        rec = part.records.first()
        self.assertEqual(self.client.get(rec.get_absolute_url()).status_code, 200)
        n = rec.items.count()
        self.client.post(rec.get_absolute_url(), {"action": "item", "i-meal": "lunch", "i-dish": Dish.objects.get(code="kabsa").pk,
                                                  "i-grams": 350, "i-style": "home"})
        self.assertEqual(rec.items.count(), n + 1)
        r = self.client.get(reverse("nutrition:record_csv", args=[rec.pk]))
        self.assertIn("kcal", r.content.decode("utf-8"))
        r = self.client.post(reverse("nutrition:api_add_item"), {"record": rec.pk, "dish": "falafel", "grams": 100, "style": "light", "meal": "snack"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_ffq_upload(self):
        self.client.force_login(self.user)
        part = Participant.objects.filter(owner=self.user).first()
        f = SimpleUploadedFile("ffq.csv", ffq.TEMPLATE.encode(), content_type="text/csv")
        r = self.client.post(reverse("nutrition:ffq"), {"participant": part.pk, "file": f})
        self.assertEqual(r.status_code, 302)
        rec = IntakeRecord.objects.filter(participant=part, method="ffq").latest("created_at")
        self.assertEqual(rec.items.count(), 5)
        maq = rec.items.get(dish__code="maqluba")
        self.assertAlmostEqual(maq.grams, 400 * 2 / 7, places=3)

    def test_recipe_builder_creates_dish(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("nutrition:recipe_builder"), {"name_en": "Test rice", "name_ar": "", "category": "Custom",
                                                                    "serving_g": 200, "cooked_g": 1000, "ing": ["rice_white_raw", "olive_oil"],
                                                                    "grams": ["400", "40"]})
        self.assertEqual(r.status_code, 302)
        p = all_profiles()["custom-test-rice"]
        self.assertAlmostEqual(p.mean["kcal"], (400 * 3.65 + 40 * 8.84) / 10, delta=0.5)

    def test_validation_metrics(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("nutrition:validation"))
        self.assertGreater(r.context["res"]["n"], 0)
        self.assertTrue(r.context["res"]["systems"])
        self.assertTrue(ValidationSample.objects.filter(owner=self.user).exists())
        csv = self.client.get(reverse("nutrition:validation_csv")).content.decode()
        self.assertTrue(csv.startswith("image_file,dish_id"))

    def test_analyze_page_uses_on_device_model(self):
        r = self.client.get(reverse("nutrition:analyze"))
        self.assertContains(r, "vendor/transformers/")
        self.assertNotContains(r, "api.anthropic.com")

    def test_other_users_cannot_see_records(self):
        other = get_user_model().objects.create_user("other", password="x-strong-pass-123")
        self.client.force_login(other)
        rec = IntakeRecord.objects.filter(participant__owner=self.user).first()
        self.assertEqual(self.client.get(rec.get_absolute_url()).status_code, 404)
        self.assertFalse(IntakeItem.objects.filter(record__participant__owner=other).exists())
