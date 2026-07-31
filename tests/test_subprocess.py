"""
Integration tests for the subprocess strategy.

Requires a standalone QGIS installation with a platform launcher
(python-qgis.bat on Windows, python-qgis.sh on Linux/macOS).
Run with: pytest -m launcher
Skip with: pytest -m "not launcher"
"""
import pytest

from qgis_project._env import find_qgis_launcher
from qgis_project._subprocess import SubprocessProject
from qgis_project.layer import Layer, MeshLayer, ProcessingOp, RasterLayer, WebLayer
from qgis_project.style import MeshStyleScalar, RasterStyleBW, RasterStylePaletted


# Skip entire module if no launcher is found
if find_qgis_launcher() is None:
    pytest.skip("No QGIS launcher found (standalone install required)", allow_module_level=True)


pytestmark = pytest.mark.launcher


# ---------------------------------------------------------------------------
# SubprocessProject interface (no launcher needed — pure Python)
# ---------------------------------------------------------------------------

def test_add_layer_accumulates():
    p = SubprocessProject()
    p.add_layer(Layer(file="a.shp"))
    p.add_layer(Layer(file="b.shp"))
    assert len(p._layers) == 2


def test_remove_layer():
    p = SubprocessProject()
    p.add_layer(Layer(file="a.shp", name="A"))
    p.add_layer(Layer(file="b.shp", name="B"))
    p.remove_layer(Layer(file="a.shp", name="A"))
    assert len(p._layers) == 1
    assert p._layers[0].file == "b.shp"


def test_exit_is_noop():
    SubprocessProject().exit()


def test_crs_constructor_normalizes():
    p = SubprocessProject(crs=3857)
    assert p._crs == "EPSG:3857"


def test_set_crs_string():
    p = SubprocessProject()
    p.set_crs("EPSG:32632")
    assert p._crs == "EPSG:32632"


def test_set_crs_int():
    p = SubprocessProject()
    p.set_crs(4326)
    assert p._crs == "EPSG:4326"


def test_process_accumulates():
    p = SubprocessProject()
    p.process("native:buffer", {"INPUT": "a.shp", "DISTANCE": 100, "OUTPUT": "memory:"}, name="Buffered")
    assert len(p._operations) == 1
    assert isinstance(p._operations[0], ProcessingOp)
    assert p._operations[0].algorithm == "native:buffer"
    assert p._operations[0].name == "Buffered"


def test_add_web_layer_accumulates():
    p = SubprocessProject()
    p.add_layer(WebLayer.osm(group="Background"))
    assert len(p._layers) == 1
    assert isinstance(p._layers[0], WebLayer)
    assert p._layers[0].group == "Background"


def test_print_layer_tree_runs(capsys):
    p = SubprocessProject()
    p.add_layer(Layer(file="a.shp", name="Root"))
    p.add_layer(Layer(file="b.shp", name="Grouped", group="terrain"))
    p.print_layer_tree()
    out = capsys.readouterr().out
    assert "Root" in out
    assert "Grouped" in out


# ---------------------------------------------------------------------------
# End-to-end: save via launcher
# ---------------------------------------------------------------------------

@pytest.mark.launcher
def test_save_vector(tmp_path, vector_file):
    p = SubprocessProject()
    p.add_layer(Layer(file=str(vector_file), name="Regions"))
    out = tmp_path / "test.qgz"
    p.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0


@pytest.mark.launcher
def test_save_raster(tmp_path, sample_tif):
    p = SubprocessProject()
    p.add_layer(RasterLayer(file=str(sample_tif), style=RasterStyleBW(vmin=0, vmax=99)))
    out = tmp_path / "raster.qgz"
    p.save(str(out))
    assert out.exists()


@pytest.mark.launcher
def test_save_paletted_raster(tmp_path, categorical_tif):
    # Exercises the full JSON round trip: the colors/labels dicts are
    # serialized to the executor, where set_style() coerces the stringified
    # band-value keys back to ints. This is the path that produced the original
    # ClassData() failure.
    p = SubprocessProject()
    p.add_layer(
        RasterLayer(
            file=str(categorical_tif),
            style=RasterStylePaletted(
                colors={1: "#ff0000", 2: "#00ff00", 3: "#0000ff"},
                labels={1: "Forest"},
            ),
        )
    )
    out = tmp_path / "paletted.qgz"
    p.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0


def test_netcdf_variable_list_round_trips_through_spec():
    # The variable list must survive JSON serialization so the executor (which
    # runs where GDAL is available) can expand it into one layer per variable.
    from qgis_project import _spec

    p = SubprocessProject()
    p.add_layer(RasterLayer(file="climate.nc", variable=["temperature", "precipitation"]))
    spec = _spec.to_dict(p._layers, "out.qgz")
    (layers, _out, _action) = _spec.from_dict(spec)
    assert layers[0].variable == ["temperature", "precipitation"]


@pytest.mark.launcher
def test_save_netcdf_all_variables(tmp_path, sample_nc):
    p = SubprocessProject()
    p.add_layer(str(sample_nc))
    out = tmp_path / "climate.qgz"
    p.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0


@pytest.mark.launcher
def test_save_mesh_layer(tmp_path, sample_2dm):
    p = SubprocessProject()
    p.add_layer(MeshLayer(file=str(sample_2dm), style=MeshStyleScalar(colormap="Viridis")))
    out = tmp_path / "mesh.qgz"
    p.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0


@pytest.mark.launcher
def test_save_nested_groups(tmp_path, vector_file, sample_tif):
    p = SubprocessProject()
    p.add_layer(Layer(file=str(vector_file), group="admin"))
    p.add_layer(RasterLayer(file=str(sample_tif), group=["terrain", "raw"]))
    out = tmp_path / "groups.qgz"
    p.save(str(out))
    assert out.exists()


@pytest.mark.launcher
def test_save_with_processing_file_output(tmp_path, vector_file):
    buf = tmp_path / "buffer.gpkg"
    p = SubprocessProject()
    p.process("native:buffer", {"INPUT": str(vector_file), "DISTANCE": 0.1, "OUTPUT": str(buf)}, name="Buffered")
    out = tmp_path / "proc.qgz"
    p.save(str(out))
    assert out.exists()
    assert buf.exists()


@pytest.mark.launcher
def test_save_with_processing_memory_output(tmp_path, vector_file):
    p = SubprocessProject()
    p.process("native:buffer", {"INPUT": str(vector_file), "DISTANCE": 0.1, "OUTPUT": "memory:"}, name="Buffered")
    out = tmp_path / "proc_mem.qgz"
    p.save(str(out))
    assert out.exists()
