# https://qgis.org/pyqgis/3.40/core/index.html
# https://qgis.org/pyqgis/3.40/search.html?q=zoom&check_keywords=yes&area=default

import importlib
import os
import pickle
import tempfile

from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path



def qgis_lazy_import(imports_dict):
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


@dataclass
class QgisLayerVisualization:
    opacity: float = 1.
    colormap: str = "bw"


    def set_layer_vis(layer):
        # TODO: either two classes, BW and pseudocolor, or if-clause
        set_bw_colorbar_limits()


@dataclass
class QgisDataset:
    # TODO: move non-dataset related params to layer class or visualization class
    # TODO: or rather name Layer
    file: str
    crs: str | int|  None = None
    opacity: float = 1.
    colormap: str = "bw"        # TODO: class & support for color
    vmin: int | None = None
    vmax: int | None = None
    visible: bool = True

    group: str | list[str] | None = None
    name: str | None = None     # TODO: implement logic
    # TODO collapse in tree

    overwrite_existing: bool = False


    def save(self, filepath: str):
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filepath: str):
        with open(filepath, 'rb') as f:
            return pickle.load(f)

    def get_layer_name(self):
        """Get the dataset's name as shown in the layer."""
        return self.name or os.path.basename(self.file)

    def get_path(self):
        """Get the dataset's path as in the layer tree."""
        if self.group is None:
            return [self.get_layer_name()]
        elif isinstance(self.group, str):
            return [self.group, self.get_layer_name()]
        else:
            return [*self.group, self.get_layer_name()]

    # TODO: import; kill or implement
    # def link(layer: QgsMapLayer):
    #     """Meant to embed an actual qgis layer object -> can be used for qgis raster calculations"""
    #     pass


@dataclass
class QgisLayer:
    def get_min_max(self):
        # TODO
        pass


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
            print(f"Added group   {group_path}")
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
    # TODO: what happens with duplicate names?

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
            print(f"Group path not found: {group_path_str}")
            return False

    # Search for the layer in the final group
    for child in parent.children():
        if isinstance(child, QgsLayerTreeLayer) and child.layer().name() == layer_name:
            project.removeMapLayer(child.layer().id())
            print(f"Removed layer '{layer_name}' @ group {group_path_str}")
            return True

    print(f"Layer '{layer_name}' not found in {group_path_str}")
    return False


