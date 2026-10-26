"""Smoke tests for Django Admin customizations.

Verifies admin pages load correctly and bulk actions work.
Not an exhaustive UI test — just confirms nothing is broken.
"""

import pytest
from django.urls import reverse

from apps.patients.models import Patient
from apps.users.models import Role, User
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    UserFactory,
    random_password,
)


@pytest.fixture
def superuser(db):
    return UserFactory(
        email="superadmin@medbook.com",
        role="admin",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def admin_client(client, superuser):
    client.force_login(superuser)
    return client


@pytest.mark.django_db
class TestAppointmentAdmin:
    def test_changelist_loads(self, admin_client):
        AppointmentFactory()
        response = admin_client.get(
            reverse("admin:appointments_appointment_changelist")
        )
        assert response.status_code == 200

    def test_detail_page_loads(self, admin_client):
        appointment = AppointmentFactory()
        response = admin_client.get(
            reverse("admin:appointments_appointment_change", args=[appointment.pk])
        )
        assert response.status_code == 200

    def test_mark_as_no_show_bulk_action(self, admin_client):
        confirmed = AppointmentFactory(status="confirmed")
        pending = AppointmentFactory(status="pending")

        admin_client.post(
            reverse("admin:appointments_appointment_changelist"),
            {
                "action": "mark_as_no_show",
                "_selected_action": [str(confirmed.pk), str(pending.pk)],
            },
        )

        confirmed.refresh_from_db()
        pending.refresh_from_db()
        assert confirmed.status == "no_show"
        assert pending.status == "pending"  # unchanged — only confirmed are affected


@pytest.mark.django_db
class TestDoctorAdmin:
    def test_changelist_loads(self, admin_client):
        DoctorFactory()
        response = admin_client.get(reverse("admin:doctors_doctor_changelist"))
        assert response.status_code == 200

    def test_detail_page_loads_with_schedule_inline(self, admin_client):
        doctor = DoctorFactory()
        response = admin_client.get(
            reverse("admin:doctors_doctor_change", args=[doctor.pk])
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestUserAdminPatientProfile:
    """Booking needs the Patient profile, which sign-up creates; the admin too."""

    def add_user(self, admin_client, role):
        password = random_password()
        return admin_client.post(
            reverse("admin:users_user_add"),
            {
                "email": "nuevo@medbook.com",
                "password1": password,
                "password2": password,
                "role": role,
            },
        )

    def change_role(self, admin_client, user, role):
        return admin_client.post(
            reverse("admin:users_user_change", args=[user.pk]),
            {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": role,
                "is_active": "on",
            },
        )

    def test_adding_a_patient_creates_the_profile(self, admin_client):
        response = self.add_user(admin_client, Role.PATIENT)

        assert response.status_code == 302
        user = User.objects.get(email="nuevo@medbook.com")
        assert Patient.objects.filter(user=user).exists()

    def test_adding_a_doctor_creates_no_patient_profile(self, admin_client):
        response = self.add_user(admin_client, Role.DOCTOR)

        assert response.status_code == 302
        assert not Patient.objects.filter(user__email="nuevo@medbook.com").exists()

    def test_switching_a_user_to_patient_creates_the_profile(self, admin_client):
        user = UserFactory(role=Role.DOCTOR)

        response = self.change_role(admin_client, user, Role.PATIENT)

        assert response.status_code == 302
        assert Patient.objects.filter(user=user).exists()
