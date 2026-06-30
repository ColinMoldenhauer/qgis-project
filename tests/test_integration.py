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
RasterStylePaletted = qgis_project.RasterStylePaletted
WebLayer = qgis_project.WebLayer


pytestmark = pytest.mark.qgis


@pytest.fixture(autouse=True)
def _fresh_project():
    """Clear the QgsProject singleton before each test to prevent state leakage."""
    from qgis.core import QgsProject
    QgsProject.instance().clear()
    yield


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


def test_raster_style_paletted_explicit_colors(qgis_app, categorical_tif):
    from qgis.core import QgsPalettedRasterRenderer
    project = Project()
    layer = RasterLayer(
        file=str(categorical_tif),
        style=RasterStylePaletted(
            colors={1: "#ff0000", 2: "#00ff00", 3: "#0000ff"},
            labels={1: "Forest", 2: "Urban"},
        ),
    )
    project.add_layer(layer)
    renderer = layer.qgis_layer.renderer()
    assert isinstance(renderer, QgsPalettedRasterRenderer)

    classes = {c.value: c for c in renderer.classes()}
    assert set(classes) == {1, 2, 3}
    assert classes[1].color.name() == "#ff0000"
    assert classes[3].color.name() == "#0000ff"
    # Explicit labels win; values without one fall back to the numeric value.
    assert classes[1].label == "Forest"
    assert classes[3].label == "3"
    project.exit()


def test_raster_style_paletted_auto_detects_classes(qgis_app, categorical_tif):
    from qgis.core import QgsPalettedRasterRenderer
    project = Project()
    layer = RasterLayer(file=str(categorical_tif), style=RasterStylePaletted())
    project.add_layer(layer)
    renderer = layer.qgis_layer.renderer()
    assert isinstance(renderer, QgsPalettedRasterRenderer)
    # The three distinct band values are discovered from the raster itself.
    assert {c.value for c in renderer.classes()} == {1, 2, 3}
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


# ---------------------------------------------------------------------------
# NetCDF — multi-variable container support
# ---------------------------------------------------------------------------

def test_netcdf_adds_all_variables_by_default(qgis_app, sample_nc):
    from qgis.core import QgsProject
    project = Project()
    project.add_layer(str(sample_nc))
    layers = QgsProject.instance().mapLayers().values()
    names = {l.name() for l in layers}
    # temperature, precipitation (root) + humidity (group) all expand.
    assert "climate.nc : temperature" in names
    assert "climate.nc : precipitation" in names
    assert all(l.isValid() for l in layers)
    project.exit()


def test_netcdf_single_variable_selection(qgis_app, sample_nc):
    from qgis.core import QgsProject
    project = Project()
    project.add_layer(str(sample_nc), variable="temperature")
    layers = list(QgsProject.instance().mapLayers().values())
    assert len(layers) == 1
    layer = layers[0]
    assert layer.isValid()
    assert layer.name() == "climate.nc : temperature"
    # The source is addressed through GDAL's NetCDF subdataset syntax.
    assert "NETCDF" in layer.source()
    assert "temperature" in layer.source()
    project.exit()


def test_netcdf_variable_subset_selection(qgis_app, sample_nc):
    from qgis.core import QgsProject
    project = Project()
    project.add_layer(str(sample_nc), variable=["temperature", "precipitation"])
    names = {l.name() for l in QgsProject.instance().mapLayers().values()}
    assert names == {"climate.nc : temperature", "climate.nc : precipitation"}
    project.exit()


def test_netcdf_unknown_variable_is_skipped(qgis_app, sample_nc):
    from qgis.core import QgsProject
    project = Project()
    project.add_layer(str(sample_nc), variable="does_not_exist")
    assert len(QgsProject.instance().mapLayers()) == 0
    project.exit()


def test_netcdf_time_dimension_is_multiband(qgis_app, sample_nc):
    from qgis.core import QgsProject
    project = Project()
    project.add_layer(str(sample_nc), variable="temperature")
    layer = next(iter(QgsProject.instance().mapLayers().values()))
    # The 3-step time dimension surfaces as three raster bands.
    assert layer.bandCount() == 3
    project.exit()


def test_netcdf_nested_group_maps_to_layer_group(qgis_app, sample_nc):
    from qgis.core import QgsLayerTreeGroup, QgsProject
    from qgis_project import list_raster_variables

    # Skip if this GDAL build doesn't expose the grouped variable as a subdataset.
    if not any("humidity" in v for v in list_raster_variables(str(sample_nc))):
        pytest.skip("GDAL build does not expose NetCDF-4 group variables")

    project = Project()
    project.add_layer(str(sample_nc), variable="/forecast/humidity")
    root = QgsProject.instance().layerTreeRoot()
    groups = [c.name() for c in root.children() if isinstance(c, QgsLayerTreeGroup)]
    assert "forecast" in groups
    project.exit()


