"""Tests for data migrations.

A data migration's forward function is tested by calling it directly with the
historical app registry at that migration, the same models `migrate` hands it.
The live registry drifts as models change: Paso 30 renamed TimeSlot's reverse
accessor from `appointment` to `appointments`.
"""

import datetime
import importlib

import pytest
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone

from apps.appointments.models import Appointment, TimeSlot
from apps.doctors.demo import DEMO_DOCTORS
from apps.doctors.models import Doctor
from tests.factories import AppointmentFactory, DoctorFactory, TimeSlotFactory

rebuild_slots = importlib.import_module(
    "apps.appointments.migrations.0002_rebuild_future_slots_in_local_time"
)


def _in_days(days: int) -> datetime.datetime:
    return timezone.now() + datetime.timedelta(days=days)


def _run_migration() -> None:
    state = MigrationLoader(None, ignore_no_migrations=True).project_state(
        ("appointments", "0002_rebuild_future_slots_in_local_time")
    )
    rebuild_slots.delete_future_unbooked_slots(state.apps, schema_editor=None)


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


DEMO_TITLES_MIGRATION = "0006_demo_doctors_title"


def _demo_titles_migration():
    return importlib.import_module(f"apps.doctors.migrations.{DEMO_TITLES_MIGRATION}")


def _run_demo_titles_migration() -> None:
    state = MigrationLoader(None, ignore_no_migrations=True).project_state(
        ("doctors", DEMO_TITLES_MIGRATION)
    )
    _demo_titles_migration().set_demo_doctors_title(state.apps, schema_editor=None)


@pytest.mark.django_db
class TestSetDemoDoctorsTitle:
    """Paso 36: seed_demo never changes existing rows, so the three demo
    doctors that dev and production already have get "Dra." here."""

    @pytest.mark.parametrize("license_number", ["DEMO-001", "DEMO-003", "DEMO-005"])
    def test_carla_valentina_and_camila_get_dra(self, license_number):
        doctor = DoctorFactory(license_number=license_number)

        _run_demo_titles_migration()

        doctor.refresh_from_db()
        assert doctor.title == Doctor.Title.DRA

    @pytest.mark.parametrize("license_number", ["DEMO-002", "LIC-1234"])
    def test_other_doctors_keep_dr(self, license_number):
        doctor = DoctorFactory(license_number=license_number)

        _run_demo_titles_migration()

        doctor.refresh_from_db()
        assert doctor.title == Doctor.Title.DR

    def test_runs_without_demo_doctors(self):
        _run_demo_titles_migration()

        assert not Doctor.objects.exists()

    def test_matches_the_demo_data(self):
        """New databases get the title from seed_demo, old ones from here."""
        demo_dra = {
            demo.license_number
            for demo in DEMO_DOCTORS
            if demo.title == Doctor.Title.DRA
        }

        assert set(_demo_titles_migration().DRA_LICENSES) == demo_dra
