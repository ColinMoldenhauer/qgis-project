# qgis-project

Create QGIS projects programmatically using Python.

## Installation

```bash
pip install qgis-project
```

QGIS itself is not on PyPI and must be available separately. The recommended approach is a conda environment with QGIS from conda-forge:

```bash
conda install -c conda-forge qgis
pip install qgis-project
```

See the [repository README](https://github.com/ColinMoldenhauer/qgis-project) for full environment setup instructions.

## Quick start

```python
from qgis_project import Project, RasterLayer, RasterStyleBW

project = Project()

layer = RasterLayer(file="dem.tif", style=RasterStyleBW())
project.add_layer(layer)

project.save("output.qgz")
project.exit()
```

## How QGIS imports work

All QGIS imports are **lazy** — the package can be imported in any Python environment and only raises an error when a QGIS-backed method is actually called. This makes it possible to install and import `qgis-project` without QGIS, and to use non-QGIS utilities freely.
