"""
Unit tests for _spec.py — no QGIS required.
"""
import json

import pytest

from qgis_project._spec import from_dict, from_json, to_dict, to_json
from qgis_project.layer import Layer, MeshLayer, RasterLayer, WebLayer
from qgis_project.style import (
    MeshStyleScalar,
    MeshStyleVector,
    RasterStyle,
    RasterStyleBW,
    RasterStylePaletted,
)


# ---------------------------------------------------------------------------
# to_dict / from_dict
# ---------------------------------------------------------------------------

def test_vector_layer_round_trip():
    layers = [Layer(file="regions.geojson", name="Regions", group="admin")]
    d = to_dict(layers, "out.qgz")
    result, output, action = from_dict(d)
    assert len(result) == 1
    assert result[0].name == "Regions"
    assert result[0].group == "admin"
    assert output == "out.qgz"
    assert action == "save"


def test_raster_layer_with_style_round_trip():
    layers = [RasterLayer(file="dem.tif", style=RasterStyleBW(vmin=0.0, vmax=3000.0))]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert isinstance(result[0].style, RasterStyleBW)
    assert result[0].style.vmin == 0.0
    assert result[0].style.vmax == 3000.0


def test_raster_style_paletted_round_trip():
    style = RasterStylePaletted(
        colors={1: "#1b9e77", 2: "red"}, labels={1: "Forest"}
    )
    layers = [RasterLayer(file="lc.tif", style=style)]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert isinstance(result[0].style, RasterStylePaletted)
    assert result[0].style.colors == {1: "#1b9e77", 2: "red"}
    assert result[0].style.labels == {1: "Forest"}


def test_raster_style_paletted_json_round_trip_stringifies_keys():
    # JSON has no integer keys, so a round trip through to_json/from_json turns
    # the band-value keys into strings. set_style() coerces them back with
    # int(), so this is expected and the values must survive.
    style = RasterStylePaletted(colors={1: "#1b9e77", 2: "red"})
    layers = [RasterLayer(file="lc.tif", style=style)]
    result, _, _ = from_json(to_json(layers, "out.qgz"))
    assert result[0].style.colors == {"1": "#1b9e77", "2": "red"}


def test_raster_style_no_limits_round_trip():
    layers = [RasterLayer(file="dem.tif", style=RasterStyleBW())]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert result[0].style.vmin is None
    assert result[0].style.vmax is None


def test_nested_group_round_trip():
    layers = [Layer(file="f.shp", group=["terrain", "raw"])]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert result[0].group == ["terrain", "raw"]


def test_visible_false_round_trip():
    layers = [Layer(file="f.shp", visible=False)]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert result[0].visible is False


def test_action_preserved():
    layers = [Layer(file="f.shp")]
    _, _, action = from_dict(to_dict(layers, "out.qgz", action="save_and_open"))
    assert action == "save_and_open"


def test_multiple_layers_round_trip():
    layers = [
        Layer(file="a.geojson"),
        RasterLayer(file="b.tif", style=RasterStyleBW(vmin=10, vmax=20)),
    ]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert len(result) == 2
    assert isinstance(result[1], RasterLayer)


def test_mesh_layer_scalar_style_round_trip():
    layers = [
        MeshLayer(
            file="model.nc",
            dataset_group="water depth",
            style=MeshStyleScalar(colormap="Spectral", vmin=0.0, vmax=5.0),
        )
    ]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert isinstance(result[0], MeshLayer)
    assert result[0].dataset_group == "water depth"
    assert isinstance(result[0].style, MeshStyleScalar)
    assert result[0].style.colormap == "Spectral"
    assert result[0].style.vmax == 5.0


def test_mesh_layer_vector_style_round_trip():
    layers = [MeshLayer(file="model.nc", style=MeshStyleVector(color="blue", line_width=0.5))]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert isinstance(result[0].style, MeshStyleVector)
    assert result[0].style.color == "blue"
    assert result[0].style.line_width == 0.5


def test_mesh_layer_no_style_round_trip():
    layers = [MeshLayer(file="terrain.2dm", dataset_group=0)]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert isinstance(result[0], MeshLayer)
    assert result[0].dataset_group == 0
    assert result[0].style is None


def test_web_layer_round_trip():
    layers = [WebLayer.osm(group="Background")]
    result, output, action = from_dict(to_dict(layers, "out.qgz"))
    assert len(result) == 1
    assert isinstance(result[0], WebLayer)
    assert result[0].name == "OpenStreetMap"
    assert result[0].group == "Background"
    assert result[0].provider == "wms"


def test_web_layer_wfs_round_trip():
    layers = [WebLayer.wfs("https://example.org/wfs", typename="ns:rivers", name="Rivers")]
    result, _, _ = from_dict(to_dict(layers, "out.qgz"))
    assert result[0].provider == "WFS"
    assert result[0].name == "Rivers"


def test_unknown_layer_type_raises():
    d = to_dict([Layer(file="x.shp")], "out.qgz")
    d["layers"][0]["type"] = "UnknownLayer"
    with pytest.raises(ValueError, match="Unknown layer type"):
        from_dict(d)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def test_to_json_is_valid_json():
    s = to_json([Layer(file="x.geojson")], "out.qgz")
    parsed = json.loads(s)
    assert "layers" in parsed
    assert "action" in parsed
    assert "output" in parsed


def test_json_round_trip():
    layers = [RasterLayer(file="dem.tif", name="DEM", style=RasterStyleBW(vmin=5, vmax=95))]
    result, output, action = from_json(to_json(layers, "test.qgz"))
    assert result[0].style.vmax == 95
    assert output == "test.qgz"


# ---------------------------------------------------------------------------
# YAML (requires pyyaml)
# ---------------------------------------------------------------------------

yaml = pytest.importorskip("yaml", reason="pyyaml not installed")


def test_yaml_round_trip():
    from qgis_project._spec import from_yaml, to_yaml
    layers = [RasterLayer(file="dem.tif", style=RasterStyleBW(vmin=10, vmax=500))]
    result, output, action = from_yaml(to_yaml(layers, "out.qgz"))
    assert result[0].style.vmax == 500
    assert action == "save"


def test_yaml_is_human_readable():
    from qgis_project._spec import to_yaml
    s = to_yaml([Layer(file="x.geojson", name="MyLayer")], "out.qgz")
    assert "MyLayer" in s
    assert "x.geojson" in s
    assert "{" not in s  # no JSON-style braces
