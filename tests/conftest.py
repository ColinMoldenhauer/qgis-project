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
