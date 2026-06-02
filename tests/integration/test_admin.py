"""Smoke tests for Django Admin customizations.

Verifies admin pages load correctly and bulk actions work.
Not an exhaustive UI test — just confirms nothing is broken.
"""

import pytest
from django.urls import reverse

from tests.factories import AppointmentFactory, DoctorFactory, UserFactory


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
