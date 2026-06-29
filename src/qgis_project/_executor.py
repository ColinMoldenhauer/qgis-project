"""
Executor entry point — runs inside the QGIS-bundled Python.

SubprocessProject injects qgis_project into PYTHONPATH before launching
this script, so the full qgis_project API is available here.
The spec JSON carries the layer/operation/state data; this script simply
reconstructs the objects and delegates to Project — no duplicated logic.

Usage (internal):
    python-qgis.bat _executor.py spec.json
"""

import json
import sys


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: _executor.py <spec.json>")

    with open(sys.argv[1]) as f:
        spec = json.load(f)

    from qgis_project import Project
    from qgis_project._spec import _layer_from_dict

    action = spec["action"]
    output = spec["output"]

    proj = Project(crs=spec.get("crs"))

    for layer_dict in spec.get("layers", []):
        proj.add_layer(_layer_from_dict(layer_dict))

    for op in spec.get("operations", []):
        proj.process(
            op["algorithm"],
            op["params"],
            name=op.get("name", ""),
            group=op.get("group"),
            visible=op.get("visible", True),
        )

    for state in spec.get("group_states", []):
        path = state.get("path")
        expanded = state["expanded"]
        if path is None:
            proj.expand_all() if expanded else proj.collapse_all()
        else:
            proj.expand_group(*path) if expanded else proj.collapse_group(*path)

    if action == "save":
        proj.save(output)
    elif action in ("open", "save_and_open"):
        proj.open(output)

    proj.exit()


if __name__ == "__main__":
    main()
