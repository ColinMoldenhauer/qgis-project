"""
Module to handle QGIS project functionality.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from qgis_project.layer import (
    Layer,
    RasterLayer,
    WebLayer,
    gdal_raster_source,
    is_netcdf,
    layer_from_path,
    netcdf_name_and_group,
)
from qgis_project.utils import (
    add_or_get_group,
    get_layer_by_idx,
    layer_exists_by_path,
    list_raster_variables,
    normalize_crs,
    remove_layer_by_path,
)

logger = logging.getLogger(__name__)


class Project:
    def __init__(
        self,
        file: str | None = None,
        crs: str | int | None = None,
        data_dir: str | Path | None = None,
    ):
        from qgis.core import QgsApplication, QgsProject
        from qgis.gui import QgsLayerTreeMapCanvasBridge, QgsMapCanvas

        existing = QgsApplication.instance()
        if existing is None:
            self._application = QgsApplication([], False)
            self._application.initQgis()
            self._owns_app = True
        else:
            self._application = existing
            self._owns_app = False

        self._project = QgsProject.instance()
        self._canvas = QgsMapCanvas()
        # Bridge keeps the canvas in sync with the project layer tree so that
        # layers added via addMapLayer() appear on the canvas automatically.
        self._bridge = QgsLayerTreeMapCanvasBridge(
            self._project.layerTreeRoot(), self._canvas
        )
        self._canvas.resize(800, 600)
        self._processing_initialized = False
        self._data_dir: Path | None = Path(data_dir) if data_dir is not None else None
        self._auto_output_idx = 0
        self._view_extent_set = False
        if file is not None:
            self._project.read(file)
        if crs is not None:
            self.set_crs(crs)

    def _resolve_netcdf(self, layer: RasterLayer) -> list[RasterLayer] | None:
        """Expand a NetCDF raster layer into one concrete layer per variable.

        Returns a list of `RasterLayer`s — each pinned to a single variable with
        its name/group derived (see `netcdf_name_and_group`) — or `None` when no
        expansion applies (not a NetCDF file, a missing file, or a single-variable
        file with no explicit `variable`), in which case the caller loads *layer*
        as-is.
        """
        if not is_netcdf(layer.file) or not os.path.exists(layer.file):
            return None

        variable = layer.variable
        available = list_raster_variables(layer.file)

        if not available:
            # Single-variable file: GDAL opens it directly as the main dataset.
            # Only intervene if the user asked for a specific variable by name.
            if variable is None:
                return None
            requested = [variable] if isinstance(variable, str) else list(variable)
        else:
            if variable is None:
                requested = list(available)
            elif isinstance(variable, str):
                requested = [variable]
            else:
                requested = list(variable)

            valid = [v for v in requested if v in available]
            unknown = [v for v in requested if v not in available]
            if unknown:
                logger.warning(
                    f"Variable(s) not found in {os.path.basename(layer.file)}: "
                    f"{', '.join(map(str, unknown))}. Available: {', '.join(available)}"
                )
            requested = valid

        multiple = len(requested) > 1
        children = []
        for token in requested:
            name, group = netcdf_name_and_group(
                layer.file, token, layer.group, layer.name, multiple
            )
            children.append(
                dataclasses.replace(layer, variable=token, name=name, group=group)
            )
        return children

    def _add_layer(self, layer: Layer | WebLayer):
        """Add a layer to the project, expanding multi-variable NetCDF files."""
        if isinstance(layer, RasterLayer):
            resolved = self._resolve_netcdf(layer)
            if resolved is not None:
                for child in resolved:
                    self._add_single_layer(child)
                return
        self._add_single_layer(layer)

    def _add_single_layer(self, layer: Layer | WebLayer):
        """Add one resolved layer to the underlying project."""
        from qgis.core import (
            QgsCoordinateReferenceSystem,
            QgsRasterLayer,
            QgsVectorLayer,
        )

        if isinstance(layer, WebLayer):
            if layer.provider == "WFS":
                qgis_layer = QgsVectorLayer(layer.uri, layer.get_layer_name(), "WFS")
            else:
                qgis_layer = QgsRasterLayer(
                    layer.uri, layer.get_layer_name(), layer.provider
                )
        else:
            if not os.path.exists(layer.file):
                logger.error(f"File does not exist: {layer.file}")
                return

            name = layer.get_layer_name()
            variable = getattr(layer, "variable", None)
            if variable is not None:
                # A resolved NetCDF variable — load it directly through GDAL.
                qgis_layer = QgsRasterLayer(
                    gdal_raster_source(layer.file, variable), name, "gdal"
                )
            else:
                # Try vector first, then raster — delegates format detection to
                # GDAL/OGR so any format they support works without an extension list.
                qgis_layer = QgsVectorLayer(layer.file, name, "ogr")
                if not qgis_layer.isValid():
                    qgis_layer = QgsRasterLayer(layer.file, name)
            if not qgis_layer.isValid():
                logger.error(f"Unsupported or unreadable file: {layer.file}")
                return

        layer.set_qgis_layer(qgis_layer)

        if not qgis_layer.isValid():
            source = layer.uri if isinstance(layer, WebLayer) else layer.file
            logger.error(f"Failed to load layer: {source}")
            return

        layer_filter = getattr(layer, "filter", None)
        if isinstance(qgis_layer, QgsVectorLayer) and layer_filter:
            if not qgis_layer.setSubsetString(layer_filter):
                logger.warning(
                    f"Invalid filter expression for '{layer.get_layer_name()}': {layer_filter!r}"
                )

        if getattr(layer, "style", None) is not None:
            layer.style.set_style(layer)

        if isinstance(qgis_layer, QgsVectorLayer) and getattr(layer, "labels", None) is not None:
            layer.labels.apply(layer)

        min_scale = getattr(layer, "min_scale", None)
        max_scale = getattr(layer, "max_scale", None)
        if min_scale is not None or max_scale is not None:
            qgis_layer.setScaleBasedVisibility(True)
            if min_scale is not None:
                qgis_layer.setMinimumScale(min_scale)
            if max_scale is not None:
                qgis_layer.setMaximumScale(max_scale)

        layer_path = layer.get_path()
        if layer_exists_by_path(self._project, layer_path):
            if layer.overwrite_existing:
                remove_layer_by_path(self._project, layer_path)
            else:
                logger.warning(f"Layer already exists, skipping: {layer_path}")
                return

        add_to_root = layer.group is None
        self._project.addMapLayer(qgis_layer, addToLegend=add_to_root)

        if add_to_root:
            layer_node = self._project.layerTreeRoot().findLayer(qgis_layer.id())
        else:
            group = add_or_get_group(self._project, layer.get_path()[:-1])
            layer_node = group.addLayer(qgis_layer)

        if layer.crs is not None:
            qgis_layer.setCrs(QgsCoordinateReferenceSystem(normalize_crs(layer.crs)))

        layer_node.setItemVisibilityChecked(layer.visible)

        group_str = (
            "/".join(["/ROOT", *layer.get_path()[:-1]]) if layer.group else "/ROOT"
        )
        logger.info(f"Added layer '{layer.get_layer_name()}' @ {group_str}")

    def add_layer(self, layer: Layer | WebLayer | str, **kwargs):
        """Add a layer to the project. Accepts a file path string, a Layer, or a WebLayer.

        When *layer* is a string path, extra keyword arguments (`name`, `group`,
        `visible`, `crs`, `overwrite_existing`, `style`, ...) are forwarded
        to the layer constructor. A :class:`RasterLayer` is built automatically
        when a raster-specific keyword is given (a :class:`RasterStyle` style,
        `band_idx`, or `statistics_kwargs`); otherwise a plain :class:`Layer`.
        """
        if isinstance(layer, str):
            layer = layer_from_path(layer, **kwargs)
        self._add_layer(layer)

    def remove_layer(self, layer: Layer | str):
        """Remove a layer from the project by path."""
        if isinstance(layer, str):
            layer = Layer(layer)
        remove_layer_by_path(self._project, layer.get_path())

    def set_crs(self, crs: str | int):
        """Set the project's coordinate reference system.

        Parameters
        ----------
        crs : str or int
            EPSG integer (e.g. `3857`) or authority string (e.g. `"EPSG:3857"`).
        """
        from qgis.core import QgsCoordinateReferenceSystem

        self._project.setCrs(QgsCoordinateReferenceSystem(normalize_crs(crs)))

    def process(
        self,
        algorithm: str,
        params: dict,
        name: str = "",
        group=None,
        visible: bool = True,
    ):
        """Run a QGIS Processing algorithm and add the result to the project.

        Parameters
        ----------
        algorithm : str
            QGIS processing algorithm identifier, e.g. `"native:buffer"`.
        params : dict
            Algorithm parameters. Must include `"INPUT"` and typically
            `"OUTPUT"`. Pass a file path for persistent outputs. `"memory:"``
            is silently redirected to a temporary GeoPackage so the layer
            survives project save/load.
        name : str
            Name for the result layer. Defaults to the algorithm tail.
        group : str or list of str or None
            Layer group path.
        visible : bool
            Whether the result layer is visible on project open.
        """
        self._ensure_processing()
        import processing as _processing  # QGIS processing plugin; plugins dir must be on sys.path

        layer_name = name or algorithm.split(":")[-1]

        # Memory layers don't survive project save/load — redirect to a persistent file.
        params = dict(params)
        output_val = params.get("OUTPUT", "")
        if isinstance(output_val, str) and output_val.startswith("memory:"):
            self._auto_output_idx += 1
            slug = f"proc_{self._auto_output_idx:02d}.gpkg"
            if self._data_dir is not None:
                self._data_dir.mkdir(parents=True, exist_ok=True)
                auto_path = str(self._data_dir / slug)
            else:
                auto_path = os.path.join(tempfile.mkdtemp(), slug)
            params["OUTPUT"] = auto_path
            logger.debug(f"Redirected memory output for '{layer_name}' to {auto_path}")

        result = _processing.run(algorithm, params)
        output = result.get("OUTPUT")
        if output is None:
            logger.warning(f"Algorithm {algorithm!r} produced no OUTPUT")
            return
        if isinstance(output, str):
            self._add_layer(
                Layer(output, name=layer_name, group=group, visible=visible)
            )
        else:
            output.setName(layer_name)
            add_to_root = group is None
            self._project.addMapLayer(output, addToLegend=add_to_root)
            if add_to_root:
                node = self._project.layerTreeRoot().findLayer(output.id())
            else:
                g = [group] if isinstance(group, str) else group
                node = add_or_get_group(self._project, g).addLayer(output)
            if node:
                node.setItemVisibilityChecked(visible)
            else:
                logger.warning(
                    f"Could not find layer tree node for processing result '{layer_name}'"
                )

    def _ensure_processing(self):
        if self._processing_initialized:
            return
        from processing.core.Processing import Processing

        Processing.initialize()
        self._processing_initialized = True

    def center(self, layer: Layer | None = None):
        """
        Set the project's initial view extent to a single layer.
        If no layer is provided, uses the last layer in the tree.
        """
        if layer is None:
            qgis_layer = get_layer_by_idx(self._project, -1)
        else:
            qgis_layer = layer.qgis_layer

        extent = self._transform_extent_to_project_crs(
            qgis_layer.extent(), qgis_layer.crs()
        )
        self._set_view_extent(extent)

    def zoom_to_all(self):
        """Set the project's initial view extent to the union of all layers."""
        from qgis.core import QgsRectangle

        combined = QgsRectangle()
        for node in self._project.layerTreeRoot().findLayers():
            qgis_layer = node.layer()
            if qgis_layer is None:
                continue
            try:
                extent = self._transform_extent_to_project_crs(
                    qgis_layer.extent(), qgis_layer.crs()
                )
                combined.combineExtentWith(extent)
            except Exception:
                logger.warning(
                    f"Could not transform extent for layer: {qgis_layer.name()}"
                )
        if not combined.isNull():
            self._set_view_extent(combined)

    def _transform_extent_to_project_crs(self, extent, layer_crs):
        from qgis.core import QgsCoordinateTransform

        project_crs = self._project.crs()
        if layer_crs == project_crs:
            return extent
        transform = QgsCoordinateTransform(layer_crs, project_crs, self._project)
        return transform.transformBoundingBox(extent)

    def _set_view_extent(self, extent):
        from qgis.core import QgsReferencedRectangle

        project_crs = self._project.crs()
        ref_extent = QgsReferencedRectangle(extent, project_crs)
        self._project.viewSettings().setDefaultViewExtent(ref_extent)
        self._canvas.setExtent(extent)
        self._canvas.refresh()
        self._view_extent_set = True

    def open(self, file: str | None = None):
        """
        Save the project and open it in QGIS for visual inspection.

        Parameters
        ----------
        file : str or None
            Path to save the project to before opening. If None, a temporary
            file is created. Note that temporary files are deleted when the
            Python process exits, so pass an explicit path for persistent output.
        """
        if file is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".qgz", delete=False)
            file = tmp.name
            tmp.close()

        self.save(file)

        qgis_bin = shutil.which("qgis")
        if qgis_bin is None:
            raise RuntimeError(
                "QGIS executable not found on PATH. "
                "Make sure your QGIS conda environment is active."
            )
        subprocess.Popen([qgis_bin, file])
        logger.info(f"Opened QGIS with project: {file}")

    def snapshot(self, path: str | None = None):
        """Capture the current canvas as a still image.

        Behaviour depends on context:

        - **Jupyter notebook**: returns an `IPython.display.Image` that
          renders inline in the cell output.
        - **path given**: saves a PNG to that path and returns a `Path`.
        - **Script (no Jupyter, no path)**: saves to a temporary file and
          returns its `Path`.

        Parameters
        ----------
        path : str or None
            Destination file path.  If `None`, auto-detected from context.
        """
        from pathlib import Path as _Path
        from qgis.PyQt.QtCore import QBuffer, QIODevice
        from qgis.PyQt.QtWidgets import QApplication

        QApplication.processEvents()

        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        self._canvas.grab().toImage().save(buf, "PNG")
        buf.close()
        png = bytes(buf.data())

        if path is not None:
            _Path(path).write_bytes(png)
            return _Path(path)

        # Jupyter: display inline
        try:
            from IPython import get_ipython

            if get_ipython() is not None:
                from IPython.display import Image

                return Image(data=png)
        except ImportError:
            pass

        # Script fallback: write to a temp file and return path
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(png)
        tmp.close()
        return _Path(tmp.name)

    def save(self, file: str):
        """Save the project to a .qgz file.

        If neither :meth:`zoom_to_all` nor :meth:`center` has been called, the
        view is automatically zoomed to the extent of all layers.
        """
        if not self._view_extent_set:
            self.zoom_to_all()

        p = Path(file)
        if self._data_dir is None:
            self._data_dir = p.parent / (p.stem + "_data")
        ok = self._project.write(file)
        if not ok:
            raise RuntimeError(
                f"QgsProject.write() failed for: {file}\n"
                "Make sure the QGIS prefix path is set correctly."
            )
        logger.info(f"Project saved to: {file}")

    def exit(self):
        """Clean up the QGIS application.

        Only tears down QgsApplication if this Project instance created it.
        When multiple Project instances share one process (e.g. in a test
        session), only the first one owns the application.
        """
        if self._owns_app:
            self._application.exitQgis()

    def print_layer_tree(self):
        """Print the layer tree to stdout."""
        from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer

        def _print_node(node, indent: int):
            prefix = "  " * indent
            if isinstance(node, QgsLayerTreeLayer):
                visible = "✓" if node.isVisible() else "○"
                print(f"{prefix}[{visible}] {node.layer().name()}")
            elif isinstance(node, QgsLayerTreeGroup):
                visible = "✓" if node.isVisible() else "○"
                print(f"{prefix}[{visible}] ▶ {node.name()}")
                for child in node.children():
                    _print_node(child, indent + 1)

        for child in self._project.layerTreeRoot().children():
            _print_node(child, 0)

    def _find_group(self, path: list[str]):
        """Return the QgsLayerTreeGroup at *path*, or None if not found."""
        from qgis.core import QgsLayerTreeGroup

        node = self._project.layerTreeRoot()
        for name in path:
            node = next(
                (
                    c
                    for c in node.children()
                    if isinstance(c, QgsLayerTreeGroup) and c.name() == name
                ),
                None,
            )
            if node is None:
                return None
        return node

    def _collapse_expand_all(self, expanded: bool):
        from qgis.core import QgsLayerTreeModel
        from qgis.gui import QgsLayerTreeView

        model = QgsLayerTreeModel(self._project.layerTreeRoot())
        view = QgsLayerTreeView()
        view.setModel(model)
        if expanded:
            view.expandAll()
        else:
            view.collapseAll()

    def collapse_group(self, *path: str):
        """Collapse a group in the layer tree.

        Parameters
        ----------
        *path : str
            Group name sequence, e.g. `collapse_group("terrain")` or
            `collapse_group("terrain", "raw")` for a nested group.
        """
        group = self._find_group(list(path))
        if group is not None:
            group.setExpanded(False)
        else:
            logger.warning(f"Group not found: {list(path)}")

    def expand_group(self, *path: str):
        """Expand a group in the layer tree.

        Parameters
        ----------
        *path : str
            Group name sequence, same syntax as :meth:`collapse_group`.
        """
        group = self._find_group(list(path))
        if group is not None:
            group.setExpanded(True)
        else:
            logger.warning(f"Group not found: {list(path)}")

    def collapse_all(self):
        """Collapse all groups in the layer tree."""
        self._collapse_expand_all(False)

    def expand_all(self):
        """Expand all groups in the layer tree."""
        self._collapse_expand_all(True)
