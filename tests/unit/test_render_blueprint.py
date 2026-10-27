"""render.yaml keeps production in step with what the web shows.

The free plan has no cron jobs, so the boot command's `generate_slots --days`
decides how far ahead slots exist in production. It must cover every week a
patient can browse on the web (apps.doctors.services.BOOKING_WEEKS_AHEAD).
Production is also a demo: it seeds the demo doctors before generating
their slots.

Paso 32 moves production to the Docker image: the `medbook-demo` service
boots with the image's CMD, scripts/start-production.sh. While the native
service still exists, every check about the boot runs on both.
"""

import re
from pathlib import Path

import pytest
import yaml

from apps.doctors.services import BOOKING_WEEKS_AHEAD

ROOT = Path(__file__).resolve().parents[2]
RENDER_YAML = ROOT / "render.yaml"
DOCKERFILE = ROOT / "Dockerfile"
START_SCRIPT = ROOT / "scripts" / "start-production.sh"
DOCKER_SERVICE = "medbook-demo"
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


def service_named(name: str) -> dict:
    return next(s for s in web_services() if s["name"] == name)


def script_commands() -> str:
    """scripts/start-production.sh without its comments."""
    lines = START_SCRIPT.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def boot_command(service: dict) -> str:
    """What a service runs on every boot: the image's script, or startCommand."""
    if service["runtime"] == "docker":
        return script_commands()
    return service["startCommand"]


def env_of(service: dict) -> dict:
    return {var["key"]: var for var in service["envVars"]}


SERVICE_NAMES = [service["name"] for service in web_services()]


@pytest.mark.parametrize("name", SERVICE_NAMES)
def test_boot_generates_slots_for_every_bookable_week(name):
    boot = boot_command(service_named(name))
    match = re.search(r"generate_slots --days=(\d+)", boot)

    assert match, f"{name} no longer runs generate_slots on boot"
    # generate_slots covers today plus the next days - 1 days
    assert int(match.group(1)) >= 7 * BOOKING_WEEKS_AHEAD


@pytest.mark.parametrize("name", SERVICE_NAMES)
def test_boot_seeds_demo_data_before_generating_slots(name):
    boot = boot_command(service_named(name))

    assert "seed_demo" in boot, f"{name} no longer runs seed_demo on boot"
    assert boot.index("seed_demo") < boot.index("generate_slots")
    # A failed seed or slot run must not stop gunicorn from starting
    assert re.search(r"python manage\.py seed_demo \|\|", boot)
    assert re.search(r"python manage\.py generate_slots --days=\d+ \|\|", boot)


@pytest.mark.parametrize("name", SERVICE_NAMES)
def test_production_enables_demo_data(name):
    env = env_of(service_named(name))

    assert env["MEDBOOK_DEMO_DATA"]["value"] == "true"
    assert env["DJANGO_SETTINGS_MODULE"]["value"] == "config.settings.production"


@pytest.mark.parametrize("name", SERVICE_NAMES)
def test_no_service_writes_a_secret(name):
    env = env_of(service_named(name))

    assert not any("value" in env[key] for key in SECRETS & env.keys())


class TestDockerService:
    """The Alpine image from the repo's Dockerfile, on the free plan."""

    def test_builds_the_repo_dockerfile(self):
        service = service_named(DOCKER_SERVICE)

        assert service["runtime"] == "docker"
        assert service["dockerfilePath"] == "./Dockerfile"
        assert service["dockerContext"] == "."
        assert service["plan"] == "free"
        assert service["branch"] == "master"
        assert service["healthCheckPath"] == "/health/"

    def test_boots_with_the_image_cmd(self):
        """No dockerCommand: render.yaml and the image cannot drift apart."""
        assert "dockerCommand" not in service_named(DOCKER_SERVICE)
        cmd = [
            line
            for line in DOCKERFILE.read_text().splitlines()
            if line.startswith("CMD")
        ]
        assert cmd == ['CMD ["/bin/sh", "scripts/start-production.sh"]']

    def test_secrets_are_declared_without_values(self):
        env = env_of(service_named(DOCKER_SERVICE))

        for key in SECRETS:
            assert env[key] == {"key": key, "sync": False}


class TestStartScript:
    """scripts/start-production.sh, the image's CMD."""

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
