<p align="center">
  <img src="https://raw.githubusercontent.com/ColinMoldenhauer/qgis-project/main/docs/assets/logo-text.png" alt="qgis-project" width="400"/>
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
from qgis_project import Project, RasterStyleBW

proj = Project()
proj.add_layer("dem.tif")                                    # raster, auto-detected
proj.add_layer("boundaries.geojson")                         # vector, auto-detected
proj.add_layer("dem.tif", style=RasterStyleBW(vmin=0, vmax=3000))  # style a path directly
proj.save("output.qgz")
proj.open()     # launch QGIS for visual inspection
```


## Installation

`qgis-project` is pure Python with no runtime dependencies. The real work
is done by QGIS's Python API, which is **not on PyPI** and must be available
separately. There are two good ways to set this up — pick based on whether you
already use the QGIS desktop application.

### Option A — drive a local QGIS install (lightweight env)

If you have the QGIS desktop app installed, the package **auto-discovers** it and
runs your script through QGIS's own **bundled Python** via its entrypoint
launcher. You can then install `qgis-project` into **any** Python environment
(venv, conda, system) with minimal overhead — the `qgis` package from conda is
**not** required.

```bash
pip install qgis-project
# …and have a standalone QGIS desktop install on the machine (auto-discovered)
```

- ✅ Tiny environment, a single QGIS install, and no QGIS/Python version conflicts.
- ⚠️ Slightly hacky: execution runs in a separate process, so there are no live
  QGIS objects (e.g. no `snapshot()`).

Ready-made env: [`environments/qgis-project-local.yml`](environments/qgis-project-local.yml).

### Option B — install QGIS from conda-forge (in-process)

Create a conda environment that includes the `qgis` package; that environment's
Python interpreter then runs your script directly, in-process.

```bash
conda env create -f environments/qgis-project-env.yml
conda activate qgis-project-env
```

Or add QGIS to an existing environment:

```bash
conda install -c conda-forge qgis
pip install qgis-project
```

- ✅ Clean, conventional, with full access to live QGIS objects.
- ⚠️ Larger environment (the QGIS stack is >1 GB), and if you also have the
  desktop app you end up with multiple QGIS installs.

See [**How qgis-project connects to QGIS**](https://qgis-project.readthedocs.io/en/latest/standalone/)
in the docs for a full explanation of every approach and how to force a specific
one with `QGIS_PROJECT_LAUNCH_MODE`.



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
| `RasterStylePaletted` | Paletted / unique-value colors for categorical rasters |

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

You can also pass a path and styling straight to `add_layer` without
constructing a `RasterLayer` yourself — a `RasterLayer` is built automatically
when a raster-specific keyword (a `RasterStyle`, `band_idx`, or
`statistics_kwargs`) is given:

```python
proj.add_layer("dem.tif", name="Elevation", group="terrain",
               style=RasterStyleBW(vmin=0, vmax=3000))
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

`RasterStylePaletted` colors a categorical raster (land cover, classification
mask) with one fixed color per discrete band value — no interpolation. Pass an
explicit `colors` mapping (with optional `labels`), or omit it to auto-detect
the distinct values and color them from `colormap`:

```python
from qgis_project import RasterStylePaletted

layer = RasterLayer(
    file="landcover.tif",
    style=RasterStylePaletted(
        colors={1: "#1b9e77", 2: "#d95f02", 3: "#7570b3"},
        labels={1: "Forest", 2: "Urban", 3: "Water"},
    ),
)
proj.add_layer(layer)
```

### NetCDF and other multi-variable rasters

A NetCDF (`.nc`) file is a container of one or more named *variables*. Adding
the file with no further arguments loads **every** variable as its own layer,
named `"<file> : <variable>"`:

```python
proj.add_layer("climate.nc")        # one layer per variable
```

Select a single variable, or a subset, with the `variable` argument:

```python
proj.add_layer("climate.nc", variable="temperature")
proj.add_layer("climate.nc", variable=["temperature", "precipitation"])
```

Variables nested inside NetCDF-4 groups are addressed by their full path, and
the group hierarchy is mirrored in the QGIS layer tree (here `humidity` lands in
a `forecast` group):

