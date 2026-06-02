"""
Unit tests for _env.py — no QGIS required.
Tests path detection logic using monkeypatching and temp directories.
"""
import platform
from pathlib import Path

import pytest

from qgis_project._env import find_qgis_prefix_path


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
