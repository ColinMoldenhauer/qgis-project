"""
Unit tests — no QGIS installation required.
"""
import pytest

# Import directly from submodules so this file is runnable without QGIS.
from qgis_project.layer import (
    Layer,
    QgisLayerLinkError,
    RasterLayer,
    WebLayer,
    gdal_raster_source,
    is_netcdf,
    layer_from_path,
    netcdf_name_and_group,
)
from qgis_project.style import (
    RasterStyle,
    RasterStyleBW,
    RasterStylePaletted,
    RasterStyleSinglePseudocolor,
    Style,
    VectorStyleSingleSymbol,
)
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
# layer_from_path
# ---------------------------------------------------------------------------

def test_layer_from_path_plain_layer():
    layer = layer_from_path("boundaries.geojson")
    assert type(layer) is Layer
    assert layer.file == "boundaries.geojson"

def test_layer_from_path_vector_style_stays_layer():
    layer = layer_from_path("regions.geojson", style=VectorStyleSingleSymbol(color="red"))
    assert type(layer) is Layer

def test_layer_from_path_raster_style_builds_raster_layer():
    layer = layer_from_path("dem.tif", style=RasterStyleBW(vmin=0, vmax=3000))
    assert type(layer) is RasterLayer
    assert isinstance(layer.style, RasterStyleBW)

def test_layer_from_path_band_idx_builds_raster_layer():
    layer = layer_from_path("rgb.tif", band_idx=[1, 2, 3])
    assert type(layer) is RasterLayer
    assert layer.band_idx == [1, 2, 3]

def test_layer_from_path_forwards_common_kwargs():
    layer = layer_from_path("dem.tif", name="Elevation", group="terrain", visible=False)
    assert layer.name == "Elevation"
    assert layer.group == "terrain"
    assert layer.visible is False


# ---------------------------------------------------------------------------
# NetCDF helpers
# ---------------------------------------------------------------------------

def test_is_netcdf_by_extension():
    assert is_netcdf("climate.nc")
    assert is_netcdf("/data/CLIMATE.NC4")
    assert is_netcdf("model.cdf")
    assert not is_netcdf("dem.tif")
    assert not is_netcdf("regions.geojson")


def test_gdal_raster_source_plain_file():
    assert gdal_raster_source("dem.tif", None) == "dem.tif"


def test_gdal_raster_source_netcdf_variable():
    assert gdal_raster_source("climate.nc", "temperature") == 'NETCDF:"climate.nc":temperature'


def test_gdal_raster_source_nested_variable():
    assert (
        gdal_raster_source("climate.nc", "/forecast/humidity")
        == 'NETCDF:"climate.nc":/forecast/humidity'
    )


def test_netcdf_name_and_group_flat_default_name():
    name, group = netcdf_name_and_group("climate.nc", "temperature", None, None, multiple=True)
    assert name == "climate.nc : temperature"
    assert group is None


def test_netcdf_name_and_group_nested_maps_to_subgroup():
    name, group = netcdf_name_and_group(
        "/data/climate.nc", "/forecast/humidity", None, None, multiple=True
    )
    assert name == "climate.nc : humidity"
    assert group == ["forecast"]


def test_netcdf_name_and_group_combines_user_group_and_internal():
    name, group = netcdf_name_and_group(
        "climate.nc", "/forecast/humidity", "weather", None, multiple=True
    )
    assert group == ["weather", "forecast"]


def test_netcdf_name_and_group_explicit_name_only_when_single():
    # A single selected variable honors the user's name...
    name, _ = netcdf_name_and_group("climate.nc", "temperature", None, "Temp", multiple=False)
    assert name == "Temp"
    # ...but when several variables expand, an explicit name would collide, so
    # the per-variable default wins.
    name, _ = netcdf_name_and_group("climate.nc", "temperature", None, "Temp", multiple=True)
    assert name == "climate.nc : temperature"


def test_layer_from_path_netcdf_builds_raster_layer():
    layer = layer_from_path("climate.nc")
    assert type(layer) is RasterLayer


def test_layer_from_path_variable_builds_raster_layer():
    layer = layer_from_path("climate.nc", variable="temperature")
    assert type(layer) is RasterLayer
    assert layer.variable == "temperature"


def test_raster_layer_variable_default_is_none():
    assert RasterLayer(file="climate.nc").variable is None


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

def test_raster_style_paletted_defaults():
    s = RasterStylePaletted()
    assert s.colors is None
    assert s.labels is None
    assert s.colormap == "Spectral"

def test_raster_style_paletted_explicit_colors():
    s = RasterStylePaletted(colors={1: "red", 2: "#00ff00"}, labels={1: "Forest"})
    assert s.colors == {1: "red", 2: "#00ff00"}
    assert s.labels == {1: "Forest"}


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


# ---------------------------------------------------------------------------
# Subprocess package staging (isolation from the host's import roots)
# ---------------------------------------------------------------------------

def test_stage_package_copies_only_qgis_project(tmp_path):
    """Staging must yield a clean import root holding only the package.

    Regression guard: pointing PYTHONPATH at a shared site-packages would leak
    every neighbouring package (numpy, GDAL, …) — built for the wrong Python —
    onto QGIS's interpreter and break import there.
    """
    from qgis_project._subprocess import SubprocessProject

    staged = SubprocessProject._stage_package(str(tmp_path))

    # The parent (the import root we put on PYTHONPATH) contains nothing but
    # the package itself.
    assert [p.name for p in tmp_path.iterdir()] == ["qgis_project"]
    assert staged == tmp_path / "qgis_project"
    assert (staged / "__init__.py").is_file()
    assert (staged / "_executor.py").is_file()


def test_stage_package_excludes_pycache(tmp_path):
    from qgis_project._subprocess import SubprocessProject

    staged = SubprocessProject._stage_package(str(tmp_path))
    assert not list(staged.rglob("__pycache__"))
    assert not list(staged.rglob("*.pyc"))
