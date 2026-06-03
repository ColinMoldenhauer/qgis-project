"""
Unit tests — no QGIS installation required.
"""
import pytest

# Import directly from submodules so this file is runnable without QGIS.
from qgis_project.layer import Layer, QgisLayerLinkError, RasterLayer, WebLayer
from qgis_project.style import RasterStyle, RasterStyleBW, RasterStyleSinglePseudocolor, Style
from qgis_project.utils import normalize_crs


# ---------------------------------------------------------------------------
# Layer
# ---------------------------------------------------------------------------

def test_layer_requires_file():
    with pytest.raises(TypeError):
        Layer()

def test_layer_defaults():
    layer = Layer(file="test.tif")
    assert layer.visible is True
    assert layer.group is None
    assert layer.name is None
    assert layer.crs is None
    assert layer.overwrite_existing is False

def test_layer_get_layer_name_from_file():
    assert Layer(file="/some/path/dem.tif").get_layer_name() == "dem.tif"

def test_layer_get_layer_name_from_name_field():
    assert Layer(file="/some/path/dem.tif", name="elevation").get_layer_name() == "elevation"

def test_layer_get_path_no_group():
    assert Layer(file="dem.tif").get_path() == "dem.tif"

def test_layer_get_path_string_group():
    assert Layer(file="dem.tif", group="terrain").get_path() == ["terrain", "dem.tif"]

def test_layer_get_path_nested_group():
    assert Layer(file="dem.tif", group=["terrain", "raster"]).get_path() == ["terrain", "raster", "dem.tif"]

def test_layer_link_error_on_extent():
    with pytest.raises(QgisLayerLinkError):
        Layer(file="dem.tif").get_layer_extent()

def test_layer_pickle_roundtrip(tmp_path):
    layer = Layer(file="dem.tif", name="elevation", group="terrain")
    path = str(tmp_path / "layer.pkl")
    layer.save(path)
    loaded = Layer.load(path)
    assert loaded.file == layer.file
    assert loaded.name == layer.name
    assert loaded.group == layer.group


# ---------------------------------------------------------------------------
# RasterLayer
# ---------------------------------------------------------------------------

def test_raster_layer_defaults():
    layer = RasterLayer(file="dem.tif")
    assert layer.band_idx == 1
    assert isinstance(layer.style, RasterStyle)

def test_raster_layer_set_band_idx():
    layer = RasterLayer(file="dem.tif")
    layer.set_band_idx(2)
    assert layer.band_idx == 2

def test_raster_layer_link_error_on_min():
    with pytest.raises(QgisLayerLinkError):
        RasterLayer(file="dem.tif").get_layer_min()

def test_raster_layer_link_error_on_max():
    with pytest.raises(QgisLayerLinkError):
        RasterLayer(file="dem.tif").get_layer_max()


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

def test_style_defaults():
    assert Style().opacity == 1.0

def test_raster_style_defaults():
    s = RasterStyle()
    assert s.vmin is None
    assert s.vmax is None
    assert s.opacity == 1.0

def test_raster_style_bw_explicit_limits():
    s = RasterStyleBW(vmin=0.0, vmax=100.0)
    assert s.vmin == 0.0
    assert s.vmax == 100.0

def test_raster_style_single_pseudocolor_default_colormap():
    assert RasterStyleSinglePseudocolor().colormap == "viridis"


# ---------------------------------------------------------------------------
# normalize_crs
# ---------------------------------------------------------------------------

def test_normalize_crs_int():
    assert normalize_crs(4326) == "EPSG:4326"

def test_normalize_crs_str_passthrough():
    assert normalize_crs("EPSG:3857") == "EPSG:3857"

def test_normalize_crs_str_custom():
    assert normalize_crs("ESRI:54009") == "ESRI:54009"


# ---------------------------------------------------------------------------
# WebLayer
# ---------------------------------------------------------------------------

def test_web_layer_osm_defaults():
    layer = WebLayer.osm()
    assert layer.name == "OpenStreetMap"
    assert layer.provider == "wms"
    assert "openstreetmap.org" in layer.uri

def test_web_layer_xyz_uri():
    layer = WebLayer.xyz("https://example.org/{z}/{x}/{y}.png", name="Custom")
    assert "type=xyz" in layer.uri
    assert "example.org" in layer.uri

def test_web_layer_wfs_provider():
    layer = WebLayer.wfs("https://ows.example.org/wfs", typename="ns:rivers")
    assert layer.provider == "WFS"
    assert layer.name == "ns:rivers"

def test_web_layer_get_path_with_group():
    layer = WebLayer.osm(group="Background")
    assert layer.get_path() == ["Background", "OpenStreetMap"]

def test_web_layer_name_fallback():
    layer = WebLayer(uri="type=xyz&url=https://x.org/{z}/{x}/{y}.png", provider="wms")
    assert layer.get_layer_name() == "Web Layer"


# ---------------------------------------------------------------------------
# Layer CRS field is not mutated during normalization
# ---------------------------------------------------------------------------

def test_layer_crs_int_field_unchanged():
    layer = Layer(file="dem.tif", crs=4326)
    assert layer.crs == 4326  # still int — normalization must not mutate this
