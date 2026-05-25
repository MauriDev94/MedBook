# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Django testing, pytest-django, TDD, factory_boy, mocking, coverage, DRF API testing | django-tdd | D:\Proyectos\python\clean\MedBook\.agent\skills\django-tdd\SKILL.md |
| Django REST Framework, DRF patterns, serializers, viewsets, permissions, JWT, SOLID in Django, service layer, ORM optimization, admin customization | django-drf-patterns | D:\Proyectos\python\clean\MedBook\.agent\skills\django-drf-patterns\SKILL.md |
| Python testing, pytest, fixtures, mocking, parameterization, async testing, coverage, CI | python-testing-patterns | C:\Users\mauri\.config\opencode\skills\python-testing-patterns\SKILL.md |
| Clean Architecture, Hexagonal Architecture, DDD, Screaming Architecture, feature-based layers | clean-architecture-ddd-complete | C:\Users\mauri\.config\opencode\skills\clean-architecture-ddd\SKILL.md |
| JWT, OAuth2, refresh token rotation, OTP, password reset, SSO, rate limiting, HttpOnly cookies, auth security | auth-security-patterns | C:\Users\mauri\.config\opencode\skills\auth-security-patterns\SKILL.md |
| FastAPI, API design, endpoints, schemas, mappers, DI providers | fastapi-api-patterns | C:\Users\mauri\.config\opencode\skills\fastapi-api-patterns\SKILL.md |
| Go testing, Bubbletea TUI testing, teatest | go-testing | C:\Users\mauri\.config\opencode\skills\go-testing\SKILL.md |
| Creating AI skills, agent instructions, documenting patterns for AI | skill-creator | C:\Users\mauri\.config\opencode\skills\skill-creator\SKILL.md |
| GitHub Actions, workflows, CI/CD pipelines, .github/workflows, YAML actions, triggers, secrets, runners, composite actions, parallelization | github-actions-core | C:\Users\mauri\.config\opencode\skills\github-actions-core\SKILL.md |
| Django CI/CD, GitHub Actions for Django, Django testing pipeline, pytest in CI, migrations check, PostgreSQL in CI, deploy Django to Railway/Render, ruff linting, bandit security | django-cicd | D:\Proyectos\python\clean\MedBook\.agent\skills\django-cicd\SKILL.md |
| OpenCode configuration, opencode.json, opencode.jsonc, .opencode/, agents, subagents, plugins, MCP | customize-opencode | C:\Users\mauri\.config\opencode\skills\customize-opencode\SKILL.md |
| Pull request, PR, opening a PR, preparing changes for review, branch workflow | branch-pr | C:\Users\mauri\.config\opencode\skills\branch-pr\SKILL.md |
| GitHub issue, bug report, feature request, issue creation | issue-creation | C:\Users\mauri\.config\opencode\skills\issue-creation\SKILL.md |
| judgment day, review adversarial, dual review, juzgar, code review, parallel adversarial review | judgment-day | C:\Users\mauri\.config\opencode\skills\judgment-day\SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### django-tdd
- Strict Red-Green-Refactor: write failing test (RED) first, then minimum code to pass (GREEN), then refactor (REFACTOR)
- Use `--reuse-db` and `--nomigrations` flags for fast test runs
- Always use factory_boy factories (UserFactory, etc.) — never manual object creation or JSON fixtures
- One assertion per test, descriptive test names like `test_user_cannot_delete_others_post`
- `@pytest.mark.django_db` (or `db` fixture) for database tests; `client` for Django views; `APIClient` for DRF endpoints
- Mock external services with `unittest.mock.patch` — never hit real APIs in tests
- Test edge cases: empty inputs, boundary conditions, None values
- Don't test Django/DRF internals, don't test private methods, don't make tests dependent on each other
- Coverage targets: Models 90%+, Serializers 85%+, Views 80%+, Services 90%+, Permissions 100%

