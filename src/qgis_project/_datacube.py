"""
Bridge to the raster provider of the Datacube Viewer QGIS plugin.

`DatacubeLayer` is plain data, so it can be built and serialized in any Python.
The functions here run where the QGIS layers are made (in-process, or in the
subprocess executor) and import `datacube_viewer` only there and only when
used, so qgis-project keeps no runtime dependency on it.

The provider reads a ``key=value&...`` source string, its layer URI, which is
also what QGIS writes into the project file. It is written here in that
documented format and parsed by ``datacube_viewer.layeruri.decode_uri``, so a
mistake on this side fails loudly instead of producing a layer that quietly
shows something else.
"""

from __future__ import annotations

import importlib
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

INSTALL_HINT = (
    "Datacube layers need the qgis-datacube-viewer package in the Python that "
    'runs QGIS: pip install "qgis-datacube-viewer[all]". Opening the saved '
    "project needs the Datacube Viewer plugin, installed and enabled in QGIS."
)


def _import(module: str):
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise ImportError(f"{INSTALL_HINT} ({exc})") from exc


def layer_uri(file, *, dataset="", ref=None, variable=None, indices=None, nodata=None):
    """Parse the provider source for one store, dataset, variable and slice.

    *nodata* replaces the store's own nodata value (one number or a list; an
    empty list masks nothing); ``None`` follows the store.

    Returns a ``datacube_viewer.layeruri.LayerUri``; raises its ``UriError``
    (a ``ValueError``) on input the provider would reject.
    """
    decode_uri = _import("datacube_viewer.layeruri").decode_uri
    if variable is not None and not isinstance(variable, str):
        variable = ",".join(variable)
    fields = {
        "url": str(file),
        "dataset": dataset,
        "ref": ref,
        "bands": variable,
        "index": ",".join(f"{dim}={int(i)}" for dim, i in (indices or {}).items()),
    }
    text = "&".join(
        f"{key}={quote(str(value), safe=':/')}" for key, value in fields.items() if value
    )
    if nodata is not None:
        # Unlike the fields above an empty value means something ("mask nothing"),
        # so the key is written whenever an override is given.
        values = [nodata] if isinstance(nodata, (int, float)) else list(nodata)
        numbers = [str(int(v)) if float(v).is_integer() else repr(float(v)) for v in values]
        text += "&nodata=" + quote(",".join(numbers), safe="")
    return decode_uri(text)


def list_variables(file, dataset: str = "", ref: str | None = None) -> list[str]:
    """Return the variable names in one dataset of a datacube store.

    Opens and describes the store with the plugin's own reader, so this lists
    exactly what the provider can show. Raises if the store cannot be read or
    has no such dataset.
    """
    uri = layer_uri(file, dataset=dataset, ref=ref)
    core = _import("datacube_viewer.core")
    info = core.describe_store(core.open_store(uri.store_uri, uri.effective_ref, kind=uri.kind))
    if not info.datasets:
        raise ValueError(f"No georeferenced datasets in {file}.")
    wanted = uri.dataset.strip("/")
    for candidate in info.datasets:
        if not wanted or wanted in (candidate.path.strip("/"), candidate.name):
            return list(candidate.variable_names)
    raise ValueError(
        f"No dataset {dataset!r} in {file}. Available: {', '.join(info.dataset_paths)}"
    )


def source(layer) -> str:
    """The provider source for a single-variable `DatacubeLayer`.

    Registers the provider first, so a QGIS without the plugin running (a
    script, or the subprocess executor) can open the layer.
    """
    _import("datacube_viewer.provider").register_provider()
    uri = layer_uri(
        layer.file,
        dataset=layer.dataset,
        ref=layer.ref,
        variable=layer.variable,
        indices=layer.indices,
        nodata=layer.nodata,
    )
    return uri.encode()


def stretch_across_cube(qgis_layer) -> None:
    """Fix the layer's stretch to the range of the whole cube, not one slice.

    This is what the plugin does when it loads a layer: a stretch taken from
    the slice on show washes out other slices, so stepping through time would
    change the colours as well as the data. Best effort: a store that cannot
    be sampled keeps the stretch QGIS worked out.
    """
    try:
        _import("datacube_viewer.provider").fit_to_cube(qgis_layer)
    except Exception as exc:
        logger.warning(f"Could not stretch '{qgis_layer.name()}' across its cube: {exc}")
