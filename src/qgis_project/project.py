"""
Module to handle QGIS project functionality.
"""

import os
import shutil
import subprocess
import tempfile

from loguru import logger

from qgis_project.layer import Layer
from qgis_project.utils import add_or_get_group, get_layer_by_idx, layer_exists_by_path, qgis_lazy_import, remove_layer_by_path


@qgis_lazy_import({
    "qgis.core": [
        "QgsApplication", "QgsProject",
        "QgsVectorLayer", "QgsRasterLayer",
        "QgsMapSettings", "QgsCoordinateReferenceSystem",
        "QgsColorRampShader", "QgsRasterShader",
        "QgsSingleBandPseudoColorRenderer", "QgsSingleBandGrayRenderer",
        "QgsContrastEnhancement", "QgsRasterBandStats", "QgsStyle",
        "QgsLayerTreeGroup", "QgsLayerTreeLayer",
    ],
    "qgis.PyQt.QtGui": ["QColor"],
    "qgis.gui": ["QgsMapCanvas"]
})
class Project:
    def __init__(self, file: str | None = None):

        self._application = QgsApplication([], False)
        self._application.initQgis()

        self._project = QgsProject.instance()
        self._canvas = QgsMapCanvas()
        if file is not None:
            self._project.read(file)

    def _add_layer(self, layer: Layer):
        """Add a layer to the underlying project."""
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
            logger.error(f"Failed to load layer: {layer.file}")
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


    def add_layer(self, layer: Layer | str):
        """Add a layer to the project. Accepts a file path string or a Layer object."""
        if isinstance(layer, str):
            layer = Layer(layer)
        self._add_layer(layer)


    def remove_layer(self, layer: Layer | str):
        """Remove a layer from the project by path."""
        if isinstance(layer, str):
            layer = Layer(layer)
        remove_layer_by_path(self._project, layer.get_path())


    def center(self, layer: Layer | None = None):
        """
        Center the project canvas on a layer.
        If no layer is provided, centers on the last layer in the tree.
        """
        if layer is None:
            qgis_layer = get_layer_by_idx(self._project, -1)
        else:
            qgis_layer = layer.qgis_layer

        self._canvas.setExtent(qgis_layer.extent())
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
        self._project.write(file)
        logger.info(f"Project saved to: {file}")


    def exit(self):
        """Clean up the QGIS application."""
        self._application.exitQgis()


    def print_layer_tree(self):
        """Print the layer tree to stdout."""
        from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer

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
