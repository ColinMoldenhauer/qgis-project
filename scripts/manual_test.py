"""
Manual visual test script — exercises the full API and saves numbered .qgz
projects to an output directory for inspection in QGIS.

Usage
-----
    python scripts/manual_test.py               # save all projects
    python scripts/manual_test.py --open        # save and open each in QGIS
    python scripts/manual_test.py --only 03     # run only tests matching "03"
    python scripts/manual_test.py --out DIR     # write to DIR (default: test_out/)

Test data (dem.tif, slope.tif, regions.geojson) is generated automatically
inside the output directory if it does not already exist.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Optionally configure QGIS env for standalone installs.
try:
    from experiments.utils import setup_local_python
    setup_local_python()
except Exception:
    pass


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

def _make_raster(path: Path, rows: int = 64, cols: int = 64, seed: int = 0) -> Path:
    """Write a small single-band float32 GeoTIFF at *path*."""
    try:
        import numpy as np
    except ImportError:
        sys.exit("numpy not found: pip install numpy")
    from osgeo import gdal, osr

    rng = np.random.default_rng(seed)
    data = rng.uniform(0, 3000, (rows, cols)).astype(np.float32)

    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(path), cols, rows, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([10.0, 0.01, 0.0, 48.0, 0.0, -0.01])   # roughly central Europe
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    ds.GetRasterBand(1).WriteArray(data)
    ds.FlushCache()
    ds = None
    return path


def _make_vector(path: Path) -> Path:
    """Write a minimal GeoJSON with two polygon features."""
    path.write_text("""{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {"name": "Region A"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[10.0, 47.5], [10.5, 47.5], [10.5, 48.0], [10.0, 48.0], [10.0, 47.5]]]
      }
    },
    {
      "type": "Feature",
      "properties": {"name": "Region B"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[10.5, 47.5], [11.0, 47.5], [11.0, 48.0], [10.5, 48.0], [10.5, 47.5]]]
      }
    }
  ]
}""")
    return path


def _ensure_data(out_dir: Path):
    dem    = out_dir / "dem.tif"
    slope  = out_dir / "slope.tif"
    vector = out_dir / "regions.geojson"
    if not dem.exists():
        _make_raster(dem, seed=0)
    if not slope.exists():
        _make_raster(slope, seed=1)
    if not vector.exists():
        _make_vector(vector)
    return dem, slope, vector


# ---------------------------------------------------------------------------
# Test registry
# ---------------------------------------------------------------------------

TESTS: list = []


def test(fn):
    TESTS.append(fn)
    return fn


def _finish(proj, path: Path, do_open: bool) -> None:
    if do_open:
        proj.open(str(path))
    else:
        proj.save(str(path))
        proj.exit()


# ---------------------------------------------------------------------------
# 01 – Basic raster (BW) and vector
# ---------------------------------------------------------------------------

@test
def t01_basic_layers(dem, slope, vector, out_dir, do_open=False) -> Path:
    """Basic raster with BW style and a vector layer.
    Expected: DEM rendered in grayscale (0–3000); vector polygons on top.
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    proj.add_layer(str(vector))
    proj.add_layer(RasterLayer(str(dem), name="DEM", style=RasterStyleBW(vmin=0, vmax=3000)))
    out = out_dir / "01_basic_layers.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 02 – Raster with auto vmin/vmax
# ---------------------------------------------------------------------------

