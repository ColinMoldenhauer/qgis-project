"""
Manual visual test — exercises the full API with synthetic data, then opens QGIS.

Usage
-----
    python scripts/manual_test.py              # run and open QGIS
    python scripts/manual_test.py --no-open   # run without opening QGIS
    python scripts/manual_test.py --out DIR   # save project to DIR instead of a temp dir
"""

import argparse
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

def _make_raster(path: Path, rows: int = 64, cols: int = 64, seed: int = 0) -> Path:
    """Write a small single-band float32 GeoTIFF at *path*."""
    try:
        import numpy as np
    except ImportError:
        sys.exit("numpy not found: pip install numpy")
    try:
        from osgeo import gdal, osr
    except ImportError:
        sys.exit("GDAL not found. Run this script inside your QGIS conda environment.")

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
    geojson = """{
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
}"""
    path.write_text(geojson)
    return path


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def run(out_dir: Path, open_qgis: bool = True):
    from qgis_project import Project, RasterLayer, RasterStyleBW

    print("── Creating synthetic test data ──")
    dem      = _make_raster(out_dir / "dem.tif",      seed=0)
    slope    = _make_raster(out_dir / "slope.tif",    seed=1)
    regions  = _make_vector(out_dir / "regions.geojson")
    print(f"  dem.tif, slope.tif, regions.geojson  →  {out_dir}")

    print("\n── Building project ──")
    proj = Project()

    # 1. Simple string shorthand (auto-detects raster/vector)
    print("  [1] add_layer(str) — auto-detect")
    proj.add_layer(str(regions))

    # 2. Raster with BW style, explicit limits
    print("  [2] RasterLayer with RasterStyleBW(vmin, vmax)")
    proj.add_layer(RasterLayer(
        file=str(dem),
        name="DEM (styled)",
        style=RasterStyleBW(vmin=0, vmax=3000),
    ))

    # 3. Raster with auto-limits (vmin/vmax inferred from data)
    print("  [3] RasterLayer with RasterStyleBW — auto limits")
    proj.add_layer(RasterLayer(
        file=str(dem),
        name="DEM (auto limits)",
        style=RasterStyleBW(),
    ))

    # 4. Layer groups (single level)
    print("  [4] Single-level group")
    proj.add_layer(RasterLayer(
        file=str(slope),
        name="slope",
        group="terrain",
        style=RasterStyleBW(),
    ))

    # 5. Layer groups (nested)
    print("  [5] Nested group")
    proj.add_layer(RasterLayer(
        file=str(dem),
        name="dem_nested",
        group=["terrain", "raw"],
        style=RasterStyleBW(),
    ))

    # 6. Hidden layer
    print("  [6] visible=False")
    proj.add_layer(RasterLayer(
        file=str(slope),
        name="slope (hidden)",
        visible=False,
        style=RasterStyleBW(),
    ))

    print("\n── Layer tree ──")
    proj.print_layer_tree()

    out_file = str(out_dir / "manual_test.qgz")
    proj.save(out_file)
    print(f"\nProject saved → {out_file}")

    if open_qgis:
        print("Launching QGIS…")
        proj.open(out_file)
        print("QGIS is running. The Python process will exit; QGIS stays open.")
    else:
        proj.exit()
        print("Done (--no-open: skipped QGIS launch).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-open", action="store_true", help="Don't launch QGIS after saving")
    parser.add_argument("--out", metavar="DIR", help="Output directory (default: a new temp dir)")
    args = parser.parse_args()

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        run(out_dir, open_qgis=not args.no_open)
    else:
        # Keep temp dir alive until this process exits so QGIS can read the files
        with tempfile.TemporaryDirectory() as tmp:
            run(Path(tmp), open_qgis=not args.no_open)


if __name__ == "__main__":
    main()
