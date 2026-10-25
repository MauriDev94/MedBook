"""Tests for the demo data: apps.doctors.demo, seed_demo_doctors() and seed_demo.

Production boots with MEDBOOK_DEMO_DATA=true (render.yaml), so seed_demo
runs on every start: it must create the demo doctors once, never change
them afterwards and never fail on doctors created by hand.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils.text import slugify

from apps.appointments.models import TimeSlot
from apps.doctors.demo import DEMO_DOCTORS
from apps.doctors.models import SEEDED_SPECIALTY_NAMES, Doctor, Schedule
from apps.doctors.services import seed_demo_doctors
from apps.users.models import Role, User
from tests.factories import DoctorFactory, SpecialtyFactory, UserFactory

DEMO_EMAILS = {demo.email for demo in DEMO_DOCTORS}


@pytest.fixture
def specialties(db):
    """The specialties the demo doctors use.

    0003_data_specialties seeds them, but a TransactionTestCase elsewhere in
    the suite can flush them (--reuse-db), so each test creates its own.
    """
    slugs = {slug for demo in DEMO_DOCTORS for slug in demo.specialty_slugs}
    return [SpecialtyFactory(slug=slug, name=slug.title()) for slug in slugs]


class TestDemoDoctors:
    """The demo data itself (no database)."""

    def test_every_seeded_specialty_has_a_demo_doctor(self):
        seeded = {slugify(name) for name in SEEDED_SPECIALTY_NAMES}

        covered = {slug for demo in DEMO_DOCTORS for slug in demo.specialty_slugs}

        assert covered == seeded

    def test_emails_use_the_reserved_example_domain(self):
        # RFC 2606: medbook.example can never belong to anyone
        assert all(email.endswith("@medbook.example") for email in DEMO_EMAILS)

    def test_emails_and_licenses_are_unique(self):
        licenses = {demo.license_number for demo in DEMO_DOCTORS}

        assert len(DEMO_EMAILS) == len(licenses) == len(DEMO_DOCTORS)

    def test_every_doctor_has_weekday_hours(self):
        for demo in DEMO_DOCTORS:
            assert demo.hours
            for day, start, end in demo.hours:
                assert Schedule.DayOfWeek.MONDAY <= day <= Schedule.DayOfWeek.FRIDAY
                assert start < end


class TestSeedDemoDoctors:
    """seed_demo_doctors(): creates what is missing, never changes what exists."""

    def test_creates_every_demo_doctor(self, specialties):
        created = seed_demo_doctors()

        assert {doctor.user.email for doctor in created} == DEMO_EMAILS
        assert Doctor.objects.count() == len(DEMO_DOCTORS)

    def test_doctors_get_their_profile_specialties_and_hours(self, specialties):
        seed_demo_doctors()

        for demo in DEMO_DOCTORS:
            doctor = Doctor.objects.get(user__email=demo.email)
            assert doctor.user.full_name == f"{demo.first_name} {demo.last_name}"
            assert doctor.license_number == demo.license_number
            assert doctor.bio == demo.bio
            assert doctor.consultation_duration == demo.consultation_duration
            assert set(doctor.specialties.values_list("slug", flat=True)) == set(
                demo.specialty_slugs
            )
            assert set(
                doctor.schedules.values_list("day_of_week", "start_time", "end_time")
            ) == set(demo.hours)

    def test_demo_doctors_cannot_log_in(self, specialties):
        seed_demo_doctors()

        users = User.objects.filter(email__in=DEMO_EMAILS)
        assert users.count() == len(DEMO_DOCTORS)
        for user in users:
            assert user.role == Role.DOCTOR
            assert user.is_active
            assert not user.has_usable_password()

    def test_new_schedules_come_with_slots(self, specialties):
        seed_demo_doctors()

        # The Schedule signal generates the first week; generate_slots the rest
        for schedule in Schedule.objects.filter(doctor__user__email__in=DEMO_EMAILS):
            assert TimeSlot.objects.filter(schedule=schedule).exists()

    def test_running_twice_creates_nothing_new(self, specialties):
        seed_demo_doctors()
        counts = (
            User.objects.count(),
            Doctor.objects.count(),
            Schedule.objects.count(),
        )

        created = seed_demo_doctors()

        assert created == []
        assert (
            User.objects.count(),
            Doctor.objects.count(),
            Schedule.objects.count(),
        ) == counts

    def test_leaves_an_existing_demo_doctor_as_it_is(self, specialties):
        seed_demo_doctors()
        demo = DEMO_DOCTORS[0]
        doctor = Doctor.objects.get(user__email=demo.email)
        doctor.bio = "Edited in the admin."
        doctor.save(update_fields=["bio", "updated_at"])
        doctor.schedules.first().delete()

        seed_demo_doctors()

        doctor.refresh_from_db()
        assert doctor.bio == "Edited in the admin."
        assert doctor.schedules.count() == len(demo.hours) - 1

    def test_skips_a_demo_doctor_whose_email_is_taken_in_any_case(self, specialties):
        demo = DEMO_DOCTORS[0]
        UserFactory(email=demo.email.upper(), role=Role.PATIENT)

        created = seed_demo_doctors()

        assert demo.email not in {doctor.user.email for doctor in created}
        assert len(created) == len(DEMO_DOCTORS) - 1
        assert not Doctor.objects.filter(license_number=demo.license_number).exists()

    def test_skips_a_demo_doctor_whose_license_is_taken(self, specialties):
        demo = DEMO_DOCTORS[0]
        DoctorFactory(license_number=demo.license_number)

        created = seed_demo_doctors()

        assert len(created) == len(DEMO_DOCTORS) - 1
        assert not User.objects.filter(email=demo.email).exists()


class TestSeedDemoCommand:
    """Management command: seed_demo, gated by MEDBOOK_DEMO_DATA."""

    def call(self):
        out = StringIO()
        call_command("seed_demo", stdout=out)
        return out.getvalue()

    def test_does_nothing_without_demo_data(self, specialties, settings):
        settings.DEMO_DATA = False

        output = self.call()

        assert not Doctor.objects.exists()
        assert "MEDBOOK_DEMO_DATA is not true" in output

    def test_creates_the_demo_doctors_with_demo_data(self, specialties, settings):
        settings.DEMO_DATA = True

        output = self.call()

        assert Doctor.objects.count() == len(DEMO_DOCTORS)
        assert f"Done. {len(DEMO_DOCTORS)} demo doctor(s) created." in output
        assert DEMO_DOCTORS[0].email in output

    def test_second_run_creates_none(self, specialties, settings):
        settings.DEMO_DATA = True
        self.call()

        output = self.call()

        assert Doctor.objects.count() == len(DEMO_DOCTORS)
        assert "Done. 0 demo doctor(s) created." in output
