<p align="center">
  <img src="docs/assets/logo-text.png" alt="qgis-project" width="400"/>
</p>

# qgis-project

[![PyPI version](https://img.shields.io/pypi/v/qgis-project)](https://pypi.org/project/qgis-project/)
[![Python versions](https://img.shields.io/pypi/pyversions/qgis-project)](https://pypi.org/project/qgis-project/)
[![Tests](https://github.com/ColinMoldenhauer/qgis-project/actions/workflows/tests.yml/badge.svg?event=push)](https://github.com/ColinMoldenhauer/qgis-project/actions/workflows/tests.yml)
[![Docs](https://readthedocs.org/projects/qgis-project/badge/?version=latest)](https://qgis-project.readthedocs.io/en/latest/)
[![License](https://img.shields.io/github/license/ColinMoldenhauer/qgis-project)](LICENSE.txt)

Create QGIS projects programmatically using Python.

**This package is** a thin wrapper around QGIS's most essential functions:
loading layers (vector/raster, local/web), basic visualization, and basic
processing.

**This package is not** a tool for advanced or complex visual analysis or
cartographic mapping — for that, use QGIS itself or a dedicated mapping
library.

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

| Class | Effect |
|---|---|
| `RasterStyleBW` | Grayscale with contrast stretch |
| `RasterStyleSinglePseudocolor` | Single-band color ramp |
| `RasterStyleMultiBandColor` | Multi-band RGB/false-color composite |

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

If `vmin`/`vmax` are omitted they are computed from the layer data.

`RasterStyleMultiBandColor` requires `band_idx` to be a list of three band
numbers `[R, G, B]`:

```python
from qgis_project import RasterStyleMultiBandColor

layer = RasterLayer(
    file="rgb.tif",
    band_idx=[1, 2, 3],
    style=RasterStyleMultiBandColor(),
)
proj.add_layer(layer)
```

### Vector styling

| Class | Effect |
|---|---|
| `VectorStyleSingleSymbol` | Uniform fill/line/marker color and outline |
| `VectorStyleCategorized` | One color per unique attribute value |
| `VectorStyleGraduated` | Equal-interval color classes (choropleth) for a numeric attribute |

```python
from qgis_project import Layer, VectorStyleSingleSymbol

layer = Layer(
    file="regions.geojson",
    style=VectorStyleSingleSymbol(color="red", outline_color="black", outline_width=1.0),
)
proj.add_layer(layer)
```

`VectorStyleCategorized` and `VectorStyleGraduated` work on point, line, and
polygon layers alike:

```python
from qgis_project import VectorStyleCategorized, VectorStyleGraduated

layer = Layer("regions.geojson", style=VectorStyleCategorized(field="class", colormap="Spectral"))
layer = Layer("regions.geojson", style=VectorStyleGraduated(field="value", num_classes=5, colormap="Viridis"))
```

If `vmin`/`vmax` are omitted from `VectorStyleGraduated`, they are computed
from the field's data. `outline_color`/`outline_width` on
`VectorStyleSingleSymbol` have no effect on line layers (a line has no
separate outline).

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