```python
proj.add_layer("climate.nc", variable="/forecast/humidity")
```

A variable with a time (or Z) dimension loads as a multi-band raster — one band
per step — so `band_idx` selects the step, and any `RasterStyle` applies as
usual. NetCDF often lacks an embedded CRS; set it with `crs=...` if needed.

List the variables in a file without loading it (requires GDAL in the current
environment):

```python
from qgis_project import list_raster_variables

list_raster_variables("climate.nc")   # ['temperature', 'precipitation', '/forecast/humidity']
```

### Mesh layers

Unstructured or curvilinear grids — hydrodynamic/ocean models, UGRID, TELEMAC,
ADCIRC, 2DM, and CF-mesh NetCDF — are loaded as **mesh layers** through QGIS's
MDAL provider with `MeshLayer`. A mesh holds one or more *dataset groups* (its
variables, e.g. `"Bed Elevation"`, `"water depth"`, `"velocity"`), each scalar
or vector and optionally carrying a time dimension for animation.

**Raster vs. mesh for NetCDF.** A `.nc` file defaults to a *raster* (see above),
which is the right choice for a regular rectilinear grid. Reach for `MeshLayer`
when the data is unstructured/curvilinear, has vector datasets, or you want
temporal animation — cases a raster cannot represent. Mesh loading of NetCDF is
opt-in precisely because the file extension alone is ambiguous:

```python
from qgis_project import MeshLayer, MeshStyleScalar, MeshStyleVector

# Colour a scalar dataset group with a ramp (min/max auto-detected if omitted)
proj.add_layer(MeshLayer(
    "flood.nc",
    style=MeshStyleScalar(dataset_group="water depth", colormap="Blues", vmin=0, vmax=5),
))

# Draw a vector dataset group as arrows
proj.add_layer(MeshLayer(
    "currents.nc",
    style=MeshStyleVector(dataset_group="velocity", color="white", line_width=0.4),
))

# 2DM and other mesh-only extensions are detected automatically
proj.add_layer("terrain.2dm")
```

| Class | Effect |
|---|---|
| `MeshStyleScalar` | Colour a scalar dataset group with a continuous ramp |
| `MeshStyleVector` | Render a vector dataset group as arrows |

`dataset_group` selects the group by name or index; set it on the `MeshLayer`
(applies with QGIS's default rendering) or on the style (overrides, per style).
If omitted, the first scalar/vector group is used. List a file's groups without
loading it (requires QGIS in the current environment):

```python
from qgis_project import list_mesh_dataset_groups

list_mesh_dataset_groups("flood.nc")   # ['Bed Elevation', 'water depth', 'velocity']
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
separate outline). For point layers, `VectorStyleSingleSymbol` also accepts
`size` (marker size in mm) and `marker_shape` (e.g. `"circle"`, `"square"`,
`"triangle"`, `"star"`).

### Filtering, labels, and scale-based visibility

`Layer.filter` restricts a vector layer to features matching a QGIS
expression (`QgsVectorLayer.setSubsetString`):

```python
layer = Layer("regions.geojson", filter="population > 1000")
```

`Layer.labels` adds attribute-based labels, independent of `style`:

```python
from qgis_project import VectorLabels

layer = Layer("regions.geojson", labels=VectorLabels(field="name", size=12, color="black"))
```

`Layer.min_scale`/`Layer.max_scale` set scale-dependent visibility (scale
denominators). `min_scale` is the most zoomed-out scale at which the layer
is still visible; `max_scale` is the most zoomed-in scale at which it's
still visible:

```python
layer = Layer("regions.geojson", max_scale=50000)  # hidden once zoomed in past 1:50,000
```

### Open in QGIS

```python
proj.open("output.qgz")      # saves and launches QGIS
proj.print_layer_tree()      # inspect the layer tree in the terminal
```


## Development

Create the full development environment (QGIS from conda-forge, test + docs +
Jupyter tooling, editable install):

```bash
conda env create -f environments/qgis-project-dev.yml
conda activate qgis-project-dev
```

Or, in an environment that already has QGIS available, just add the dev deps:

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
