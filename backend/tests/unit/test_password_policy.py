"""Unit tests for the shared password-strength policy."""

from __future__ import annotations

import pytest

from app.core.password import (
    PASSWORD_MIN_LENGTH,
    password_problems,
    validate_password_strength,
)

# A password that satisfies every rule: length, upper, lower, digit, special.
STRONG_PASSWORD = "Str0ng!Passw0rd"


def test_strong_password_has_no_problems() -> None:
    assert password_problems(STRONG_PASSWORD) == []
    assert validate_password_strength(STRONG_PASSWORD) == STRONG_PASSWORD


@pytest.mark.parametrize(
    ("password", "expected_problem"),
    [
        ("Aa1!short", f"at least {PASSWORD_MIN_LENGTH} characters"),
        ("alllowercase1!", "an uppercase letter"),
        ("ALLUPPERCASE1!", "a lowercase letter"),
        ("NoNumbersHere!!", "a number"),
        ("NoSpecialChar12X", "a special character"),
    ],
)
def test_each_weakness_is_reported(password: str, expected_problem: str) -> None:
    assert expected_problem in password_problems(password)


def test_validate_raises_and_lists_every_unmet_rule() -> None:
    with pytest.raises(ValueError) as exc:
        validate_password_strength("short")
    message = str(exc.value)
    assert f"at least {PASSWORD_MIN_LENGTH} characters" in message
    assert "an uppercase letter" in message
    assert "a number" in message
    assert "a special character" in message
