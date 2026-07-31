<p align="center">
  <img src="assets/logo-text.png" alt="qgis-project"/>
</p>

# qgis-project

Create QGIS projects programmatically using Python — a matplotlib-style API for building `.qgz` project files.

**This package is** a thin wrapper around QGIS's most essential functions:
loading layers (vector/raster, local/web), basic visualization, and basic
processing.

**This package is not** a tool for advanced or complex visual analysis or
cartographic mapping — for that, use QGIS itself or a dedicated mapping
library.

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

`qgis-project` is pure Python (no runtime dependencies); the heavy lifting is done by QGIS,
which is **not on PyPI**. There are two good ways to provide it:

- **A — drive a local QGIS install:** if you have the QGIS desktop app, it is
  auto-discovered and its bundled Python runs your script. Install
  `qgis-project` into any lightweight env — the `qgis` conda package is *not*
  needed.
- **B — QGIS from conda-forge:** install `qgis` into a conda environment and run
  in-process.

```bash
# Option B, the quickest conda route:
conda install -c conda-forge qgis
pip install qgis-project
```

See [**Connecting to QGIS**](standalone.md) for a full explanation of both
approaches (and a third, advanced one), and how to force a specific one with
`QGIS_PROJECT_LAUNCH_MODE`.


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
| `RasterStyleSinglePseudocolor` | Single-band color ramp |
| `RasterStyleMultiBandColor` | Multi-band RGB/false-color composite |
| `RasterStylePaletted` | Paletted / unique-value colors for categorical rasters |

```python
from qgis_project import RasterStyleBW

layer = RasterLayer("dem.tif", style=RasterStyleBW(vmin=0, vmax=3000))
```

If `vmin`/`vmax` are omitted they are computed from the layer data.

`RasterStyleMultiBandColor` requires `band_idx` to be a list of three band
numbers `[R, G, B]`:

```python
from qgis_project import RasterStyleMultiBandColor

layer = RasterLayer("rgb.tif", band_idx=[1, 2, 3], style=RasterStyleMultiBandColor())
```

`RasterStylePaletted` assigns a fixed color per discrete band value — ideal for
categorical rasters like land cover. Pass an explicit `colors` mapping, or omit
it to auto-detect the distinct values and color them from `colormap`:

```python
from qgis_project import RasterStylePaletted

layer = RasterLayer(
    "landcover.tif",
    style=RasterStylePaletted(
        colors={1: "#1b9e77", 2: "#d95f02", 3: "#7570b3"},
        labels={1: "Forest", 2: "Urban", 3: "Water"},
    ),
)
```

### NetCDF and mesh data

A NetCDF (`.nc`) file holds several named *variables*. By default every variable
is added as its own raster layer; select one or a subset with `variable`:

```python
proj.add_layer("climate.nc")                              # all variables
proj.add_layer("climate.nc", variable="temperature")      # one
proj.add_layer("climate.nc", variable=["temperature", "precipitation"])
```

Variables in NetCDF-4 groups (`"/forecast/humidity"`) map onto the layer-tree
group hierarchy, and a time dimension loads as raster bands (`band_idx` selects
the step). `list_raster_variables("climate.nc")` lists the variables.

