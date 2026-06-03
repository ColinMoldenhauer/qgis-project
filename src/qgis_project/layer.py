"""
Module to handle QGIS layer functionality.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import wraps
import pickle

from qgis.core import QgsRasterBandStats

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


class _LayerMixin:
    """Shared interface methods for all layer types."""

    def get_path(self):
        """Get the layer's path in the layer tree."""
        if self.group is None:
            return self.get_layer_name()
        elif isinstance(self.group, str):
            return [self.group, self.get_layer_name()]
        else:
            return [*self.group, self.get_layer_name()]

    def set_qgis_layer(self, qgis_layer):
        self.qgis_layer = qgis_layer

    @assert_link
    def get_layer_extent(self):
        return self.qgis_layer.extent()


@dataclass
class Layer(_LayerMixin):
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


    def get_layer_name(self):
        """Get the dataset's name as shown in the layer."""
        return self.name or os.path.basename(self.file)


@dataclass
class RasterLayer(Layer):
    # TODO: how to handle multi-layer visualization (pseudo-color plots)
    band_idx: int | list[int] = 1
    style: RasterStyle = field(default_factory=RasterStyle)

    # TODO: computation mode estimate/exact
    @assert_link
    def get_layer_min(self):
        return self.qgis_layer.dataProvider().bandStatistics(self.band_idx, QgsRasterBandStats.Min).minimumValue

    @assert_link
    def get_layer_max(self):
        return self.qgis_layer.dataProvider().bandStatistics(self.band_idx, QgsRasterBandStats.Max).maximumValue

    def set_band_idx(self, band_idx: int | list[int]):
        self.band_idx = band_idx

        # TODO: re-compute min/max? redraw? other re-computes?


@dataclass
class WebLayer(_LayerMixin):
    """A layer sourced from a web service (XYZ tiles, WMS, WFS, etc.).

    Prefer the factory class methods over constructing directly:
        WebLayer.osm()
        WebLayer.xyz(url)
        WebLayer.wms(url, layers)
        WebLayer.wfs(url, typename)
    """
    uri: str
    provider: str = "wms"
    name: str = ""
    group: str | list[str] | None = None
    visible: bool = True
    crs: str | int | None = None
    overwrite_existing: bool = False

    def get_layer_name(self) -> str:
        return self.name or "Web Layer"

    @classmethod
    def xyz(cls, url: str, name: str = "XYZ", zmin: int = 0, zmax: int = 19, **kwargs) -> "WebLayer":
        """XYZ/slippy-map tile layer."""
        uri = f"type=xyz&url={url}&zmin={zmin}&zmax={zmax}"
        return cls(uri=uri, provider="wms", name=name, **kwargs)

    @classmethod
    def osm(cls, **kwargs) -> "WebLayer":
        """OpenStreetMap tile layer."""
        kwargs.setdefault("name", "OpenStreetMap")
        return cls.xyz("https://tile.openstreetmap.org/{z}/{x}/{y}.png", **kwargs)

    @classmethod
    def wms(cls, url: str, layers: str, format: str = "image/png",
            crs: str = "EPSG:4326", name: str = "", **kwargs) -> "WebLayer":
        """OGC Web Map Service layer."""
        uri = f"url={url}&layers={layers}&styles=&format={format}&crs={crs}"
        return cls(uri=uri, provider="wms", name=name or layers, crs=crs, **kwargs)

    @classmethod
    def wfs(cls, url: str, typename: str, name: str = "", **kwargs) -> "WebLayer":
        """OGC Web Feature Service layer."""
        uri = f"url={url}&typename={typename}&version=auto"
        return cls(uri=uri, provider="WFS", name=name or typename, **kwargs)
