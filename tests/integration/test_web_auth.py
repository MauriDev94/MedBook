"""Web session auth: login, logout and patient sign-up (Paso 25, ADR 0002).

Session auth only; the API's JWT flow is unchanged. Sign-up reuses
apps.users.services.register_patient. Login and sign-up POSTs share the
API's throttle scopes ("login" 5/min, "register" 10/h) and cache keys, so
the web form and the API endpoint draw from one budget per IP.
"""

import pytest
from django.contrib.auth import SESSION_KEY
from django.core.cache import cache
from django.core.exceptions import ValidationError
from pytest_django.asserts import assertTemplateUsed

from apps.patients.models import Patient
from apps.users.models import Role, User
from apps.users.services import DUPLICATE_EMAIL_MESSAGE
from tests.factories import UserFactory, random_password, short_password

LOGIN_URL = "/login/"
LOGOUT_URL = "/logout/"
SIGNUP_URL = "/signup/"
PANEL_URL = "/panel/"
# Generated per run, never hardcoded
PASSPHRASE = random_password()
INVALID_LOGIN_ES = "Correo o contraseña incorrectos."


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


def logged_in_user_id(client):
    return client.session.get(SESSION_KEY)


def signup_data(**overrides):
    data = {
        "first_name": "Ana",
        "last_name": "Rojas",
        "email": "ana@example.com",
        "password": PASSPHRASE,
        "password_confirm": PASSPHRASE,
    }
    return {**data, **overrides}


@pytest.mark.django_db
class TestLogin:
    def test_get_renders_form(self, client):
        response = client.get(LOGIN_URL)

        assert response.status_code == 200
        assertTemplateUsed(response, "web/auth/login.html")

    def test_patient_lands_on_home(self, client):
        user = UserFactory(role=Role.PATIENT)

        response = client.post(
            LOGIN_URL, {"username": user.email, "password": user.raw_password}
        )

        assert response.status_code == 302
        assert response["Location"] == "/"
        assert logged_in_user_id(client) == str(user.pk)

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_doctor_and_admin_land_on_panel_notice(self, client, role):
        user = UserFactory(role=role)

        response = client.post(
            LOGIN_URL, {"username": user.email, "password": user.raw_password}
        )

        assert response["Location"] == PANEL_URL

    def test_next_parameter_wins(self, client):
        user = UserFactory()

        response = client.post(
            f"{LOGIN_URL}?next=/api/docs/",
            {"username": user.email, "password": user.raw_password},
        )

        assert response["Location"] == "/api/docs/"

    def test_external_next_is_ignored(self, client):
        user = UserFactory()

        response = client.post(
            f"{LOGIN_URL}?next=https://evil.example.com/",
            {"username": user.email, "password": user.raw_password},
        )

        assert response["Location"] == "/"

    def test_email_in_another_case_logs_in(self, client):
        """An account registered as ana@… logs in as Ana@… (Paso 34)."""
        user = UserFactory(email="ana@example.com", role=Role.PATIENT)

        response = client.post(
            LOGIN_URL, {"username": "Ana@Example.com", "password": user.raw_password}
        )

        assert response.status_code == 302
        assert logged_in_user_id(client) == str(user.pk)

    def test_wrong_password_shows_generic_error(self, client):
        user = UserFactory()

        response = client.post(
            LOGIN_URL, {"username": user.email, "password": random_password()}
        )

        assert response.status_code == 200
        assert INVALID_LOGIN_ES in response.content.decode()
        assert logged_in_user_id(client) is None

    def test_unknown_email_gets_the_same_error(self, client):
        """The message must not reveal whether the email is registered."""
        known = UserFactory()
        wrong_password = client.post(
            LOGIN_URL, {"username": known.email, "password": random_password()}
        )
        unknown_email = client.post(
            LOGIN_URL, {"username": "nadie@example.com", "password": random_password()}
        )

        assert (
            wrong_password.context["form"].non_field_errors()
            == unknown_email.context["form"].non_field_errors()
        )

    def test_inactive_user_cannot_log_in(self, client):
        user = UserFactory(is_active=False)

        response = client.post(
            LOGIN_URL, {"username": user.email, "password": user.raw_password}
        )

        assert INVALID_LOGIN_ES in response.content.decode()
        assert logged_in_user_id(client) is None

    def test_logged_in_user_is_redirected_away(self, client):
        client.force_login(UserFactory(role=Role.PATIENT))

        response = client.get(LOGIN_URL)

        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_form_in_english(self, client):
        response = client.get(LOGIN_URL, headers={"Accept-Language": "en"})

        assert "Log in" in response.content.decode()


@pytest.mark.django_db
class TestLogout:
    def test_get_is_not_allowed(self, client):
        client.force_login(UserFactory())

        response = client.get(LOGOUT_URL)

        assert response.status_code == 405
        assert logged_in_user_id(client) is not None

    def test_post_logs_out_and_goes_home(self, client):
        client.force_login(UserFactory())

        response = client.post(LOGOUT_URL)

        assert response.status_code == 302
        assert response["Location"] == "/"
        assert logged_in_user_id(client) is None


