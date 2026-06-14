# SPDX-FileCopyrightText: 2025-present Colin Moldenhauer <colin.moldenhauer@posteo.de>
#
# SPDX-License-Identifier: MIT
from ._env import find_qgis_launcher, find_qgis_prefix_path, setup_qgis_env

_qgis_available = setup_qgis_env()

if _qgis_available:
    # Strategy 1 (standalone, in-process) or Strategy 3 (conda-forge).
    from qgis.core import QgsApplication
    try:
        QgsApplication.setPrefixPath(find_qgis_prefix_path(), True)
    except RuntimeError:
        pass  # prefix not found (e.g. mocked qgis in unit-test env); safe to skip
    from .project import Project
else:
    _launcher = find_qgis_launcher()
    if _launcher is not None:
        # Strategy 2 (subprocess): delegate to the standalone QGIS Python.
        from ._subprocess import SubprocessProject as Project  # type: ignore[assignment]
    else:
        # No QGIS available at all.  Layer/Style/RasterLayer are still
        # importable (pure Python); only Project() will raise.
        class Project:  # type: ignore[no-redef]
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "QGIS not found. Install QGIS via conda-forge into this "
                    "environment or install a standalone QGIS application."
                )

from .layer import Layer, ProcessingOp, RasterLayer, WebLayer
from .style import (
    Style,
    RasterStyle,
    RasterStyleBW,
    RasterStyleSinglePseudocolor,
    RasterStyleMultiBandColor,
    VectorStyle,
    VectorStyleSingleSymbol,
    VectorStyleCategorized,
    VectorStyleGraduated,
)