@qgis_lazy_import({
    "qgis.core": [
        "QgsApplication", "QgsProject",
        "QgsVectorLayer", "QgsRasterLayer",
        "QgsMapSettings", "QgsCoordinateReferenceSystem",

        "QgsColorRampShader", "QgsRasterShader",
        "QgsSingleBandPseudoColorRenderer", "QgsSingleBandGrayRenderer",
        "QgsContrastEnhancement", "QgsRasterBandStats", "QgsStyle",
    ],
    "qgis.PyQt.QtGui": ["QColor"],
    "qgis.gui": ["QgsMapCanvas"]
})
def create_qgis_project(
    datasets: list[QgisDataset | str],
    project_outfile: str,
    project_crs: str | int = "EPSG:4326",
    overwrite_existing: bool = False,
):
    """
    Create a QGIS project and add the specified files as layers.

    Parameters
    ----------
    datasets : list[QgisDataset  |  str]
        A list of datasets/layers to add to the project. Can either be a path to the dataset, or the an instance of `QgisDataset`, which encapsulates further layer options
    project_outfile : str
        Path to QGIS project to create
    project_crs : str
        Set the project's CRS, by default "EPSG:4326"
    """


    """
    Create a QGIS project and add the specified files as layers.

    Parameters:
        files (list of str): Paths to shapefiles, GeoTIFFs, etc.
        project_outfile (str): Output path for the .qgz project file.
        qgis_prefix (str): Path to the QGIS installation prefix.
                           Default is "/usr" (Linux). On Windows, use something like "C:/OSGeo4W64/apps/qgis".
    """

    def get_layer_min_max(rlayer, vmin, vmax, band_idx=1):
        # compute auto-limits if not provided
        # TODO: computation mode estimate/exact
        if vmin is None:
            stats = rlayer.dataProvider().bandStatistics(band_idx, QgsRasterBandStats.Min)

            # TODO: test
            stats_exact = rlayer.dataProvider().bandStatistics(band_idx, QgsRasterBandStats.Min, layer.extent(), 0)     # sample size 0 -> exact

            assert stats.minimumValue == stats_exact.minimumValue, "Not equal, use exact one and introduce param to function"

            vmin = stats.minimumValue
        if vmax is None:
            stats = rlayer.dataProvider().bandStatistics(band_idx, QgsRasterBandStats.Max)
            vmax = stats.maximumValue

        return vmin, vmax


    # TODO: fix; sets colormap, but limit setting does not work
    def apply_named_colormap(rlayer, vmin, vmax, ramp_name="Viridis", steps=10):
        vmin, vmax = get_layer_min_max(rlayer, vmin, vmax)

        # Get color ramp from QGIS's style manager
        style = QgsStyle().defaultStyle()
        color_ramp = style.colorRamp(ramp_name)
        # color_ramp_discrete = color_ramp.convertToDiscrete()

        if not color_ramp:
            raise ValueError(f"Color ramp '{ramp_name}' not found.")

        # Create evenly spaced color ramp items
        shader_items = []
        for i in range(steps + 1):
            value = vmin + (i / steps) * (vmax - vmin)
            color = color_ramp.color(float(i) / steps)
            label = f"{value:.2f}"
            shader_items.append(QgsColorRampShader.ColorRampItem(value, color, label))

        shader = QgsColorRampShader()
        shader.setColorRampType(QgsColorRampShader.Interpolated)
        shader.setColorRampItemList(shader_items)

        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(shader)

        renderer = QgsSingleBandPseudoColorRenderer(rlayer.dataProvider(), 1, raster_shader)
        renderer.setClassificationMin(vmin)
        renderer.setClassificationMax(vmax)

        # TODO: test
        # Configure the min/max origin
        # origin = QgsRasterMinMaxOrigin()
        # origin.setLimits(QgsRasterMinMaxOrigin.MinMax)              # use min/max, not user-defined
        # origin.setExtent(QgsRasterMinMaxOrigin.WholeRaster)         # use whole raster extent
        # origin.setAccuracy(QgsRasterMinMaxOrigin.Exact)             # <-- forces actual stats calculation
        # renderer.setMinMaxOrigin(origin)

        rlayer.setRenderer(renderer)
        rlayer.triggerRepaint()



    def apply_named_colormap_new(rlayer, vmin, vmax, ramp_name="Viridis", steps=10):
        vmin, vmax = get_layer_min_max(rlayer, vmin, vmax)

        # Get color ramp from QGIS's style manager
        style = QgsStyle().defaultStyle()
        color_ramp = style.colorRamp(ramp_name)
        # color_ramp_discrete = color_ramp.convertToDiscrete()

        if not color_ramp:
            raise ValueError(f"Color ramp '{ramp_name}' not found.")

        # Create evenly spaced color ramp items
        shader_items = []
        for i in range(steps + 1):
            value = vmin + (i / steps) * (vmax - vmin)
            color = color_ramp.color(float(i) / steps)
            label = f"{value:.2f}"
            shader_items.append(QgsColorRampShader.ColorRampItem(value, color, label))

        fcn = QgsColorRampShader()
        fcn.setColorRampType(QgsColorRampShader.Interpolated)
        lst = [
            QgsColorRampShader.ColorRampItem(0, QColor(0,255,0)),
            QgsColorRampShader.ColorRampItem(255, QColor(255,255,0))
        ]
        fcn.setColorRampItemList(lst)
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(fcn)

        renderer = QgsSingleBandPseudoColorRenderer(rlayer.dataProvider(), 1, shader)
        renderer.setClassificationMin(vmin)
        renderer.setClassificationMax(vmax)
        rlayer.setRenderer(renderer)
        rlayer.triggerRepaint()



    def set_bw_colorbar_limits(rlayer, vmin=None, vmax=None):
        vmin, vmax = get_layer_min_max(rlayer, vmin, vmax)


        """
        # see: https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/raster.html
        fcn = QgsColorRampShader()
        fcn.setColorRampType(QgsColorRampShader.Interpolated)   # linear interpolation; also: Discrete (closest higher value); Exact
        lst = [
            # green to yellow
            QgsColorRampShader.ColorRampItem(0, QColor(0,255,0)),
            QgsColorRampShader.ColorRampItem(255, QColor(255,255,0))
        ]
        fcn.setColorRampItemList(lst)

        shader = QgsRasterShader()
        shader.setRasterShaderFunction(fcn)

        renderer = QgsSingleBandPseudoColorRenderer(rlayer.dataProvider(), 1, shader)
        rlayer.setRenderer(renderer)
        rlayer.triggerRepaint()
        """

        # https://gis.stackexchange.com/questions/377569/setting-max-min-values-of-singleband-grey-layer-using-pyqgis
        renderer = QgsSingleBandGrayRenderer(rlayer.dataProvider(), 1)
        myType = renderer.dataType(1)
        myEnhancement = QgsContrastEnhancement(myType)
        contrast_enhancement = QgsContrastEnhancement.StretchToMinimumMaximum
        myEnhancement.setContrastEnhancementAlgorithm(contrast_enhancement,True)
        myEnhancement.setMinimumValue(vmin)   #Set the minimum value you want
        myEnhancement.setMaximumValue(vmax)   #Put the maximum value you want

        rlayer.setRenderer(renderer)
        rlayer.renderer().setContrastEnhancement(myEnhancement)
        rlayer.triggerRepaint()


    # Initialize QGIS application
    qgs = QgsApplication([], False)
    qgs.initQgis()

    # Get the project instance
    project = QgsProject.instance()
    canvas = QgsMapCanvas()     # https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/canvas.html

    # load existing project
    if not overwrite_existing and os.path.exists(project_outfile):
        project.read(project_outfile)


    if project_crs is not None:
        if isinstance(project_crs, int):
            project_crs = f"EPSG:{project_crs}"
        project.setCrs(QgsCoordinateReferenceSystem(project_crs))

    layer = None
    for ds in datasets:
        if isinstance(ds, str):
            ds = QgisDataset(ds)

        if not os.path.exists(ds.file):
            print(f"File does not exist: {ds.file}")
            continue

        # Determine layer type
        ext = os.path.splitext(ds.file)[1].lower()
        if ext in ['.shp', '.geojson', '.gpkg']:
            layer = QgsVectorLayer(ds.file, os.path.basename(ds.file), "ogr")
        elif ext in ['.tif', '.tiff', '.img']:
            layer = QgsRasterLayer(ds.file, os.path.basename(ds.file))
            if ds.colormap == "bw":
                set_bw_colorbar_limits(layer, ds.vmin, ds.vmax)
            else:
                apply_named_colormap(layer, ds.vmin, ds.vmax, ds.colormap)
            # apply_named_colormap(layer, ds.vmin, ds.vmax, "Viridis")
        else:
            print(f"Unsupported file format: {ds.file}")
            continue

        if not layer.isValid():
            print(f"Failed to load layer: {ds.file}")
        else:
            layer_path = ds.get_path()
            if layer_exists_by_path(project, layer_path):
                if ds.overwrite_existing:
                    remove_layer_by_path(project, layer_path)

            add_to_root = ds.group is None
            project.addMapLayer(layer, addToLegend=add_to_root)

            group_str = '/'.join(['/ROOT', *ds.get_path()[:-1]])
            print(f"Added layer   '{ds.get_layer_name()}' @ group {group_str}")

            if not add_to_root:
                # group = add_or_get_group(project, ds.group)
                group = add_or_get_group(project, ds.get_path()[:-1])
                group.addLayer(layer)


        if ds.crs is not None:
            if isinstance(ds.crs, int):
                ds.crs = f"EPSG:{ds.crs}"
            layer.setCrs(QgsCoordinateReferenceSystem(ds.crs))

        if ds.opacity is not None:
            layer.setOpacity(ds.opacity)

        if ds.visible is False:
            # Find the corresponding layer tree node and set visibility to False (hide)
            layer_node = project.layerTreeRoot().findLayer(layer.id())
            if layer_node:
                layer_node.setItemVisibilityChecked(False)


    # zoom on last added layer (if layers were added)
    # TODO: replace by `get_top_layer` or smth
    if layer is not None:
        layer_extent = layer.extent()
        canvas.setExtent(layer_extent)

    # Save the project
    project.write(project_outfile)
    print(f"Project saved to: {project_outfile}")

    # Clean up
    qgs.exitQgis()


