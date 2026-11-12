#!/usr/bin/env bash
# Build script for Render (or any Linux host)
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py load_reference_data
