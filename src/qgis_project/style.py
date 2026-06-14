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
        renderer = QgsSingleBandGrayRenderer(
            qgis_layer.dataProvider(), 1
        )  # TODO: what is 1?
        render_type = renderer.dataType(1)  # TODO: what is 1?
        enhancement = QgsContrastEnhancement(render_type)
        contrast_enhancement = QgsContrastEnhancement.StretchToMinimumMaximum
        enhancement.setContrastEnhancementAlgorithm(contrast_enhancement, True)
        enhancement.setMinimumValue(vmin)
        enhancement.setMaximumValue(vmax)

        qgis_layer.setRenderer(renderer)
        qgis_layer.renderer().setContrastEnhancement(enhancement)
        qgis_layer.triggerRepaint()  # TODO: necessary?
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
            QgsStyle,
        )

        qgis_layer = layer.qgis_layer
        band = getattr(layer, "band_idx", 1)
        provider = qgis_layer.dataProvider()

        vmin = self.vmin if self.vmin is not None else layer.get_layer_min()
        vmax = self.vmax if self.vmax is not None else layer.get_layer_max()

        style = QgsStyle.defaultStyle()
        ramp_names = style.colorRampNames()
        matched = next(
            (n for n in ramp_names if n.lower() == self.colormap.lower()), None
        )
        if matched is None:
            raise ValueError(
                f"Color ramp {self.colormap!r} not found in QGIS style library. "
                f"Run QgsStyle.defaultStyle().colorRampNames() to list available names."
            )
        ramp = style.colorRamp(matched)

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