@contextmanager
def export_dataset_objects(objects: list[QgisDataset | str]):
    """
    Temporarily pickle the dataset objects, such that they can be passed to the subprocess running `conda run`.
    This allows to pass custom dataclass objects via CLI.

    Usage:
    ```
    with export_dataset_objects(list_of_files_and_qgisdatasets) as picke_files:
        ...
    ```
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        file_paths = []
        for i, obj in enumerate(objects):
            # make Dataset if str
            if isinstance(obj, str): obj = QgisDataset(obj)

            file_path = tmp_path / (os.path.splitext(os.path.basename(obj.file))[0]+".pkl")
            obj.save(file_path)
            file_paths.append(file_path)

        yield file_paths
    # TemporaryDirectory automatically deletes tmpdir after block


# TODO: move to `standalone` module
def create_qgis_project_env(datasets, outfile):
    """
    Create a qgis project and populate with files.

    Run this script within a conda environment that supports the python bindings of qgis.
    This way, functions can be called from other environments as well.
    """
    import subprocess

    with export_dataset_objects(datasets) as picke_files:
        result = subprocess.run([
            "conda", "run", "-n", "qgis-env", "python", os.path.abspath(__file__), *picke_files, outfile
        ], capture_output=True, text=True)

    if result.returncode == 0:
        print("Script ran successfully!")
        print(result.stdout)
        print(result.stderr)
    else:
        print("Script failed!")
        print("stderr output:", result.stderr)
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError("Script failed:\n\n--- stderr:\n" + result.stderr)
    return result


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("files", nargs="+", help="All files (or pickled QgisDataset objects containing a file) which should be added to the project.")
    parser.add_argument("project_file", help="Filename of QGIS project to create")
    args = parser.parse_args()

    # allow mixture of pickled dataset objects or pure files
    args.files = [
        (QgisDataset.load(file) if file.endswith("pkl") else file) for file in args.files
    ]

    create_qgis_project(args.files, args.project_file)
