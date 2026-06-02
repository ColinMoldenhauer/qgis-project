# SPDX-FileCopyrightText: 2025-present Colin Moldenhauer <colin.moldenhauer@posteo.de>
#
# SPDX-License-Identifier: MIT
from ._env import find_qgis_prefix_path, setup_qgis_env
setup_qgis_env()

from qgis.core import QgsApplication
QgsApplication.setPrefixPath(find_qgis_prefix_path(), True)

from .project import Project
from .layer import Layer, RasterLayer
from .style import Style, RasterStyle, RasterStyleBW, RasterStyleSinglePseudocolor, RasterStyleMultiPseudocolor