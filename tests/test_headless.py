"""
Running without a display (over SSH, in CI): Qt must not need one.

QGIS starts a Qt application even with the GUI disabled, and without a display
Qt's default platform aborts the process. The in-process `Project` therefore
defaults to the offscreen platform when there is no display, and keeps that
choice out of the QGIS it launches with `open`.
"""
import os
import subprocess
import sys

import pytest

from qgis_project import project as project_module

NO_DISPLAY = ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM")


@pytest.fixture
def linux_without_display(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(project_module, "_chose_offscreen", False)
    for name in NO_DISPLAY:
        monkeypatch.delenv(name, raising=False)


def test_no_display_means_offscreen(linux_without_display):
    assert project_module._ensure_qt_platform() is True
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"

@pytest.mark.parametrize("name", ["DISPLAY", "WAYLAND_DISPLAY"])
def test_a_display_is_used(linux_without_display, monkeypatch, name):
    monkeypatch.setenv(name, ":0")
    assert project_module._ensure_qt_platform() is False
    assert "QT_QPA_PLATFORM" not in os.environ

def test_a_platform_the_user_chose_is_kept(linux_without_display, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "minimal")
    assert project_module._ensure_qt_platform() is False
    assert os.environ["QT_QPA_PLATFORM"] == "minimal"

@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_windows_and_macos_are_left_alone(linux_without_display, monkeypatch, platform):
    monkeypatch.setattr(sys, "platform", platform)
    assert project_module._ensure_qt_platform() is False

def test_the_launched_gui_does_not_inherit_our_offscreen(linux_without_display):
    project_module._ensure_qt_platform()
    assert "QT_QPA_PLATFORM" not in project_module._gui_environment()

def test_the_launched_gui_keeps_a_platform_the_user_chose(linux_without_display, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "wayland")
    project_module._ensure_qt_platform()
    assert project_module._gui_environment()["QT_QPA_PLATFORM"] == "wayland"


@pytest.mark.qgis
@pytest.mark.skipif(sys.platform != "linux", reason="a missing display is a Linux matter")
def test_a_project_builds_without_a_display(qgis_app, tmp_path):
    """The real thing, in a fresh interpreter: Qt aborts the process, not raises."""
    env = {k: v for k, v in os.environ.items() if k not in NO_DISPLAY}
    out = tmp_path / "headless.qgz"
    script = (
        "from qgis_project import Project\n"
        f"Project(crs=4326).save({str(out)!r})\n"
        "import os; os._exit(0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert out.exists()
