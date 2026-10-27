"""render.yaml keeps production in step with what the web shows.

Production is the `medbook-demo` service: Render builds the repo's
Dockerfile and boots it with the image's CMD, scripts/start-production.sh
(Paso 32). The free plan has no cron jobs, so the boot's
`generate_slots --days` decides how far ahead slots exist in production. It
must cover every week a patient can browse on the web
(apps.doctors.services.BOOKING_WEEKS_AHEAD). Production is also a demo: it
seeds the demo doctors before generating their slots.
"""

import re
from pathlib import Path

import yaml

from apps.doctors.services import BOOKING_WEEKS_AHEAD

ROOT = Path(__file__).resolve().parents[2]
RENDER_YAML = ROOT / "render.yaml"
DOCKERFILE = ROOT / "Dockerfile"
START_SCRIPT = ROOT / "scripts" / "start-production.sh"
SERVICE = "medbook-demo"
HOST = "medbook-demo.onrender.com"
# Never in render.yaml with a value: they live only in the dashboard
SECRETS = {
    "SECRET_KEY",
    "DATABASE_URL",
    "DJANGO_SUPERUSER_EMAIL",
    "DJANGO_SUPERUSER_PASSWORD",
}


def web_services() -> list[dict]:
    blueprint = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    return [service for service in blueprint["services"] if service["type"] == "web"]


def production() -> dict:
    return next(s for s in web_services() if s["name"] == SERVICE)


def env() -> dict:
    return {var["key"]: var for var in production()["envVars"]}


def script_commands() -> str:
    """scripts/start-production.sh without its comments."""
    lines = START_SCRIPT.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


class TestDockerService:
    """The Alpine image from the repo's Dockerfile, on the free plan."""

    def test_is_the_only_web_service(self):
        """The native `MedBook` service was retired in Paso 32."""
        assert [service["name"] for service in web_services()] == [SERVICE]

    def test_builds_the_repo_dockerfile(self):
        service = production()

        assert service["runtime"] == "docker"
        assert service["dockerfilePath"] == "./Dockerfile"
        assert service["dockerContext"] == "."
        assert service["plan"] == "free"
        assert service["branch"] == "master"
        assert service["healthCheckPath"] == "/health/"

    def test_boots_with_the_image_cmd(self):
        """No dockerCommand: render.yaml and the image cannot drift apart."""
        assert "dockerCommand" not in production()
        cmd = [
            line
            for line in DOCKERFILE.read_text().splitlines()
            if line.startswith("CMD")
        ]
        assert cmd == ['CMD ["/bin/sh", "scripts/start-production.sh"]']

    def test_only_serves_its_own_host(self):
        """Render's health checks send this Host too (no custom domain)."""
        assert env()["ALLOWED_HOSTS"]["value"] == HOST

    def test_enables_demo_data(self):
        assert env()["MEDBOOK_DEMO_DATA"]["value"] == "true"
        assert env()["DJANGO_SETTINGS_MODULE"]["value"] == "config.settings.production"

    def test_secrets_are_declared_without_values(self):
        for key in SECRETS:
            assert env()[key] == {"key": key, "sync": False}


class TestStartScript:
    """scripts/start-production.sh, the image's CMD."""

    def test_generates_slots_for_every_bookable_week(self):
        match = re.search(r"generate_slots --days=(\d+)", script_commands())

        assert match, "the boot no longer runs generate_slots"
        # generate_slots covers today plus the next days - 1 days
        assert int(match.group(1)) >= 7 * BOOKING_WEEKS_AHEAD

    def test_seeds_demo_data_before_generating_slots(self):
        script = script_commands()

        assert script.index("seed_demo") < script.index("generate_slots")
        # A failed seed or slot run must not stop gunicorn from starting
        assert re.search(r"python manage\.py seed_demo \|\|", script)
        assert re.search(r"python manage\.py generate_slots --days=\d+ \|\|", script)

    def test_stops_if_migrate_or_the_superuser_fails(self):
        script = script_commands()

        assert re.search(r"^set -e$", script, re.MULTILINE)
        assert script.index("migrate --noinput") < script.index("ensure_superuser")
        assert script.index("ensure_superuser") < script.index("seed_demo")

    def test_gunicorn_replaces_the_shell_and_binds_the_platform_port(self):
        """exec: gunicorn gets the stop signal; Render sets PORT (10000)."""
        last = script_commands().strip().splitlines()[-1]

        assert last.startswith("exec gunicorn config.wsgi:application")
        assert '--bind "0.0.0.0:${PORT:-8000}"' in last

    def test_has_unix_line_endings(self):
        """A CRLF script fails in Alpine's sh ("set: illegal option -")."""
        assert b"\r\n" not in START_SCRIPT.read_bytes()
