import importlib
import os
import platform
import sys
from functools import wraps

from loguru import logger


def setup_qgis_env() -> bool:
    """
    Make the QGIS Python bindings importable by auto-configuring sys.path.

    When QGIS is installed via conda-forge, its Python bindings are not
    placed on sys.path automatically. This function detects the active conda
    environment and adds the correct paths for the current platform.

    Returns True if ``import qgis`` succeeds after this call, False if QGIS
    could not be located (the package can still be imported, QGIS-backed
    methods will just raise ModuleNotFoundError at call time).
    """
    try:
        import qgis  # noqa: F401
        return True
    except ImportError:
        pass

    conda_prefix = os.environ.get("CONDA_PREFIX")
    if not conda_prefix:
        return False

    if platform.system() == "Windows":
        # conda-forge QGIS on Windows: bindings live under Library/python
        python_paths = [os.path.join(conda_prefix, "Library", "python")]
        dll_dir = os.path.join(conda_prefix, "Library", "bin")
    else:
        # conda-forge QGIS on Linux/Mac: bindings under share/qgis/python
        python_paths = [
            os.path.join(conda_prefix, "share", "qgis", "python"),
            os.path.join(conda_prefix, "share", "qgis", "python", "plugins"),
        ]
        dll_dir = None

    for path in python_paths:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.debug(f"Added to sys.path: {path}")

    if dll_dir and os.path.isdir(dll_dir):
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
        # Python 3.8+ on Windows requires explicit DLL directory registration
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_dir)

    try:
        import qgis  # noqa: F401
        logger.debug("QGIS Python bindings found and configured.")
        return True
    except ImportError:
        logger.debug("QGIS Python bindings not found after path setup.")
        return False


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


@qgis_lazy_import({"qgis.core": ["QgsLayerTreeLayer"]})
def get_layer_by_idx(project, idx: int):
    """Return the QGIS layer at position *idx* in a flat, depth-first traversal of the layer tree."""
    layers = [
        node.layer()
        for node in project.layerTreeRoot().findLayers()
        if node.layer() is not None
    ]
    return layers[idx]


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
            logger.info(f"Added group   {group_path}")
            group = group.addGroup(name)
        else:
            group = found
            path.append(name)

    return group


@qgis_lazy_import({"qgis.core": ["QgsLayerTreeGroup", "QgsLayerTreeLayer"]})
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


@qgis_lazy_import({"qgis.core": ["QgsLayerTreeGroup", "QgsLayerTreeLayer"]})
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
