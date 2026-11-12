#!/usr/bin/env bash
# Build script for Render (or any Linux host).
# With the default SQLite database the data are rebuilt at every deploy/restart (demo use);
# set DATABASE_URL to a PostgreSQL database to keep researchers' records permanently.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py load_reference_data
python manage.py seed_demo
python manage.py ensure_admin