@test
def t02_auto_limits(dem, slope, vector, out_dir, do_open=False) -> Path:
    """BW raster with vmin/vmax inferred from data statistics.
    Expected: grayscale stretched to the actual data range (no clipping).
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    proj.add_layer(RasterLayer(str(dem), name="DEM (auto limits)", style=RasterStyleBW()))
    out = out_dir / "02_auto_limits.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 03 – Pseudocolor style
# ---------------------------------------------------------------------------

@test
def t03_pseudocolor(dem, slope, vector, out_dir, do_open=False) -> Path:
    """Single-band pseudocolor using Viridis and Spectral ramps.
    Expected: DEM shows Viridis gradient; slope shows Spectral clamped to 0–3000.
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleSinglePseudocolor

    proj = Project()
    proj.add_layer(RasterLayer(str(dem), name="DEM (Viridis)",
                               style=RasterStyleSinglePseudocolor(colormap="Viridis")))
    proj.add_layer(RasterLayer(str(slope), name="Slope (Spectral)",
                               style=RasterStyleSinglePseudocolor(colormap="Spectral",
                                                                   vmin=0, vmax=3000)))
    out = out_dir / "03_pseudocolor.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 04 – Layer groups (flat and nested)
# ---------------------------------------------------------------------------

@test
def t04_layer_groups(dem, slope, vector, out_dir, do_open=False) -> Path:
    """Layers in top-level and nested groups.
    Expected: root has 'terrain' group containing 'DEM'; inside that, 'derived'
    sub-group with 'Slope'. Vector sits at the root level.
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    proj.add_layer(str(vector))
    proj.add_layer(RasterLayer(str(dem), name="DEM", group="terrain", style=RasterStyleBW()))
    proj.add_layer(RasterLayer(str(slope), name="Slope", group=["terrain", "derived"],
                               style=RasterStyleBW()))
    out = out_dir / "04_layer_groups.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 05 – Visibility and opacity
# ---------------------------------------------------------------------------

@test
def t05_visibility_opacity(dem, slope, vector, out_dir, do_open=False) -> Path:
    """Layer visibility and opacity.
    Expected: 'Visible' shown; 'Hidden' unchecked in layer panel;
    'Semi-transparent' displayed at 50 % opacity.
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    proj.add_layer(RasterLayer(str(dem), name="Visible", style=RasterStyleBW(vmin=0, vmax=3000)))
    proj.add_layer(RasterLayer(str(dem), name="Hidden", visible=False,
                               style=RasterStyleBW(vmin=0, vmax=3000)))
    proj.add_layer(RasterLayer(str(dem), name="Semi-transparent",
                               style=RasterStyleBW(vmin=0, vmax=3000, opacity=0.5)))
    out = out_dir / "05_visibility_opacity.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 06 – Project CRS
# ---------------------------------------------------------------------------

@test
def t06_project_crs(dem, slope, vector, out_dir, do_open=False) -> Path:
    """Project CRS set to Web Mercator (EPSG:3857).
    Expected: status bar shows EPSG:3857; layers reprojected on-the-fly.
    """
    from qgis_project import Project, RasterLayer

    proj = Project(crs="EPSG:3857")
    proj.add_layer(RasterLayer(str(dem), name="DEM"))
    proj.add_layer(str(vector))
    out = out_dir / "06_project_crs.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 07 – Layer CRS override
# ---------------------------------------------------------------------------

@test
def t07_layer_crs(dem, slope, vector, out_dir, do_open=False) -> Path:
    """Layer CRS overridden to UTM 32N (EPSG:32632).
    Expected: layer properties panel shows EPSG:32632 for the DEM.
    """
    from qgis_project import Project, RasterLayer

    proj = Project()
    proj.add_layer(RasterLayer(str(dem), name="DEM (forced UTM 32N)", crs=32632))
    proj.add_layer(str(vector))
    out = out_dir / "07_layer_crs.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 08 – Web layers (requires internet)
# ---------------------------------------------------------------------------

@test
def t08_web_layers(dem, slope, vector, out_dir, do_open=False) -> Path:
    """OpenStreetMap XYZ tile basemap underneath vector data.
    Expected: OSM tiles visible; vector polygons on top. Requires internet.
    """
    from qgis_project import Project, WebLayer

    proj = Project(crs="EPSG:3857")
    proj.add_layer(WebLayer.osm(group="Background"))
    proj.add_layer(str(vector))
    out = out_dir / "08_web_layers.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 09 – Processing: buffer to file and to memory
# ---------------------------------------------------------------------------

