"""Tests for data migrations.

A data migration's forward function is tested by calling it directly with the
live app registry, which matches the current models.
"""

import datetime
import importlib

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

from apps.appointments.models import Appointment, TimeSlot
from tests.factories import AppointmentFactory, TimeSlotFactory

rebuild_slots = importlib.import_module(
    "apps.appointments.migrations.0002_rebuild_future_slots_in_local_time"
)


def _in_days(days: int) -> datetime.datetime:
    return timezone.now() + datetime.timedelta(days=days)


def _run_migration() -> None:
    rebuild_slots.delete_future_unbooked_slots(django_apps, schema_editor=None)


@pytest.mark.django_db
class TestDeleteFutureUnbookedSlots:
    """ADR 0003: future free slots were built in UTC, so they are dropped and
    the next `generate_slots` run recreates them in Chilean time. Anything
    that is history or is held by an appointment stays untouched."""

    def test_deletes_future_available_slot_without_appointment(self):
        slot = TimeSlotFactory(start_datetime=_in_days(3))

        _run_migration()

        assert not TimeSlot.objects.filter(pk=slot.pk).exists()

    def test_keeps_past_available_slot(self):
        slot = TimeSlotFactory(start_datetime=_in_days(-3))

        _run_migration()

        assert TimeSlot.objects.filter(pk=slot.pk).exists()

    def test_keeps_future_reserved_slot(self):
        slot = TimeSlotFactory(
            start_datetime=_in_days(3), status=TimeSlot.Status.RESERVED
        )
        AppointmentFactory(slot=slot)

        _run_migration()

        assert TimeSlot.objects.filter(pk=slot.pk).exists()

    def test_keeps_future_blocked_slot(self):
        slot = TimeSlotFactory(
            start_datetime=_in_days(3), status=TimeSlot.Status.BLOCKED
        )

        _run_migration()

        assert TimeSlot.objects.filter(pk=slot.pk).exists()

    def test_keeps_available_slot_still_linked_to_cancelled_appointment(self):
        """Appointment.slot is PROTECT: deleting it would raise and abort."""
        slot = TimeSlotFactory(start_datetime=_in_days(3))
        AppointmentFactory(slot=slot, status=Appointment.Status.CANCELLED)

        _run_migration()

        assert TimeSlot.objects.filter(pk=slot.pk).exists()
