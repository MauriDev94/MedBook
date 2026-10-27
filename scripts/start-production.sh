#!/bin/sh
# Production boot of the Docker image (its CMD): Render runs it on every
# deploy and every time the free instance wakes up.
#
# migrate and ensure_superuser must succeed (set -e). seed_demo and
# generate_slots are idempotent: if they fail they only leave a WARNING and
# gunicorn starts anyway. The free plan has no cron jobs, so slots are
# generated here, 28 days ahead: the four weeks the web shows
# (BOOKING_WEEKS_AHEAD, checked by tests/unit/test_render_blueprint.py).
set -e

python manage.py migrate --noinput
python manage.py ensure_superuser
python manage.py seed_demo || echo "WARNING: seed_demo failed, starting without demo data"
python manage.py generate_slots --days=28 || echo "WARNING: generate_slots failed, starting without new slots"

# exec: gunicorn replaces the shell, so it gets the platform's stop signal.
# Render sets PORT (10000); a plain `docker run` falls back to 8000.
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120
