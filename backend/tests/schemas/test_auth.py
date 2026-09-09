"""Unit tests for the auth request schemas.

The bound is 72 BYTES, not 72 characters: `max_length` counts characters, and a
72-character accented password is up to 144 bytes, which bcrypt still refuses.
The accented case below is what tells the two bounds apart.
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
)

# 43 characters, 83 UTF-8 bytes. The suffix is uppercase-digit-symbol on purpose:
# "É" is not in [A-Z], so a lowercase suffix would be rejected by the client's
# character rules instead, and this case would prove nothing about the byte bound.
_ACCENTED_83_BYTES = "É" * 40 + "A1!"
_EXACTLY_72 = "a" * 72
_ONE_TOO_MANY = "a" * 73


def _build(model: type, password: str) -> object:
    """Build each model with its own required fields, varying only the password."""
    if model is SignupRequest:
        return SignupRequest(email="eco@cabinet.fr", password=password, name="Cabinet")
    if model is LoginRequest:
        return LoginRequest(email="eco@cabinet.fr", password=password)
    if model is ResetPasswordRequest:
        return ResetPasswordRequest(token="tok", password=password)
    raise AssertionError(f"unhandled model {model}")


_CREATES_A_PASSWORD = [SignupRequest, ResetPasswordRequest]


class TestPasswordByteBound:
    @pytest.mark.parametrize("model", _CREATES_A_PASSWORD)
    def test_exactly_72_bytes_is_accepted(self, model: type) -> None:
        """The bound is inclusive: 72 is bcrypt's limit, not one past it."""
        assert _build(model, _EXACTLY_72) is not None

    @pytest.mark.parametrize("model", _CREATES_A_PASSWORD)
    def test_73_bytes_is_refused(self, model: type) -> None:
        with pytest.raises(ValidationError):
            _build(model, _ONE_TOO_MANY)

    @pytest.mark.parametrize("model", _CREATES_A_PASSWORD)
    def test_accented_password_under_72_characters_is_refused(self, model: type) -> None:
        with pytest.raises(ValidationError):
            _build(model, _ACCENTED_83_BYTES)

    def test_login_password_is_bounded_too(self) -> None:
        """The unbounded field is what produced the 500-versus-401 oracle."""
        assert LoginRequest(email="eco@cabinet.fr", password=_EXACTLY_72) is not None
        with pytest.raises(ValidationError):
            LoginRequest(email="eco@cabinet.fr", password=_ONE_TOO_MANY)
        with pytest.raises(ValidationError):
            LoginRequest(email="eco@cabinet.fr", password=_ACCENTED_83_BYTES)

    def test_both_change_password_fields_are_bounded(self) -> None:
        assert ChangePasswordRequest(
            current_password=_EXACTLY_72, new_password=_EXACTLY_72
        ) is not None
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password=_ONE_TOO_MANY, new_password=_EXACTLY_72)
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password=_EXACTLY_72, new_password=_ONE_TOO_MANY)


class TestPasswordLengthPolicySurvives:
    @pytest.mark.parametrize("model", _CREATES_A_PASSWORD)
    def test_a_created_password_still_needs_eight_characters(self, model: type) -> None:
        """A single shared alias would have dropped min_length on three fields."""
        with pytest.raises(ValidationError):
            _build(model, "Ab1!567")

    def test_change_password_new_field_still_needs_eight_characters(self) -> None:
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="whatever", new_password="Ab1!567")

    def test_a_presented_password_gains_no_minimum(self) -> None:
        """A minimum here would be a second existence signal on an open endpoint."""
        assert LoginRequest(email="eco@cabinet.fr", password="x") is not None
        assert ChangePasswordRequest(current_password="x", new_password="Ab1!5678") is not None
