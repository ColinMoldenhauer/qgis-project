"""
Module to handle QGIS project functionality.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from loguru import logger
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsProject,
    QgsRasterLayer,
    QgsReferencedRectangle,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.gui import QgsLayerTreeMapCanvasBridge, QgsMapCanvas

from qgis_project.layer import Layer, WebLayer
from qgis_project.utils import add_or_get_group, get_layer_by_idx, layer_exists_by_path, normalize_crs, remove_layer_by_path


class Project:
    def __init__(self, file: str | None = None, crs: str | int | None = None,
                 data_dir: str | Path | None = None):
        existing = QgsApplication.instance()
        if existing is None:
            self._application = QgsApplication([], False)
            self._application.initQgis()
            self._owns_app = True
        else:
            self._application = existing
            self._owns_app = False

        self._project = QgsProject.instance()
        self._canvas = QgsMapCanvas()
        # Bridge keeps the canvas in sync with the project layer tree so that
        # layers added via addMapLayer() appear on the canvas automatically.
        self._bridge = QgsLayerTreeMapCanvasBridge(
            self._project.layerTreeRoot(), self._canvas
        )
        self._canvas.resize(800, 600)
        self._processing_initialized = False
        self._data_dir: Path | None = Path(data_dir) if data_dir is not None else None
        self._auto_output_idx = 0
        if file is not None:
            self._project.read(file)
        if crs is not None:
            self.set_crs(crs)

    def _add_layer(self, layer: Layer | WebLayer):
        """Add a layer to the underlying project."""
        if isinstance(layer, WebLayer):
            if layer.provider == "WFS":
                qgis_layer = QgsVectorLayer(layer.uri, layer.get_layer_name(), "WFS")
            else:
                qgis_layer = QgsRasterLayer(layer.uri, layer.get_layer_name(), layer.provider)
        else:
            if not os.path.exists(layer.file):
                logger.error(f"File does not exist: {layer.file}")
                return

            # Try vector first, then raster — delegates format detection to
            # GDAL/OGR so any format they support works without an extension list.
            name = layer.get_layer_name()
            qgis_layer = QgsVectorLayer(layer.file, name, "ogr")
            if not qgis_layer.isValid():
                qgis_layer = QgsRasterLayer(layer.file, name)
            if not qgis_layer.isValid():
                logger.error(f"Unsupported or unreadable file: {layer.file}")
                return

        layer.set_qgis_layer(qgis_layer)

        if not qgis_layer.isValid():
            source = layer.uri if isinstance(layer, WebLayer) else layer.file
            logger.error(f"Failed to load layer: {source}")
            return

        if hasattr(layer, 'style'):
            layer.style.set_style(layer)

        layer_path = layer.get_path()
        if layer_exists_by_path(self._project, layer_path):
            if layer.overwrite_existing:
                remove_layer_by_path(self._project, layer_path)
            else:
                logger.warning(f"Layer already exists, skipping: {layer_path}")
                return

        add_to_root = layer.group is None
        self._project.addMapLayer(qgis_layer, addToLegend=add_to_root)

        if add_to_root:
            layer_node = self._project.layerTreeRoot().findLayer(qgis_layer.id())
        else:
            group = add_or_get_group(self._project, layer.get_path()[:-1])
            layer_node = group.addLayer(qgis_layer)

        if layer.crs is not None:
            qgis_layer.setCrs(QgsCoordinateReferenceSystem(normalize_crs(layer.crs)))

        layer_node.setItemVisibilityChecked(layer.visible)

        group_str = '/'.join(['/ROOT', *layer.get_path()[:-1]]) if layer.group else '/ROOT'
        logger.info(f"Added layer '{layer.get_layer_name()}' @ {group_str}")


    def add_layer(self, layer: Layer | WebLayer | str):
        """Add a layer to the project. Accepts a file path string, a Layer, or a WebLayer."""
        if isinstance(layer, str):
            layer = Layer(layer)
        self._add_layer(layer)


    def remove_layer(self, layer: Layer | str):
        """Remove a layer from the project by path."""
        if isinstance(layer, str):
            layer = Layer(layer)
        remove_layer_by_path(self._project, layer.get_path())


    def set_crs(self, crs: str | int):
        """Set the project's coordinate reference system.

        Parameters
        ----------
        crs : str or int
            EPSG integer (e.g. ``3857``) or authority string (e.g. ``"EPSG:3857"``).
        """
        self._project.setCrs(QgsCoordinateReferenceSystem(normalize_crs(crs)))


    def process(self, algorithm: str, params: dict, name: str = "", group=None, visible: bool = True):
        """Run a QGIS Processing algorithm and add the result to the project.

        Parameters
        ----------
        algorithm : str
            QGIS processing algorithm identifier, e.g. ``"native:buffer"``.
        params : dict
            Algorithm parameters. Must include ``"INPUT"`` and typically
            ``"OUTPUT"``. Pass a file path for persistent outputs. ``"memory:"``
            is silently redirected to a temporary GeoPackage so the layer
            survives project save/load.
        name : str
            Name for the result layer. Defaults to the algorithm tail.
        group : str or list of str or None
            Layer group path.
        visible : bool
            Whether the result layer is visible on project open.
        """
        self._ensure_processing()
        import processing as _processing  # QGIS processing plugin; plugins dir must be on sys.path

        layer_name = name or algorithm.split(":")[-1]

        # Memory layers don't survive project save/load — redirect to a persistent file.
        params = dict(params)
        output_val = params.get("OUTPUT", "")
        if isinstance(output_val, str) and output_val.startswith("memory:"):
            self._auto_output_idx += 1
            slug = f"proc_{self._auto_output_idx:02d}.gpkg"
            if self._data_dir is not None:
                self._data_dir.mkdir(parents=True, exist_ok=True)
                auto_path = str(self._data_dir / slug)
            else:
                auto_path = os.path.join(tempfile.mkdtemp(), slug)
            params["OUTPUT"] = auto_path
            logger.debug(f"Redirected memory output for '{layer_name}' to {auto_path}")

        result = _processing.run(algorithm, params)
        output = result.get("OUTPUT")
        if output is None:
            logger.warning(f"Algorithm {algorithm!r} produced no OUTPUT")
            return
        if isinstance(output, str):
            self._add_layer(Layer(output, name=layer_name, group=group, visible=visible))
        else:
            output.setName(layer_name)
            add_to_root = group is None
            self._project.addMapLayer(output, addToLegend=add_to_root)
            if add_to_root:
                node = self._project.layerTreeRoot().findLayer(output.id())
            else:
                g = [group] if isinstance(group, str) else group
                node = add_or_get_group(self._project, g).addLayer(output)
            if node:
                node.setItemVisibilityChecked(visible)
            else:
                logger.warning(f"Could not find layer tree node for processing result '{layer_name}'")


    def _ensure_processing(self):
        if self._processing_initialized:
            return
        from processing.core.Processing import Processing
        Processing.initialize()
        self._processing_initialized = True


    def center(self, layer: Layer | None = None):
        """
        Set the project's initial view extent to a single layer.
        If no layer is provided, uses the last layer in the tree.
        """
        if layer is None:
            qgis_layer = get_layer_by_idx(self._project, -1)
        else:
            qgis_layer = layer.qgis_layer

        extent = self._transform_extent_to_project_crs(qgis_layer.extent(), qgis_layer.crs())
        self._set_view_extent(extent)


    def zoom_to_all(self):
        """Set the project's initial view extent to the union of all layers."""
        combined = QgsRectangle()
        for node in self._project.layerTreeRoot().findLayers():
            qgis_layer = node.layer()
            if qgis_layer is None:
                continue
            try:
                extent = self._transform_extent_to_project_crs(qgis_layer.extent(), qgis_layer.crs())
                combined.combineExtentWith(extent)
            except Exception:
                logger.warning(f"Could not transform extent for layer: {qgis_layer.name()}")
        if not combined.isNull():
            self._set_view_extent(combined)


    def _transform_extent_to_project_crs(self, extent, layer_crs):
        project_crs = self._project.crs()
        if layer_crs == project_crs:
            return extent
        transform = QgsCoordinateTransform(layer_crs, project_crs, self._project)
        return transform.transformBoundingBox(extent)


    def _set_view_extent(self, extent):
        project_crs = self._project.crs()
        ref_extent = QgsReferencedRectangle(extent, project_crs)
        self._project.viewSettings().setDefaultViewExtent(ref_extent)
        self._canvas.setExtent(extent)
        self._canvas.refresh()


    def open(self, file: str | None = None):
        """
        Save the project and open it in QGIS for visual inspection.

        Parameters
        ----------
        file : str or None
            Path to save the project to before opening. If None, a temporary
            file is created. Note that temporary files are deleted when the
            Python process exits, so pass an explicit path for persistent output.
        """
        if file is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".qgz", delete=False)
            file = tmp.name
            tmp.close()

        self.save(file)

        qgis_bin = shutil.which("qgis")
        if qgis_bin is None:
            raise RuntimeError(
                "QGIS executable not found on PATH. "
                "Make sure your QGIS conda environment is active."
            )
        subprocess.Popen([qgis_bin, file])
        logger.info(f"Opened QGIS with project: {file}")


    def snapshot(self, path: str | None = None):
        """Capture the current canvas as a still image.

        Behaviour depends on context:

        - **Jupyter notebook**: returns an ``IPython.display.Image`` that
          renders inline in the cell output.
        - **path given**: saves a PNG to that path and returns a ``Path``.
        - **Script (no Jupyter, no path)**: saves to a temporary file and
          returns its ``Path``.

        Parameters
        ----------
        path : str or None
            Destination file path.  If ``None``, auto-detected from context.
        """
        from pathlib import Path as _Path
        from qgis.PyQt.QtCore import QBuffer, QIODevice
        from qgis.PyQt.QtWidgets import QApplication

        QApplication.processEvents()

        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        self._canvas.grab().toImage().save(buf, "PNG")
        buf.close()
        png = bytes(buf.data())

        if path is not None:
            _Path(path).write_bytes(png)
            return _Path(path)

        # Jupyter: display inline
        try:
            from IPython import get_ipython
            if get_ipython() is not None:
                from IPython.display import Image
                return Image(data=png)
        except ImportError:
            pass

        # Script fallback: write to a temp file and return path
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(png)
        tmp.close()
        return _Path(tmp.name)


    def save(self, file: str):
        """Save the project to a .qgz file."""
        p = Path(file)
        if self._data_dir is None:
            self._data_dir = p.parent / (p.stem + "_data")
        ok = self._project.write(file)
        if not ok:
            raise RuntimeError(
                f"QgsProject.write() failed for: {file}\n"
                "Make sure the QGIS prefix path is set correctly."
            )
        logger.info(f"Project saved to: {file}")


    def exit(self):
        """Clean up the QGIS application.

        Only tears down QgsApplication if this Project instance created it.
        When multiple Project instances share one process (e.g. in a test
        session), only the first one owns the application.
        """
        if self._owns_app:
            self._application.exitQgis()


    def print_layer_tree(self):
        """Print the layer tree to stdout."""
        def _print_node(node, indent: int = 0):
            prefix = "  " * indent
            if isinstance(node, QgsLayerTreeLayer):
                visible = "✓" if node.isVisible() else "○"
                print(f"{prefix}[{visible}] {node.layer().name()}")
            elif isinstance(node, QgsLayerTreeGroup):
                if indent > 0:
                    print(f"{prefix}▶ {node.name()}")
                for child in node.children():
                    _print_node(child, indent + (1 if indent > 0 else 0))

        _print_node(self._project.layerTreeRoot())


    def _find_group(self, path: list[str]):
        """Return the QgsLayerTreeGroup at *path*, or None if not found."""
        node = self._project.layerTreeRoot()
        for name in path:
            node = next(
                (c for c in node.children() if isinstance(c, QgsLayerTreeGroup) and c.name() == name),
                None,
            )
            if node is None:
                return None
        return node

    def _set_all_groups_expanded(self, node, expanded: bool):
        for child in node.children():
            if isinstance(child, QgsLayerTreeGroup):
                child.setExpanded(expanded)
                self._set_all_groups_expanded(child, expanded)

    def collapse_group(self, *path: str):
        """Collapse a group in the layer tree.

        Parameters
        ----------
        *path : str
            Group name sequence, e.g. ``collapse_group("terrain")`` or
            ``collapse_group("terrain", "raw")`` for a nested group.
        """
        group = self._find_group(list(path))
        if group is not None:
            group.setExpanded(False)
        else:
            logger.warning(f"Group not found: {list(path)}")

    def expand_group(self, *path: str):
        """Expand a group in the layer tree.

        Parameters
        ----------
        *path : str
            Group name sequence, same syntax as :meth:`collapse_group`.
        """
        group = self._find_group(list(path))
        if group is not None:
            group.setExpanded(True)
        else:
            logger.warning(f"Group not found: {list(path)}")

    def collapse_all(self):
        """Collapse all groups in the layer tree."""
        self._set_all_groups_expanded(self._project.layerTreeRoot(), False)

    def expand_all(self):
        """Expand all groups in the layer tree."""
        self._set_all_groups_expanded(self._project.layerTreeRoot(), True)


def _set_setters(cls_target, cls_src):
    for attr_ in dir(cls_src):
        if attr_.startswith("_"): continue
        def setter(self, val): setattr(self, attr_, val)
        setattr(cls_target, f"set_{attr_}", setter)
