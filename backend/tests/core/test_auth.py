"""The two password primitives, called for real.

Every other test in this repository patches them — eighteen sites do. So until
this file existed, nothing asserted that hashing then verifying actually works,
and a chantier moving all six call sites off the event loop would have had no
ground truth to move away from.

Two bcrypt operations at cost 12, so this file costs roughly a third of a second
and no more.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core import auth
from app.core.auth import hash_password, verify_password
from app.core.config import settings
from app.core.exceptions import UnauthorizedError


class TestHashingRoundTrip:
    def test_a_password_verifies_against_its_own_hash(self) -> None:
        assert verify_password("motdepasse-du-cabinet", hash_password("motdepasse-du-cabinet"))

    def test_another_password_does_not(self) -> None:
        assert not verify_password("presque-le-bon", hash_password("motdepasse-du-cabinet"))


class TestResetTokenContract:
    def test_decode_returns_the_issued_user_and_version(self) -> None:
        user_id = uuid.UUID("63ea8db8-0123-4da7-9cb8-123456789abc")

        claims = auth.decode_reset_token(auth.create_reset_token(user_id, 7))

        assert isinstance(claims, auth.ResetClaims)
        assert claims.user_id == user_id
        assert claims.token_version == 7

    @pytest.mark.parametrize(
        ("claim", "value"),
        [
            pytest.param("token_version", None, id="missing-version"),
            pytest.param("token_version", "0", id="string-version"),
            pytest.param("token_version", 0.0, id="float-version"),
            pytest.param("token_version", True, id="boolean-version"),
            pytest.param("type", "access", id="wrong-type"),
            pytest.param("exp", datetime(2000, 1, 1, tzinfo=UTC), id="expired"),
            pytest.param("sub", None, id="missing-subject"),
            pytest.param("sub", "not-a-uuid", id="malformed-subject"),
            pytest.param("sub", 123, id="non-string-subject"),
        ],
    )
    def test_invalid_claim_is_refused(
        self, claim: str, value: str | int | float | datetime | None
    ) -> None:
        payload: dict[str, str | int | float | datetime] = {
            "sub": "63ea8db8-0123-4da7-9cb8-123456789abc",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
            "type": "reset",
            "token_version": 0,
        }
        if value is None:
            del payload[claim]
        else:
            payload[claim] = value
        token = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        with pytest.raises(UnauthorizedError, match="^invalid reset token$"):
            auth.decode_reset_token(token)

    def test_wrong_signature_is_refused(self) -> None:
        payload = {
            "sub": "63ea8db8-0123-4da7-9cb8-123456789abc",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
            "type": "reset",
            "token_version": 0,
        }
        token = jwt.encode(
            payload,
            settings.jwt_secret_key + "-wrong-signature",
            algorithm=settings.jwt_algorithm,
        )

        with pytest.raises(UnauthorizedError, match="^invalid reset token$"):
            auth.decode_reset_token(token)
