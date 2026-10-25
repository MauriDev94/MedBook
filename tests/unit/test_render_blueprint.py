"""render.yaml keeps production in step with what the web shows.

The free plan has no cron jobs, so the startCommand's `generate_slots --days`
decides how far ahead slots exist in production. It must cover every week a
patient can browse on the web (apps.doctors.services.BOOKING_WEEKS_AHEAD).
Production is also a demo: it seeds the demo doctors before generating
their slots.
"""

import re
from pathlib import Path

import yaml

from apps.doctors.services import BOOKING_WEEKS_AHEAD

RENDER_YAML = Path(__file__).resolve().parents[2] / "render.yaml"


def web_service() -> dict:
    blueprint = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    return next(s for s in blueprint["services"] if s["name"] == "MedBook")


def test_boot_generates_slots_for_every_bookable_week():
    match = re.search(r"generate_slots --days=(\d+)", web_service()["startCommand"])

    assert match, "render.yaml no longer runs generate_slots on boot"
    # generate_slots covers today plus the next days - 1 days
    assert int(match.group(1)) >= 7 * BOOKING_WEEKS_AHEAD


def test_boot_seeds_demo_data_before_generating_slots():
    start = web_service()["startCommand"]

    assert "seed_demo" in start, "render.yaml no longer runs seed_demo on boot"
    assert start.index("seed_demo") < start.index("generate_slots")
    # Like generate_slots, a failed seed must not stop gunicorn from starting
    assert re.search(r"\(python manage\.py seed_demo \|\|", start)


def test_production_enables_demo_data():
    env = {var["key"]: var.get("value") for var in web_service()["envVars"]}

    assert env.get("MEDBOOK_DEMO_DATA") == "true"
