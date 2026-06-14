from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from qgis.core import QgsContrastEnhancement, QgsSingleBandGrayRenderer

if TYPE_CHECKING:
    from qgis_project.layer import Layer


@dataclass
class Style:
    """
    Base class for layer styling.

    Parameters
    ----------
    opacity : float
        The layer opacity in the interval [0, 1]
    """

    opacity: float = 1.0

    def set_style(self, layer: Layer):
        """Apply the style to the low-level QGIS objects for layer styling."""
        if self.opacity is not None:
            layer.qgis_layer.setOpacity(self.opacity)


@dataclass
class RasterStyle(Style):
    """
    Base class for raster layer styling.

    Parameters
    ----------
    vmin : float | list[float] | None
        The minimum value used for the colorbar/contrast stretch.
        If None, will be automatically determined from the layer data.
        For styles with multiple bands (e.g. RasterStyleMultiBandColor), a
        list applies one value per band; a single value applies to all bands.
    vmax : float | list[float] | None
        The maximum value used for the colorbar/contrast stretch.
        If None, will be automatically determined from the layer data.
        For styles with multiple bands (e.g. RasterStyleMultiBandColor), a
        list applies one value per band; a single value applies to all bands.
    """

    vmin: float | list[float] | None = None
    vmax: float | list[float] | None = None


@dataclass
class RasterStyleBW(RasterStyle):
    """
    A black-and-white style for raster layers.
    """

    def set_style(self, layer: Layer):
        vmin = self.vmin if self.vmin is not None else layer.get_layer_min()
        vmax = self.vmax if self.vmax is not None else layer.get_layer_max()

        # https://gis.stackexchange.com/questions/377569/setting-max-min-values-of-singleband-grey-layer-using-pyqgis
        qgis_layer = layer.qgis_layer
        band = getattr(layer, "band_idx", 1)
        renderer = QgsSingleBandGrayRenderer(qgis_layer.dataProvider(), band)
        render_type = renderer.dataType(band)
        enhancement = QgsContrastEnhancement(render_type)
        contrast_enhancement = QgsContrastEnhancement.StretchToMinimumMaximum
        enhancement.setContrastEnhancementAlgorithm(contrast_enhancement, True)
        enhancement.setMinimumValue(vmin)
        enhancement.setMaximumValue(vmax)

        qgis_layer.setRenderer(renderer)
        qgis_layer.renderer().setContrastEnhancement(enhancement)
        # Apply opacity after setRenderer() — raster opacity lives on the renderer,
        # so calling super before setRenderer() would be overwritten by the new renderer.
        super().set_style(layer)


@dataclass
class RasterStyleSinglePseudocolor(RasterStyle):
    """
    A single-band pseudocolor style for raster layers.

    Parameters
    ----------
    colormap : str
        Name of a QGIS built-in color ramp (case-insensitive), e.g. ``"Viridis"``,
        ``"Spectral"``, ``"RdYlBu"``. Run ``QgsStyle.defaultStyle().colorRampNames()``
        to see all available names.
    """

    colormap: str = "viridis"

    def set_style(self, layer: "Layer"):
        from qgis.core import (
            QgsColorRampShader,
            QgsRasterShader,
            QgsSingleBandPseudoColorRenderer,
        )

        qgis_layer = layer.qgis_layer
        band = getattr(layer, "band_idx", 1)
        provider = qgis_layer.dataProvider()

        vmin = self.vmin if self.vmin is not None else layer.get_layer_min()
        vmax = self.vmax if self.vmax is not None else layer.get_layer_max()

        ramp = _get_color_ramp(self.colormap)

        color_shader = QgsColorRampShader(vmin, vmax, ramp)
        color_shader.setColorRampType(QgsColorRampShader.Interpolated)
        color_shader.classifyColorRamp()

        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(color_shader)

        renderer = QgsSingleBandPseudoColorRenderer(provider, band, raster_shader)
        renderer.setClassificationMin(vmin)
        renderer.setClassificationMax(vmax)
        qgis_layer.setRenderer(renderer)
        super().set_style(layer)


