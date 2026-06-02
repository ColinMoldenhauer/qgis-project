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
from qgis_project.layer import Layer, RasterLayer
from qgis_project.style import RasterStyleBW


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
def test_save_nested_groups(tmp_path, vector_file, sample_tif):
    p = SubprocessProject()
    p.add_layer(Layer(file=str(vector_file), group="admin"))
    p.add_layer(RasterLayer(file=str(sample_tif), group=["terrain", "raw"]))
    out = tmp_path / "groups.qgz"
    p.save(str(out))
    assert out.exists()
