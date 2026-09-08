"""The password rules must be the same rules on every schema that takes one.

``_validate_password_complexity`` used to document a length floor it did not
enforce: ``ChangePasswordRequest`` and ``SetupRequest`` carried
``Field(min_length=8)``, but ``UserCreate`` and ``UserUpdate`` never did. So an
admin creating an account through Settings could set ``Ab1`` — which the same
account then could not be given again through Change Password, and which the
frontend's own rules refuse. The floor now lives in the shared validator, so
every schema inherits it.
"""

import pytest
from pydantic import ValidationError

from backend.app.schemas.auth import (
    MIN_PASSWORD_LENGTH,
    ChangePasswordRequest,
    SetupRequest,
    UserCreate,
    UserUpdate,
)

VALID = "Abcdef12"


def _make(model, password):
    if model is UserCreate:
        return model(username="alice", password=password)
    if model is UserUpdate:
        return model(password=password)
    if model is ChangePasswordRequest:
        return model(current_password="whatever", new_password=password)
    return model(admin_username="alice", admin_password=password)


PASSWORD_MODELS = [UserCreate, UserUpdate, ChangePasswordRequest, SetupRequest]


@pytest.mark.parametrize("model", PASSWORD_MODELS)
def test_a_valid_password_is_accepted_everywhere(model):
    _make(model, VALID)


@pytest.mark.parametrize("model", PASSWORD_MODELS)
@pytest.mark.parametrize(
    "password",
    [
        "Ab1",  # too short — the rule UserCreate/UserUpdate used to skip
        "abcdef12",  # no uppercase
        "ABCDEF12",  # no lowercase
        "AbcdefGh",  # no digit
    ],
)
def test_every_schema_refuses_a_password_that_breaks_a_rule(model, password):
    with pytest.raises(ValidationError):
        _make(model, password)


@pytest.mark.parametrize("model", PASSWORD_MODELS)
def test_the_shortest_accepted_password_is_the_documented_floor(model):
    """One character below the floor fails, the floor itself passes."""
    at_floor = "Abcdefg1"[: MIN_PASSWORD_LENGTH - 1] + "9"
    assert len(at_floor) == MIN_PASSWORD_LENGTH
    _make(model, at_floor)
    with pytest.raises(ValidationError):
        _make(model, at_floor[:-1])


def test_an_omitted_password_is_still_optional_on_the_user_schemas():
    """Advanced-auth creates users with a generated password, and an edit that
    leaves the field blank keeps the current one — neither may be forced to
    satisfy rules for a password it is not setting."""
    assert UserCreate(username="alice").password is None
    assert UserUpdate(email="alice@example.com").password is None
