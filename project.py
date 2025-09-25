"""
Module to handle QGIS project functionality.
"""



from typing import Literal
from pyqgis.create_project import QgisLayer, qgis_lazy_import

# TODO: multiprocessing? probably possible by serialization

@qgis_lazy_import({"qgis.core": ["QgsApplication", "QgsProject", "QgsMapCanvas"]})
class Project:
    def __init__(self):

        self._application = QgsApplication([], False)
        self._application.initQgis()

        # Get the project instance
        self._project = QgsProject.instance()
        self._canvas = QgsMapCanvas()     # https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/canvas.html

        self._layers = []


    def add_layer(self, dataset: str | QgisDataset):
        if isinstance(dataset, str):
            dataset = QgisDataset(dataset)

        self._layers.append(dataset)


    def write(self):
        # TODO: similar to `create_qgis_project`
        for ds in self._layers:
            pass





    def focus_on_layer(self, layer): pass


class Layer:
    # TODO: == QgisDataset or not?
    pass


class RasterLayer(Layer):
    # active band?
    pass



def join_projects(
    *projects: Project,
    merging_strategy: Literal["rename", "ask", "first", "last", "ask"] = "rename",
):
    # TODO: implement
    pass