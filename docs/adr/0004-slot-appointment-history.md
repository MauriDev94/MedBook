# ADR 0004: A time slot keeps its appointment history, with one active appointment at most

## Status

Accepted

## Context

`Appointment.slot` was a `OneToOneField`, so PostgreSQL kept a UNIQUE
constraint on `appointments_appointment.slot_id`: a slot could appear in one
appointment row ever, whatever that appointment's status. Cancelling keeps the
appointment as `cancelled` (history, audit log, notification) and sets the slot
back to `available`, so the slot looked free but could not be booked again
(issue #142):

- The API answered 400 "appointment with this slot already exists", because
  DRF's `ModelSerializer` adds a `UniqueValidator` for a one-to-one field.
- Calling `create_appointment` directly, as the web will in Paso 27, raised an
  `IntegrityError` on `appointments_appointment_slot_id_key`: a 500.

Booking had two more gaps. `validate_appointment_booking` accepted slots that
had already started, and `get_available_slots` (the API's `available-slots`)
filtered by date only, so it listed today's slots that had already started.

## Decision

- `Appointment.slot` becomes a `ForeignKey` (`on_delete=PROTECT`,
  `related_name="appointments"`): a slot keeps every appointment ever booked on
  it.
- A conditional `UniqueConstraint` named `one_active_appointment_per_slot` on
  `slot`, where `status IN ('pending', 'confirmed')`. PostgreSQL builds it as a
  partial unique index. Cancelled, completed and no-show appointments do not
  count.
- The atomic `UPDATE ... WHERE status='available'` stays as the first guard
  against double booking. The index is the last guard, for states the slot
  status does not reflect (for example, a slot set back to available in the
  admin while an appointment on it is still active). `create_appointment`
  catches the `IntegrityError`, checks the constraint name PostgreSQL reports
  (`diag.constraint_name`) and raises `SlotConflict` (409). The exception
  leaves the atomic block, so the slot UPDATE rolls back. Any other integrity
  error propagates.
- `validate_appointment_booking` rejects a slot that has already started (400,
  "This time slot has already started."), and `get_available_slots` filters
  `start_datetime > now`, like the web's `get_available_slots_week`.
- Migration `0003_alter_appointment_slot_and_more` drops the UNIQUE
  constraint, adds a plain index on `slot_id` and creates the partial unique
  index. Existing data already satisfies it, since every slot had one
  appointment at most.

## Alternatives considered

### A. Delete the cancelled appointment

Frees the one-to-one slot, but loses who booked and cancelled what and when,
deletes any medical note attached to it (`CASCADE`) and leaves the audit log
pointing at a missing row.

### B. Set `slot` to NULL on cancel

Keeps the appointment but loses the time it was for, which lives on the slot.

### C. Create a new slot for the same time

Clashes with `unique_slot_per_schedule_start` (`schedule`, `start_datetime`),
and the slot listings would show duplicates.

### D. Reuse the cancelled appointment row for the new booking

Overwrites the history in place.

## Consequences

- The reverse accessor changes from `slot.appointment` to `slot.appointments`.
  No application code used it. Data migration 0002 still filters on
  `appointment__isnull`, which is right: migrations run on historical models.
  Its tests now call it with the historical app registry too
  (`tests/unit/test_migrations.py`).
- DRF no longer adds a validator for `slot`. The service and the index cover
  it: 400 from validation, 409 from a conflict.
- Reversing the migration recreates the UNIQUE constraint, which fails as soon
  as any slot holds more than one appointment. Rolling back after real
  rebookings needs a data fix first.
- The API's `available-slots` no longer lists slots that already started today.

## Revisit if

- A slot ever needs more than one active appointment (group sessions): the
  index would have to become a capacity check.
