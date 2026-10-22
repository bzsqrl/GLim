"""Per-shader settings stored next to the shader as <name>.ffmaker.json.

{
  "plugin_name": "My Shader",
  "channels": {"iChannel1": "rock.jpg", "iChannel2": "noise"},
  "params": {
     "glow":  {"expose": true, "label": "Glow", "min": 0, "max": 4, "default": 1.5},
     "speed": {"default": 0.5}            # synthetic params are keyed by kind
  }
}
"""
import json
import os

SUFFIX = ".ffmaker.json"


def path_for(shader_path):
    return os.path.splitext(shader_path)[0] + SUFFIX


def load(shader_path):
    if not shader_path:
        return {}
    p = path_for(shader_path)
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save(shader_path, data):
    # Drop empty sections so the file stays readable.
    clean = {k: v for k, v in data.items() if v not in (None, "", {}, [])}
    p = path_for(shader_path)
    if not clean:
        if os.path.isfile(p):
            os.remove(p)
        return None
    with open(p, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
    return p


def param_key(p):
    return p.name or p.kind


def excluded_constants(settings):
    """Promoted constants the user chose not to expose (they stay constants)."""
    return {k for k, v in settings.get("params", {}).items() if v.get("expose") is False}


def apply(ir, settings):
    """Apply label/range/default/visibility overrides to a converted ShaderIR."""
    overrides = settings.get("params", {})
    for p in ir.params:
        if p.source_default is None:
            p.source_default = list(p.default) if isinstance(p.default, (list, tuple)) else p.default
        ov = overrides.get(param_key(p))
        if not ov:
            continue
        if ov.get("label"):
            p.label = str(ov["label"])
        if p.kind in ("float", "int", "speed"):
            if ov.get("min") is not None:
                p.min = float(ov["min"])
            if ov.get("max") is not None:
                p.max = float(ov["max"])
            if p.min > p.max:
                p.min, p.max = p.max, p.min
        if "default" in ov and ov["default"] is not None:
            p.default = _coerce(p, ov["default"])
            if p.kind in ("float", "int", "speed"):
                p.min = min(p.min, p.default)
                p.max = max(p.max, p.default)
        if ov.get("expose") is False and p.origin not in ("const", "define"):
            p.hidden = True
    return ir


def _coerce(p, v):
    try:
        if p.kind in ("float", "speed"):
            return float(v)
        if p.kind in ("int", "long"):
            return int(v)
        if p.kind in ("bool", "event", "mouseclick"):
            return bool(v)
        if p.kind in ("color",):
            return [float(x) for x in v][:4]
        if p.kind in ("point2D", "mouse"):
            return [float(x) for x in v][:2]
    except (TypeError, ValueError):
        pass
    return p.default