### django-drf-patterns
- 15-line rule: if a `validate_*`, ViewSet action, or model method exceeds ~15 lines, extract to `services.py`
- NEVER put business logic in views — ViewSets handle HTTP concerns only (auth, permissions, serialization, response codes)
- One serializer per action when logic diverges — use `get_serializer_class()` in ViewSet
- DIP: ViewSets call service functions, not ORM directly, when logic is complex
- Custom permissions: one class = one check, extend `BasePermission` with `has_permission`/`has_object_permission`
- Use `select_related`/`prefetch_related` in all `get_queryset()` to prevent N+1
- `@action(detail=True, methods=['post'])` for state transitions; never put action logic inline in the view
- JWT via simplejwt — never store tokens in DB; use blacklist for logout
- Signals: wrap in try/except, never let a signal failure interrupt the save() call
- Context: for DRF-specific tasks, read the relevant reference file from `references/` before writing code

### python-testing-patterns
- Use pytest over unittest: simpler assertions, better fixtures, powerful parameterization
- Fixtures over setup methods: share state via dependency injection, not class hierarchy
- One assertion per test for clear failure messages and independent test cases
- Mock at the source: patch where the function is imported/used, not where it's defined
- `conftest.py` for shared fixtures: scoped fixtures (`session`, `module`, `function`) for appropriate reuse
- Test layers: unit (fast, no IO) → integration (DB, API) → e2e (full system); keep 70%+ at unit level
- Coverage: 80%+ overall, 90%+ for business logic, 100% for critical paths
- Async tests: use `pytest-asyncio` with `@pytest.mark.asyncio` marker

### clean-architecture-ddd-complete
- Feature-based layers: domain/ → application/ → infrastructure/ → presentation/ → di/
- Domain entities: no framework dependencies, plain Python with business rules only
- Repository pattern: abstract interfaces in domain/, implementations in infrastructure/
- Service layer: application services orchestrate domain objects, infrastructure handles IO
- Dependency inversion: high-level modules don't depend on low-level modules; both depend on abstractions
- Value objects: immutable, self-validating, with `__eq__` and `__hash__` when needed

### auth-security-patterns
- JWT best practices: short-lived access tokens (15min), long-lived refresh tokens (7d), rotation on refresh
- HttpOnly cookies for tokens in production, Authorization header for API clients
- Rate limiting on auth endpoints: 5 attempts per minute on login, 3 on password reset
- Password hashing: always use bcrypt/argon2, never plain text or MD5/SHA1
- OAuth2: use authorization code flow with PKCE for SPAs, never implicit grant

### github-actions-core
- NEVER use `ubuntu-latest` — pin to `ubuntu-24.04` or `ubuntu-22.04` to prevent breaking builds
- Declare minimum `permissions:` explicitly (contents: read, pull-requests: write, etc.) — never omit
- Pass `${{ inputs.x }}` through `env:` before using in `run:` steps — never interpolate directly in shell commands
- Use `needs:` for job dependencies and parallelize independent jobs
- Extract reusable steps into composite actions under `.github/actions/`
- Use `environment:` for per-environment secrets, never a single flat set
- Secrets hierarchy: repo → environment → org; use the most specific available
- Matrix strategy for version testing: `fail-fast: false` to see all failures
- For Claude Code Review: use `anthropics/claude-code-action@beta` with OAuth token

### django-cicd
- Create `.github/actions/setup-django/action.yml` composite action for reusable Django setup (checkout + Python + dependencies with pip cache)
- CI pipeline order: lint (ruff) → security (bandit + safety) → test (pytest matrix) → build (Docker)
- Use PostgreSQL service container in CI: `postgres:16` with health check `pg_isready`
- ALWAYS run `makemigrations --check --dry-run` before `migrate` to verify no missing migrations
- Then run `migrate --no-input`, then `manage.py check --deploy` — in that order
- pytest with `--cov=xml` for Codecov upload, `--tb=short`, `-q`
- Verify `SECRET_KEY`, `DATABASE_URL`, `DJANGO_SETTINGS_MODULE` are set in CI env
- Never hardcode secrets — use GitHub Secrets with `${{ secrets.NAME }}`
- CI checklist: lint, makemigrations --check, migrate, manage.py check, pytest, bandit + safety, build
- Common CI errors: SECRET_KEY missing, migrations not run, PostgreSQL not ready (use health check)

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| PRD.md | D:\Proyectos\python\clean\MedBook\PRD.md | Product Requirements Document — full project scope, architecture, stack, timeline, API spec |
| AGENT.md | D:\Proyectos\python\clean\MedBook\AGENT.md | Agent instructions — currently empty |
