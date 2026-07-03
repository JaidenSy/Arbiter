"""
Arbiter shared password-strength policy.

Single source of truth for the password rules. Every flow that sets a
password (register, change-password, reset-password, accept-invite) runs
through here so the requirements stay consistent across the app. The
frontend mirrors these rules in ``components/PasswordRequirements.tsx``.
Keep the two in sync.
"""

from __future__ import annotations

PASSWORD_MIN_LENGTH = 12


def password_problems(password: str) -> list[str]:
    """Return human-readable descriptions of every unmet rule.

    An empty list means the password satisfies the policy.
    """
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"at least {PASSWORD_MIN_LENGTH} characters")
    if not any(c.islower() for c in password):
        problems.append("a lowercase letter")
    if not any(c.isupper() for c in password):
        problems.append("an uppercase letter")
    if not any(c.isdigit() for c in password):
        problems.append("a number")
    if not any(not c.isalnum() for c in password):
        problems.append("a special character")
    return problems


def validate_password_strength(password: str) -> str:
    """Pydantic/endpoint validator: raise ``ValueError`` listing unmet rules.

    Returns the password unchanged when it satisfies the policy so this can
    be used directly as a Pydantic ``field_validator`` body.
    """
    problems = password_problems(password)
    if problems:
        raise ValueError("Password must contain " + ", ".join(problems))
    return password
