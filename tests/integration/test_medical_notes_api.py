"""Integration tests for MedicalNoteViewSet.

Covers:
- GET  /api/appointments/{appointment_pk}/notes/        → list
- POST /api/appointments/{appointment_pk}/notes/        → create (doctor only)
- GET  /api/appointments/{appointment_pk}/notes/{pk}/   → retrieve
"""

import pytest
from rest_framework import status

from apps.appointments.models import MedicalNote
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    MedicalNoteFactory,
    PatientFactory,
    UserFactory,
)


def notes_list_url(appointment):
    return f"/api/v1/appointments/{appointment.id}/notes/"


def notes_detail_url(appointment, note):
    return f"/api/v1/appointments/{appointment.id}/notes/{note.id}/"


@pytest.mark.django_db
class TestMedicalNoteList:
    """GET /api/appointments/{pk}/notes/ — list notes."""

    def test_doctor_lists_notes_for_own_appointment(self, api_client):
        appointment = AppointmentFactory()
        note = MedicalNoteFactory(
            appointment=appointment, author=appointment.doctor.user
        )

        api_client.force_authenticate(user=appointment.doctor.user)
        response = api_client.get(notes_list_url(appointment))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert str(response.data["results"][0]["id"]) == str(note.id)

    def test_doctor_cannot_list_notes_from_other_appointment(self, api_client):
        other_doctor = DoctorFactory()
        appointment = AppointmentFactory()
        MedicalNoteFactory(appointment=appointment)

        api_client.force_authenticate(user=other_doctor.user)
        response = api_client.get(notes_list_url(appointment))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_lists_all_notes(self, api_client):
        admin = UserFactory(role="admin")
        appointment = AppointmentFactory()
        MedicalNoteFactory(appointment=appointment)
        MedicalNoteFactory(appointment=appointment)

        api_client.force_authenticate(user=admin)
        response = api_client.get(notes_list_url(appointment))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_patient_cannot_list_notes(self, api_client):
        patient = PatientFactory()
        appointment = AppointmentFactory()

        api_client.force_authenticate(user=patient.user)
        response = api_client.get(notes_list_url(appointment))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self, api_client):
        appointment = AppointmentFactory()
        response = api_client.get(notes_list_url(appointment))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_response_has_expected_fields(self, api_client):
        appointment = AppointmentFactory()
        MedicalNoteFactory(appointment=appointment, author=appointment.doctor.user)

        api_client.force_authenticate(user=appointment.doctor.user)
        response = api_client.get(notes_list_url(appointment))

        note = response.data["results"][0]
        for field in ["id", "content", "author_name", "created_at"]:
            assert field in note, f"Missing field: {field}"


@pytest.mark.django_db
class TestMedicalNoteCreate:
    """POST /api/appointments/{pk}/notes/ — create note (doctor only)."""

    def test_doctor_creates_note(self, api_client):
        appointment = AppointmentFactory()
        api_client.force_authenticate(user=appointment.doctor.user)

        response = api_client.post(
            notes_list_url(appointment),
            {"content": "Patient shows improvement."},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert MedicalNote.objects.filter(appointment=appointment).exists()

    def test_author_auto_assigned_from_request_user(self, api_client):
        appointment = AppointmentFactory()
        api_client.force_authenticate(user=appointment.doctor.user)

        response = api_client.post(
            notes_list_url(appointment),
            {"content": "Auto-assigned author test."},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        note = MedicalNote.objects.get(id=response.data["id"])
        assert note.author == appointment.doctor.user

    def test_patient_cannot_create_note(self, api_client):
        patient = PatientFactory()
        appointment = AppointmentFactory()

        api_client.force_authenticate(user=patient.user)
        response = api_client.post(
            notes_list_url(appointment),
            {"content": "Patient trying to write note."},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_other_doctor_cannot_create_note(self, api_client):
        other_doctor = DoctorFactory()
        appointment = AppointmentFactory()

        api_client.force_authenticate(user=other_doctor.user)
        response = api_client.post(
            notes_list_url(appointment),
            {"content": "Other doctor trying to write."},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_empty_content_returns_400(self, api_client):
        appointment = AppointmentFactory()
        api_client.force_authenticate(user=appointment.doctor.user)

        response = api_client.post(
            notes_list_url(appointment),
            {"content": ""},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        appointment = AppointmentFactory()
        response = api_client.post(
            notes_list_url(appointment),
            {"content": "Some note."},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMedicalNoteRetrieve:
    """GET /api/appointments/{pk}/notes/{note_pk}/ — retrieve single note."""

    def test_doctor_retrieves_own_note(self, api_client):
        appointment = AppointmentFactory()
        note = MedicalNoteFactory(
            appointment=appointment, author=appointment.doctor.user
        )

        api_client.force_authenticate(user=appointment.doctor.user)
        response = api_client.get(notes_detail_url(appointment, note))

        assert response.status_code == status.HTTP_200_OK
        assert str(response.data["id"]) == str(note.id)
        assert response.data["content"] == note.content

    def test_doctor_cannot_retrieve_note_from_other_appointment(self, api_client):
        other_doctor = DoctorFactory()
        appointment = AppointmentFactory()
        note = MedicalNoteFactory(appointment=appointment)

        api_client.force_authenticate(user=other_doctor.user)
        response = api_client.get(notes_detail_url(appointment, note))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_retrieves_any_note(self, api_client):
        admin = UserFactory(role="admin")
        appointment = AppointmentFactory()
        note = MedicalNoteFactory(appointment=appointment)

        api_client.force_authenticate(user=admin)
        response = api_client.get(notes_detail_url(appointment, note))

        assert response.status_code == status.HTTP_200_OK

    def test_patient_cannot_retrieve_note(self, api_client):
        patient = PatientFactory()
        appointment = AppointmentFactory()
        note = MedicalNoteFactory(appointment=appointment)

        api_client.force_authenticate(user=patient.user)
        response = api_client.get(notes_detail_url(appointment, note))

        assert response.status_code == status.HTTP_403_FORBIDDEN
