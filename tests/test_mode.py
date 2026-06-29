"""
Unit tests for the launch-mode override (env var + set_mode).

These exercise the resolution/validation logic without needing a real QGIS
install by monkeypatching the backend resolvers on the package module.
"""
import importlib

import pytest

import qgis_project


@pytest.fixture
def restore_mode():
    """Restore the active mode/backend cache after a test mutates it."""
    saved_mode = qgis_project.get_mode()
    saved_backend = qgis_project._backend
    yield
    qgis_project._mode = saved_mode
    qgis_project._backend = saved_backend


def test_default_mode_is_auto():
    assert qgis_project.get_mode() == "auto"


def test_invalid_mode_raises(restore_mode):
    with pytest.raises(ValueError, match="Invalid mode"):
        qgis_project.set_mode("standalone")


def test_set_mode_normalizes_case(monkeypatch, restore_mode):
    monkeypatch.setattr(qgis_project, "_resolve_env_backend", lambda: object())
    qgis_project.set_mode("ENV")
    assert qgis_project.get_mode() == "env"


def test_force_env_resolves_env_backend(monkeypatch, restore_mode):
    sentinel = object()
    monkeypatch.setattr(qgis_project, "_resolve_env_backend", lambda: sentinel)
    qgis_project.set_mode("env")
    assert qgis_project._resolve_backend() is sentinel


def test_force_local_resolves_local_backend(monkeypatch, restore_mode):
    sentinel = object()
    monkeypatch.setattr(qgis_project, "_resolve_local_backend", lambda: sentinel)
    qgis_project.set_mode("local")
    assert qgis_project._resolve_backend() is sentinel


def test_force_env_unavailable_fails_fast(monkeypatch, restore_mode):
    def boom():
        raise ImportError("no bindings")

    monkeypatch.setattr(qgis_project, "_resolve_env_backend", boom)
    with pytest.raises(ImportError, match="no bindings"):
        qgis_project.set_mode("env")


def test_force_local_unavailable_fails_fast(monkeypatch, restore_mode):
    def boom():
        raise RuntimeError("no launcher")

    monkeypatch.setattr(qgis_project, "_resolve_local_backend", boom)
    with pytest.raises(RuntimeError, match="no launcher"):
        qgis_project.set_mode("local")


def test_auto_falls_back_to_local(monkeypatch, restore_mode):
    sentinel = object()

    def no_env():
        raise ImportError("not importable")

    monkeypatch.setattr(qgis_project, "_resolve_env_backend", no_env)
    monkeypatch.setattr(qgis_project, "_resolve_local_backend", lambda: sentinel)
    monkeypatch.setattr(qgis_project, "find_qgis_launcher", lambda: "python-qgis.bat")
    qgis_project.set_mode("auto")
    assert qgis_project._resolve_backend() is sentinel


def test_project_factory_dispatches_to_backend(monkeypatch, restore_mode):
    class FakeBackend:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    monkeypatch.setattr(qgis_project, "_resolve_env_backend", lambda: FakeBackend)
    qgis_project.set_mode("env")
    proj = qgis_project.Project(crs=3857)
    assert isinstance(proj, FakeBackend)
    assert proj.kwargs == {"crs": 3857}