For unstructured/curvilinear grids, vector datasets, or temporal animation, use
a **mesh layer** (QGIS's MDAL provider) instead — the correct representation
when a rectilinear raster can't describe the grid:

```python
from qgis_project import MeshLayer, MeshStyleScalar, MeshStyleVector

proj.add_layer(MeshLayer("flood.nc",
    style=MeshStyleScalar(dataset_group="water depth", colormap="Blues")))
proj.add_layer(MeshLayer("currents.nc",
    style=MeshStyleVector(dataset_group="velocity", color="white")))
proj.add_layer("terrain.2dm")   # mesh-only extensions auto-detected
```

| Class | Effect |
|---|---|
| `MeshStyleScalar` | Colour a scalar dataset group with a continuous ramp |
| `MeshStyleVector` | Render a vector dataset group as arrows |

`dataset_group` picks the group by name or index (on the `MeshLayer`, or on the
style to override); `list_mesh_dataset_groups(file)` lists them.

### Vector styles

| Class | Effect |
|---|---|
| `VectorStyleSingleSymbol` | Uniform fill/line/marker color and outline |
| `VectorStyleCategorized` | One color per unique attribute value |
| `VectorStyleGraduated` | Equal-interval color classes (choropleth) for a numeric attribute |

```python
from qgis_project import Layer, VectorStyleSingleSymbol

layer = Layer("regions.geojson", style=VectorStyleSingleSymbol(
    color="red", outline_color="black", outline_width=1.0,
))
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

### Inspect and open

```python
proj.print_layer_tree()     # print the layer tree to the terminal
proj.open("output.qgz")    # save and launch QGIS
proj.exit()                 # clean up without opening QGIS
```

### Project CRS

Pass `crs` to the constructor or call `set_crs()` at any point before saving.
Both EPSG integers and authority strings are accepted:

```python
proj = Project(crs="EPSG:3857")    # Web Mercator
proj = Project(crs=32632)          # UTM zone 32N (integer form)

proj.set_crs("EPSG:4326")          # change later
```

Layer CRS overrides work the same way — set `crs` on any `Layer` or `RasterLayer`
to tell QGIS the layer's CRS when the file lacks embedded metadata:

```python
proj.add_layer(Layer("scan.tif", crs=4326))
```

### Web layers

Add tile services, WMS, or WFS sources with `WebLayer`. The built-in factory methods cover the most common cases:

```python
from qgis_project import WebLayer

# OpenStreetMap XYZ tiles
proj.add_layer(WebLayer.osm())
proj.add_layer(WebLayer.osm(group="Background", visible=False))

# Any XYZ tile service
proj.add_layer(WebLayer.xyz(
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    name="OSM",
))

# OGC Web Map Service
proj.add_layer(WebLayer.wms(
    "https://ows.example.org/wms",
    layers="elevation",
    name="Elevation WMS",
))

# OGC Web Feature Service
proj.add_layer(WebLayer.wfs(
    "https://ows.example.org/wfs",
    typename="ns:rivers",
    name="Rivers",
))
```

### Processing

Run any QGIS Processing algorithm and add the result directly to the project. Works with both the in-process and subprocess strategies.

```python
# Buffer a vector layer — result saved to a file and added to the project
proj.process(
    "native:buffer",
    {"INPUT": "roads.geojson", "DISTANCE": 100, "OUTPUT": "roads_buffered.gpkg"},
    name="Roads (100 m buffer)",
    group="Derived",
)

# In-memory result (vector only)
proj.process(
    "native:dissolve",
    {"INPUT": "admin.geojson", "OUTPUT": "memory:"},
    name="Admin Dissolved",
)
```

Set `"OUTPUT"` to `"memory:"` for an in-memory layer (vectors only), or a file path for a persistent output. The result is automatically added to the project; no `add_layer()` call is needed.

#### Common algorithms

The table below covers frequently used operations. Pass the algorithm ID as the first argument to `process()` and match the parameter names exactly.

**Vector**

| Algorithm ID | Operation | Key parameters |
|---|---|---|
| `native:buffer` | Buffer geometries | `INPUT`, `DISTANCE`, `OUTPUT` |
| `native:dissolve` | Dissolve by field | `INPUT`, `FIELD`, `OUTPUT` |
| `native:clip` | Clip by mask layer | `INPUT`, `OVERLAY`, `OUTPUT` |
| `native:intersection` | Intersection of two layers | `INPUT`, `OVERLAY`, `OUTPUT` |
| `native:difference` | Difference (erase) | `INPUT`, `OVERLAY`, `OUTPUT` |
| `native:reprojectlayer` | Reproject to CRS | `INPUT`, `TARGET_CRS`, `OUTPUT` |
| `native:centroid` | Polygon centroids | `INPUT`, `OUTPUT` |
| `native:fixgeometries` | Repair invalid geometries | `INPUT`, `OUTPUT` |

**Raster**

| Algorithm ID | Operation | Key parameters |
|---|---|---|
| `gdal:warpreproject` | Reproject raster | `INPUT`, `TARGET_CRS`, `OUTPUT` |
| `gdal:cliprasterbymasklayer` | Clip raster by vector mask | `INPUT`, `MASK`, `OUTPUT` |
| `gdal:hillshade` | Hillshade from DEM | `INPUT`, `Z_FACTOR`, `OUTPUT` |
| `gdal:slope` | Slope from DEM | `INPUT`, `OUTPUT` |
| `gdal:aspect` | Aspect from DEM | `INPUT`, `OUTPUT` |
| `gdal:rastercalculator` | Band math | `INPUT_A`, `BAND_A`, `FORMULA`, `OUTPUT` |

To inspect all parameters for any algorithm, run `processing.algorithmHelp("native:buffer")` inside a QGIS Python console or after calling `project.process()` once to initialise the processing registry.
