"""
Datacube layers, and raster layers read through a chosen provider.

The tests that build or serialize layer specs need neither QGIS nor the
datacube package. Reading a store needs the `qgis-datacube-viewer` package;
making QGIS layers (marked `qgis`) needs QGIS as well.
"""
import pytest

from qgis_project._spec import from_dict, from_json, to_dict, to_json
from qgis_project._subprocess import SubprocessProject
from qgis_project.layer import (
    DATACUBE_PROVIDER,
    DatacubeLayer,
    RasterLayer,
    layer_from_path,
)
from qgis_project.style import RasterStyleBW


# ---------------------------------------------------------------------------
# Choosing the layer class
# ---------------------------------------------------------------------------

def test_datacube_layer_defaults():
    layer = DatacubeLayer("cube.zarr")
    assert isinstance(layer, RasterLayer)
    assert layer.provider == DATACUBE_PROVIDER
    assert layer.variable is None
    assert layer.dataset == ""
    assert layer.indices == {}
    assert layer.ref is None

def test_raster_layer_detects_its_provider_by_default():
    assert RasterLayer("dem.tif").provider is None

def test_layer_from_path_datacube_provider_builds_datacube_layer():
    layer = layer_from_path("dem.zarr", provider=DATACUBE_PROVIDER)
    assert type(layer) is DatacubeLayer

def test_layer_from_path_netcdf_with_datacube_provider_is_a_datacube():
    layer = layer_from_path("cube.nc", provider=DATACUBE_PROVIDER, variable="temperature")
    assert type(layer) is DatacubeLayer
    assert layer.variable == "temperature"

@pytest.mark.parametrize(
    "keyword, value",
    [("dataset", "utm32"), ("indices", {"time": 2}), ("ref", "tag:v1")],
)
def test_layer_from_path_datacube_keyword_builds_datacube_layer(keyword, value):
    layer = layer_from_path("cube.zarr", **{keyword: value})
    assert type(layer) is DatacubeLayer
    assert getattr(layer, keyword) == value

def test_layer_from_path_other_provider_builds_raster_layer():
    layer = layer_from_path("dem.tif", provider="gdal")
    assert type(layer) is RasterLayer
    assert layer.provider == "gdal"


# ---------------------------------------------------------------------------
# Serialization (the subprocess executor rebuilds layers from JSON)
# ---------------------------------------------------------------------------

def test_datacube_layer_json_round_trip():
    layer = DatacubeLayer(
        "s3://bucket/cube.zarr",
        variable="temperature",
        dataset="utm32",
        indices={"time": 2},
        ref="tag:v1",
        style=RasterStyleBW(vmin=0, vmax=10),
    )
    (restored,), _, _ = from_json(to_json([layer], "out.qgz"))
    assert restored == layer

def test_raster_layer_provider_round_trip():
    layer = RasterLayer("url=cube.zarr&bands=elevation", provider="some_provider")
    (restored,), _, _ = from_dict(to_dict([layer], "out.qgz"))
    assert restored == layer

def test_subprocess_add_datacube_layer_accumulates():
    proj = SubprocessProject()
    proj.add_datacube_layer("cube.zarr", variable="temperature", indices={"time": 1})
    (layer,) = proj._layers
    assert type(layer) is DatacubeLayer
    assert layer.indices == {"time": 1}


# ---------------------------------------------------------------------------
# Reading stores (needs qgis-datacube-viewer, not QGIS)
# ---------------------------------------------------------------------------

def test_layer_uri_carries_every_field():
    pytest.importorskip("datacube_viewer.layeruri")
    from qgis_project._datacube import layer_uri

    uri = layer_uri(
        "C:/data/my cube & more.zarr",
        dataset="utm32",
        ref="tag:v1",
        variable="temperature",
        indices={"time": 2, "sensor": 1},
    )
    assert uri.store_uri == "C:/data/my cube & more.zarr"
    assert uri.dataset == "utm32"
    assert uri.ref.label == "tag:v1"
    assert uri.bands == ("temperature",)
    assert dict(uri.indices) == {"time": 2, "sensor": 1}

@pytest.mark.parametrize(
    "nodata, expected",
    [(None, None), ([], ()), (-9999, (-9999.0,)), ([0, 1.5], (0.0, 1.5))],
)
def test_layer_uri_carries_the_nodata_override(nodata, expected):
    pytest.importorskip("datacube_viewer.layeruri")
    from qgis_project._datacube import layer_uri

    assert layer_uri("cube.zarr", nodata=nodata).nodata == expected

def test_layer_uri_follows_branch_main_by_default():
    pytest.importorskip("datacube_viewer.layeruri")
    from qgis_project._datacube import layer_uri

    uri = layer_uri("cube.zarr")
    assert uri.ref.label == "branch:main"
    assert uri.bands == ()

def test_list_datacube_variables(datacube_nc):
    pytest.importorskip("datacube_viewer.core")
    from qgis_project import list_datacube_variables

    assert sorted(list_datacube_variables(str(datacube_nc))) == ["elevation", "temperature"]

def test_list_datacube_variables_unknown_dataset(datacube_nc):
    pytest.importorskip("datacube_viewer.core")
    from qgis_project import list_datacube_variables

    with pytest.raises(ValueError, match="No dataset"):
        list_datacube_variables(str(datacube_nc), dataset="nope")


# ---------------------------------------------------------------------------
# Choosing the provider in QGIS (needs QGIS)
# ---------------------------------------------------------------------------

def _layers_by_name():
    from qgis.core import QgsProject

    return {layer.name(): layer for layer in QgsProject.instance().mapLayers().values()}

