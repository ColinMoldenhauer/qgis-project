import json

import pytest


@pytest.fixture(scope="session")
def qgis_app():
    """Ensure QGIS is initialised for the test session.

    Our __init__.py calls setup_qgis_env() on import, so by the time any
    test runs, QGIS is already configured.  This fixture simply verifies
    the import succeeded; tests that declare it as an argument are skipped
    when QGIS is not available.
    """
    try:
        import qgis_project  # noqa: F401 — triggers setup_qgis_env
    except (ImportError, RuntimeError) as e:
        pytest.skip(f"QGIS not available: {e}")


@pytest.fixture(scope="session")
def sample_tif(tmp_path_factory):
    """A small 10x10 single-band float32 GeoTIFF, EPSG:4326, values 0-99."""
    try:
        import numpy as np
        from osgeo import gdal, osr
    except ImportError:
        pytest.skip("GDAL or numpy not available")

    path = tmp_path_factory.mktemp("data") / "dem.tif"
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(path), 10, 10, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([0.0, 1.0, 0.0, 10.0, 0.0, -1.0])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    ds.GetRasterBand(1).WriteArray(np.arange(100, dtype=np.float32).reshape(10, 10))
    ds.FlushCache()
    ds = None
    return path


@pytest.fixture(scope="session")
def vector_file(tmp_path_factory):
    """A minimal two-feature GeoJSON polygon file."""
    path = tmp_path_factory.mktemp("data") / "regions.geojson"
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "B"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
                },
            },
        ],
    }))
    return path