@test
def t09_processing(dem, slope, vector, out_dir, do_open=False) -> Path:
    """QGIS Processing: buffer to file and to memory.
    Expected: three layers — original vector, 'Buffer (file)' from a .gpkg,
    'Buffer (memory)' as in-memory. Both buffers in a 'Processing' group.
    """
    from qgis_project import Project

    buf_file = str(out_dir / "buffer.gpkg")
    proj = Project()
    proj.add_layer(str(vector))
    proj.process(
        "native:buffer",
        {"INPUT": str(vector), "DISTANCE": 0.05, "SEGMENTS": 5,
         "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2,
         "DISSOLVE": False, "OUTPUT": buf_file},
        name="Buffer (file)", group="Processing",
    )
    proj.process(
        "native:buffer",
        {"INPUT": str(vector), "DISTANCE": 0.1, "SEGMENTS": 5,
         "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2,
         "DISSOLVE": False, "OUTPUT": "memory:"},
        name="Buffer (memory)", group="Processing",
    )
    out = out_dir / "09_processing.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 10 – overwrite_existing
# ---------------------------------------------------------------------------

@test
def t10_overwrite_existing(dem, slope, vector, out_dir, do_open=False) -> Path:
    """Adding a layer twice with overwrite_existing=True replaces the first.
    Expected: exactly one 'DEM' layer in 'terrain', with vmax=3000 (second add wins).
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    proj.add_layer(RasterLayer(str(dem), name="DEM", group="terrain",
                               style=RasterStyleBW(vmin=0, vmax=1000)))
    proj.add_layer(RasterLayer(str(dem), name="DEM", group="terrain",
                               style=RasterStyleBW(vmin=0, vmax=3000),
                               overwrite_existing=True))
    out = out_dir / "10_overwrite_existing.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 11 – Group collapse / expand
# ---------------------------------------------------------------------------

@test
def t11_group_collapse(dem, slope, vector, out_dir, do_open=False) -> Path:
    """Explicit group collapse and expand.
    Expected: 'terrain' group appears collapsed; 'Background' group expanded.
    """
    from qgis_project import Project, RasterLayer, WebLayer

    proj = Project(crs="EPSG:3857")
    proj.add_layer(WebLayer.osm(group="Background", visible=False))
    proj.add_layer(RasterLayer(str(dem), group="terrain", name="DEM"))
    proj.add_layer(RasterLayer(str(slope), group=["terrain", "derived"], name="Slope"))
    proj.collapse_group("terrain")
    proj.expand_group("Background")
    out = out_dir / "11_group_collapse.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 12 – Collapse all
# ---------------------------------------------------------------------------

@test
def t12_collapse_all(dem, slope, vector, out_dir, do_open=False) -> Path:
    """All groups collapsed on project open.
    Expected: every group in the layer panel is collapsed.
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    proj.add_layer(RasterLayer(str(dem), group="terrain", name="DEM", style=RasterStyleBW()))
    proj.add_layer(RasterLayer(str(slope), group=["terrain", "derived"], name="Slope",
                               style=RasterStyleBW()))
    proj.add_layer(str(vector))
    proj.collapse_all()
    out = out_dir / "12_collapse_all.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 13 – zoom_to_all
# ---------------------------------------------------------------------------

@test
def t13_zoom_to_all(dem, slope, vector, out_dir, do_open=False) -> Path:
    """zoom_to_all() sets the initial view to cover all layers.
    Expected: opening the project shows all layers without manually zooming.
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    proj.add_layer(RasterLayer(str(dem), name="DEM", style=RasterStyleBW()))
    proj.add_layer(str(vector))
    proj.zoom_to_all()
    out = out_dir / "13_zoom_to_all.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 14 – center on specific layer
# ---------------------------------------------------------------------------

@test
def t14_center(dem, slope, vector, out_dir, do_open=False) -> Path:
    """center() sets the initial view to one layer's extent.
    Expected: opening the project shows only the raster's bounding box.
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    raster = RasterLayer(str(dem), name="DEM", style=RasterStyleBW())
    proj.add_layer(raster)
    proj.add_layer(str(vector))
    proj.center(raster)
    out = out_dir / "14_center.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 15 – print_layer_tree (terminal output)
