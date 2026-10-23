"""render.yaml keeps production slots in step with the web's booking horizon.

The free plan has no cron jobs, so the startCommand's `generate_slots --days`
decides how far ahead slots exist in production. It must cover every week a
patient can browse on the web (apps.doctors.services.BOOKING_WEEKS_AHEAD).
"""

import re
from pathlib import Path

from apps.doctors.services import BOOKING_WEEKS_AHEAD

RENDER_YAML = Path(__file__).resolve().parents[2] / "render.yaml"


def test_boot_generates_slots_for_every_bookable_week():
    match = re.search(
        r"generate_slots --days=(\d+)", RENDER_YAML.read_text(encoding="utf-8")
    )

    assert match, "render.yaml no longer runs generate_slots on boot"
    # generate_slots covers today plus the next days - 1 days
    assert int(match.group(1)) >= 7 * BOOKING_WEEKS_AHEAD
