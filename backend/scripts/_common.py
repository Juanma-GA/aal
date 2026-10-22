"""Shared bits of the backend scripts: UTF-8 output on any console (Windows
included), the backend on sys.path, and passwords that are asked for or read
from the environment, never taken as arguments (D17).

A password is checked against the policy (auth.password.min_length and
bcrypt's 72 bytes) as soon as it is typed: a bad one is explained and asked
again, two entries that differ ask for both again, and Ctrl+C cancels
cleanly (cancellable()). From the environment there is no retry: a bad one
ends the script with the reason.

The prompts run outside asyncio.run(): inside it, the first Ctrl+C only
cancels the main task, which a blocking getpass() never notices.
"""

import getpass
import os
import sys
from collections.abc import Callable
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.security import BCRYPT_MAX_PASSWORD_BYTES  # noqa: E402

CANCELLED_EXIT_CODE = 130


def utf8_output() -> None:
    for _stream in (sys.stdout, sys.stderr):  # UTF-8 on any console or pipe, Windows included
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def password_problem(password: str, min_length: int) -> str | None:
    """Why `password` breaks the policy, in Spanish, or None."""
    if len(password) < min_length:
        return f"La contraseña debe tener al menos {min_length} caracteres (tiene {len(password)})."
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        return f"La contraseña no puede pasar de {BCRYPT_MAX_PASSWORD_BYTES} bytes en UTF-8."
    return None


def new_password(env_name: str, prompt: str, min_length: int) -> str:
    """The password in `env_name` (checked; a bad one exits 1), or asked
    with getpass until it meets the policy and is typed twice the same.
    Without a console to ask, exits 2."""
    value = os.environ.get(env_name)
    if value:
        problem = password_problem(value, min_length)
        if problem:
            print(f"{env_name}: {problem}", file=sys.stderr)
            sys.exit(1)
        return value
    if not sys.stdin.isatty():
        print(f"{env_name} is not set and there is no console to ask for it.", file=sys.stderr)
        sys.exit(2)
    while True:
        first = getpass.getpass(f"{prompt}: ")
        problem = password_problem(first, min_length)
        if problem:
            print(f"{problem} Escríbela de nuevo.", file=sys.stderr)
            continue
        if getpass.getpass(f"{prompt} (otra vez): ") != first:
            print("Las dos entradas no coinciden. Escríbelas de nuevo.", file=sys.stderr)
            continue
        return first


def cancellable(main: Callable[[], int]) -> int:
    """main(), with Ctrl+C (or the end of the input) ending it cleanly: one
    line, no traceback, exit code 130."""
    try:
        return main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado: no se ha creado nada.", file=sys.stderr)
        return CANCELLED_EXIT_CODE
