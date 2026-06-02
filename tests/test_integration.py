"""
Integration tests — require a QGIS installation in the current Python process.
Run with:  pytest -m qgis
Skip with: pytest -m "not qgis"
"""
import pytest

# Skip collection if qgis_project itself cannot be imported (no QGIS, no launcher).
qgis_project = pytest.importorskip("qgis_project", reason="qgis_project not importable")
Project = qgis_project.Project
RasterLayer = qgis_project.RasterLayer
RasterStyleBW = qgis_project.RasterStyleBW


pytestmark = pytest.mark.qgis


def test_project_initializes(qgis_app):
    project = Project()
    project.exit()


def test_add_raster_layer_links_qgis_object(qgis_app, sample_tif):
    project = Project()
    layer = RasterLayer(file=str(sample_tif))
    project.add_layer(layer)
    assert hasattr(layer, "qgis_layer")
    assert layer.qgis_layer.isValid()
    project.exit()


def test_raster_layer_extent_after_add(qgis_app, sample_tif):
    project = Project()
    layer = RasterLayer(file=str(sample_tif))
    project.add_layer(layer)
    extent = layer.get_layer_extent()
    assert extent is not None
    assert not extent.isEmpty()
    project.exit()


def test_raster_style_bw_sets_gray_renderer(qgis_app, sample_tif):
    from qgis.core import QgsSingleBandGrayRenderer
    project = Project()
    layer = RasterLayer(file=str(sample_tif), style=RasterStyleBW(vmin=0.0, vmax=99.0))
    project.add_layer(layer)
    assert isinstance(layer.qgis_layer.renderer(), QgsSingleBandGrayRenderer)
    project.exit()


def test_raster_style_bw_contrast_enhancement(qgis_app, sample_tif):
    vmin, vmax = 10.0, 90.0
    project = Project()
    layer = RasterLayer(file=str(sample_tif), style=RasterStyleBW(vmin=vmin, vmax=vmax))
    project.add_layer(layer)
    ce = layer.qgis_layer.renderer().contrastEnhancement()
    assert ce.minimumValue() == vmin
    assert ce.maximumValue() == vmax
    project.exit()


def test_project_save_creates_file(qgis_app, sample_tif, tmp_path):
    project = Project()
    project.add_layer(RasterLayer(file=str(sample_tif)))
    out = tmp_path / "test.qgz"
    project.save(str(out))
    assert out.exists()
    project.exit()


def test_layer_hidden_visibility(qgis_app, sample_tif):
    from qgis.core import QgsProject
    project = Project()
    layer = RasterLayer(file=str(sample_tif), visible=False)
    project.add_layer(layer)
    node = QgsProject.instance().layerTreeRoot().findLayer(layer.qgis_layer.id())
    assert not node.isVisible()
    project.exit()


def test_add_vector_layer(qgis_app, vector_file):
    project = Project()
    project.add_layer(str(vector_file))
    project.exit()


def test_layer_group(qgis_app, sample_tif):
    from qgis.core import QgsLayerTreeGroup, QgsProject
    project = Project()
    project.add_layer(RasterLayer(file=str(sample_tif), group="terrain"))
    root = QgsProject.instance().layerTreeRoot()
    groups = [c for c in root.children() if isinstance(c, QgsLayerTreeGroup)]
    assert any(g.name() == "terrain" for g in groups)
    project.exit()
