from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
        super().set_style(layer)

        vmin = self.vmin if self.vmin is not None else layer.get_layer_min()
        vmax = self.vmax if self.vmax is not None else layer.get_layer_max()

        from qgis.core import QgsSingleBandGrayRenderer, QgsContrastEnhancement
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



# TODO: implement and test
@dataclass
class RasterStyleSinglePseudocolor(RasterStyle):
    """
    A single-band pseudocolor style for raster layers.

    Parameters
    ----------
    colormap : str
        Name of the colormap to use for layer styling
    """
    colormap: str = "viridis"

    # TODO: check with CLIMERS PC
    # def set_style(self): pass


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

    # TODO: check with CLIMERS PC
    # def set_style(self): pass