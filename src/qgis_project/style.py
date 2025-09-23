from dataclasses import dataclass

from qgis_project.layer import Layer
from qgis_project.utils import qgis_lazy_import


@dataclass
class Style:
    opacity: float = 1.

    def set_style(self, layer: Layer):
        if layer.opacity is not None:
            layer.setOpacity(layer.opacity)


@dataclass
@qgis_lazy_import({
    "qgis.core": ["QgsSingleBandGrayRenderer", "QgsContrastEnhancement"],
})
class RasterStyle(Style):
    vmin: float | None = None
    vmax: float | None = None


@dataclass
class RasterStyleBW(RasterStyle):

    def set_style(self, layer: Layer):
        super().set_style(layer)

        vmin = self.vmin if self.vmin is not None else layer.get_layer_min()
        vmax = self.vmax if self.vmax is not None else layer.get_layer_max()

        # https://gis.stackexchange.com/questions/377569/setting-max-min-values-of-singleband-grey-layer-using-pyqgis
        renderer = QgsSingleBandGrayRenderer(layer.dataProvider(), 1)   # TODO: what is 1?
        render_type = renderer.dataType(1)   # TODO: what is 1?
        enhancement = QgsContrastEnhancement(render_type)
        contrast_enhancement = QgsContrastEnhancement.StretchToMinimumMaximum
        enhancement.setContrastEnhancementAlgorithm(contrast_enhancement, True)
        enhancement.setMinimumValue(vmin)
        enhancement.setMaximumValue(vmax)

        layer.setRenderer(renderer)
        layer.renderer().setContrastEnhancement(enhancement)
        layer.triggerRepaint()  # TODO: necessary?




@dataclass
class RasterStylePseudocolor(RasterStyle):
    colormap: str = "viridis"

    # TODO: check with CLIMERS PC
    # def set_style(self): pass