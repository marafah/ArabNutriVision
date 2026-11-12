"""Render the static edition (GitHub Pages) of ArabNutriVision.

    ANV_STATIC_SITE=1 ANV_BASE_PATH=/ArabNutriVision python manage.py build_site --out _site

English pages are written under <base>/ and Arabic pages under <base>/ar/. Static files are collected to
<base>/static/. Researcher pages are shells driven by workspace.js and Supabase.
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.test import Client, override_settings
from django.urls import set_script_prefix

from nutrition.models import Dish

PAGES = ["/", "/research/", "/analyze/", "/dishes/", "/dishes/new/", "/accounts/login/", "/workspace/", "/participants/",
         "/participants/view/", "/records/view/", "/ffq/", "/validation/", "/inbody/", "/body/", "/participants/report/"]


class Command(BaseCommand):
    help = "Build the static GitHub Pages edition into a folder."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="_site")

    def handle(self, *args, out, **kw):
        if not settings.STATIC_SITE:
            raise CommandError("Set ANV_STATIC_SITE=1 (and optionally ANV_BASE_PATH, SUPABASE_URL, SUPABASE_ANON_KEY).")
        out = Path(out).resolve()
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        base = settings.ANV_BASE_PATH
        pages = PAGES + [f"/dishes/{c}/" for c in Dish.objects.order_by("code").values_list("code", flat=True)]
        n = 0
        for lang, prefix in (("en", ""), ("ar", "/ar")):
            with override_settings(FORCE_SCRIPT_NAME=base + prefix):
                set_script_prefix(base + prefix + "/")
                client = Client(HTTP_ACCEPT_LANGUAGE=lang)
                client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
                for path in pages:
                    r = client.get(path)
                    if r.status_code != 200:
                        raise CommandError(f"{lang}{path}: HTTP {r.status_code}")
                    html = r.content.decode("utf-8")
                    if base + "/admin/" in html:
                        html = html.replace(base + "/admin/", base + "/")
                    target = out / prefix.strip("/") / path.strip("/") / "index.html"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(html, encoding="utf-8")
                    n += 1
        set_script_prefix(base + "/")
        (out / "404.html").write_text((out / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
        (out / ".nojekyll").write_text("", encoding="utf-8")
        with override_settings(STATIC_ROOT=str(out / "static")):
            call_command("collectstatic", interactive=False, verbosity=0, ignore_patterns=["admin", "*.map"])
        if not settings.SUPABASE_URL:
            self.stdout.write(self.style.WARNING("SUPABASE_URL is empty: public pages work; the researcher workspace will show a setup notice."))
        self.stdout.write(self.style.SUCCESS(f"Wrote {n} pages to {out} for base path {base}/"))
