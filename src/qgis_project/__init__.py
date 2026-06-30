# SPDX-FileCopyrightText: 2025-present Colin Moldenhauer <colin.moldenhauer@posteo.de>
#
# SPDX-License-Identifier: MIT
"""qgis-project — build QGIS projects from Python.

Launch mode
-----------
`Project` runs against QGIS in one of two ways:

- **env** — the QGIS Python bindings importable in the *current* environment
  are used in-process (a conda-forge env, or a standalone install whose bundled
  Python matches yours).
- **local** — a standalone/local QGIS application is driven out-of-process via
  its bundled Python launcher (`python-qgis.bat` / `python-qgis.sh`).

By default the mode is **auto**: `env` is used when QGIS is importable,
otherwise it falls back to `local`. Override the automatic pick either with
the `QGIS_PROJECT_LAUNCH_MODE` environment variable (`auto` / `env` /
`local`) or at runtime via :func:`set_mode`. Forcing a mode whose backend is
unavailable raises immediately (`set_mode`) or on first `Project()` (env var).
"""
import logging as _logging
import os
from typing import Literal

# Configure the package logger with a stderr handler so messages are visible
# out of the box (mirroring loguru's default). Done on the package logger only
# — never the root logger — so importing qgis_project does not hijack logging
# config for the host application. Applications can adjust the level or attach
# their own handlers via logging.getLogger("qgis_project").
_pkg_logger = _logging.getLogger(__name__)
if not _pkg_logger.handlers:
    _handler = _logging.StreamHandler()
    _handler.setFormatter(
        _logging.Formatter("%(levelname)-8s | %(name)s — %(message)s")
    )
    _pkg_logger.addHandler(_handler)
    _pkg_logger.setLevel(_logging.DEBUG)
    _pkg_logger.propagate = False

from ._env import find_qgis_launcher, find_qgis_prefix_path, setup_qgis_env

Mode = Literal["auto", "env", "local"]
_VALID_MODES = ("auto", "env", "local")


def _normalize_mode(mode: str, *, source: str) -> str:
    norm = str(mode).strip().lower()
    if norm not in _VALID_MODES:
        raise ValueError(
            f"Invalid {source} {mode!r}; expected one of {_VALID_MODES}."
        )
    return norm


# Active mode, seeded from the environment. The default of "auto" preserves the
# historical behavior (env if importable, otherwise local).
_mode: str = _normalize_mode(
    os.environ.get("QGIS_PROJECT_LAUNCH_MODE", "auto"), source="QGIS_PROJECT_LAUNCH_MODE"
)

# Cached resolved backend class (the concrete Project implementation), or None
# until first resolved. Invalidated by set_mode().
_backend = None


def _resolve_env_backend():
    """Configure and return the in-process Project class; raise if unavailable."""
    if not setup_qgis_env():
        raise ImportError(
            "Launch mode 'env' was requested but the QGIS Python bindings are "
            "not importable in this environment. Install QGIS via conda-forge "
            "into this env, or use mode 'local' / 'auto' to delegate to a "
            "standalone install."
        )
    from qgis.core import QgsApplication
    try:
        QgsApplication.setPrefixPath(find_qgis_prefix_path(), True)
    except RuntimeError:
        pass  # prefix not found (e.g. mocked qgis in unit-test env); safe to skip
    from .project import Project as _Project
    return _Project


def _resolve_local_backend():
    """Return the subprocess Project class; raise if no launcher is available."""
    if find_qgis_launcher() is None:
        raise RuntimeError(
            "Launch mode 'local' was requested but no standalone QGIS launcher "
            "(python-qgis.bat / python-qgis.sh) could be found. Install a "
            "standalone QGIS application or set QGIS_PREFIX_PATH, or use mode "
            "'env' / 'auto'."
        )
    from ._subprocess import SubprocessProject
    return SubprocessProject


def _resolve_backend():
    """Resolve (and cache) the Project backend for the active mode."""
    global _backend
    if _backend is not None:
        return _backend

    if _mode == "env":
        _backend = _resolve_env_backend()
    elif _mode == "local":
        _backend = _resolve_local_backend()
    else:  # auto: prefer in-process, fall back to subprocess
        try:
            _backend = _resolve_env_backend()
        except ImportError:
            if find_qgis_launcher() is not None:
                _backend = _resolve_local_backend()
            else:
                raise ImportError(
                    "QGIS not found. Install QGIS via conda-forge into this "
                    "environment or install a standalone QGIS application."
                )
    return _backend


def set_mode(mode: Mode) -> None:
    """Override the QGIS launch mode at runtime.

    Parameters
    ----------
    mode : {"auto", "env", "local"}
        - `"auto"`  — use the env bindings if importable, else a local install.
        - `"env"`   — force the QGIS bindings in the current environment
          (in-process). Raises :class:`ImportError` if they are not importable.
        - `"local"` — force a standalone/local QGIS install (out-of-process
          via its launcher). Raises :class:`RuntimeError` if no launcher exists.

    Forcing `"env"` or `"local"` resolves the backend immediately so an
    unavailable choice fails fast. Call this before constructing a `Project`.
    """
    global _mode, _backend
    _mode = _normalize_mode(mode, source="mode")
    _backend = None  # invalidate cache so the next Project() re-resolves
    if _mode != "auto":
        _resolve_backend()  # fail fast if the forced backend is unavailable


def get_mode() -> str:
    """Return the active launch mode (`"auto"`, `"env"`, or `"local"`)."""
    return _mode


class Project:
    """Build a QGIS project. Dispatches to the backend for the active mode.

    This is a thin factory: each instantiation resolves the concrete backend
    (in-process or subprocess) for the current :func:`get_mode`, so that
    `from qgis_project import Project` keeps honoring later :func:`set_mode`
    calls.
    """

    def __new__(cls, *args, **kwargs):
        return _resolve_backend()(*args, **kwargs)


from .layer import Layer, ProcessingOp, RasterLayer, WebLayer
from .utils import list_raster_variables
from .style import (
    Style,
    RasterStyle,
    RasterStyleBW,
    RasterStyleSinglePseudocolor,
    RasterStyleMultiBandColor,
    RasterStylePaletted,
    VectorStyle,
    VectorStyleSingleSymbol,
    VectorStyleCategorized,
    VectorStyleGraduated,
    VectorLabels,
)
