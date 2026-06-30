# ADR 0001: TimeSlot lives in `appointments`, not in `doctors`

## Status

Accepted

## Context

`TimeSlot` (`apps/appointments/models.py`) is the concrete, bookable unit of
time a patient reserves. `Schedule` (`apps/doctors/models.py`) is the
recurring weekly availability template a doctor configures (day of week,
start/end time). One `Schedule` generates many `TimeSlot` rows.

The lifecycle coupling is tight and one-directional:

- A `post_save` signal on `Schedule` (`apps/doctors/signals.py:18-49`,
  `generate_initial_slots`) creates the initial batch of `TimeSlot` rows
  whenever a new `Schedule` is created.
- `apps/doctors/services.py` (`get_available_slots`) queries `TimeSlot`
  directly — `from apps.appointments.models import TimeSlot` — to answer
  "what slots does this doctor have open in the next N days?", a query that
  is conceptually about doctor availability.
- `apps/appointments/management/commands/generate_slots.py` (the periodic
  regeneration command) also imports `Schedule` from `doctors` and
  `generate_slots_for_schedule` from `appointments.services` to do bulk
  generation across all active schedules.

So today: `TimeSlot` lives in `appointments`, but a meaningful share of the
code that *creates* and *reads* it lives in `doctors`. This is the situation
this ADR documents — on purpose, not by accident.

The signal in `apps/doctors/signals.py:35` does a **local (lazy) import**:

```python
# Late import to avoid circular dependency:
# doctors.signals → appointments.services → appointments.models
from apps.appointments.services import generate_slots_for_schedule
```

If this import were hoisted to module level, `apps/doctors/signals.py` would
import `apps.appointments.services`, which imports
`apps.appointments.models` (for `TimeSlot`, which itself has a
`ForeignKey("doctors.Schedule", ...)`). `doctors` is loaded before
`appointments` in `INSTALLED_APPS` app-loading order, and `doctors/signals.py`
is wired up in `DoctorsConfig.ready()` — at that point in Django's app
registry startup, importing `appointments.services` eagerly risks importing
`appointments.models` before the `doctors` app's own models have finished
registering, producing a circular/partial-import failure. The lazy import
defers the `appointments` import until the signal actually *fires* (i.e.
until after both apps are fully loaded), which breaks the cycle without
restructuring either app.

## Decision

We keep `TimeSlot` in `apps/appointments/`, and we keep the lazy import in
`apps/doctors/signals.py:35` as the intentional mechanism that lets
`doctors` trigger slot generation without creating a hard circular import
with `appointments`.

Rationale for keeping `TimeSlot` in `appointments` rather than moving it to
`doctors`:

- A `TimeSlot` only becomes meaningful to the rest of the system once it can
  be reserved by an `Appointment` (`apps/appointments/models.py`,
  `Appointment.slot` is a `OneToOneField` to `TimeSlot`). Its primary
  consumer — the booking flow — lives in `appointments`.
- `TimeSlot.status` (`available` / `reserved` / `blocked`) is driven by
  appointment lifecycle events (create, cancel, no-show), not by schedule
  edits. Conceptually it's closer to "bookable inventory" than to "doctor
  configuration."
- `doctors.Schedule` only needs to *trigger* slot generation (fire-and-forget
  side effect via signal) and *query* slots for availability — it does not
  need to own `TimeSlot`'s write model or its state machine.

## Alternatives considered

### A. Move `TimeSlot` into `apps/doctors/`

Would make `Schedule` and `TimeSlot` co-located, removing the need for the
lazy import in the signal. Rejected because it pulls booking-state logic
(`status` transitions tied to `Appointment`) into an app that should stay
focused on doctor profile/availability configuration, and it would just
invert the circular-import problem: `appointments.models.Appointment` (which
has `slot = OneToOneField(TimeSlot)`) would then depend on `doctors`, while
`doctors` already depends on `appointments` for notifications and other
cross-app calls elsewhere in the codebase. Net complexity is the same or
worse, just moved.

### B. Extract a new bounded context `scheduling` (owns `Schedule` + `TimeSlot`)

Would give scheduling its own app, with `doctors` and `appointments` both
depending on it for availability data. This is the "textbook DDD" answer and
was seriously considered. Rejected for now because:

- The current domain is small (3 core apps: `doctors`, `appointments`,
  `notifications`, plus `users`/`core`). A 4th app whose only reason to
  exist is to host two models and break one import cycle is over-engineering
  relative to the actual complexity being managed.
- It does not remove a real conceptual coupling — `scheduling` would still
  need to know about `Doctor` (FK target) and `Appointment` (slot consumer),
  so the cross-app dependency edges don't disappear, they just get
  relabeled.
- No second consumer of `Schedule`/`TimeSlot` exists today that would
  justify a shared, independently-versioned context. YAGNI applies.

This is not a permanent rejection — see "Revisit if" below.

### C. Hoist the import in `doctors/signals.py` to module level and restructure app-loading order

Rejected because it requires reordering `INSTALLED_APPS` and/or restructuring
`AppConfig.ready()` hooks repo-wide to guarantee load order, which is a
fragile, implicit contract that's easy to silently break in a future change.
The lazy import is a well-understood, localized, one-line fix to a
well-understood problem (circular import at app-registry startup); it is
the standard Django idiom for this exact situation.

## Consequences

**Accepted trade-offs:**

- `apps/doctors/services.py` and `apps/doctors/signals.py` reach across app
  boundaries into `apps/appointments/models.py` and
  `apps/appointments/services.py`. This is a known, deliberate coupling, not
  an oversight.
- The lazy import in `apps/doctors/signals.py:35` must stay a local import.
  If a future refactor hoists it to the top of the file "for cleanliness,"
  it will reintroduce the circular import. This ADR is the documentation
  that should stop that change in code review.
- Anyone reading `apps/doctors/` in isolation will see `TimeSlot` used but
  not defined there — they need to know to look in `apps/appointments/`.

**Revisit if:**

- A third app needs to read/write `Schedule` or `TimeSlot` independently of
  both `doctors` and `appointments` (e.g. a future `billing` or `analytics`
  app), at which point shared ownership in a dedicated `scheduling` app
  starts paying for itself.
- The slot-generation logic grows beyond "generate N days of slots from a
  weekly template" (e.g. holiday calendars, per-slot doctor overrides,
  multi-location scheduling) to the point where it deserves its own
  service layer and tests independent of both `doctors` and `appointments`.
