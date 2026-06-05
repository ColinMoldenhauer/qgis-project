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
    opacity: float = 1.

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
    vmin : float | None
        The minimum value used for the colorbar.
        If None, will be automatically determined from the layer data
    vmax : float | None
        The maximum value used for the colorbar.
        If None, will be automatically determined from the layer data
    """
    vmin: float | None = None
    vmax: float | None = None


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
        renderer = QgsSingleBandGrayRenderer(qgis_layer.dataProvider(), 1)   # TODO: what is 1?
        render_type = renderer.dataType(1)   # TODO: what is 1?
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
        matched = next((n for n in ramp_names if n.lower() == self.colormap.lower()), None)
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


# TODO: implement and test
@dataclass
class RasterStyleMultiPseudocolor(RasterStyle):
    """
    A multi-band pseudocolor style for raster layers.

    Parameters
    ----------
    colormap : str
        Name of the colormap to use for layer styling
    """
    colormap: str = "viridis"