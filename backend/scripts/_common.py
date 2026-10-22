"""Shared bits of the backend scripts: UTF-8 output on any console (Windows
included), the backend on sys.path, and secrets that are asked for or read
from the environment, never taken as arguments (D17)."""

import getpass
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def utf8_output() -> None:
    for _stream in (sys.stdout, sys.stderr):  # UTF-8 on any console or pipe, Windows included
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def secret(env_name: str, prompt: str, *, confirm: bool = True) -> str:
    """The value of `env_name`, or asked with getpass (twice when
    `confirm`). Never echoed, never an argument."""
    value = os.environ.get(env_name)
    if value:
        return value
    if not sys.stdin.isatty():
        print(f"{env_name} is not set and there is no console to ask for it.", file=sys.stderr)
        sys.exit(2)
    value = getpass.getpass(f"{prompt}: ")
    if confirm and value != getpass.getpass(f"{prompt} (otra vez): "):
        print("Las dos entradas no coinciden.", file=sys.stderr)
        sys.exit(1)
    return value