@pytest.fixture
def project(qgis_app):
    from qgis.core import QgsProject
    from qgis_project import Project

    QgsProject.instance().clear()
    return Project()

@pytest.mark.qgis
def test_forced_gdal_provider(project, sample_tif):
    project.add_layer(str(sample_tif), provider="gdal")
    (qgis_layer,) = _layers_by_name().values()
    assert qgis_layer.isValid()
    assert qgis_layer.providerType() == "gdal"

@pytest.mark.qgis
def test_unknown_provider_adds_nothing(project, sample_tif):
    layer = RasterLayer(str(sample_tif), provider="no_such_provider")
    project.add_layer(layer)
    assert not hasattr(layer, "qgis_layer")
    assert _layers_by_name() == {}

@pytest.mark.qgis
def test_ensure_provider_knows_qgis_own_providers(qgis_app):
    from qgis_project.utils import ensure_provider

    assert ensure_provider("gdal")

@pytest.mark.qgis
def test_ensure_provider_registers_through_entry_points(qgis_app, monkeypatch):
    from qgis_project import utils

    calls = []

    class FakeEntryPoint:
        name = "qgis_project_test_provider"
        value = "tests:register"

        def load(self):
            return lambda: calls.append(self.name)

    monkeypatch.setattr(utils, "_provider_entry_points", lambda: [FakeEntryPoint()])
    # The fake registers nothing, so the provider is still missing afterwards.
    assert utils.ensure_provider("qgis_project_test_provider") is False
    assert calls == ["qgis_project_test_provider"]


# ---------------------------------------------------------------------------
# Datacube layers in QGIS (needs QGIS and qgis-datacube-viewer)
# ---------------------------------------------------------------------------

@pytest.fixture
def datacube_project(project):
    pytest.importorskip("datacube_viewer.provider")
    return project

@pytest.mark.qgis
def test_add_datacube_layer_adds_one_layer_per_variable(datacube_project, datacube_nc):
    datacube_project.add_datacube_layer(str(datacube_nc))
    layers = _layers_by_name()
    assert sorted(layers) == ["cube.nc : elevation", "cube.nc : temperature"]
    for qgis_layer in layers.values():
        assert qgis_layer.isValid()
        assert qgis_layer.providerType() == DATACUBE_PROVIDER
        assert qgis_layer.bandCount() == 1

@pytest.mark.qgis
def test_datacube_variable_name_and_slice(datacube_project, datacube_nc):
    datacube_project.add_layer(
        DatacubeLayer(
            str(datacube_nc), variable="temperature", indices={"time": 2}, name="March"
        )
    )
    (qgis_layer,) = _layers_by_name().values()
    assert qgis_layer.name() == "March"
    assert qgis_layer.dataProvider().indices() == {"time": 2}

@pytest.mark.qgis
def test_add_layer_with_datacube_provider_key(datacube_project, datacube_nc):
    datacube_project.add_layer(str(datacube_nc), provider=DATACUBE_PROVIDER, variable="elevation")
    (qgis_layer,) = _layers_by_name().values()
    assert qgis_layer.isValid()
    assert qgis_layer.providerType() == DATACUBE_PROVIDER

@pytest.mark.qgis
def test_raster_layer_with_provider_uri(datacube_project, datacube_nc):
    """The generic route: any provider, with its own source string."""
    uri = f"url={datacube_nc.as_posix()}&bands=elevation"
    datacube_project.add_layer(RasterLayer(uri, name="dem", provider=DATACUBE_PROVIDER))
    assert _layers_by_name()["dem"].isValid()

@pytest.mark.qgis
def test_datacube_nodata_override_reaches_the_provider(datacube_project, datacube_nc):
    datacube_project.add_datacube_layer(
        str(datacube_nc), variable="elevation", nodata=[0, 1]
    )
    (qgis_layer,) = _layers_by_name().values()
    assert "nodata=0%2C1" in qgis_layer.dataProvider().dataSourceUri()

@pytest.mark.qgis
def test_datacube_stretch_spans_the_whole_cube(datacube_project, datacube_nc):
    datacube_project.add_datacube_layer(str(datacube_nc), variable="temperature")
    (qgis_layer,) = _layers_by_name().values()
    enhancement = qgis_layer.renderer().contrastEnhancement()
    # The first time step alone runs from 0 to 47; the whole cube to 247.
    assert enhancement.minimumValue() == pytest.approx(0)
    assert enhancement.maximumValue() == pytest.approx(247)

@pytest.mark.qgis
def test_datacube_explicit_limits_are_kept(datacube_project, datacube_nc):
    datacube_project.add_datacube_layer(
        str(datacube_nc), variable="temperature", style=RasterStyleBW(vmin=0, vmax=10)
    )
    (qgis_layer,) = _layers_by_name().values()
    assert qgis_layer.renderer().contrastEnhancement().maximumValue() == pytest.approx(10)

@pytest.mark.qgis
def test_unreadable_datacube_adds_nothing(datacube_project, tmp_path):
    datacube_project.add_datacube_layer(str(tmp_path / "missing.zarr"))
    assert _layers_by_name() == {}

@pytest.mark.qgis
def test_saved_datacube_project_reopens(datacube_project, datacube_nc, tmp_path):
    from qgis.core import QgsProject

    datacube_project.add_datacube_layer(str(datacube_nc))
    path = tmp_path / "cube.qgz"
    datacube_project.save(str(path))

    reopened = QgsProject()
    assert reopened.read(str(path))
    layers = list(reopened.mapLayers().values())
    assert len(layers) == 2
    assert all(layer.isValid() for layer in layers)
    assert {layer.providerType() for layer in layers} == {DATACUBE_PROVIDER}
