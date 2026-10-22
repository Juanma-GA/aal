"""The password policy (parameter "auth.password"): a refusal names the
rule, the password is never cut or echoed (HR6/HR7)."""

from fastapi import HTTPException, status

from app.core.errors import error_detail
from app.core.security import BCRYPT_MAX_PASSWORD_BYTES


def check_new_password(password: str, policy: dict) -> None:
    if len(password) < policy["min_length"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error_detail("password_too_short", min_length=policy["min_length"]),
        )
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error_detail("password_too_long", max_bytes=BCRYPT_MAX_PASSWORD_BYTES),
        )