# ---------------------------------------------------------------------------

@test
def t15_print_layer_tree(dem, slope, vector, out_dir, do_open=False) -> Path:
    """print_layer_tree() prints the layer tree to stdout.
    Expected terminal output:
        [✓] regions.geojson
        ▶ terrain
          [✓] DEM
          ▶ derived
            [✓] Slope
    """
    from qgis_project import Project, RasterLayer
    from qgis_project.style import RasterStyleBW

    proj = Project()
    proj.add_layer(str(vector))
    proj.add_layer(RasterLayer(str(dem), group="terrain", name="DEM", style=RasterStyleBW()))
    proj.add_layer(RasterLayer(str(slope), group=["terrain", "derived"], name="Slope",
                               style=RasterStyleBW()))
    print()
    proj.print_layer_tree()
    out = out_dir / "15_print_layer_tree.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# 16 – Combined: all major features in one project
# ---------------------------------------------------------------------------

@test
def t16_combined(dem, slope, vector, out_dir, do_open=False) -> Path:
    """All major features combined in a single project.
    Use this as a quick end-to-end sanity check.
    Expected: OSM basemap (collapsed, hidden); terrain group (collapsed) with
    DEM in grayscale and Viridis (hidden); Slope; vector at root; Web Mercator CRS.
    """
    from qgis_project import Project, RasterLayer, WebLayer
    from qgis_project.style import RasterStyleBW, RasterStyleSinglePseudocolor

    proj = Project(crs="EPSG:3857")
    proj.add_layer(WebLayer.osm(group="Background", visible=False))
    proj.add_layer(RasterLayer(str(dem), name="DEM (BW)", group="terrain",
                               style=RasterStyleBW(vmin=0, vmax=3000)))
    proj.add_layer(RasterLayer(str(dem), name="DEM (Viridis)", group="terrain",
                               style=RasterStyleSinglePseudocolor(colormap="Viridis"),
                               visible=False))
    proj.add_layer(RasterLayer(str(slope), name="Slope", group=["terrain", "derived"],
                               style=RasterStyleBW()))
    proj.add_layer(str(vector))
    proj.collapse_group("terrain")
    proj.expand_group("Background")
    proj.zoom_to_all()
    out = out_dir / "16_combined.qgz"
    _finish(proj, out, do_open)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_DEFAULT_OUT = Path(__file__).parent.parent / "test_out"


def main() -> None:
    epilog_lines = ["available tests:"]
    for fn in TESTS:
        desc = (fn.__doc__ or "").strip().splitlines()[0]
        epilog_lines.append(f"  {fn.__name__:<28}  {desc}")

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(epilog_lines),
    )
    parser.add_argument("--open", action="store_true",
                        help="Open each project in QGIS after saving")
    parser.add_argument("--only", metavar="SUBSTR",
                        help="Run only tests whose name contains SUBSTR")
    parser.add_argument("--out", metavar="DIR",
                        help=f"Output directory (default: {_DEFAULT_OUT})")
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else _DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    dem, slope, vector = _ensure_data(out_dir)

    passed, failed = 0, 0
    for fn in TESTS:
        name = fn.__name__
        if args.only and args.only not in name:
            continue
        desc = (fn.__doc__ or "").strip().splitlines()[0]
        try:
            out = fn(dem, slope, vector, out_dir, do_open=args.open)
            print(f"  PASS  {name}  →  {out.name}  ({desc})")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {name}  —  {exc}  ({desc})")
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} failed)")
    else:
        print()

    if not args.open and total > 0:
        print(f"\nProjects saved to {out_dir}/")
        print("Open them in QGIS to verify visually.")


if __name__ == "__main__":
    main()
