# ADR 0003: Doctor schedules are interpreted in America/Santiago

## Status

Accepted

## Context

`Schedule.start_time` and `Schedule.end_time` are naive `TimeField`s: a doctor
enters "09:00–17:00". `generate_slots_for_schedule`
(`apps/appointments/services.py`) combines them with `tzinfo=datetime.timezone.utc`,
and `TIME_ZONE = "UTC"`. As a result:

- A 09:00–17:00 schedule produces slots at 09:00 UTC, which is 06:00 in Chile
  in summer (CLST, UTC-3) and 05:00 in winter (CLT, UTC-4).
- "Today" (`timezone.localdate()`) is the UTC date, so after 20:00 or 21:00
  Chilean time slot generation already starts from tomorrow.
- The `date_from` / `date_to` appointment filters (`__date` lookups) compare
  UTC dates.

The upcoming web UI (ADR 0002) shows slots to patients in Chile, so the API-only
assumption of "everything is UTC" no longer holds.

## Decision

- Set `TIME_ZONE = "America/Santiago"`. With `USE_TZ = True`, Django keeps
  storing aware datetimes in UTC; `TIME_ZONE` only sets the default *current*
  time zone used for conversions, `localdate()` and `__date` lookups.
- `generate_slots_for_schedule` builds slot datetimes with
  `timezone.make_aware(datetime.combine(date, time))` in the current time zone
  instead of hard-coding UTC. `zoneinfo` handles daylight saving time. Chile
  switches at midnight, so slots within business hours never fall into a DST
  gap or fold.
- Existing data: a data migration deletes **future, available** slots that have
  no appointment. On the next boot, `generate_slots` (`render.yaml`
  `startCommand`) recreates them in local time. Reserved, blocked and past
  slots are kept as they are, as historical records.
- Tests stop forcing UTC (`tests/conftest.py`) and pin the behavior with
  dates in both summer (UTC-3) and winter (UTC-4).

## Alternatives considered

### A. A `timezone` field per doctor

Supports clinics in several countries. Rejected for now because MedBook models a
single-country clinic. It would add a migration, form fields and a per-request
time-zone activation for little gain (YAGNI).

### B. Keep `TIME_ZONE = "UTC"` and add a separate `CLINIC_TIME_ZONE`

Use the new setting only for slot generation and UI display. Rejected because
Django's `TIME_ZONE` already means "the default time zone of this installation".
Two settings would drift apart: `localdate()`, `__date` filters and admin display
would keep using UTC while slots used Chilean time.

### C. Keep UTC and ask doctors to enter UTC times

No code change, but poor UX and confusing in a demo.

## Consequences

- **API output changes format, not meaning**: DRF serialises datetimes in the
  current time zone, so `2026-10-26T12:00:00Z` becomes
  `2026-10-26T09:00:00-03:00`. It is the same instant and still ISO 8601, so
  clients that parse offsets are unaffected. Release notes must mention it.
- `date_from` / `date_to` filters now match Chilean calendar dates, which is
  what users expect.
- The admin shows local times.
- Slots booked before the migration keep their original (UTC-based) times.

## Revisit if

- MedBook needs to serve clinics in more than one time zone (see alternative A).
