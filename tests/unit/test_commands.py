"""Tests for apps/appointments/management/commands/generate_slots.py.

Coverage target: ≥ 70% in the command.

Tests use call_command() from django.core.management — the standard way
to invoke management commands in tests without spawning a subprocess.

Key pattern: ScheduleFactory triggers the post_save signal which already
generates slots. Tests must delete those signal-created slots before
calling the command, to cleanly measure what the command itself produces.
"""

from django.core.management import call_command

from apps.appointments.models import TimeSlot
from tests.factories import ScheduleFactory


class TestGenerateSlotsCommand:
    """Management command: generate_slots."""

    def test_command_creates_slots_for_active_schedules(self, db):
        """Running the command generates slots for all active schedules."""
        schedule = ScheduleFactory()
        # Clear signal-created slots to isolate the command's output
        TimeSlot.objects.filter(schedule=schedule).delete()
        assert TimeSlot.objects.filter(schedule=schedule).count() == 0

        call_command("generate_slots", days=14)

        assert TimeSlot.objects.filter(schedule=schedule).count() > 0

    def test_command_is_idempotent(self, db):
        """Running the command twice produces the same slot count (no duplicates)."""
        schedule = ScheduleFactory()
        TimeSlot.objects.filter(schedule=schedule).delete()

        call_command("generate_slots", days=7)
        count_after_first = TimeSlot.objects.filter(schedule=schedule).count()

        call_command("generate_slots", days=7)
        count_after_second = TimeSlot.objects.filter(schedule=schedule).count()

        assert count_after_first == count_after_second
        assert count_after_first > 0

    def test_command_with_doctor_id_filters_correctly(self, db):
        """--doctor-id generates slots only for that doctor's schedules."""
        target_schedule = ScheduleFactory()
        other_schedule = ScheduleFactory()

        # Clear all signal-created slots
        TimeSlot.objects.filter(schedule=target_schedule).delete()
        TimeSlot.objects.filter(schedule=other_schedule).delete()

        call_command(
            "generate_slots",
            days=14,
            doctor_id=str(target_schedule.doctor.id),
        )

        assert TimeSlot.objects.filter(schedule=target_schedule).count() > 0
        assert TimeSlot.objects.filter(schedule=other_schedule).count() == 0

    def test_command_skips_inactive_schedules(self, db):
        """Inactive schedules are not processed."""
        schedule = ScheduleFactory(is_active=False)
        TimeSlot.objects.filter(schedule=schedule).delete()

        call_command("generate_slots", days=14)

        assert TimeSlot.objects.filter(schedule=schedule).count() == 0

    def test_command_with_zero_days_generates_nothing(self, db):
        """--days=0 produces no new slots."""
        schedule = ScheduleFactory()
        TimeSlot.objects.filter(schedule=schedule).delete()

        call_command("generate_slots", days=0)

        assert TimeSlot.objects.filter(schedule=schedule).count() == 0

    def test_command_output_includes_success_message(self, db, capsys):
        """Command writes a success summary to stdout."""
        ScheduleFactory()
        call_command("generate_slots", days=7)
        captured = capsys.readouterr()
        assert "Done" in captured.out or "slot" in captured.out.lower()

    def test_command_reports_created_slot_count(self, db, capsys):
        """The summary reports exactly how many slots were inserted."""
        schedule = ScheduleFactory()
        TimeSlot.objects.filter(schedule=schedule).delete()

        call_command("generate_slots", days=7)

        created = TimeSlot.objects.filter(schedule=schedule).count()
        assert created > 0
        assert (
            f"Done. {created} new slots generated across 1 schedule(s)."
            in capsys.readouterr().out
        )

    def test_command_rerun_reports_zero_new_slots(self, db, capsys):
        """On Render the command runs on every boot; reruns must report 0."""
        ScheduleFactory()  # post_save signal already created 7 days of slots

        call_command("generate_slots", days=7)

        assert (
            "Done. 0 new slots generated across 1 schedule(s)."
            in capsys.readouterr().out
        )

    def test_command_queries_scale_with_schedules_not_slots(
        self, db, django_assert_max_num_queries
    ):
        """No N+1: one query for the schedules, at most two per schedule
        (existing-slot lookup + one bulk INSERT), regardless of slot count."""
        schedules = ScheduleFactory.create_batch(3)
        TimeSlot.objects.all().delete()

        with django_assert_max_num_queries(1 + 2 * len(schedules)):
            call_command("generate_slots", days=14)
