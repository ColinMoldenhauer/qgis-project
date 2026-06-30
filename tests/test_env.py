"""
Unit tests for _env.py — no QGIS required.
Tests path detection logic using monkeypatching and temp directories.
"""
import platform
from pathlib import Path
from types import SimpleNamespace

import pytest

import qgis_project._env as _env
from qgis_project._env import (
    _find_qgis_python,
    _is_sandboxed_install,
    find_qgis_launcher,
    find_qgis_prefix_path,
)


def test_env_var_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("QGIS_PREFIX_PATH", str(tmp_path))
    assert find_qgis_prefix_path() == str(tmp_path)


def test_env_var_beats_conda_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv("QGIS_PREFIX_PATH", "/explicit")
    monkeypatch.setenv("CONDA_PREFIX", str(tmp_path))
    assert find_qgis_prefix_path() == "/explicit"


def test_conda_prefix_used_when_bindings_present(monkeypatch, tmp_path):
    monkeypatch.delenv("QGIS_PREFIX_PATH", raising=False)
    monkeypatch.setenv("CONDA_PREFIX", str(tmp_path))

    if platform.system() == "Windows":
        bindings_dir = tmp_path / "Library" / "python"
        expected = str(tmp_path / "Library")
    else:
        bindings_dir = tmp_path / "share" / "qgis" / "python"
        expected = str(tmp_path)

    bindings_dir.mkdir(parents=True)
    assert find_qgis_prefix_path() == expected


def test_conda_prefix_skipped_when_no_bindings(monkeypatch, tmp_path):
    """CONDA_PREFIX set but QGIS not installed there: should fall through."""
    monkeypatch.delenv("QGIS_PREFIX_PATH", raising=False)
    monkeypatch.setenv("CONDA_PREFIX", str(tmp_path))
    # tmp_path has no QGIS bindings and no standalone install on the path,
    # so expect RuntimeError.
    if platform.system() == "Windows":
        monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
        monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path))
    with pytest.raises(RuntimeError, match="Could not find"):
        find_qgis_prefix_path()


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only")
def test_windows_programfiles_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("QGIS_PREFIX_PATH", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path))

    # Create a fake QGIS install layout
    qgis_dir = tmp_path / "QGIS 3.99.0" / "apps" / "qgis"
    qgis_dir.mkdir(parents=True)
    result = find_qgis_prefix_path()
    assert Path(result) == qgis_dir


def test_raises_when_nothing_found(monkeypatch, tmp_path):
    monkeypatch.delenv("QGIS_PREFIX_PATH", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    if platform.system() == "Windows":
        monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
        monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path))
    with pytest.raises(RuntimeError, match="Could not find"):
        find_qgis_prefix_path()


# ---------------------------------------------------------------------------
# Sandbox classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/snap/qgis/current/bin/qgis",
    "/var/lib/flatpak/app/org.qgis.qgis/current/active/files/bin/qgis",
    "/home/user/Apps/QGIS-3.34.AppImage",
    "/tmp/.mount_QGISabcXYZ/usr/bin/qgis",
])
def test_sandboxed_install_detected(path):
    assert _is_sandboxed_install(path) is True


@pytest.mark.parametrize("path", [
    "/usr/bin/qgis",
    "/usr/local/bin/qgis",
    "/opt/qgis/bin/qgis",
])
def test_non_sandboxed_install_not_flagged(path):
    assert _is_sandboxed_install(path) is False


# ---------------------------------------------------------------------------
# Linux interpreter probe
# ---------------------------------------------------------------------------

def _fake_run(ok_for):
    """Build a subprocess.run stub that 'imports qgis' only for `ok_for`."""
    def run(cmd, *args, **kwargs):
        rc = 0 if cmd[0] == ok_for else 1
        return SimpleNamespace(returncode=rc, stdout=b"", stderr=b"")
    return run


def test_find_qgis_python_returns_importable_interpreter(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").touch()
    (bin_dir / "python3.11").touch()
    py3 = str(bin_dir / "python3")

    monkeypatch.setattr(_env.subprocess, "run", _fake_run(py3))
    # python3 (the default symlink) is probed first and succeeds.
    assert _find_qgis_python(tmp_path) == py3


def test_find_qgis_python_skips_interpreter_without_bindings(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").touch()
    (bin_dir / "python3.11").touch()
    py311 = str(bin_dir / "python3.11")

    # Only the versioned interpreter can import qgis; the bare symlink cannot.
    monkeypatch.setattr(_env.subprocess, "run", _fake_run(py311))
    assert _find_qgis_python(tmp_path) == py311


def test_find_qgis_python_returns_none_when_nothing_imports(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").touch()

    monkeypatch.setattr(_env.subprocess, "run", _fake_run("nonexistent"))
    assert _find_qgis_python(tmp_path) is None


def test_find_qgis_python_returns_none_when_no_interpreter(tmp_path):
    (tmp_path / "bin").mkdir()
    assert _find_qgis_python(tmp_path) is None


# ---------------------------------------------------------------------------
# Linux launcher fallback wiring
# ---------------------------------------------------------------------------

def test_launcher_falls_back_to_system_python_on_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(_env.platform, "system", lambda: "Linux")
    monkeypatch.setenv("QGIS_PREFIX_PATH", str(tmp_path))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").touch()
    py3 = str(bin_dir / "python3")

    # No qgis on PATH and no wrapper script: must fall through to the probe.
    monkeypatch.setattr(_env.shutil, "which", lambda _: None)
    monkeypatch.setattr(_env.subprocess, "run", _fake_run(py3))
    assert find_qgis_launcher() == py3


def test_launcher_returns_none_for_sandboxed_qgis(monkeypatch, tmp_path):
    monkeypatch.setattr(_env.platform, "system", lambda: "Linux")
    monkeypatch.setenv("QGIS_PREFIX_PATH", str(tmp_path))
    (tmp_path / "bin").mkdir()

    # which qgis resolves into a snap → bail before probing any interpreter.
    monkeypatch.setattr(_env.shutil, "which", lambda _: "/snap/bin/qgis")

    def _fail(*a, **k):
        raise AssertionError("interpreter probe must not run for sandboxed installs")

    monkeypatch.setattr(_env.subprocess, "run", _fail)
    assert find_qgis_launcher() is None
