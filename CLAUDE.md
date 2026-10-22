# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

MedBook is a medical appointment booking REST API (portfolio project) built with Django + DRF (versions pinned in `requirements/base.txt`), PostgreSQL 16, Python 3.12. Default branch: `master`.

Today it is API-only, with no templates and no frontend. Sprint "Semana 5" in `SPRINT.md` (Pasos 23–29, issues #133–#139) builds the patient-facing web UI. Its decisions are recorded in two ADRs:
- `docs/adr/0002-server-rendered-web-frontend.md`: Django templates + HTMX in a new `apps/web` app, session auth reusing the service layer, Tailwind 4 via `django-tailwind-cli` (no Node), Spanish/English i18n with the JSON API kept in English, no Alpine.js.
- `docs/adr/0003-clinic-time-zone.md`: schedules are interpreted in `America/Santiago` (`TIME_ZONE`), and slots are built with `make_aware` instead of hard-coded UTC. Implemented in Paso 23. The API serialises datetimes with the Chilean offset and `__date` filters use Chilean dates. Never hard-code UTC when combining dates with schedule times.

Sources of truth: `README.md` (endpoints, RBAC matrix, setup), `docs/architecture.md` (decision log with trade-offs), `docs/adr/`, `SPRINT.md` (historical sprint plan), `docs/REMEDIATION-PLAN.md` (post-audit work). There is no `PRD.md` or `AGENT.md` in the repo.

## Environment

This project uses **pip + venv and `requirements/*.txt`**, not uv (unlike the workspace default).

```powershell
.venv\Scripts\activate
$env:DJANGO_SETTINGS_MODULE='config.settings.local'
pip install -r requirements/local.txt   # once per clone
pre-commit install                      # ruff --fix + ruff-format on commit
```

Never use `Start-Process` to launch Django on Windows — run `python manage.py runserver` in a dedicated terminal with env vars already set.

Settings modules: `config.settings.local` (dev), `config.settings.test` (pytest, set in `pytest.ini`), `config.settings.production` (Render). Config is read with `python-decouple` from `.env`; `.env.example` lists the keys.

Databases (Docker):
- Dev: `docker compose up` starts Postgres on host port **5435** plus the app on 8000 (runs `migrate` then gunicorn with local settings). `docker compose up db` for just the DB.
- Tests: `docker compose -f docker-compose.test.yml up -d` starts Postgres on host port **5436**, which is the default `DATABASE_URL` in `config/settings/test.py`. An optional `.env.test` overrides it (loaded in `test.py`, not `conftest.py`, because pytest-django imports settings first).

## Commands

```bash
# Lint (CI runs both)
ruff check . && ruff format --check .

# Tests — always against PostgreSQL, never SQLite
pytest                                   # full suite, --reuse-db, branch coverage, fails under 95%
pytest tests/unit/ --no-cov
pytest tests/integration/test_appointments_api.py::TestClass::test_name --no-cov -x
pytest --create-db                       # after changing migrations (because of --reuse-db)

# Migrations (CI fails if any are missing)
python manage.py makemigrations --check --dry-run
python manage.py makemigrations && python manage.py migrate

# OpenAPI schema validation (PYTHONIOENCODING needed on Windows)
PYTHONIOENCODING=utf-8 python manage.py spectacular --validate --fail-on-warn

# Project management commands
python manage.py generate_slots [--days=30] [--doctor-id=<uuid>]
python manage.py ensure_superuser        # idempotent, used by the Render start command
```

`pytest.ini` addopts include `--cov-fail-under=95`, so any partial run without `--no-cov` will "fail" on coverage even when every test passes. The `fail_under = 85` in `pyproject.toml` is overridden by that flag.

CI (`.github/workflows/ci.yml`): ruff lint + format → missing-migrations check → pytest on Postgres 16 → Codecov.

Deploy: the production Render service (`MedBook`, https://medbook-oiio.onrender.com, free plan, auto-deploy from `master`) was created by hand, **not from a Blueprint**, so Render ignores `render.yaml`; that file is reference only. Any change to the build or start command or to env vars must also be pasted in the Render dashboard (Settings) by the owner. Confirm it from the deploy log line `==> Running '…'`. The free plan has no pre-deploy command and no cron jobs.

## Architecture

Apps under `apps/`: `core` (shared base model, permissions, exception handler, pagination, throttling, health check), `users` (custom `AbstractBaseUser` with email login and a `role` field: admin/doctor/patient; JWT views), `doctors` (Doctor, Specialty M2M, weekly Schedule), `patients`, `appointments` (TimeSlot, Appointment, MedicalNote), `notifications` (email senders). All models use UUID primary keys.

Key flows that span multiple apps:

- **Slot generation**: creating a `Schedule` fires a `post_save` signal (`apps/doctors/signals.py`) that calls `appointments.services.generate_slots_for_schedule` (7 days ahead). The service skips slots that already exist and returns only the ones it inserted; `bulk_create(ignore_conflicts=True)` only guards concurrent runs, and its return value cannot be trusted as "created". In production the `generate_slots --days=14` command runs on every Render boot (`startCommand`, inside a subshell so a failure never blocks gunicorn), since the free plan has no cron jobs. The signal swallows errors so the Schedule save always succeeds. `TimeSlot` deliberately lives in `appointments` and is imported lazily from `doctors` to avoid a circular import — see `docs/adr/0001-timeslot-boundary.md`.
- **Booking**: `AppointmentCreateSerializer.validate()` calls `validate_appointment_booking` (slot available, no overlapping patient appointment via `Q`/range filters → 400). `create_appointment` then reserves the slot with an atomic conditional `UPDATE ... WHERE status=available`; losing the race raises `SlotConflict` (409). The doctor is always derived from `slot.schedule.doctor`.
- **State machine**: transition methods live on `Appointment` (`confirm()`, `cancel()`, `complete()`, `mark_no_show()`) and raise `InvalidTransition` on illegal moves. Service functions wrap them in `@transaction.atomic`, write an audit line to the `medbook.audit` logger, free the slot on cancel, and send emails via `transaction.on_commit` (never inline).
- **Errors**: `apps/core/exceptions.custom_exception_handler` normalises every error to `{detail, code, field_errors?}` and maps Django `ValidationError` / `InvalidTransition` to 400. Keep this shape when adding errors.
- **Routing**: everything is under `/api/v1/` (`config/urls.py`); JWT at `/api/v1/token/`, `token/refresh/`, `token/blacklist/`; medical notes are nested manually at `/api/v1/appointments/<id>/notes/`. Swagger at `/api/docs/`, `/` redirects there, `/health/` for Render. Admin path comes from `DJANGO_ADMIN_URL`.
- **Auth/security**: SimpleJWT with 15-min access, 1-day refresh, rotation + blacklist; global anon/user throttles plus `login`/`refresh`/`register` scopes; `NUM_PROXIES=1` in production.
- **Registration**: patients self-register through `apps/users/services.register_patient` (User with role=patient + Patient profile in one transaction; case-insensitive email uniqueness; Django password validators; field-keyed `ValidationError`). `POST /api/v1/users/register/` is public, skips authentication and returns the profile only, never tokens. The future web sign-up form must call the same service. Doctors and admins are still created via the admin.

## Non-negotiable rules

Layer responsibilities:

| Layer | Owns | Must not contain |
|---|---|---|
| `models.py` | Fields, relations, simple state transitions | Complex business logic |
| `serializers.py` | Input validation, output shape | Direct ORM queries, business rules, `request.user` (pass via `context`) |
| `views.py` | HTTP: auth, permissions, serialization, status codes | Direct ORM (beyond `get_queryset`), business rules |
| `services.py` | All business logic | HTTP, serializers |
| `permissions.py` | One check per class | Business logic |

- **15-line rule**: any `validate_*`, ViewSet action or model method beyond ~15 lines gets extracted to `services.py`.
- One serializer per action when logic diverges (`get_serializer_class` switching on `self.action`).
- ORM: `select_related` in every `get_queryset()` with FKs, `prefetch_related` for Doctor → specialties, `annotate()`/`Count()` for stats, `Q()` for schedule conflicts, `save(update_fields=[..., "updated_at"])` on partial saves. Filter in the ORM, never in Python loops.
- Catch specific exceptions, never bare `except Exception` (the signal handler's last-resort `logger.exception` is the documented exception).
- Never log passwords, tokens or Authorization headers.

## Testing

Strict TDD (red → green → refactor): write the failing test before the implementation.

- `tests/unit/` — models, services, permissions, commands, signals (DB allowed via `@pytest.mark.django_db`, no HTTP).
- `tests/integration/` — full HTTP stack with `APIClient`.
- All test data via `factory_boy` (`tests/factories.py`); no JSON/YAML fixtures. Shared fixtures (`api_client`, `user_patient`, `user_doctor`, `user_admin`, `doctor_profile`, …) are in `tests/conftest.py`, which also resets `mail.outbox` before each test (locmem email backend).
- Every permission class needs a positive and a negative test.
- Coverage targets: models + services 90%, views + serializers 80%, permissions 100%, management commands 70%; the global branch-coverage gate is 95%.

## Workflow

- One branch and one PR per numbered step; PRs reference their issue (`Closes #N`). Recent branches use `audit/<area>-<desc>`; sprint work used `semana{N}/paso-{N}-<desc>`. Conventional Commits (`feat|fix|refactor|docs|test|chore(scope): …`).
- Pause and show full output (and wait for confirmation) after: any `makemigrations` (show the generated file), any `migrate`, a full test run (counts + coverage), and each completed numbered step.
- On a failing command or an unexpected test failure, report the full traceback/diff and ask before changing the implementation — do not iterate silently.
- If an architecture decision is not covered by the docs or this file, ask first.
- For Django/DRF work, load the `django-drf-patterns` skill; for tests, `python-testing-patterns`. (The `.agent/skills/` paths referenced in `.atl/skill-registry.md` point to an old machine and do not exist here.)
