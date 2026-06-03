"""
Module to handle QGIS project functionality.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

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
from qgis.gui import QgsMapCanvas

from qgis_project.layer import Layer, WebLayer
from qgis_project.utils import add_or_get_group, get_layer_by_idx, layer_exists_by_path, remove_layer_by_path


class Project:
    def __init__(self, file: str | None = None):
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
        self._processing_initialized = False
        if file is not None:
            self._project.read(file)

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

            ext = os.path.splitext(layer.file)[-1].lower()
            if ext in ['.shp', '.geojson', '.gpkg']:
                qgis_layer = QgsVectorLayer(layer.file, layer.get_layer_name(), "ogr")
            elif ext in ['.tif', '.tiff', '.img']:
                qgis_layer = QgsRasterLayer(layer.file, layer.get_layer_name())
            else:
                logger.error(f"Unsupported file format: {layer.file}")
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

        if not add_to_root:
            group = add_or_get_group(self._project, layer.get_path()[:-1])
            group.addLayer(qgis_layer)

        if layer.crs is not None:
            if isinstance(layer.crs, int):
                layer.crs = f"EPSG:{layer.crs}"
            qgis_layer.setCrs(QgsCoordinateReferenceSystem(layer.crs))

        layer_node = self._project.layerTreeRoot().findLayer(qgis_layer.id())
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


    def process(self, algorithm: str, params: dict, name: str = "", group=None, visible: bool = True):
        """Run a QGIS Processing algorithm and add the result to the project.

        Parameters
        ----------
        algorithm : str
            QGIS processing algorithm identifier, e.g. ``"native:buffer"``.
        params : dict
            Algorithm parameters. Must include ``"INPUT"`` and typically
            ``"OUTPUT"``. Use ``"OUTPUT": "memory:"`` for in-memory vector
            results, or a file path for persistent outputs.
        name : str
            Name for the result layer. Defaults to the algorithm tail.
        group : str or list of str or None
            Layer group path.
        visible : bool
            Whether the result layer is visible on project open.
        """
        self._ensure_processing()
        import processing as _processing  # QGIS processing module; only available after initQgis
        layer_name = name or algorithm.split(":")[-1]
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
            if not add_to_root:
                g = [group] if isinstance(group, str) else group
                add_or_get_group(self._project, g).addLayer(output)
            node = self._project.layerTreeRoot().findLayer(output.id())
            if node:
                node.setItemVisibilityChecked(visible)


    def _ensure_processing(self):
        if self._processing_initialized:
            return
        from qgis.analysis import QgsNativeAlgorithms
        QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
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


    def save(self, file: str):
        """Save the project to a .qgz file."""
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


    def collapse_group(self, *group):
        # TODO
        pass


def _set_setters(cls_target, cls_src):
    for attr_ in dir(cls_src):
        if attr_.startswith("_"): continue
        def setter(self, val): setattr(self, attr_, val)
        setattr(cls_target, f"set_{attr_}", setter)
