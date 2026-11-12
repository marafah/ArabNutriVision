"""Create or update an administrator account from environment variables (used at deploy time).

    ANV_ADMIN_USERNAME=... ANV_ADMIN_PASSWORD=... python manage.py ensure_admin

Nothing happens when the variables are not set, so no default password ever exists.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create/update the admin account from ANV_ADMIN_USERNAME / ANV_ADMIN_PASSWORD"

    def handle(self, *args, **o):
        name, pw = os.environ.get("ANV_ADMIN_USERNAME"), os.environ.get("ANV_ADMIN_PASSWORD")
        if not name or not pw:
            self.stdout.write("ANV_ADMIN_USERNAME / ANV_ADMIN_PASSWORD not set; skipping admin account")
            return
        User = get_user_model()
        u, created = User.objects.get_or_create(username=name)
        u.is_staff = u.is_superuser = True
        u.first_name = u.first_name or os.environ.get("ANV_ADMIN_FIRST_NAME", "")
        u.last_name = u.last_name or os.environ.get("ANV_ADMIN_LAST_NAME", "")
        u.set_password(pw)
        u.save()
        self.stdout.write(self.style.SUCCESS(f"admin account '{name}' {'created' if created else 'updated'}"))
