"""Passwords in create_admin_user.py and seed_dev_data.py (E03, fleco of
E01): checked as soon as they are typed, asked again when they break the
policy or the two entries differ, Ctrl+C cancels without a traceback, and a
bad one in the environment ends the script with no retry."""

import sys

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts"))

import _common  # noqa: E402

MIN = 12
GOOD = "Una-contraseña-buena"


@pytest.fixture
def console(monkeypatch, capsys):
    """Feeds getpass() the given entries, in order; returns the prompts it
    was asked with."""
    monkeypatch.delenv("AAL_TEST_PASSWORD", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    prompts: list[str] = []

    def feed(*entries):
        queue = list(entries)

        def fake_getpass(prompt):
            prompts.append(prompt)
            item = queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

        monkeypatch.setattr(_common.getpass, "getpass", fake_getpass)
        return prompts

    return feed


def ask():
    return _common.new_password("AAL_TEST_PASSWORD", "Contraseña", MIN)


def test_a_good_password_typed_twice_is_accepted(console):
    prompts = console(GOOD, GOOD)
    assert ask() == GOOD
    assert len(prompts) == 2


def test_a_short_password_is_explained_and_asked_again_at_once(console, capsys):
    prompts = console("corta", GOOD, GOOD)
    assert ask() == GOOD
    # The short one was refused before the confirmation was asked.
    assert prompts == ["Contraseña: ", "Contraseña: ", "Contraseña (otra vez): "]
    err = capsys.readouterr().err
    assert f"al menos {MIN} caracteres" in err and "corta" not in err


def test_over_72_bytes_is_explained_and_asked_again(console, capsys):
    long = "ñ" * 40  # 40 characters, 80 bytes
    console(long, GOOD, GOOD)
    assert ask() == GOOD
    assert "72 bytes" in capsys.readouterr().err


def test_two_different_entries_ask_for_both_again(console, capsys):
    prompts = console(GOOD, GOOD + "x", GOOD, GOOD)
    assert ask() == GOOD
    assert len(prompts) == 4
    assert "no coinciden" in capsys.readouterr().err


def test_ctrl_c_cancels_cleanly(console, capsys):
    console(KeyboardInterrupt())
    assert _common.cancellable(ask) == _common.CANCELLED_EXIT_CODE
    err = capsys.readouterr().err
    assert "Cancelado" in err and "Traceback" not in err


def test_end_of_input_cancels_cleanly_too(console, capsys):
    console(GOOD, EOFError())
    assert _common.cancellable(ask) == _common.CANCELLED_EXIT_CODE


def test_a_bad_password_in_the_environment_exits_with_the_reason(monkeypatch, capsys):
    monkeypatch.setenv("AAL_TEST_PASSWORD", "corta")
    with pytest.raises(SystemExit) as exc:
        ask()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "AAL_TEST_PASSWORD" in err and f"al menos {MIN}" in err and "corta" not in err


def test_a_good_password_in_the_environment_is_used_without_asking(monkeypatch):
    monkeypatch.setenv("AAL_TEST_PASSWORD", GOOD)
    monkeypatch.setattr(_common.getpass, "getpass", lambda prompt: pytest.fail("asked"))
    assert ask() == GOOD


def test_without_a_console_it_exits_2(monkeypatch):
    monkeypatch.delenv("AAL_TEST_PASSWORD", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    with pytest.raises(SystemExit) as exc:
        ask()
    assert exc.value.code == 2


@pytest.mark.parametrize("script", ["create_admin_user.py", "seed_dev_data.py"])
def test_both_scripts_use_the_checked_prompt_and_the_cancel_wrapper(script):
    text = (_common.BACKEND / "scripts" / script).read_text(encoding="utf-8")
    assert "new_password(" in text and "cancellable(main)" in text
    # The prompts never run inside asyncio.run() (Ctrl+C would only cancel
    # the task): no getpass and no new_password inside an async def.
    for block in text.split("async def ")[1:]:
        body = block.split("\ndef ")[0]
        assert "new_password(" not in body and "getpass" not in body
