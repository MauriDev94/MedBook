"""Tests for apps/doctors/signals.py.

The post_save signal on Schedule must:
  - Generate TimeSlots automatically when a Schedule is CREATED
  - NOT regenerate slots when a Schedule is UPDATED
  - NOT crash the save if slot generation fails
"""

from apps.appointments.models import TimeSlot
from tests.factories import ScheduleFactory


class TestSchedulePostSaveSignal:
    """Signal: post_save on Schedule triggers slot generation."""

    def test_creating_schedule_generates_slots(self, db):
        """Creating a Schedule via signal produces TimeSlot objects."""
        schedule = ScheduleFactory()  # post_save fires with created=True
        assert TimeSlot.objects.filter(schedule=schedule).exists()

    def test_slots_belong_to_created_schedule(self, db):
        """All generated slots reference the correct schedule."""
        schedule = ScheduleFactory()
        slots = TimeSlot.objects.filter(schedule=schedule)
        assert slots.count() > 0
        for slot in slots:
            assert slot.schedule == schedule

    def test_generated_slots_are_available(self, db):
        """Signal-created slots start in AVAILABLE status."""
        schedule = ScheduleFactory()
        slots = TimeSlot.objects.filter(schedule=schedule)
        assert all(s.status == TimeSlot.Status.AVAILABLE for s in slots)

    def test_updating_schedule_does_not_regenerate_slots(self, db):
        """Saving an existing Schedule (update) does NOT create duplicate slots."""
        schedule = ScheduleFactory()
        initial_count = TimeSlot.objects.filter(schedule=schedule).count()
        assert initial_count > 0  # signal ran on create

        # Simulate an update — post_save fires with created=False
        schedule.is_active = False
        schedule.save(update_fields=["is_active", "updated_at"])

        assert TimeSlot.objects.filter(schedule=schedule).count() == initial_count

    def test_two_schedules_generate_independent_slots(self, db):
        """Each Schedule generates its own set of slots, not shared."""
        schedule_a = ScheduleFactory()
        schedule_b = ScheduleFactory()

        slots_a = TimeSlot.objects.filter(schedule=schedule_a).count()
        slots_b = TimeSlot.objects.filter(schedule=schedule_b).count()

        assert slots_a > 0
        assert slots_b > 0
        # No slots cross-contamination
        assert not TimeSlot.objects.filter(
            schedule=schedule_a, schedule__in=[schedule_b]
        ).exists()

    def test_signal_does_not_raise_on_generation_failure(self, db):
        """If generate_slots_for_schedule raises, the Schedule save still succeeds."""
        from unittest.mock import patch

        # Patch where the function lives, not where it's imported.
        # The signal uses a late import (inside the function body), so there is
        # no 'apps.doctors.signals.generate_slots_for_schedule' attribute to patch.
        with patch(
            "apps.appointments.services.generate_slots_for_schedule",
            side_effect=Exception("simulated failure"),
        ):
            # Should NOT raise — signal wraps in try/except
            schedule = ScheduleFactory()

        # The Schedule was saved successfully despite the signal error
        from apps.doctors.models import Schedule

        assert Schedule.objects.filter(pk=schedule.pk).exists()
