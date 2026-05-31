"""
Module to handle QGIS layer functionality.
"""

from functools import wraps
import os
from dataclasses import dataclass
import pickle

from qgis_project.style import RasterStyle



class QgisLayerLinkError(Exception):
    def __init__(self):
        super().__init__("Layer has not been linked with a low-level QGIS layer object.")


def assert_link(f):
    """
    Decorator to check if a QGIS layer has been linked. Some layer functionality requires access to low-level layer objects of the QGIS python API.

    Raise an exception if no low-level QGIS layer object has been linked to the layer.
    """
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "qgis_layer"):
            raise QgisLayerLinkError()
        return f(self, *args, **kwargs)
    return wrapper


@dataclass
class Layer:
    file: str
    crs: str | int|  None = None
    visible: bool = True

    group: str | list[str] | None = None
    name: str | None = None

    overwrite_existing: bool = False    # if layer is added, check whether to replace or ignore new layer on existing
    statistics_precision: str | None = None     # TODO: how?


    # serialization methods (save/load)
    def save(self, filepath: str):
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filepath: str):
        with open(filepath, 'rb') as f:
            return pickle.load(f)


    # layer path methods
    def get_layer_name(self):
        """Get the dataset's name as shown in the layer."""
        return self.name or os.path.basename(self.file)

    def get_path(self):
        """Get the dataset's path as in the layer tree."""
        if self.group is None:
            return self.get_layer_name()
        elif isinstance(self.group, str):
            return [self.group, self.get_layer_name()]
        else:
            return [*self.group, self.get_layer_name()]

    # other
    def set_qgis_layer(self, qgis_layer):
        self.qgis_layer = qgis_layer

    @assert_link
    def get_layer_extent(self):
        return self.qgis_layer.extent()


class RasterLayer(Layer):
    # TODO: how to handle multi-layer visualization (pseudo-color plots)
    band_idx: int | list[int] = 1
    style: RasterStyle = RasterStyle()

    # TODO: computation mode estimate/exact
    @assert_link
    def get_layer_min(self):
        from qgis.core import QgsRasterBandStats
        return self.qgis_layer.dataProvider().bandStatistics(self.band_idx, QgsRasterBandStats.Min).minimumValue

    @assert_link
    def get_layer_max(self):
        from qgis.core import QgsRasterBandStats
        return self.qgis_layer.dataProvider().bandStatistics(self.band_idx, QgsRasterBandStats.Max).maximumValue

    def set_band_idx(self, band_idx: int | list[int]):
        self.band_idx = band_idx

        # TODO: re-compute min/max? redraw? other re-computes?