# ---------------------------------------------------------------------------
# Format coverage — one test per common file format
# ---------------------------------------------------------------------------

def test_load_gpkg(qgis_app, gpkg_file):
    project = Project()
    project.add_layer(str(gpkg_file))
    from qgis.core import QgsProject
    assert len(QgsProject.instance().mapLayers()) == 1
    project.exit()


def test_load_shp(qgis_app, shp_file):
    project = Project()
    project.add_layer(str(shp_file))
    from qgis.core import QgsProject
    assert len(QgsProject.instance().mapLayers()) == 1
    project.exit()


def test_load_kml(qgis_app, kml_file):
    project = Project()
    project.add_layer(str(kml_file))
    from qgis.core import QgsProject
    assert len(QgsProject.instance().mapLayers()) == 1
    project.exit()


def test_load_flatgeobuf(qgis_app, flatgeobuf_file):
    project = Project()
    project.add_layer(str(flatgeobuf_file))
    from qgis.core import QgsProject
    assert len(QgsProject.instance().mapLayers()) == 1
    project.exit()


def test_layer_group(qgis_app, sample_tif):
    from qgis.core import QgsLayerTreeGroup, QgsProject
    project = Project()
    project.add_layer(RasterLayer(file=str(sample_tif), group="terrain"))
    root = QgsProject.instance().layerTreeRoot()
    groups = [c for c in root.children() if isinstance(c, QgsLayerTreeGroup)]
    assert any(g.name() == "terrain" for g in groups)
    project.exit()


def test_project_crs_constructor(qgis_app):
    from qgis.core import QgsProject
    project = Project(crs="EPSG:3857")
    assert QgsProject.instance().crs().authid() == "EPSG:3857"
    project.exit()


def test_project_crs_int_form(qgis_app):
    from qgis.core import QgsProject
    project = Project(crs=3857)
    assert QgsProject.instance().crs().authid() == "EPSG:3857"
    project.exit()


def test_project_set_crs(qgis_app):
    from qgis.core import QgsProject
    project = Project()
    project.set_crs(32632)
    assert QgsProject.instance().crs().authid() == "EPSG:32632"
    project.exit()


def test_layer_crs_field_not_mutated(qgis_app, sample_tif):
    project = Project()
    layer = RasterLayer(file=str(sample_tif), crs=4326)
    project.add_layer(layer)
    assert layer.crs == 4326  # must remain int, not coerced to "EPSG:4326"
    project.exit()


def test_add_web_layer_osm(qgis_app):
    from qgis.core import QgsProject
    project = Project()
    project.add_layer(WebLayer.osm())
    layers = QgsProject.instance().mapLayers()
    assert len(layers) == 1
    project.exit()


def test_add_web_layer_group(qgis_app):
    from qgis.core import QgsLayerTreeGroup, QgsProject
    project = Project()
    project.add_layer(WebLayer.osm(group="Background"))
    root = QgsProject.instance().layerTreeRoot()
    groups = [c for c in root.children() if isinstance(c, QgsLayerTreeGroup)]
    assert any(g.name() == "Background" for g in groups)
    project.exit()


def test_process_buffer_to_file(qgis_app, vector_file, tmp_path):
    from qgis.core import QgsProject
    project = Project()
    out = str(tmp_path / "buffer.gpkg")
    project.process("native:buffer", {"INPUT": str(vector_file), "DISTANCE": 0.1, "OUTPUT": out}, name="Buffered")
    assert (tmp_path / "buffer.gpkg").exists()
    layers = QgsProject.instance().mapLayers()
    assert len(layers) == 1
    project.exit()


def test_process_buffer_memory(qgis_app, vector_file):
    from qgis.core import QgsProject
    project = Project()
    project.process("native:buffer", {"INPUT": str(vector_file), "DISTANCE": 0.1, "OUTPUT": "memory:"}, name="Buffered")
    layers = QgsProject.instance().mapLayers()
    assert len(layers) == 1
    project.exit()


def test_process_result_in_group(qgis_app, vector_file, tmp_path):
    from qgis.core import QgsLayerTreeGroup, QgsProject
    project = Project()
    out = str(tmp_path / "buf.gpkg")
    project.process("native:buffer", {"INPUT": str(vector_file), "DISTANCE": 0.1, "OUTPUT": out},
                    name="Buffered", group="Results")
    root = QgsProject.instance().layerTreeRoot()
    groups = [c for c in root.children() if isinstance(c, QgsLayerTreeGroup)]
    assert any(g.name() == "Results" for g in groups)
    project.exit()
