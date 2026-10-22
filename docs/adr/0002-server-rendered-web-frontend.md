# ADR 0002: Server-rendered web frontend with Django templates + HTMX

## Status

Accepted

## Context

MedBook is API-only today: a DRF API under `/api/v1/`, JWT auth, Swagger at
`/api/docs/`, and the Django admin for staff. To turn it into a full-stack
portfolio piece, patients and doctors need a real UI:

- **Patients**: sign up, browse doctors by specialty, see available slots,
  book, list and cancel their appointments.
- **Doctors**: manage weekly schedules, confirm / complete / mark no-show,
  write medical notes.
- **Admins** keep using the customised Django admin; no new UI is needed.

The project's goal is to demonstrate depth in Django specifically. The domain
logic already lives in `services.py` functions that know nothing about HTTP or
serializers, so any presentation layer can call them directly.

## Decision

Build the UI **inside the same Django project** as server-rendered templates,
using **HTMX** for partial page updates (slot pickers, state-transition
buttons, filters) instead of a JavaScript SPA.

- A new `apps/web` app owns the templates, form classes, views and URLs of the
  UI. It has no models and no business logic.
- Web views follow the same layer rules as the API: they validate input with
  Django `Form`s (the template-side equivalent of serializers), call the
  existing service functions, and never query the ORM directly.
- The web UI uses **Django session authentication** (`login()` / `logout()`,
  CSRF protection) with the same `User` model and `role` field. The JWT API
  stays unchanged and keeps serving API clients.
- Role checks that the API expresses as DRF permission classes get web
  equivalents (view mixins or decorators). Both should share the same plain
  role predicates so the two RBAC paths cannot drift.
- HTMX is served as a pinned, vendored static file (no runtime CDN
  dependency) through the existing WhiteNoise setup.
- Web views are tested with pytest-django's `client` under `tests/integration/`,
  including requests that carry the `HX-Request` header.

## Alternatives considered

### A. Separate SPA (React + Vite) consuming the API

The industry-standard split, and the owner already uses it in another project
(Monolith frontend). Rejected here because it showcases React more than Django,
needs a second repo and deploy, and forces a token-storage decision (an HttpOnly
refresh cookie or JWT in browser storage) that a session-based UI avoids.

### B. Hybrid: React rendered by Django (Inertia.js / django-vite)

One deploy and React components with Django routing. Rejected because it adds a
JS build chain plus a less common integration layer, which means less
documentation and fewer examples, for little gain over HTMX at this scope.

## Consequences

- Still a single Render web service. No CORS or token storage concerns for the
  UI.
- A public patient registration flow is required first. It is implemented as a
  service plus an API endpoint (Paso 21), and the web sign-up view will reuse
  the same service.
- Slots must be generated continuously, not only when a schedule is created,
  otherwise the booking UI shows an empty calendar (Paso 22).
- `config/urls.py` currently redirects `/` to `/api/docs/`. The web UI will take
  over `/`, and Swagger stays at `/api/docs/`.
- Two presentation layers (DRF and templates) share one service layer. Any
  business rule added in a view instead of a service would have to be
  duplicated, which the existing layer rules already forbid.

## Open questions — resolved when planning the frontend sprint (2026-10-22)

- **CSS**: Tailwind CSS 4 through `django-tailwind-cli`, which downloads the
  standalone Tailwind binary, so no Node or npm is needed. The CSS is compiled at
  build time (Render `buildCommand`, `Dockerfile` and CI) before
  `collectstatic`. The generated file is not committed.
- **Language**: a bilingual UI with Django i18n — Spanish by default, English
  available. `LocaleMiddleware` picks the language from a cookie (a switcher
  posting to `set_language`), then from `Accept-Language`. URLs carry no language
  prefix. `.po` and compiled `.mo` files are committed, so Render needs no
  gettext; CI checks they are up to date. The JSON API stays in English whatever
  `Accept-Language` says, to keep its contract stable.
- **Time zone**: schedules are interpreted in `America/Santiago` — see
  [ADR 0003](./0003-clinic-time-zone.md).
- **Alpine.js**: not adopted. HTMX covers the planned interactions, and small
  vanilla JS is added only if a case needs it. HTMX helpers come from
  `django-htmx` (`request.htmx`, HX response classes).

## Revisit if

- The UI needs rich client-side state (drag-and-drop calendars, offline
  support) that HTMX handles poorly.
- A mobile app or a third-party client becomes a first-class consumer, at which
  point a dedicated SPA on top of the existing API becomes more attractive.
