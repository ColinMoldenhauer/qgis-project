"""
Module to handle QGIS project functionality.
"""



from pyqgis.create_project import QgisDataset


class Project:
    def __init__(self):

        self._application = QgsApplication([], False)
        self._application.initQgis()

        # Get the project instance
        self._project = QgsProject.instance()
        self._canvas = QgsMapCanvas()     # https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/canvas.html


    def add_layer(self, dataset: str | QgisDataset):
        pass


class Layer:
    # TODO: == QgisDataset or not?
    pass


class RasterLayer(Layer):
    # active band?
    pass