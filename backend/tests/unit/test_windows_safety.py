"""The backend's scripts and tests on Windows (adapted from brdp-manager).

- A script that prints writes UTF-8 whatever the console: on Windows a
  Python whose output is a pipe or a file uses the console's code page
  (cp1252) and an accent, "→" or a rule's text would come out wrong or stop
  the script with UnicodeEncodeError. Every script that prints reconfigures
  stdout/stderr to UTF-8 (or writes UTF-8 bytes itself).
- Every text file is opened with encoding="utf-8": on Windows the default
  is cp1252, not UTF-8.
- No Linux-only location ("/tmp", .venv/bin) and no program Windows lacks
  (ps, xmllint, psql, a shell; shell=True, os.system) in the code.
- No script takes a secret (password, token, key) as an argument: it asks
  for it (getpass) or reads it from the environment.
- The lockfiles are uv --universal with hashes on every requirement, so the
  same file installs on Windows and Linux.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SCRIPTS = sorted((BACKEND / "scripts").glob("*.py"))
RECONFIGURE = 'for _stream in (sys.stdout, sys.stderr):  # UTF-8 on any console or pipe, Windows included\n    _stream.reconfigure(encoding="utf-8", errors="backslashreplace")\n'


def _prints(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "print":
                return True
            # sys.stdout.write(...) and sys.stdout.buffer.write(...)
            if isinstance(f, ast.Attribute) and f.attr == "write":
                target = f.value
                if isinstance(target, ast.Attribute) and target.attr == "buffer":
                    target = target.value
                if isinstance(target, ast.Attribute) and target.attr in ("stdout", "stderr"):
                    return True
    return False


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_a_script_that_prints_writes_utf8(script):
    source = script.read_text(encoding="utf-8")
    if not _prints(source):
        pytest.skip("prints nothing")
    handled = 'reconfigure(encoding="utf-8"' in source or "sys.stdout.buffer.write" in source or "utf8_output()" in source
    assert handled, f"{script.name} prints but does not reconfigure stdout to UTF-8 (see the module docstring)"


def test_the_reconfigure_lines_never_fail_on_a_cp1252_console():
    code = "import sys\n" + RECONFIGURE + 'print("→ áéíóú ✓ — CUF 000000 «cita»")\n'
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        check=False,
    )
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    assert out.stdout.decode("utf-8").strip() == "→ áéíóú ✓ — CUF 000000 «cita»"


def _text_io_without_encoding(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        if name not in ("open", "read_text", "write_text"):
            continue
        keywords = {k.arg for k in node.keywords}
        modes = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str) and set(a.value) <= set("rwabxt+")]
        modes += [k.value.value for k in node.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
        if any("b" in m for m in modes):
            continue
        encoding = next((k.value for k in node.keywords if k.arg == "encoding"), None)
        if not (isinstance(encoding, ast.Constant) and str(encoding.value).lower().replace("_", "-") in ("utf-8", "utf8")):
            found.append(f"{path.relative_to(BACKEND)}:{node.lineno} {name}()")
    return found


def _python_files() -> list[Path]:
    return [p for d in ("app", "scripts", "tests", "alembic") for p in (BACKEND / d).rglob("*.py")]


def test_no_text_file_is_opened_without_utf8():
    found = [hit for p in _python_files() for hit in _text_io_without_encoding(p)]
    assert found == [], 'open as text without encoding="utf-8" (cp1252 on Windows): ' + ", ".join(found)


def test_the_encoding_scanner_on_its_own_fixtures(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        'open("a")\nopen("a", encoding="latin-1")\nPath("a").read_text()\n'
        'open("a", encoding="utf-8")\nopen("a", "rb")\nPath("a").write_text("x", encoding="utf-8")\n',
        encoding="utf-8",
    )
    original = globals()["BACKEND"]
    globals()["BACKEND"] = tmp_path
    try:
        found = _text_io_without_encoding(sample)
    finally:
        globals()["BACKEND"] = original
    assert [hit.split(":")[1].split()[0] for hit in found] == ["1", "2", "3"]


# Linux-only locations and programs, as string literals in the code. Built
# by joining so this file does not flag itself.
_LINUX_PATHS = ("/" + "tmp", ".venv/" + "bin")
_LINUX_PROGRAMS = {"ps", "xmllint", "psql", "sh", "bash", "/bin/sh", "/bin/bash"}
_SUBPROCESS_CALLS = {"run", "call", "check_call", "check_output", "Popen", "create_subprocess_exec", "create_subprocess_shell"}


def _linux_only(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(node.value == p or node.value.startswith(p + "/") or p in node.value for p in _LINUX_PATHS if p.startswith(".")) or any(
                node.value == p or node.value.startswith(p + "/") for p in _LINUX_PATHS if p.startswith("/")
            ):
                found.append(f"{node.lineno}: path {node.value!r}")
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        if name == "system" and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "os":
            found.append(f"{node.lineno}: os.system")
        if name not in _SUBPROCESS_CALLS:
            continue
        if name == "create_subprocess_shell" or any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value for k in node.keywords):
            found.append(f"{node.lineno}: a shell")
        if node.args:
            first = node.args[0]
            program = first.elts[0] if isinstance(first, (ast.List, ast.Tuple)) and first.elts else first
            if isinstance(program, ast.Constant) and program.value in _LINUX_PROGRAMS:
                found.append(f"{node.lineno}: program {program.value!r}")
    return found


def test_the_linux_only_scanner_on_its_own_fixtures():
    tmp = "/" + "tmp"
    venv = ".venv/" + "bin"
    assert _linux_only(f'shot = "{tmp}/x.png"')
    assert _linux_only(f'python = "backend/{venv}/python"')
    assert _linux_only('subprocess.run(["ps", "-eo", "pid"])')
    assert _linux_only('subprocess.run(["psql", "-c", "select 1"])')
    assert _linux_only('subprocess.run("ls", shell=True)')
    assert _linux_only('os.system("ls")')
    assert not _linux_only('subprocess.run([sys.executable, "-m", "alembic"])')
    assert not _linux_only('tempfile.gettempdir()')
    assert not _linux_only('"tmpl" + "/tmpfile"')


def test_no_linux_only_paths_or_programs():
    this = Path(__file__).resolve()
    found = [f"{p.relative_to(BACKEND)}:{hit}" for p in _python_files() if p.resolve() != this for hit in _linux_only(p.read_text(encoding="utf-8"))]
    assert found == [], "Linux-only path or program (breaks on Windows): " + ", ".join(found)


# Secrets as arguments: an option or a positional whose name says secret.
_SECRET_WORDS = ("password", "passwd", "pwd", "secret", "token", "apikey", "api-key", "api_key", "private-key", "private_key")


def _secret_arguments(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"):
            continue
        names = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        names += [k.value.value for k in node.keywords if k.arg == "dest" and isinstance(k.value, ast.Constant)]
        if any(word in name.lower() for name in names for word in _SECRET_WORDS):
            found.append(f"{node.lineno}: {', '.join(names)}")
    return found


def test_the_secret_argument_scanner_on_its_own_fixtures():
    assert _secret_arguments('parser.add_argument("--password")')
    assert _secret_arguments('parser.add_argument("-t", "--api-token")')
    assert _secret_arguments('parser.add_argument("pw", dest="admin_password")')
    assert not _secret_arguments('parser.add_argument("--email")')


def test_no_script_takes_a_secret_as_an_argument():
    found = [f"{p.name}:{hit}" for p in SCRIPTS for hit in _secret_arguments(p.read_text(encoding="utf-8"))]
    assert found == [], "a secret as an argument (ask with getpass or read the environment): " + ", ".join(found)
    for script in SCRIPTS:
        source = script.read_text(encoding="utf-8")
        assert not ("sys.argv" in source and any(w in source.lower() for w in ("password", "secret", "token"))), (
            f"{script.name} reads sys.argv and handles a secret: ask with getpass or read the environment"
        )


@pytest.mark.parametrize("lockfile", ["requirements.lock.txt", "requirements-dev.lock.txt"])
def test_lockfiles_are_universal_with_hashes(lockfile):
    text = (BACKEND / lockfile).read_text(encoding="utf-8")
    header = "\n".join(text.splitlines()[:3])
    assert "uv pip compile" in header and "--universal" in header and "--generate-hashes" in header
    requirements = [line for line in text.splitlines() if line and not line.startswith((" ", "#"))]
    assert requirements, "no requirements"
    blocks = text.split("\n")
    for i, line in enumerate(blocks):
        if line in requirements:
            assert i + 1 < len(blocks) and blocks[i + 1].strip().startswith("--hash=sha256:"), f"{lockfile}: {line} has no hash"
    # Resolved for Windows too (one lock for both systems): markers name it.
    assert "'win32'" in text and "platform_machine == 'AMD64'" in text