@dataclass
class RasterStyleMultiBandColor(RasterStyle):
    """
    A multi-band color (RGB) style for raster layers.

    Maps three raster bands to the red, green, and blue channels, each with
    an independent contrast stretch — e.g. true-color or false-color
    composites. Requires ``layer.band_idx`` to be a list of three band
    numbers, e.g. ``[1, 2, 3]`` for (R, G, B).
    """

    def set_style(self, layer: "Layer"):
        from qgis.core import QgsMultiBandColorRenderer

        band_idx = layer.band_idx
        if not isinstance(band_idx, (list, tuple)) or len(band_idx) != 3:
            raise ValueError(
                "RasterStyleMultiBandColor requires layer.band_idx to be a "
                "list of three band numbers, e.g. [1, 2, 3] for (R, G, B)."
            )

        qgis_layer = layer.qgis_layer
        provider = qgis_layer.dataProvider()

        vmins = self.vmin if isinstance(self.vmin, (list, tuple)) else [self.vmin] * 3
        vmaxs = self.vmax if isinstance(self.vmax, (list, tuple)) else [self.vmax] * 3

        renderer = QgsMultiBandColorRenderer(provider, *band_idx)
        setters = [
            renderer.setRedContrastEnhancement,
            renderer.setGreenContrastEnhancement,
            renderer.setBlueContrastEnhancement,
        ]
        for band, vmin, vmax, set_enhancement in zip(band_idx, vmins, vmaxs, setters):
            vmin = vmin if vmin is not None else layer.get_layer_min(band)
            vmax = vmax if vmax is not None else layer.get_layer_max(band)
            enhancement = QgsContrastEnhancement(provider.dataType(band))
            enhancement.setContrastEnhancementAlgorithm(
                QgsContrastEnhancement.StretchToMinimumMaximum, True
            )
            enhancement.setMinimumValue(vmin)
            enhancement.setMaximumValue(vmax)
            set_enhancement(enhancement)

        qgis_layer.setRenderer(renderer)
        super().set_style(layer)


@dataclass
class VectorStyle(Style):
    """
    Base class for vector layer styling.
    """


@dataclass
class VectorStyleSingleSymbol(VectorStyle):
    """
    A single-symbol style for vector layers — every feature rendered identically.

    Parameters
    ----------
    color : str | None
        Fill (polygon), line, or marker color, e.g. ``"red"``, ``"#ff0000"``,
        or ``"255,0,0,255"``. If ``None``, the QGIS default symbol color is kept.
    outline_color : str | None
        Outline/stroke color for polygon and marker symbols.
    outline_width : float | None
        Outline/stroke width in millimeters for polygon, line, and marker symbols.
    size : float | None
        Marker size in millimeters. Only applies to point layers.
    marker_shape : str | None
        Marker shape for point layers, e.g. ``"circle"``, ``"square"``,
        ``"triangle"``, ``"star"``. See
        ``QgsSimpleMarkerSymbolLayerBase.decodeShape()`` for all accepted names.
    """

    color: str | None = None
    outline_color: str | None = None
    outline_width: float | None = None
    size: float | None = None
    marker_shape: str | None = None

    def set_style(self, layer: "Layer"):
        from qgis.core import QgsSimpleMarkerSymbolLayerBase, QgsSingleSymbolRenderer
        from qgis.PyQt.QtGui import QColor

        qgis_layer = layer.qgis_layer
        symbol = qgis_layer.renderer().symbol().clone()

        if self.color is not None:
            symbol.setColor(QColor(self.color))
        if self.size is not None and hasattr(symbol, "setSize"):
            symbol.setSize(self.size)
        for i in range(symbol.symbolLayerCount()):
            symbol_layer = symbol.symbolLayer(i)
            if self.outline_color is not None and hasattr(symbol_layer, "setStrokeColor"):
                symbol_layer.setStrokeColor(QColor(self.outline_color))
            if self.outline_width is not None and hasattr(symbol_layer, "setStrokeWidth"):
                symbol_layer.setStrokeWidth(self.outline_width)
            if self.marker_shape is not None and hasattr(symbol_layer, "setShape"):
                shape, ok = QgsSimpleMarkerSymbolLayerBase.decodeShape(self.marker_shape)
                if not ok:
                    raise ValueError(f"Unknown marker shape: {self.marker_shape!r}")
                symbol_layer.setShape(shape)

        qgis_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        super().set_style(layer)


@dataclass
class VectorStyleCategorized(VectorStyle):
    """
    A categorized style for vector layers — one color per unique attribute value.

    Parameters
    ----------
    field : str
        Name of the attribute field to categorize by.
    colormap : str
        Name of a QGIS built-in color ramp (case-insensitive), e.g. ``"Spectral"``,
        ``"RdYlBu"``, ``"Turbo"``. Run
        ``QgsStyle.defaultStyle().colorRampNames()`` to see all available names.
    """

    field: str = ""
    colormap: str = "Spectral"

    def set_style(self, layer: "Layer"):
        from qgis.core import (
            QgsCategorizedSymbolRenderer,
            QgsRendererCategory,
            QgsSymbol,
        )

        qgis_layer = layer.qgis_layer
        if not self.field:
            raise ValueError("VectorStyleCategorized requires 'field' to be set.")

        if qgis_layer.fields().indexOf(self.field) < 0:
            raise ValueError(
                f"Field {self.field!r} not found on layer {layer.get_layer_name()!r}."
            )

        ramp = _get_color_ramp(self.colormap)

        values = sorted(
            {f[self.field] for f in qgis_layer.getFeatures()},
            key=lambda v: (v is None, v),
        )

        n = len(values)
        categories = []
        for i, value in enumerate(values):
            symbol = QgsSymbol.defaultSymbol(qgis_layer.geometryType())
            symbol.setColor(ramp.color(i / (n - 1) if n > 1 else 0.0))
            categories.append(QgsRendererCategory(value, symbol, str(value)))

        qgis_layer.setRenderer(QgsCategorizedSymbolRenderer(self.field, categories))
        super().set_style(layer)


