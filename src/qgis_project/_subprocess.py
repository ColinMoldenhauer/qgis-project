"""
Subprocess-mode Project implementation.

Used when QGIS is not importable in the current Python process but a
standalone QGIS installation is available. Collects layer specs, then
serializes them to a JSON temp file and delegates execution to
_executor.py via the platform-specific QGIS Python launcher.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .layer import Layer, ProcessingOp, WebLayer, layer_from_path
from .utils import normalize_crs

logger = logging.getLogger(__name__)


class SubprocessProject:
    """Accumulates a layer spec and executes it via the QGIS bundled Python.

    The interface mirrors `Project` so user code is strategy-agnostic.
    """

    def __init__(self, file: str | None = None, crs: str | int | None = None):
        self._layers: list[Layer | WebLayer] = []
        self._operations: list[ProcessingOp] = []
        self._crs: str | None = None
        self._group_states: list[dict] = []
        if crs is not None:
            self.set_crs(crs)
        if file is not None:
            logger.warning("Loading an existing project is not supported in subprocess mode.")

    # ------------------------------------------------------------------
    # Layer management
    # ------------------------------------------------------------------

    def add_layer(self, layer: Layer | WebLayer | str, **kwargs) -> None:
        """Append a layer to the pending spec.

        When *layer* is a string path, extra keyword arguments are forwarded to
        the layer constructor; a :class:`RasterLayer` is built automatically when
        a raster-specific keyword is given (see :meth:`Project.add_layer`).
        """
        if isinstance(layer, str):
            layer = layer_from_path(layer, **kwargs)
        self._layers.append(layer)

    def remove_layer(self, layer: Layer | str) -> None:
        """Remove a layer from the pending spec by path."""
        if isinstance(layer, str):
            layer = Layer(layer)
        target = layer.get_path()
        self._layers = [l for l in self._layers if l.get_path() != target]

    def set_crs(self, crs: str | int) -> None:
        """Set the project's coordinate reference system.

        Parameters
        ----------
        crs : str or int
            EPSG integer (e.g. `3857`) or authority string (e.g. `"EPSG:3857"`).
        """
        self._crs = normalize_crs(crs)

    def process(self, algorithm: str, params: dict, name: str = "", group=None, visible: bool = True) -> None:
        """Queue a QGIS Processing algorithm; its result is added to the project on save.

        Parameters
        ----------
        algorithm : str
            QGIS processing algorithm identifier, e.g. `"native:buffer"`.
        params : dict
            Algorithm parameters. Must include `"INPUT"` and typically
            `"OUTPUT"`. Use `"OUTPUT": "memory:"` for in-memory vector
            results, or a file path for persistent outputs.
        name : str
            Name for the result layer. Defaults to the algorithm tail.
        group : str or list of str or None
            Layer group path.
        visible : bool
            Whether the result layer is visible on project open.
        """
        self._operations.append(ProcessingOp(
            algorithm=algorithm,
            params=params,
            name=name,
            group=group,
            visible=visible,
        ))

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def save(self, file: str) -> None:
        """Serialize the spec and run the executor to produce a .qgz file."""
        self._run(str(file), action="save")

    def open(self, file: str | None = None) -> None:
        """Save the project and open it in QGIS."""
        if file is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".qgz", delete=False)
            file = tmp.name
            tmp.close()
        self._run(str(file), action="save_and_open")

    def exit(self) -> None:
        pass  # nothing to clean up in subprocess mode

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def print_layer_tree(self) -> None:
        """Print the pending layer spec (no live QGIS tree available)."""
        for layer in self._layers:
            group = layer.group
            if group is None:
                print(layer.get_layer_name())
            else:
                path = [group] if isinstance(group, str) else group
                indent = "  " * len(path)
                print(f"{indent}{layer.get_layer_name()}")

    def snapshot(self, **_) -> None:
        raise NotImplementedError(
            "snapshot() requires an in-process QGIS (Strategy 1 or 3). "
            "In subprocess mode there is no live canvas to capture."
        )

    def center(self, layer=None) -> None:
        logger.warning("center() is not supported in subprocess mode.")

    def zoom_to_all(self) -> None:
        logger.warning("zoom_to_all() is not supported in subprocess mode; zoom is applied automatically on save.")

    def collapse_group(self, *path: str) -> None:
        """Queue a group collapse; applied when the project is saved.

        Parameters
        ----------
        *path : str
            Group name sequence, e.g. `collapse_group("terrain")` or
            `collapse_group("terrain", "raw")` for a nested group.
        """
        self._group_states.append({"path": list(path), "expanded": False})

    def expand_group(self, *path: str) -> None:
        """Queue a group expand; applied when the project is saved."""
        self._group_states.append({"path": list(path), "expanded": True})

    def collapse_all(self) -> None:
        """Queue collapse of all groups; applied when the project is saved."""
        self._group_states.append({"path": None, "expanded": False})

    def expand_all(self) -> None:
        """Queue expand of all groups; applied when the project is saved."""
        self._group_states.append({"path": None, "expanded": True})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _stage_package(dest_parent: str) -> Path:
        """Copy the qgis_project package into *dest_parent* and return its path.

        The executor needs to ``import qgis_project`` in QGIS's interpreter, but
        we must NOT expose the rest of the host interpreter's import roots to it.
        Pointing PYTHONPATH at the directory that *contains* the installed
        package would, when the package lives in a shared site-packages, drag
        every other package there (numpy, GDAL, Qt, …) onto QGIS's path — built
        for the wrong Python ABI — and break ``import`` inside QGIS. qgis_project
        has no runtime dependencies of its own, so copying just the package into
        an isolated directory gives the executor everything it needs and nothing
        it doesn't.
        """
        import qgis_project as _pkg

        pkg_dir = Path(_pkg.__file__).parent
        staged = Path(dest_parent) / pkg_dir.name
        shutil.copytree(
            pkg_dir,
            staged,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        return staged

    def _run(self, output: str, action: str) -> None:
        from ._env import find_qgis_launcher

        launcher = find_qgis_launcher()
        if launcher is None:
            raise RuntimeError(
                "No QGIS launcher found. "
                "Install QGIS as a standalone application or set QGIS_PREFIX_PATH."
            )

        from . import _spec
        spec_dict = _spec.to_dict(self._layers, output, action)
        if self._crs is not None:
            spec_dict["crs"] = self._crs
        if self._operations:
            spec_dict["operations"] = [dataclasses.asdict(op) for op in self._operations]
        if self._group_states:
            spec_dict["group_states"] = self._group_states

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(spec_dict, f, indent=2)
            spec_path = f.name

        # Stage qgis_project into an isolated directory so the only import root
        # exposed to QGIS's interpreter is the package itself (see _stage_package).
        staging = tempfile.mkdtemp(prefix="qgis_project_")

        try:
            staged_pkg = self._stage_package(staging)
            executor = staged_pkg / "_executor.py"

            env = os.environ.copy()
            # Replace, don't extend: a host PYTHONPATH (e.g. a conda env's
            # site-packages) must not leak into QGIS's interpreter, where it
            # would shadow QGIS's own ABI-matched numpy/GDAL/Qt and break import.
            env["PYTHONPATH"] = staging
            # The executor runs in QGIS's bundled Python, where qgis is importable,
            # so it must use the in-process backend. Pin the mode explicitly so a
            # parent QGIS_PROJECT_LAUNCH_MODE=local does not get inherited and recurse
            # into another subprocess launch.
            env["QGIS_PROJECT_LAUNCH_MODE"] = "env"

            # On Windows, .bat files must be invoked through cmd.exe.
            # On other platforms the launcher is a plain executable.
            if sys.platform == "win32":
                cmd = ["cmd", "/c", launcher, str(executor), spec_path]
            else:
                cmd = [launcher, str(executor), spec_path]

            result = subprocess.run(cmd, env=env)
            if result.returncode != 0:
                raise RuntimeError(f"QGIS executor exited with code {result.returncode}")
        finally:
            os.unlink(spec_path)
            shutil.rmtree(staging, ignore_errors=True)
