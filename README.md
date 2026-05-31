# qgis-project

[![PyPI version](https://img.shields.io/pypi/v/qgis-project)](https://pypi.org/project/qgis-project/)
[![Python versions](https://img.shields.io/pypi/pyversions/qgis-project)](https://pypi.org/project/qgis-project/)
[![License](https://img.shields.io/github/license/ColinMoldenhauer/qgis-project)](LICENSE.txt)
[![CI](https://github.com/ColinMoldenhauer/qgis-project/actions/workflows/test.yml/badge.svg)](https://github.com/ColinMoldenhauer/qgis-project/actions/workflows/test.yml)
[![Docs](https://readthedocs.org/projects/qgis-project/badge/?version=latest)](https://qgis-project.readthedocs.io/en/latest/)

Create QGIS projects programmatically using Python.

```python
from qgis_project import Project, RasterLayer, RasterStyleBW

proj = Project()
proj.add_layer("dem.tif")                                    # raster, auto-detected
proj.add_layer("boundaries.geojson")                         # vector, auto-detected
proj.add_layer(RasterLayer("dem.tif", style=RasterStyleBW(vmin=0, vmax=3000)))
proj.save("output.qgz")
proj.open()     # launch QGIS for visual inspection
```


## Installation

Install the package:

```bash
pip install qgis-project
```

QGIS is not on PyPI and must be available separately. The recommended approach is a dedicated conda environment:

```bash
conda env create -f environment_platform_independent.yml
conda activate qgis-env-pi
pip install qgis-project
```

Or install QGIS from conda-forge into an existing environment:

```bash
conda install -c conda-forge qgis
pip install qgis-project
```



## Usage

### Basic project

```python
from qgis_project import Project

proj = Project()
proj.add_layer("dem.tif")
proj.add_layer("roads.geojson")
proj.save("my_project.qgz")
proj.exit()
```

### Layer groups

```python
proj.add_layer(RasterLayer("dem.tif", group="terrain"))
proj.add_layer(RasterLayer("slope.tif", group=["terrain", "derived"]))
```

### Raster styling

```python
from qgis_project import RasterLayer, RasterStyleBW

layer = RasterLayer(
    file="dem.tif",
    name="Elevation",
    group="terrain",
    style=RasterStyleBW(vmin=0, vmax=3000),
)
proj.add_layer(layer)
```

### Open in QGIS

```python
proj.open("output.qgz")      # saves and launches QGIS
proj.print_layer_tree()      # inspect the layer tree in the terminal
```


## Development

Install with dev dependencies:

```bash
pip install -e ".[dev]"
```

Run unit tests (no QGIS required):

```bash
pytest -m "not qgis"
```

Run integration tests (QGIS environment required):

```bash
pytest -m qgis
```

Run the manual visual test:

```bash
python scripts/manual_test.py
```
