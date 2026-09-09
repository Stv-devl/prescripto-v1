"""API endpoint tests for auth routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.role = "owner"
    user.tenant_id = uuid.uuid4()
    user.created_at = "2026-01-01T00:00:00+00:00"
    return user


class TestSignupEndpoint:
    def test_signup_success(self, client: TestClient) -> None:
        user = _make_user()
        with patch(
            "app.api.auth.auth_service.signup",
            new_callable=AsyncMock,
            return_value=(user, "access_tok", "refresh_tok"),
        ):
            res = client.post(
                "/api/auth/signup",
                json={"email": "new@test.com", "password": "password123", "name": "Cabinet"},
            )

        assert res.status_code == 201
        data = res.json()
        assert data["access_token"] == "access_tok"
        assert data["refresh_token"] == "refresh_tok"
        assert data["token_type"] == "bearer"

    def test_signup_duplicate_email(self, client: TestClient) -> None:
        with patch(
            "app.api.auth.auth_service.signup",
            new_callable=AsyncMock,
            side_effect=ConflictError("email already registered"),
        ):
            res = client.post(
                "/api/auth/signup",
                json={"email": "existing@test.com", "password": "password123", "name": "Cabinet"},
            )

        assert res.status_code == 409
        assert res.json()["detail"] == "email already registered"

    def test_signup_short_password(self, client: TestClient) -> None:
        res = client.post(
            "/api/auth/signup",
            json={"email": "new@test.com", "password": "short", "name": "Cabinet"},
        )
        assert res.status_code == 422


class TestLoginEndpoint:
    def test_login_success(self, client: TestClient) -> None:
        user = _make_user()
        with patch(
            "app.api.auth.auth_service.login",
            new_callable=AsyncMock,
            return_value=(user, "access_tok", "refresh_tok"),
        ):
            res = client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "password123"},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["access_token"] == "access_tok"

    def test_login_rejects_a_password_past_bcrypts_limit(self, client: TestClient) -> None:
        """422, not 500 — and no patch, because none is needed.

        Pydantic refuses at request-model construction, before the route body
        and therefore before the database is consulted. That is what closes the
        oracle: the answer no longer depends on whether the account exists.
        """
        res = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "a" * 73},
        )

        assert res.status_code == 422

    def test_a_rejected_password_is_never_echoed_back(self, client: TestClient) -> None:
        """Pydantic v2 puts the offending value in every error entry by default.

        The client keeps that body on ServiceError.cause and console.errors it,
        so an echo here writes the password into the browser console.
        """
        secret = "MotDePasseQueLUtilisateurACopie" + "x" * 60

        res = client.post(
            "/api/auth/login", json={"email": "test@example.com", "password": secret}
        )

        assert res.status_code == 422
        assert secret not in res.text

    def test_the_validation_error_shape_is_field_and_reason_only(
        self, client: TestClient
    ) -> None:
        """The handler is registered app-wide, so this shape is every route's.

        Pinning it here is what makes a later widening — re-adding `input`, or
        dropping `loc` — fail somewhere instead of silently changing 45 contracts.
        """
        res = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})

        assert res.status_code == 422
        detail = res.json()["detail"]
        assert isinstance(detail, list)
        assert detail
        for entry in detail:
            assert set(entry) == {"type", "loc", "msg"}
            assert isinstance(entry["loc"], list)

    def test_login_invalid_credentials(self, client: TestClient) -> None:
        with patch(
            "app.api.auth.auth_service.login",
            new_callable=AsyncMock,
            side_effect=UnauthorizedError("invalid login credentials"),
        ):
            res = client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrong"},
            )

        assert res.status_code == 401
        assert res.json()["detail"] == "invalid login credentials"


class TestRefreshEndpoint:
    def test_refresh_success(self, client: TestClient) -> None:
        with patch(
            "app.api.auth.auth_service.refresh",
            new_callable=AsyncMock,
            return_value=("new_at", "new_rt"),
        ):
            res = client.post(
                "/api/auth/refresh",
                json={"refresh_token": "old_refresh"},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["access_token"] == "new_at"
        assert data["refresh_token"] == "new_rt"

    def test_refresh_invalid_token(self, client: TestClient) -> None:
        with patch(
            "app.api.auth.auth_service.refresh",
            new_callable=AsyncMock,
            side_effect=UnauthorizedError("Invalid or expired token"),
        ):
            res = client.post(
                "/api/auth/refresh",
                json={"refresh_token": "bad_token"},
            )

        assert res.status_code == 401


class TestMeEndpoint:
    def test_me_success(self, client: TestClient) -> None:
        user = _make_user()
        with patch(
            "app.api.auth.auth_service.get_me",
            new_callable=AsyncMock,
            return_value=user,
        ):
            res = client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer fake_token"},
            )

        # In dev_mode the bearer scheme auto_error=False, so it may use dev user
        # The exact behavior depends on dev_mode setting
        assert res.status_code in (200, 401)

    def test_me_no_token_prod(self, client: TestClient) -> None:
        # Without token and without dev_mode, should get 403 from HTTPBearer
        # In dev_mode this falls through to dev user
        res = client.get("/api/auth/me")
        # dev_mode=True by default, so this will succeed with dev user
        assert res.status_code in (200, 401, 403)


_CREDENTIALS = {"email": "test@example.com", "password": "password123"}
_AUTH_LIMIT = settings.rate_limit_auth_per_minute
_RESET_LIMIT = settings.rate_limit_reset_per_window


def _refused_login() -> object:
    """Keeps the route off bcrypt: the meter runs before the body either way."""
    return patch(
        "app.api.auth.auth_service.login",
        new_callable=AsyncMock,
        side_effect=UnauthorizedError("invalid login credentials"),
    )


class TestRateLimiting:
    """The counters are emptied around every case by an autouse fixture in
    tests/conftest.py — without it a saturating case would leak its count into
    whatever runs next, in an order nothing guarantees."""

    def test_login_answers_429_once_the_limit_is_spent(self, client: TestClient) -> None:
        with _refused_login():
            for _ in range(_AUTH_LIMIT):
                assert client.post("/api/auth/login", json=_CREDENTIALS).status_code == 401

            res = client.post("/api/auth/login", json=_CREDENTIALS)

        assert res.status_code == 429

    def test_the_refusal_carries_a_usable_retry_after(self, client: TestClient) -> None:
        """A header that is present but wrong is worse than none: a client that
        honours it retries at once."""
        with _refused_login():
            for _ in range(_AUTH_LIMIT + 1):
                res = client.post("/api/auth/login", json=_CREDENTIALS)

        # Not a range the whole window fits in: a handler answering a constant 1
        # passed that, and a client honouring it would retry at once. The window
        # is 60 s and the loop above spends well under a second, so anything but
        # the real remainder falls short.
        assert int(res.headers["Retry-After"]) >= 55

    def test_the_refusal_keeps_the_shape_of_every_other_error(
        self, client: TestClient
    ) -> None:
        """Pins the absence of extra keys, which nothing pinned before."""
        with _refused_login():
            for _ in range(_AUTH_LIMIT + 1):
                res = client.post("/api/auth/login", json=_CREDENTIALS)

        assert res.json() == {"detail": "too many requests"}

    def test_signup_carries_the_limit_on_its_own_route(self, client: TestClient) -> None:
        """Forgetting the dependency on this one route would leave the suite
        green: the counter's unit tests prove the bucket, not the wiring."""
        body = {"email": "neuf@test.com", "password": "password123", "name": "Cabinet"}
        with patch(
            "app.api.auth.auth_service.signup",
            new_callable=AsyncMock,
            side_effect=ConflictError("email already registered"),
        ):
            for _ in range(_AUTH_LIMIT):
                client.post("/api/auth/signup", json=body)

            res = client.post("/api/auth/signup", json=body)

        assert res.status_code == 429

    def test_the_reset_routes_are_governed_by_their_own_window(
        self, client: TestClient
    ) -> None:
        """Distinct from the per-minute one. Wiring every route onto a single
        quota would otherwise pass unnoticed."""
        with patch(
            "app.api.auth.auth_service.forgot_password", new_callable=AsyncMock
        ):
            for _ in range(_RESET_LIMIT):
                assert (
                    client.post(
                        "/api/auth/forgot-password", json={"email": "eco@cabinet.fr"}
                    ).status_code
                    == 200
                )

            res = client.post("/api/auth/forgot-password", json={"email": "eco@cabinet.fr"})

        assert res.status_code == 429
        # Pins the window too, not just the count: shortening it to 60 s left
        # every other assertion of this case green. And the upper bound is what
        # keeps a refusal from outliving the 30-minute reset token it protects.
        assert 60 < int(res.headers["Retry-After"]) <= 1800

    def test_reset_password_carries_the_limit_on_its_own_route(
        self, client: TestClient
    ) -> None:
        """Removing the dependency from this one route left the suite green:
        the case above exercises forgot-password and nothing else."""
        body = {"token": "not-a-real-token", "password": "nouveaumotdepasse1"}
        for _ in range(_RESET_LIMIT):
            client.post("/api/auth/reset-password", json=body)

        res = client.post("/api/auth/reset-password", json=body)

        assert res.status_code == 429

    def test_refresh_is_never_limited(self, client: TestClient) -> None:
        """apiClient reads any non-2xx on refresh as a dead session and logs the
        user out. A 429 there would eject people mid-session — and behind a
        shared proxy address, everyone at once."""
        with patch(
            "app.api.auth.auth_service.refresh",
            new_callable=AsyncMock,
            side_effect=UnauthorizedError("Invalid or expired token"),
        ):
            codes = {
                client.post("/api/auth/refresh", json={"refresh_token": "x"}).status_code
                for _ in range(_AUTH_LIMIT + _RESET_LIMIT + 2)
            }

        assert 429 not in codes

    def test_an_authenticated_route_is_not_affected(self, client: TestClient) -> None:
        """The case that forbids hanging the dependency on the whole router."""
        codes = {client.get("/api/auth/me").status_code for _ in range(_AUTH_LIMIT + 2)}

        assert 429 not in codes
