"""
Module to handle QGIS project functionality.
"""

import os

from loguru import logger

from qgis_project.layer import Layer
from qgis_project.utils import add_or_get_group, get_layer_by_idx, layer_exists_by_path, qgis_lazy_import, remove_layer_by_path


# TODO: benchmark: lazy_import slow?
# TODO: benchmark: conda run slow?


@qgis_lazy_import({
    "qgis.core": [
        "QgsApplication", "QgsProject",
        "QgsVectorLayer", "QgsRasterLayer",
        "QgsMapSettings", "QgsCoordinateReferenceSystem",

        "QgsColorRampShader", "QgsRasterShader",
        "QgsSingleBandPseudoColorRenderer", "QgsSingleBandGrayRenderer",
        "QgsContrastEnhancement", "QgsRasterBandStats", "QgsStyle",
    ],
    "qgis.PyQt.QtGui": ["QColor"],
    "qgis.gui": ["QgsMapCanvas"]
})
class Project:
    def __init__(self, file: str | None = None):

        self._application = QgsApplication([], False)
        self._application.initQgis()

        # Get the project instance
        self._project = QgsProject.instance()
        self._canvas = QgsMapCanvas()     # https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/canvas.html
        if file is not None:
            self._project.read(file)

        self._centered = False

    def _add_layer(self, layer: Layer):
        """Add a layer to the underlying project."""

        # existance
        if not os.path.exists(layer.file):
            logger.error(f"File does not exist: {layer.file}")
            return

        # Determine layer type
        ext = os.path.splitext(layer.file)[-1].lower()
        if ext in ['.shp', '.geojson', '.gpkg']:
            qgis_layer = QgsVectorLayer(layer.file, os.path.basename(layer.file), "ogr")
        elif ext in ['.tif', '.tiff', '.img']:
            qgis_layer = QgsRasterLayer(layer.file, os.path.basename(layer.file))
        else:
            logger.error(f"Unsupported file format: {layer.file}")

        # link project layer with low-level layer object from QGIS python API
        layer.set_qgis_layer(qgis_layer)

        # apply style to layer
        layer.style.set_style(layer)


        if not layer.isValid():
            logger.error(f"Failed to load layer: {layer.file}")
            return
        else:
            logger.log(f"Successfully loaded layer: {layer.file}")

            layer_path = layer.get_path()
            if layer_exists_by_path(self._project, layer_path):
                if layer.overwrite_existing:
                    remove_layer_by_path(self._project, layer_path)
                else:
                    return

            add_to_root = layer.group is None
            self._project.addMapLayer(qgis_layer, addToLegend=add_to_root)

            group_str = '/'.join(['/ROOT', *layer.get_path()[:-1]])
            logger.log(f"Added layer   '{layer.get_layer_name()}' @ group {group_str}")

            if not add_to_root:
                group = add_or_get_group(self._project, layer.get_path()[:-1])
                group.addLayer(qgis_layer)

        # set layer CRS
        if layer.crs is not None:
            if isinstance(layer.crs, int):
                layer.crs = f"EPSG:{layer.crs}"
            layer.setCrs(QgsCoordinateReferenceSystem(layer.crs))

        # show/hide layer
        layer_node = self._project.layerTreeRoot().findLayer(layer.qgis_layer.id())
        # if layer_node:
        layer_node.setItemVisibilityChecked(layer.visible)


    def add_layer(self, layer: Layer | str):
        if isinstance(layer, str): layer = Layer(layer)
        self._add_layer(layer)


    def remove_layer(self, layer: Layer | str):
        if isinstance(layer, str): layer = Layer(layer)
        remove_layer_by_path(self._project, layer.get_path())


    # project functions
    def center(self, layer: Layer | None):
        """
        Center the project canvas to a layer.
        If layer is not provided, will center on last added layer.
        """
        if layer is None:
            layer = get_layer_by_idx(self._project, -1)

        # zoom to layer
        layer_extent = layer.get_layer_extent()
        self._canvas.setExtent(layer_extent)

        self._centered = True


    def open(self):
        if not self._centered:
            self.center()

        # TODO
        pass

    def save(self, file: str):
        if not self._centered:
            self.center()

        self._project.write(file)
        logger.log(f"Project saved to: {file}")


    # TODO: how to do proper cleanup?
    def exit(self):
        # Clean up
        self._application.exitQgis()


    # convenience functions
    def print_layer_tree(self):
        # TODO
        pass

    def collapse_group(self, *group):
        # TODO
        pass


def _set_setters(cls_target, cls_src):
    for attr_ in dir(cls_src):
        if attr_.startswith("_"): continue

        # create setter and assign to class
        def setter(self, val): setattr(self, attr_, val)
        setattr(cls_target, f"set_{attr_}", setter)
