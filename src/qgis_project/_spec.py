"""
Serialization of Project specs to JSON and YAML.

JSON is the wire format used between SubprocessProject and _executor.py
because it is always available in the Python stdlib. YAML support is
provided as an optional human-readable alternative (requires pyyaml).

Both formats represent the same dict structure:

    {
      "action": "save" | "open" | "save_and_open",
      "output": "/path/to/output.qgz",
      "layers": [
        {
          "type": "Layer" | "RasterLayer",
          "file": "...",
          "name": "...",
          "group": null | "grp" | ["parent", "child"],
          "visible": true,
          "crs": null,
          "overwrite_existing": false
        },
        {
          "type": "RasterLayer",
          ...,
          "band_idx": 1,
          "style": {
            "type": "RasterStyleBW",
            "vmin": 0.0,
            "vmax": 3000.0,
            "opacity": 1.0
          }
        }
      ]
    }
"""

from __future__ import annotations

import dataclasses
import json


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _layer_to_dict(layer) -> dict:
    d = dataclasses.asdict(layer)
    d["type"] = type(layer).__name__
    if "style" in d and d["style"] is not None:
        d["style"]["type"] = type(layer.style).__name__
    return d


def _layer_from_dict(d: dict):
    from .layer import Layer, RasterLayer
    from .style import RasterStyle, RasterStyleBW, RasterStyleSinglePseudocolor, RasterStyleMultiPseudocolor

    _style_types = {
        "RasterStyle": RasterStyle,
        "RasterStyleBW": RasterStyleBW,
        "RasterStyleSinglePseudocolor": RasterStyleSinglePseudocolor,
        "RasterStyleMultiPseudocolor": RasterStyleMultiPseudocolor,
    }

    d = dict(d)
    layer_type = d.pop("type")

    if "style" in d and d["style"] is not None:
        style_d = dict(d["style"])
        style_type = style_d.pop("type")
        d["style"] = _style_types[style_type](**style_d)

    if layer_type == "Layer":
        return Layer(**d)
    if layer_type == "RasterLayer":
        return RasterLayer(**d)
    raise ValueError(f"Unknown layer type: {layer_type!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def to_dict(layers: list, output: str, action: str = "save") -> dict:
    """Serialize a layer list + output path to a plain dict."""
    return {
        "action": action,
        "output": str(output),
        "layers": [_layer_to_dict(layer) for layer in layers],
    }


def from_dict(d: dict) -> tuple[list, str, str]:
    """Deserialize a spec dict back to (layers, output, action)."""
    layers = [_layer_from_dict(ld) for ld in d["layers"]]
    return layers, d["output"], d["action"]


# --- JSON (wire format, always available) ---

def to_json(layers: list, output: str, action: str = "save") -> str:
    return json.dumps(to_dict(layers, output, action), indent=2)


def from_json(s: str) -> tuple[list, str, str]:
    return from_dict(json.loads(s))


def save_json(layers: list, output: str, path: str, action: str = "save") -> None:
    """Write a JSON spec file to *path*."""
    with open(path, "w") as f:
        f.write(to_json(layers, output, action))


def load_json(path: str) -> tuple[list, str, str]:
    with open(path) as f:
        return from_json(f.read())


# --- YAML (human-readable, requires pyyaml) ---

def to_yaml(layers: list, output: str, action: str = "save") -> str:
    import yaml
    return yaml.dump(
        to_dict(layers, output, action),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def from_yaml(s: str) -> tuple[list, str, str]:
    import yaml
    return from_dict(yaml.safe_load(s))


def save_yaml(layers: list, output: str, path: str, action: str = "save") -> None:
    """Write a YAML spec file to *path*."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_yaml(layers, output, action))


def load_yaml(path: str) -> tuple[list, str, str]:
    with open(path, encoding="utf-8") as f:
        return from_yaml(f.read())
