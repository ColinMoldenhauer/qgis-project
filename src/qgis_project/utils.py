from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def normalize_crs(crs: str | int) -> str:
    """Return a CRS authority string, normalizing bare EPSG integers.

    Examples: `4326` → `"EPSG:4326"`, `"EPSG:3857"` → `"EPSG:3857"`.
    """
    return f"EPSG:{crs}" if isinstance(crs, int) else crs


def list_raster_variables(file: str) -> list[str]:
    """Return the variable (subdataset) tokens in a NetCDF/HDF raster file.

    Each token is the identifier used after the file in a GDAL NETCDF
    connection string — e.g. `"temperature"`, or `"/forecast/humidity"` for a
    variable inside a NetCDF-4 group — and is what you pass as
    `RasterLayer(..., variable=...)`.

    Returns an empty list for a single-variable file (GDAL exposes it as the
    main dataset, not a subdataset) or when the file cannot be read. Requires
    GDAL's Python bindings in the current interpreter, so call it from an
    in-process (env) backend rather than subprocess mode.
    """
    try:
        from osgeo import gdal
    except ImportError:
        logger.warning("osgeo.gdal not importable; cannot enumerate raster variables.")
        return []

    ds = gdal.Open(str(file))
    if ds is None:
        return []

    tokens = []
    for name, _desc in ds.GetSubDatasets():
        # name looks like NETCDF:"<path>":<var>. The path is quoted, so taking
        # the text after the final quote isolates ":<var>" regardless of any
        # colons in the path (e.g. a Windows drive letter).
        tokens.append(name.rsplit('"', 1)[-1].lstrip(":"))
    return tokens


def list_datacube_variables(
    file: str, dataset: str = "", ref: str | None = None
) -> list[str]:
    """Return the variable names in a Zarr, Icechunk or NetCDF datacube.

    The names are what you pass as `DatacubeLayer(..., variable=...)`;
    `dataset` and `ref` have the same meaning as there. Reads the store with
    the Datacube Viewer plugin's own reader, so it needs the
    `qgis-datacube-viewer` package in the current interpreter (QGIS itself is
    not needed). Raises if the store cannot be read.
    """
    from qgis_project import _datacube

    return _datacube.list_variables(file, dataset, ref)


#: Entry point group through which a package offers a QGIS data provider to
#: `RasterLayer(provider=...)`: the entry point's name is the provider key, and
#: it loads a callable that registers the provider with QGIS.
PROVIDER_ENTRY_POINTS = "qgis_project.providers"


def _provider_entry_points() -> list:
    from importlib.metadata import entry_points

    found = entry_points()
    if hasattr(found, "select"):  # Python 3.10+
        return list(found.select(group=PROVIDER_ENTRY_POINTS))
    return list(found.get(PROVIDER_ENTRY_POINTS, []))  # Python 3.9


def ensure_provider(key: str) -> bool:
    """Make sure the QGIS data provider *key* is registered; return whether it is.

    QGIS's own providers (`gdal`, `ogr`, `wms`, ...) and those registered by a
    plugin running in this QGIS are there already. Any other is looked up in
    the `qgis_project.providers` entry points of the installed packages and
    registered from there.
    """
    from qgis.core import QgsProviderRegistry

    registry = QgsProviderRegistry.instance()
    if key in registry.providerList():
        return True
    for entry_point in _provider_entry_points():
        if entry_point.name == key:
            try:
                entry_point.load()()
            except Exception as exc:
                logger.error(
                    f"Registering provider {key!r} from {entry_point.value} failed: {exc!r}"
                )
            break
    return key in registry.providerList()


def list_mesh_variables(file: str) -> list[str]:
    """Return the dataset group names in a mesh file (via QGIS's MDAL provider).

    Dataset groups are a mesh's variables — e.g. `"Bed Elevation"`,
    `"water depth"`, `"velocity"` — and are what you pass as
    `MeshLayer(..., variable=...)`. Returns an empty list if the file
    cannot be read as a mesh. Requires QGIS to be importable in the current
    interpreter (an in-process/env backend), not subprocess mode.
    """
    from qgis.core import QgsMeshDatasetIndex, QgsMeshLayer

    layer = QgsMeshLayer(str(file), "mesh", "mdal")
    if not layer.isValid():
        return []
    return [
        layer.datasetGroupMetadata(QgsMeshDatasetIndex(i, 0)).name()
        for i in layer.datasetGroupsIndexes()
    ]


def get_layer_by_idx(project, idx: int):
    """Return the QGIS layer at position *idx* in a flat, depth-first traversal of the layer tree."""
    layers = [
        node.layer()
        for node in project.layerTreeRoot().findLayers()
        if node.layer() is not None
    ]
    return layers[idx]


def add_or_get_group(project, group_name: str | list[str]):
    from qgis.core import QgsLayerTreeGroup

    root = project.layerTreeRoot()
    group = root

    if isinstance(group_name, str):
        group_name = [group_name]

    path = []
    for name in group_name:
        found = next(
            (child for child in group.children()
             if isinstance(child, QgsLayerTreeGroup) and child.name() == name),
            None
        )
        if found is None:
            group_path = '/'.join(['/ROOT', *path, name])
            logger.info(f"Added group   {group_path}")
            group = group.addGroup(name)
        else:
            group = found
            path.append(name)

    return group


def layer_exists_by_path(project, path: str | list[str]) -> bool:
    """
    Check if a layer exists at a specific full group path.

    Parameters
    ----------
    project : QgsProject
    path : str or list of str
        Either a bare layer name (no group) or a list like ["Group1", "SubGroup", "LayerName"].
    """
    from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer

    if isinstance(path, str):
        path = [path]
    if not path:
        return False

    *group_path, layer_name = path
    parent = project.layerTreeRoot()

    for group_name in group_path:
        parent = next(
            (child for child in parent.children()
             if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name),
            None
        )
        if parent is None:
            return False

    for child in parent.children():
        if isinstance(child, QgsLayerTreeLayer) and child.layer().name() == layer_name:
            return True

    return False


def remove_layer_by_path(project, path: str | list[str]) -> bool:
    """
    Remove a layer by full group path, e.g. ["Group1", "SubGroup", "LayerName"].
    """
    from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer

    if isinstance(path, str):
        path = [path]
    if not path:
        return False

    parent = project.layerTreeRoot()
    *group_path, layer_name = path
    group_path_str = '/'.join(['/ROOT', *group_path])

    for group_name in group_path:
        parent = next(
            (child for child in parent.children()
             if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name),
            None
        )
        if parent is None:
            logger.error(f"Group path not found: {group_path_str}")
            return False

    for child in parent.children():
        if isinstance(child, QgsLayerTreeLayer) and child.layer().name() == layer_name:
            project.removeMapLayer(child.layer().id())
            logger.info(f"Removed layer '{layer_name}' @ group {group_path_str}")
            return True

    logger.error(f"Layer '{layer_name}' not found in {group_path_str}")
    return False
