# ADR 0005: Doctor panel, immutable schedules and demo doctor access

## Status

Accepted (planning of sprint "Semana 6", 2026-10-28)

## Context

ADR 0002 scoped the web UI for doctors: manage weekly schedules, confirm,
complete or mark appointments as no-show, and write medical notes. Sprint
"Semana 5" built the patient side only; a doctor who logs in today lands on a
notice at `/panel/`. The appointment state machine and its services already
exist, so the panel reuses them like the patient pages do.

Planning the panel surfaced three gaps in the schedule rules the API has today:

- **A deactivated schedule keeps its free future slots bookable.** `DELETE
  /api/v1/schedules/<id>/` sets `is_active=False`, but the slots it already
  generated stay `available`, and the slot listings do not look at the
  schedule.
- **Editing a schedule's hours leaves its slots behind.** A PATCH changes the
  hours but not the slots: the old ones stay bookable and the new hours get no
  slots until the next `generate_slots` run.
- **Overlapping schedules are accepted.** The only guard is the unique
  constraint on (`doctor`, `day_of_week`, `start_time`), so 09:00–13:00 and
  10:00–12:00 on the same day both generate slots and the doctor can be
  double-booked.

The public demo has one more problem: the demo doctors have no usable
password (Paso 33), so a visitor cannot see the doctor side at all.

## Decision

### Panel

- `/panel/` becomes the doctor's agenda, behind a new `DoctorRequiredMixin`:
  tabs for today, upcoming (after today) and past (before today), grouped by
  day, with Chilean dates (ADR 0003). It is built on
  `appointments_visible_to`, like everything else that lists appointments.
- Each appointment has a doctor page with the state transitions (confirm,
  cancel, complete, no-show) through the existing services, and its medical
  notes. Notes stay immutable. The notes API moves its queries into services
  that the web shares.
- A schedules page lists, adds and deactivates the doctor's schedules.
- The panel shows a patient's name and the reason for the visit, never the
  patient's email.
- Admins land on the Django admin (`landing_url_for`), as ADR 0002 planned;
  the notice page goes away.

### Schedules are created or deactivated, never edited

- Changing hours means deactivating the schedule and creating another one. The
  API follows the same rule: `ScheduleViewSet` stops accepting PATCH (405).
- Deactivating a schedule (`doctors.services.deactivate_schedule`) blocks its
  free future slots (`TimeSlot.Status.BLOCKED`) in one UPDATE and leaves the
  reserved ones alone, so booked appointments go ahead. Cancelling an
  appointment on a slot of an inactive schedule blocks the slot instead of
  freeing it.
- Slot generation skips the times at which the doctor already has a slot that
  is not blocked, from any schedule. Without that, replacing 09:00–13:00 (with
  a booking at 10:00) by 09:00–12:00 would open a second 10:00 slot.
- A new schedule must not overlap another active schedule of the same doctor
  on the same day (`doctors.services.validate_schedule`, a `Q` range filter).
  The unique constraint becomes partial (`is_active = true`), so a deactivated
  schedule does not block a new one that starts at the same time.
- A data migration blocks the free future slots of schedules that are already
  inactive.
- Creating a schedule generates the same 28 days the web lets patients browse
  (`BOOKING_WEEKS_AHEAD`), not 7.

### Completing needs a started appointment

`complete()` and `mark_no_show()` require that the slot has started, the
mirror of Paso 35 (nobody cancels a started appointment). The API answers 400
before that time and the web hides those actions.

### Demo doctor access

- When `MEDBOOK_DEMO_DATA` is true (only production, the portfolio demo), the
  login page shows a visible box with one button per demo doctor: "Log in as
  Dra. Carla Soto". It is not hidden on purpose: the point is that a visitor
  finds it, and hiding it would not protect anything.
- Each button is a POST form (CSRF) to `/demo/doctors/<id>/login/`, throttled
  with the login's scope. The view answers 404 when the flag is off or when
  the doctor is not one of `apps/doctors/demo.py` (matched by license number),
  so it never opens a session for a real doctor, an admin or a patient. It
  logs in with `ModelBackend`, writes an audit line and redirects to the panel.
- No password is created, stored or published. The session reaches the web
  only: the API authenticates with JWT, and a token needs a password. Doctors
  have no `is_staff`, so the Django admin stays closed.
- With the flag on, the sign-up form and the booking dialog warn that the demo
  is public: anyone can log in as a demo doctor and see the appointments booked
  with them, so no real data should be used.

## Alternatives considered

### A. A temporary doctor per visit

Each click creates a doctor of its own, so visitors never share state. It
starts with no appointments, so fake patients and appointments would have to
be generated too, and everything cleaned up on boot (the free plan has no
cron jobs). Much more code for a demo.

### B. No public doctor access

Only a doctor whose password an admin sets can log in, and the README shows
the panel with screenshots. Simplest, but a visitor cannot try it.

### C. A shared password published in the README

A credential in the docs, which the repo's rules forbid (GitGuardian scans
every PR), and it would also open the API to anyone.

### D. Edit schedules in place, regenerating slots

Keeps one row per schedule, but every edit has to block the free slots that
fall outside the new hours, create the new ones and leave bookings alone: more
logic and more edge cases than deactivating and creating.

## Consequences

- Demo visitors share the six demo doctors: what one does (confirm, cancel,
  write a note) the next one sees, and a patient's appointment with a demo
  doctor can be confirmed or cancelled by any visitor. Emails only reach
  Render's logs, so nobody outside receives them. The warning on sign-up and
  booking is the mitigation for the patient data.
- Two API changes: `PATCH /api/v1/schedules/<id>/` answers 405, and
  `complete` / `no-show` answer 400 before the appointment starts. The README
  and the OpenAPI schema document both.
- Neither the web nor the API reactivates a schedule: the doctor creates a new
  one. The Django admin can still edit a schedule's hours or `is_active` and
  does not adjust its slots; that stays a staff tool, with its blocked slots
  staying blocked.
