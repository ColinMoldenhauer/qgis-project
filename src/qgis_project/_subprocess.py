"""
Subprocess-mode Project implementation.

Used when QGIS is not importable in the current Python process but a
standalone QGIS installation is available. Collects layer specs, then
serializes them to a JSON temp file and delegates execution to
_executor.py via the platform-specific QGIS Python launcher.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger

from .layer import Layer


class SubprocessProject:
    """Accumulates a layer spec and executes it via the QGIS bundled Python.

    The interface mirrors ``Project`` so user code is strategy-agnostic.
    """

    def __init__(self, file: str | None = None):
        self._layers: list[Layer] = []
        if file is not None:
            logger.warning("Loading an existing project is not supported in subprocess mode.")

    # ------------------------------------------------------------------
    # Layer management
    # ------------------------------------------------------------------

    def add_layer(self, layer: Layer | str) -> None:
        """Append a layer to the pending spec."""
        if isinstance(layer, str):
            layer = Layer(layer)
        self._layers.append(layer)

    def remove_layer(self, layer: Layer | str) -> None:
        """Remove a layer from the pending spec by path."""
        if isinstance(layer, str):
            layer = Layer(layer)
        target = layer.get_path()
        self._layers = [l for l in self._layers if l.get_path() != target]

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

    def center(self, layer=None) -> None:
        logger.warning("center() is not supported in subprocess mode.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self, output: str, action: str) -> None:
        from . import _spec
        from ._env import find_qgis_launcher

        launcher = find_qgis_launcher()
        if launcher is None:
            raise RuntimeError(
                "No QGIS launcher found. "
                "Install QGIS as a standalone application or set QGIS_PREFIX_PATH."
            )

        executor = Path(__file__).parent / "_executor.py"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_spec.to_json(self._layers, output, action))
            spec_path = f.name

        try:
            # On Windows, .bat files must be invoked through cmd.exe.
            # On other platforms the launcher is a plain executable.
            if sys.platform == "win32":
                cmd = ["cmd", "/c", launcher, str(executor), spec_path]
            else:
                cmd = [launcher, str(executor), spec_path]

            result = subprocess.run(cmd)
            if result.returncode != 0:
                raise RuntimeError(f"QGIS executor exited with code {result.returncode}")
        finally:
            os.unlink(spec_path)
