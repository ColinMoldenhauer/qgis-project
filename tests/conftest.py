import pytest


@pytest.fixture(scope="session")
def sample_tif(tmp_path_factory):
    """A small 10×10 single-band GeoTIFF with values 0–99, EPSG:4326."""
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
