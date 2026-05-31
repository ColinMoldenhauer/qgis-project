
import sys
sys.path.append("src")
from qgis_project.layer import RasterLayer


r = RasterLayer("some_file")
r.get_layer_min_max()
