import importlib
from functools import wraps

from loguru import logger


def qgis_lazy_import(imports_dict):
    """
    Decorator to only import packages upon execution.

    Necessary to run separated environments for user environment and qgis environment.


    Usage
    -----

    ```python
    @qgis_lazy_import({
        "qgis.core": ["QgsApplication"],
    })
    def my_fun():
        appl = QgsApplication(...)
    ```
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Inject each import into the function's global scope
            for module_name, symbols in imports_dict.items():
                module = importlib.import_module(module_name)
                for symbol in symbols:
                    func.__globals__[symbol] = getattr(module, symbol)
            return func(*args, **kwargs)
        return wrapper
    return decorator



@qgis_lazy_import({"qgis.core": ["QgsLayerTreeGroup"]})
def get_layer_by_idx(project, idx: int):
    root = project.layerTreeRoot()

    # collect all layers
    # use index to return layer

    # TODO: implement


@qgis_lazy_import({"qgis.core": ["QgsLayerTreeGroup"]})
def add_or_get_group(project, group_name: str | list[str]):
    root = project.layerTreeRoot()
    group = root

    # Convert single string to list
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
            logger.log(f"Added group   {group_path}")
            group = group.addGroup(name)
        else:
            group = found
            path.append(name)

    return group


@qgis_lazy_import({"qgis.core": ["QgsLayerTreeGroup", "QgsLayerTreeLayer"]})
def layer_exists_by_path(project, path: list[str]) -> bool:
    """
    Check if a layer exists at a specific full group path.
    :param project: QgsProject instance
    :param path: List like ["Group1", "SubGroup", "LayerName"]
    :return: True if the layer exists at that path
    """
    if not path or len(path) < 1:
        return False

    *group_path, layer_name = path
    parent = project.layerTreeRoot()

    # Traverse group hierarchy
    for group_name in group_path:
        parent = next(
            (child for child in parent.children()
             if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name),
            None
        )
        if parent is None:
            return False  # Group path doesn't exist

    # Look for a matching layer name in the final group
    for child in parent.children():
        if isinstance(child, QgsLayerTreeLayer) and child.layer().name() == layer_name:
            return True

    return False


@qgis_lazy_import({"qgis.core": ["QgsLayerTreeGroup", "QgsLayerTreeLayer"]})
def remove_layer_by_path(project, path):
    """
    Remove a layer by full group path, e.g. ["Group1", "SubGroup", "LayerName"]
    """
    if not path:
        return False

    parent = project.layerTreeRoot()
    *group_path, layer_name = path

    group_path_str = '/'.join(['/ROOT', *group_path])

    # Navigate to the correct group
    for group_name in group_path:
        parent = next(
            (child for child in parent.children()
             if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name),
            None
        )
        if parent is None:
            logger.error(f"Group path not found: {group_path_str}")
            return False

    # Search for the layer in the final group
    for child in parent.children():
        if isinstance(child, QgsLayerTreeLayer) and child.layer().name() == layer_name:
            project.removeMapLayer(child.layer().id())
            logger.log(f"Removed layer '{layer_name}' @ group {group_path_str}")
            return True

    logger.error(f"Layer '{layer_name}' not found in {group_path_str}")
    return False
