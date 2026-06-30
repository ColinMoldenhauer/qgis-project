"""
conftest.py — session-wide fixtures and QGIS availability handling.

When QGIS is not installed, a MagicMock is injected into sys.modules for the
entire qgis.* namespace before any test module is imported.  This allows
module-level imports like `from qgis.core import QgsRasterBandStats` in the
source to succeed, so pure-Python unit tests (Layer dataclass, _spec
serialization, _env path detection) can run without a QGIS installation.

Integration tests that require a live QgsApplication are gated by the
`qgis_app` fixture, which skips when only the mock is present.
"""

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# QGIS availability — must happen before any qgis_project import
# ---------------------------------------------------------------------------

_QGIS_AVAILABLE: bool = False

try:
    import qgis  # noqa: F401
    _QGIS_AVAILABLE = True
except ImportError:
    _qgis_mock = MagicMock()
    for _mod in [
        "qgis",
        "qgis.core",
        "qgis.gui",
        "qgis.PyQt",
        "qgis.PyQt.QtCore",
        "qgis.PyQt.QtGui",
        "qgis.PyQt.QtWidgets",
    ]:
        sys.modules[_mod] = _qgis_mock
    # Provide a dummy prefix so _env.find_qgis_prefix_path() does not raise
    # after setup_qgis_env() returns True (the mock satisfies `import qgis`).
    os.environ.setdefault("QGIS_PREFIX_PATH", "/mock/qgis")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qgis_app():
    """Initialize a real QgsApplication for the test session.

    Skips when QGIS is only present as a mock (no actual installation).
    Owns the singleton for the full session so tests never destroy and
    recreate it (which crashes the process on the second creation).
    """
    if not _QGIS_AVAILABLE:
        pytest.skip("QGIS not installed — skipping integration test")

    from qgis.core import QgsApplication
    app = QgsApplication([], False)
    app.initQgis()
    yield app
    app.exitQgis()


@pytest.fixture(scope="session")
def sample_tif(tmp_path_factory):
    """A small 10x10 single-band float32 GeoTIFF, EPSG:4326, values 0-99."""
    if not _QGIS_AVAILABLE:
        pytest.skip("QGIS not installed")
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
def categorical_tif(tmp_path_factory):
    """A small 10x10 single-band byte GeoTIFF, EPSG:4326, holding the three
    discrete class values 1, 2, 3 — a stand-in for a land-cover/classification
    raster used to exercise paletted styling."""
    if not _QGIS_AVAILABLE:
        pytest.skip("QGIS not installed")
    try:
        import numpy as np
        from osgeo import gdal, osr
    except ImportError:
        pytest.skip("GDAL or numpy not available")

    path = tmp_path_factory.mktemp("data") / "landcover.tif"
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(path), 10, 10, 1, gdal.GDT_Byte)
    ds.SetGeoTransform([0.0, 1.0, 0.0, 10.0, 0.0, -1.0])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    # Tile the values 1, 2, 3 across the 100 cells so all three classes appear.
    data = (np.arange(100, dtype=np.uint8) % 3 + 1).reshape(10, 10)
    ds.GetRasterBand(1).WriteArray(data)
    ds.FlushCache()
    ds = None
    return path


_GEOJSON_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "A"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        },
        {
            "type": "Feature",
            "properties": {"name": "B"},
            "geometry": {"type": "Polygon", "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]]},
        },
    ],
}


@pytest.fixture(scope="session")
def vector_file(tmp_path_factory):
    """A minimal two-feature GeoJSON polygon file."""
    path = tmp_path_factory.mktemp("data") / "regions.geojson"
    path.write_text(json.dumps(_GEOJSON_FC))
    return path


@pytest.fixture(scope="session")
def gpkg_file(tmp_path_factory):
    """A minimal GeoPackage vector file."""
    if not _QGIS_AVAILABLE:
        pytest.skip("QGIS not installed")
    try:
        from osgeo import ogr, osr
    except ImportError:
        pytest.skip("GDAL/OGR not available")
    path = tmp_path_factory.mktemp("data") / "regions.gpkg"
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    layer = ds.CreateLayer("regions", srs, ogr.wkbPolygon)
    layer.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    for coords, name in [([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], "A"),
                         ([[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]], "B")]:
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for x, y in coords:
            ring.AddPoint(x, y)
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetGeometry(poly)
        feat.SetField("name", name)
        layer.CreateFeature(feat)
    ds = None
    return path


@pytest.fixture(scope="session")
def shp_file(tmp_path_factory):
    """A minimal Shapefile."""
    if not _QGIS_AVAILABLE:
        pytest.skip("QGIS not installed")
    try:
        from osgeo import ogr, osr
    except ImportError:
        pytest.skip("GDAL/OGR not available")
    path = tmp_path_factory.mktemp("data") / "regions.shp"
    driver = ogr.GetDriverByName("ESRI Shapefile")
    ds = driver.CreateDataSource(str(path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    lyr = ds.CreateLayer("regions", srs, ogr.wkbPolygon)
    for coords in [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
                   [[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]]:
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for x, y in coords:
            ring.AddPoint(x, y)
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        feat = ogr.Feature(lyr.GetLayerDefn())
        feat.SetGeometry(poly)
        lyr.CreateFeature(feat)
    ds = None
    return path


@pytest.fixture(scope="session")
def kml_file(tmp_path_factory):
    """A minimal KML file."""
    path = tmp_path_factory.mktemp("data") / "regions.kml"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2">'
        "<Document>"
        "<Placemark><name>A</name>"
        "<Polygon><outerBoundaryIs><LinearRing>"
        "<coordinates>0,0 1,0 1,1 0,1 0,0</coordinates>"
        "</LinearRing></outerBoundaryIs></Polygon></Placemark>"
        "</Document></kml>"
    )
    return path


@pytest.fixture(scope="session")
def flatgeobuf_file(tmp_path_factory):
    """A minimal FlatGeobuf file created via OGR."""
    if not _QGIS_AVAILABLE:
        pytest.skip("QGIS not installed")
    try:
        from osgeo import ogr, osr
    except ImportError:
        pytest.skip("GDAL/OGR not available")
    driver = ogr.GetDriverByName("FlatGeobuf")
    if driver is None:
        pytest.skip("FlatGeobuf driver not available in this GDAL build")
    path = tmp_path_factory.mktemp("data") / "regions.fgb"
    ds = driver.CreateDataSource(str(path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    lyr = ds.CreateLayer("regions", srs, ogr.wkbPolygon)
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]:
        ring.AddPoint(x, y)
    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)
    feat = ogr.Feature(lyr.GetLayerDefn())
    feat.SetGeometry(poly)
    lyr.CreateFeature(feat)
    ds = None
    return path