@pytest.mark.django_db
class TestSignup:
    def test_get_renders_form(self, client):
        response = client.get(SIGNUP_URL)

        assert response.status_code == 200
        assertTemplateUsed(response, "web/auth/signup.html")

    def test_creates_patient_and_logs_in(self, client):
        response = client.post(SIGNUP_URL, signup_data())

        user = User.objects.get(email="ana@example.com")
        assert user.role == Role.PATIENT
        assert user.check_password(PASSPHRASE)
        assert Patient.objects.filter(user=user).exists()
        assert response.status_code == 302
        assert response["Location"] == "/"
        assert logged_in_user_id(client) == str(user.pk)

    def test_duplicate_email_shows_field_error(self, client):
        UserFactory(email="ana@example.com")

        response = client.post(SIGNUP_URL, signup_data(email="Ana@Example.com"))

        assert response.status_code == 200
        assert response.context["form"].errors["email"] == [
            "Ya existe un usuario con este correo."
        ]
        assert User.objects.filter(email__iexact="ana@example.com").count() == 1

    def test_email_taken_between_check_and_insert_shows_field_error(
        self, client, monkeypatch
    ):
        """register_patient() re-checks inside its transaction (race)."""

        def taken_meanwhile(**kwargs):
            raise ValidationError({"email": [DUPLICATE_EMAIL_MESSAGE]})

        monkeypatch.setattr("apps.web.views.register_patient", taken_meanwhile)

        response = client.post(SIGNUP_URL, signup_data())

        assert response.status_code == 200
        assert response.context["form"].errors["email"] == [
            "Ya existe un usuario con este correo."
        ]
        assert logged_in_user_id(client) is None

    def test_errors_follow_the_active_language(self, client):
        UserFactory(email="ana@example.com")

        response = client.post(
            SIGNUP_URL, signup_data(), headers={"Accept-Language": "en"}
        )

        assert response.context["form"].errors["email"] == [
            "A user with this email already exists."
        ]

    def test_weak_password_shows_field_error(self, client):
        weak = short_password()

        response = client.post(
            SIGNUP_URL, signup_data(password=weak, password_confirm=weak)
        )

        assert response.status_code == 200
        assert "password" in response.context["form"].errors
        assert not User.objects.filter(email="ana@example.com").exists()

    def test_role_cannot_be_chosen(self, client):
        client.post(SIGNUP_URL, signup_data(role=Role.ADMIN))

        assert User.objects.get(email="ana@example.com").role == Role.PATIENT

    def test_logged_in_user_is_redirected_away(self, client):
        client.force_login(UserFactory(role=Role.PATIENT))

        response = client.get(SIGNUP_URL)

        assert response.status_code == 302
        assert response["Location"] == "/"


@pytest.mark.django_db
class TestAuthThrottling:
    def test_sixth_login_attempt_in_a_minute_is_rejected(self, client):
        for _ in range(5):
            response = client.post(
                LOGIN_URL, {"username": "x@example.com", "password": random_password()}
            )
            assert response.status_code == 200

        response = client.post(
            LOGIN_URL, {"username": "x@example.com", "password": random_password()}
        )

        assert response.status_code == 429
        assert int(response["Retry-After"]) > 0
        assertTemplateUsed(response, "web/throttled.html")

    def test_login_form_get_is_not_throttled(self, client):
        for _ in range(6):
            response = client.get(LOGIN_URL)

        assert response.status_code == 200

    def test_web_and_api_login_share_one_budget(self, client, api_client):
        for _ in range(5):
            api_client.post(
                "/api/v1/token/",
                {"email": "x@example.com", "password": random_password()},
                format="json",
            )

        response = client.post(
            LOGIN_URL, {"username": "x@example.com", "password": random_password()}
        )

        assert response.status_code == 429

    def test_eleventh_signup_in_an_hour_is_rejected(self, client):
        for _ in range(10):
            response = client.post(SIGNUP_URL, signup_data(email="not-an-email"))
            assert response.status_code == 200

        response = client.post(SIGNUP_URL, signup_data())

        assert response.status_code == 429
        assert not User.objects.filter(email="ana@example.com").exists()


@pytest.mark.django_db
class TestPanelNotice:
    def test_anonymous_is_sent_to_login(self, client):
        response = client.get(PANEL_URL)

        assert response.status_code == 302
        assert response["Location"] == f"{LOGIN_URL}?next={PANEL_URL}"

    def test_patient_is_forbidden(self, client):
        client.force_login(UserFactory(role=Role.PATIENT))

        assert client.get(PANEL_URL).status_code == 403

    def test_doctor_sees_upcoming_panel_notice(self, client):
        client.force_login(UserFactory(role=Role.DOCTOR))

        response = client.get(PANEL_URL)

        assert response.status_code == 200
        assert "próximo sprint" in response.content.decode()

    def test_admin_gets_a_link_to_the_django_admin(self, client):
        client.force_login(UserFactory(role=Role.ADMIN, is_staff=True))

        response = client.get(PANEL_URL)

        assert 'href="/admin/"' in response.content.decode()


@pytest.mark.django_db
class TestNavigation:
    def test_anonymous_sees_login_and_signup(self, client):
        html = client.get("/").content.decode()

        assert f'href="{LOGIN_URL}"' in html
        assert f'href="{SIGNUP_URL}"' in html
        assert f'action="{LOGOUT_URL}"' not in html

    def test_patient_sees_name_and_logout(self, client):
        client.force_login(UserFactory(role=Role.PATIENT, first_name="Ana"))

        html = client.get("/").content.decode()

        assert "Ana" in html
        assert f'action="{LOGOUT_URL}"' in html
        assert f'href="{LOGIN_URL}"' not in html
        assert f'href="{PANEL_URL}"' not in html

    @pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
    def test_doctor_and_admin_see_panel_link(self, client, role):
        client.force_login(UserFactory(role=role))

        html = client.get("/").content.decode()

        assert f'href="{PANEL_URL}"' in html
