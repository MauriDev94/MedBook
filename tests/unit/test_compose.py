"""docker-compose.yml: `up` starts only Postgres, and `web` is the production image.

For development the app runs with `runserver`. The `web` service sits behind a
profile and boots the image the way Render does (Paso 39): production
settings, the image's CMD (scripts/start-production.sh) and PORT=10000, so
the image can be tried before a deploy.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
TEST_COMPOSE = ROOT / "docker-compose.test.yml"
RENDER_YAML = ROOT / "render.yaml"


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def web() -> dict:
    return load(COMPOSE)["services"]["web"]


def render_env() -> dict:
    (service,) = load(RENDER_YAML)["services"]
    return {var["key"]: var.get("value") for var in service["envVars"]}


def test_up_starts_only_the_database():
    services = load(COMPOSE)["services"]

    assert [name for name, s in services.items() if "profiles" not in s] == ["db"]


class TestWebService:
    def test_boots_with_the_image_cmd(self):
        """No command: the same boot as Render, scripts/start-production.sh."""
        assert "command" not in web()

    def test_listens_on_renders_port(self):
        assert web()["environment"]["PORT"] == "10000"
        assert web()["ports"] == ["8001:10000"]

    def test_uses_renders_settings(self):
        """Same non-secret values as render.yaml; only the host is local."""
        env = web()["environment"]

        for key in ("DJANGO_SETTINGS_MODULE", "EMAIL_BACKEND", "MEDBOOK_DEMO_DATA"):
            assert env[key] == render_env()[key]
        assert env["ALLOWED_HOSTS"] == "localhost,127.0.0.1"


def test_compose_files_have_no_obsolete_version():
    """Compose v2 ignores `version` and warns about it on every command."""
    for path in (COMPOSE, TEST_COMPOSE):
        assert "version" not in load(path)
