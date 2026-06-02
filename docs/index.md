<p align="center">
  <img src="assets/logo-text.png" alt="qgis-project"/>
</p>

# qgis-project

Create QGIS projects programmatically using Python — a matplotlib-style API for building `.qgz` project files.

```python
from qgis_project import Project, RasterLayer, RasterStyleBW

proj = Project()
proj.add_layer("dem.tif")
proj.add_layer("boundaries.geojson")
proj.add_layer(RasterLayer("dem.tif", style=RasterStyleBW(vmin=0, vmax=3000)))
proj.save("output.qgz")
proj.open()     # launch QGIS for visual inspection
```


## Installation

```bash
pip install qgis-project
```

QGIS is not on PyPI and must be installed separately via conda-forge:

```bash
conda install -c conda-forge qgis
pip install qgis-project
```

See the [repository README](https://github.com/ColinMoldenhauer/qgis-project#readme) for full environment setup instructions.


## Quick start

### Add layers

Pass a file path string to auto-detect the layer type (raster or vector):

```python
proj = Project()
proj.add_layer("dem.tif")           # QgsRasterLayer
proj.add_layer("roads.geojson")     # QgsVectorLayer
```

Or pass a `Layer`/`RasterLayer` object for explicit control:

```python
from qgis_project import RasterLayer

proj.add_layer(RasterLayer(file="dem.tif", name="Elevation", group="terrain"))
```

### Layer groups

```python
proj.add_layer(RasterLayer("dem.tif",   group="terrain"))
proj.add_layer(RasterLayer("slope.tif", group=["terrain", "derived"]))
```

### Raster styles

| Class | Effect |
|---|---|
| `RasterStyleBW` | Grayscale with contrast stretch |
| `RasterStyleSinglePseudocolor` | Single-band color ramp *(planned)* |
| `RasterStyleMultiPseudocolor` | Multi-band color ramp *(planned)* |

```python
from qgis_project import RasterStyleBW

layer = RasterLayer("dem.tif", style=RasterStyleBW(vmin=0, vmax=3000))
```

If `vmin`/`vmax` are omitted they are computed from the layer data.

### Inspect and open

```python
proj.print_layer_tree()     # print the layer tree to the terminal
proj.open("output.qgz")    # save and launch QGIS
proj.exit()                 # clean up without opening QGIS
```
