"""
Executor entry point - runs inside the QGIS-bundled Python.

Reads a JSON spec written by SubprocessProject, builds the QGIS project,
and saves (and optionally opens) it.

Usage:
    python-qgis.bat _executor.py spec.json
"""

import json
import os
import sys


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: _executor.py <spec.json>")

    with open(sys.argv[1]) as f:
        spec = json.load(f)

    action = spec["action"]
    output = spec["output"]

    from qgis.core import QgsApplication, QgsProject
    from qgis.gui import QgsMapCanvas

    prefix = os.environ.get("QGIS_PREFIX_PATH", "")
    QgsApplication.setPrefixPath(prefix, True)
    app = QgsApplication([], False)
    app.initQgis()

    project = QgsProject.instance()
    QgsMapCanvas()  # required for some providers to initialise correctly

    for layer_spec in spec["layers"]:
        _add_layer(project, layer_spec)

    _zoom_to_all_layers(project)

    if action in ("save", "save_and_open"):
        ok = project.write(output)
        if not ok:
            app.exitQgis()
            sys.exit(f"QgsProject.write() failed for: {output}")
        print(f"Project saved to: {output}")

    if action in ("open", "save_and_open"):
        import shutil
        import subprocess
        qgis_bin = shutil.which("qgis")
        if qgis_bin:
            subprocess.Popen([qgis_bin, output])
        else:
            print("QGIS executable not found on PATH; skipping open.", file=sys.stderr)

    app.exitQgis()


def _add_layer(project, spec: dict) -> None:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsRasterLayer,
        QgsVectorLayer,
    )

    file = spec["file"]
    name = spec.get("name") or os.path.basename(file)
    visible = spec.get("visible", True)
    crs = spec.get("crs")
    group = spec.get("group")
    overwrite = spec.get("overwrite_existing", False)

    ext = os.path.splitext(file)[-1].lower()
    if ext in (".shp", ".geojson", ".gpkg"):
        qgis_layer = QgsVectorLayer(file, name, "ogr")
    elif ext in (".tif", ".tiff", ".img"):
        qgis_layer = QgsRasterLayer(file, name)
    else:
        print(f"Unsupported format: {file}", file=sys.stderr)
        return

    if not qgis_layer.isValid():
        print(f"Failed to load layer: {file}", file=sys.stderr)
        return

    style_spec = spec.get("style")
    if style_spec:
        band_idx = spec.get("band_idx", 1)
        _apply_style(qgis_layer, style_spec, band_idx)

    if group is None:
        project.addMapLayer(qgis_layer, addToLegend=True)
    else:
        project.addMapLayer(qgis_layer, addToLegend=False)
        group_path = [group] if isinstance(group, str) else group
        _get_or_create_group(project.layerTreeRoot(), group_path).addLayer(qgis_layer)

    layer_node = project.layerTreeRoot().findLayer(qgis_layer.id())
    if layer_node:
        layer_node.setItemVisibilityChecked(visible)

    if crs is not None:
        if isinstance(crs, int):
            crs = f"EPSG:{crs}"
        qgis_layer.setCrs(QgsCoordinateReferenceSystem(crs))


def _apply_style(qgis_layer, style_spec: dict, band_idx: int = 1) -> None:
    style_type = style_spec.get("type", "")
    opacity = style_spec.get("opacity", 1.0)

    if style_type == "RasterStyleBW":
        from qgis.core import (
            QgsContrastEnhancement,
            QgsRasterBandStats,
            QgsSingleBandGrayRenderer,
        )

        vmin = style_spec.get("vmin")
        vmax = style_spec.get("vmax")
        if vmin is None:
            vmin = qgis_layer.dataProvider().bandStatistics(band_idx, QgsRasterBandStats.Min).minimumValue
        if vmax is None:
            vmax = qgis_layer.dataProvider().bandStatistics(band_idx, QgsRasterBandStats.Max).maximumValue

        renderer = QgsSingleBandGrayRenderer(qgis_layer.dataProvider(), 1)
        enhancement = QgsContrastEnhancement(renderer.dataType(1))
        enhancement.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum, True)
        enhancement.setMinimumValue(vmin)
        enhancement.setMaximumValue(vmax)
        qgis_layer.setRenderer(renderer)
        qgis_layer.renderer().setContrastEnhancement(enhancement)

    qgis_layer.setOpacity(opacity)


def _zoom_to_all_layers(project) -> None:
    from qgis.core import QgsCoordinateTransform, QgsReferencedRectangle, QgsRectangle

    project_crs = project.crs()
    combined = QgsRectangle()

    for node in project.layerTreeRoot().findLayers():
        layer = node.layer()
        if layer is None:
            continue
        try:
            extent = layer.extent()
            if layer.crs() != project_crs:
                transform = QgsCoordinateTransform(layer.crs(), project_crs, project)
                extent = transform.transformBoundingBox(extent)
            combined.combineExtentWith(extent)
        except Exception:
            pass

    if not combined.isNull():
        project.viewSettings().setDefaultViewExtent(
            QgsReferencedRectangle(combined, project_crs)
        )


def _get_or_create_group(root, path: list):
    from qgis.core import QgsLayerTreeGroup

    node = root
    for name in path:
        child = next(
            (c for c in node.children() if isinstance(c, QgsLayerTreeGroup) and c.name() == name),
            None,
        )
        if child is None:
            child = node.addGroup(name)
        node = child
    return node


if __name__ == "__main__":
    main()