@dataclass
class VectorStyleGraduated(VectorStyle):
    """
    A graduated (choropleth) style for vector layers — equal-interval color
    classes based on a numeric attribute.

    Parameters
    ----------
    field : str
        Name of the numeric attribute field to classify.
    num_classes : int
        Number of equal-width classes.
    vmin : float | None
        Lower bound of the classification range. If ``None``, uses the
        field's minimum value.
    vmax : float | None
        Upper bound of the classification range. If ``None``, uses the
        field's maximum value.
    colormap : str
        Name of a QGIS built-in color ramp (case-insensitive), e.g. ``"Viridis"``,
        ``"Spectral"``, ``"RdYlBu"``. Run
        ``QgsStyle.defaultStyle().colorRampNames()`` to see all available names.
    """

    field: str = ""
    num_classes: int = 5
    vmin: float | None = None
    vmax: float | None = None
    colormap: str = "Viridis"

    def set_style(self, layer: "Layer"):
        from qgis.core import QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol

        qgis_layer = layer.qgis_layer
        if not self.field:
            raise ValueError("VectorStyleGraduated requires 'field' to be set.")

        idx = qgis_layer.fields().indexOf(self.field)
        if idx < 0:
            raise ValueError(
                f"Field {self.field!r} not found on layer {layer.get_layer_name()!r}."
            )

        vmin = self.vmin if self.vmin is not None else qgis_layer.minimumValue(idx)
        vmax = self.vmax if self.vmax is not None else qgis_layer.maximumValue(idx)

        ramp = _get_color_ramp(self.colormap)

        n = self.num_classes
        step = (vmax - vmin) / n
        ranges = []
        for i in range(n):
            lower = vmin + i * step
            upper = vmax if i == n - 1 else vmin + (i + 1) * step
            symbol = QgsSymbol.defaultSymbol(qgis_layer.geometryType())
            symbol.setColor(ramp.color(i / (n - 1) if n > 1 else 0.0))
            ranges.append(QgsRendererRange(lower, upper, symbol, f"{lower:.2f} - {upper:.2f}"))

        qgis_layer.setRenderer(QgsGraduatedSymbolRenderer(self.field, ranges))
        super().set_style(layer)


def _get_color_ramp(colormap: str):
    """Look up a QGIS built-in color ramp by name, case-insensitive."""
    from qgis.core import QgsStyle

    style = QgsStyle.defaultStyle()
    ramp_names = style.colorRampNames()
    matched = next((n for n in ramp_names if n.lower() == colormap.lower()), None)
    if matched is None:
        raise ValueError(
            f"Color ramp {colormap!r} not found in QGIS style library. "
            f"Run QgsStyle.defaultStyle().colorRampNames() to list available names."
        )
    return style.colorRamp(matched)


@dataclass
class VectorLabels:
    """
    Attribute-based labels for vector layers.

    Labeling is independent of the layer's renderer/style and can be combined
    with any ``VectorStyle``.

    Parameters
    ----------
    field : str
        Name of the attribute field to use as label text, or a QGIS
        expression if ``is_expression`` is ``True``.
    size : float
        Font size in points.
    color : str
        Text color, e.g. ``"black"``, ``"#000000"``.
    is_expression : bool
        If ``True``, ``field`` is evaluated as a QGIS expression rather than
        a plain field name, e.g. ``"name || ' (' || value || ')'"``.
    """

    field: str = ""
    size: float = 10.0
    color: str = "black"
    is_expression: bool = False

    def apply(self, layer: "Layer"):
        from qgis.core import QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling
        from qgis.PyQt.QtGui import QColor

        if not self.field:
            raise ValueError("VectorLabels requires 'field' to be set.")

        qgis_layer = layer.qgis_layer
        if not self.is_expression and qgis_layer.fields().indexOf(self.field) < 0:
            raise ValueError(
                f"Field {self.field!r} not found on layer {layer.get_layer_name()!r}."
            )

        text_format = QgsTextFormat()
        text_format.setSize(self.size)
        text_format.setColor(QColor(self.color))

        settings = QgsPalLayerSettings()
        settings.fieldName = self.field
        settings.isExpression = self.is_expression
        settings.setFormat(text_format)

        qgis_layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        qgis_layer.setLabelsEnabled(True)
