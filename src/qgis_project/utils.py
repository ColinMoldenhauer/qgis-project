from __future__ import annotations

import logging

from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer

logger = logging.getLogger(__name__)


def normalize_crs(crs: str | int) -> str:
    """Return a CRS authority string, normalizing bare EPSG integers.

    Examples: `4326` → `"EPSG:4326"`, `"EPSG:3857"` → `"EPSG:3857"`.
    """
    return f"EPSG:{crs}" if isinstance(crs, int) else crs


def get_layer_by_idx(project, idx: int):
    """Return the QGIS layer at position *idx* in a flat, depth-first traversal of the layer tree."""
    layers = [
        node.layer()
        for node in project.layerTreeRoot().findLayers()
        if node.layer() is not None
    ]
    return layers[idx]


def add_or_get_group(project, group_name: str | list[str]):
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
