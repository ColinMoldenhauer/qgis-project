"""
Module to handle QGIS layer functionality.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import wraps
import pickle

from qgis.core import QgsRasterBandStats

from qgis_project.style import RasterStyle, VectorLabels, VectorStyle


class QgisLayerLinkError(Exception):
    def __init__(self):
        super().__init__(
            "Layer has not been linked with a low-level QGIS layer object."
        )


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
    """A local file-based layer (vector or raster).

    Parameters
    ----------
    file : str
        Path to the layer file (`".shp"`, `".geojson"`, `".gpkg"`,
        `".tif"`, `".tiff"`, `".img"`).
    crs : str or int or None
        Override the layer CRS. Accepts an EPSG integer or authority string
        (e.g. `"EPSG:4326"`). If `None`, the layer's native CRS is used.
    visible : bool
        Whether the layer is visible when the project opens.
    group : str or list of str or None
        Layer group path. A plain string places the layer in a top-level group;
        a list creates a nested hierarchy, e.g. `["terrain", "raw"]`.
    name : str or None
        Display name in the layer tree. Defaults to the file's basename.
    overwrite_existing : bool
        If `True`, replace an existing layer at the same group path;
        if `False` (default), skip silently.
    style : VectorStyle or None
        Vector styling to apply (e.g. `VectorStyleSingleSymbol`,
        `VectorStyleCategorized`, `VectorStyleGraduated`). If `None`,
        the QGIS default symbol is used. Ignored for raster files.
    filter : str or None
        QGIS expression used as a subset filter (`QgsVectorLayer.setSubsetString`),
        e.g. `"population > 1000"`. Only the matching features are loaded,
        rendered, and included in extent/statistics calculations. Ignored for
        raster files.
    min_scale : float or None
        Most zoomed-out scale denominator at which the layer is still visible,
        e.g. `100000` for 1:100,000. Zooming out further (larger denominator)
        hides the layer. If `None`, no zoomed-out limit.
    max_scale : float or None
        Most zoomed-in scale denominator at which the layer is still visible,
        e.g. `1000` for 1:1,000. Zooming in further (smaller denominator)
        hides the layer. If `None`, no zoomed-in limit.
    labels : VectorLabels or None
        Attribute-based labels to show on the layer. Independent of `style`.
        Ignored for raster files.
    """

    file: str
    crs: str | int | None = None
    visible: bool = True

    group: str | list[str] | None = None
    name: str | None = None

    overwrite_existing: bool = False  # if layer is added, check whether to replace or ignore new layer on existing

    style: VectorStyle | None = None
    filter: str | None = None
    min_scale: float | None = None
    max_scale: float | None = None
    labels: VectorLabels | None = None

    # serialization methods (save/load)
    def save(self, filepath: str):
        with open(filepath, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filepath: str):
        with open(filepath, "rb") as f:
            return pickle.load(f)

    def get_layer_name(self):
        """Get the dataset's name as shown in the layer."""
        return self.name or os.path.basename(self.file)


@dataclass
class RasterLayer(Layer):
    # int for single-band styles (RasterStyleBW, RasterStyleSinglePseudocolor);
    # list of three band numbers [R, G, B] for RasterStyleMultiBandColor.
    band_idx: int | list[int] = 1
    style: RasterStyle = field(default_factory=RasterStyle)

    # Extra kwargs forwarded to QgsRasterDataProvider.bandStatistics(), e.g.
    # sampleSize=0 for exact stats (default), sampleSize=250000 for a fast
    # estimate, or extent=... to restrict the computed region.
    statistics_kwargs: dict = field(default_factory=dict)

    @assert_link
    def get_layer_min(self, band: int | None = None):
        band = band if band is not None else self.band_idx
        if not isinstance(band, int):
            raise ValueError("band must be specified explicitly when band_idx is a list")
        return (
            self.qgis_layer.dataProvider()
            .bandStatistics(band, QgsRasterBandStats.Min, **self.statistics_kwargs)
            .minimumValue
        )

    @assert_link
    def get_layer_max(self, band: int | None = None):
        band = band if band is not None else self.band_idx
        if not isinstance(band, int):
            raise ValueError("band must be specified explicitly when band_idx is a list")
        return (
            self.qgis_layer.dataProvider()
            .bandStatistics(band, QgsRasterBandStats.Max, **self.statistics_kwargs)
            .maximumValue
        )

    def set_band_idx(self, band_idx: int | list[int]):
        self.band_idx = band_idx


def layer_from_path(file: str, **kwargs) -> Layer:
    """Build a :class:`Layer` or :class:`RasterLayer` from a file path and kwargs.

    Chooses :class:`RasterLayer` when a raster-specific keyword is present
    (a :class:`RasterStyle` style, `band_idx`, or `statistics_kwargs`);
    otherwise returns a plain :class:`Layer`. This lets callers pass raster
    styling directly to `add_layer` without wrapping the path in a
    `RasterLayer` themselves.
    """
    is_raster = (
        isinstance(kwargs.get("style"), RasterStyle)
        or "band_idx" in kwargs
        or "statistics_kwargs" in kwargs
    )
    cls = RasterLayer if is_raster else Layer
    return cls(file, **kwargs)


@dataclass
class ProcessingOp:
    """A QGIS Processing algorithm to run, whose result is added to the project as a layer.

    Parameters
    ----------
    algorithm : str
        QGIS processing algorithm identifier, e.g. `"native:buffer"`.
    params : dict
        Algorithm parameters passed directly to `processing.run()`.
        Must include `"INPUT"` and, for most algorithms, `"OUTPUT"`.
        Set `"OUTPUT"` to `"memory:"` for an in-memory vector result,
        or a file path (e.g. `"/tmp/out.gpkg"`) for a persistent output.
    name : str
        Name for the result layer in the layer tree.
        Defaults to the algorithm identifier tail (e.g. `"buffer"`).
    group : str or list of str or None
        Layer group path, same syntax as :class:`Layer`.
    visible : bool
        Whether the result layer is visible when the project opens.
    """

    algorithm: str
    params: dict
    name: str = ""
    group: str | list[str] | None = None
    visible: bool = True


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
    def xyz(
        cls, url: str, name: str = "XYZ", zmin: int = 0, zmax: int = 19, **kwargs
    ) -> "WebLayer":
        """XYZ/slippy-map tile layer."""
        uri = f"type=xyz&url={url}&zmin={zmin}&zmax={zmax}"
        return cls(uri=uri, provider="wms", name=name, **kwargs)

    @classmethod
    def osm(cls, **kwargs) -> "WebLayer":
        """OpenStreetMap tile layer."""
        kwargs.setdefault("name", "OpenStreetMap")
        return cls.xyz("https://tile.openstreetmap.org/{z}/{x}/{y}.png", **kwargs)

    @classmethod
    def wms(
        cls,
        url: str,
        layers: str,
        format: str = "image/png",
        crs: str = "EPSG:4326",
        name: str = "",
        **kwargs,
    ) -> "WebLayer":
        """OGC Web Map Service layer."""
        uri = f"url={url}&layers={layers}&styles=&format={format}&crs={crs}"
        return cls(uri=uri, provider="wms", name=name or layers, crs=crs, **kwargs)

    @classmethod
    def wfs(cls, url: str, typename: str, name: str = "", **kwargs) -> "WebLayer":
        """OGC Web Feature Service layer."""
        uri = f"url={url}&typename={typename}&version=auto"
        return cls(uri=uri, provider="WFS", name=name or typename, **kwargs)
