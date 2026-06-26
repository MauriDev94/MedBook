"""API versioning tests.

All business endpoints live under /api/v1/. The unversioned /api/ prefix
must no longer resolve — this is a breaking change tracked by issue #81.
Meta-endpoints (docs, schema, health, root) are intentionally NOT versioned.
"""

import pytest

from apps.users.models import Role
from tests.factories import UserFactory


@pytest.fixture
def authed_patient_client(db, api_client):
    user = UserFactory(role=Role.PATIENT)
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
class TestApiVersioning:
    def test_v1_users_me_is_reachable(self, authed_patient_client):
        response = authed_patient_client.get("/api/v1/users/me/")

        assert response.status_code == 200

    def test_v1_doctors_list_is_reachable(self, authed_patient_client):
        response = authed_patient_client.get("/api/v1/doctors/")

        assert response.status_code == 200

    def test_unversioned_users_me_no_longer_exists(self, authed_patient_client):
        response = authed_patient_client.get("/api/users/me/")

        assert response.status_code == 404

    def test_unversioned_doctors_no_longer_exists(self, authed_patient_client):
        response = authed_patient_client.get("/api/doctors/")

        assert response.status_code == 404

    def test_unversioned_token_no_longer_exists(self, client):
        response = client.post("/api/token/", {"email": "x", "password": "y"})

        assert response.status_code == 404

    def test_docs_endpoint_is_not_versioned(self, client):
        response = client.get("/api/docs/")

        assert response.status_code == 200

    def test_schema_endpoint_is_not_versioned(self, client):
        response = client.get("/api/schema/")

        assert response.status_code == 200

    def test_health_check_is_not_versioned(self, client):
        response = client.get("/health/")

        assert response.status_code == 200
