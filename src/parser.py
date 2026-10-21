import re
import json

# ISF input types we know how to handle downstream in builder.py
SUPPORTED_TYPES = {"float", "bool", "boolean", "event", "color", "point2D", "long"}

# Built-in Shadertoy uniforms that should not become ISF user params.
# We map these to their actual GLSL types so the builder can declare them correctly.
_BUILTIN_SHADERTOY = {
    "iTime":        "float",
    "iGlobalTime":  "float",
    "iResolution":  "vec3",
    "iTimeDelta":   "float",
    "iFrame":       "int",
    "iMouse":       "vec4",
    "iDate":        "vec4",
    "iSampleRate":  "float",
    "iChannel0":    "sampler2D",
    "iChannel1":    "sampler2D",
    "iChannel2":    "sampler2D",
    "iChannel3":    "sampler2D",
}


def parse_code(code: str, fmt: str, extract_params: bool = True) -> dict:
    """Top-level dispatcher: route by format selector."""
    code = code.lstrip('\ufeff')
    if fmt in ("ISF (.fs)", "ISF FX"):
        return parse_isf(code)
    elif fmt == "GLSL Sandbox":
        return parse_glslsandbox(code, extract_params)
    else:
        return parse_shadertoy(code, extract_params)


def parse_glslsandbox(code: str, extract_params: bool = True) -> dict:
    """
    Translates GLSL Sandbox format into Shadertoy format and then runs the Shadertoy parser.
    """
    # Remove standard explicit uniforms
    code = re.sub(r'uniform\s+float\s+time\s*;', '', code)
    code = re.sub(r'uniform\s+vec2\s+mouse\s*;', '', code)
    code = re.sub(r'uniform\s+vec2\s+resolution\s*;', '', code)
    
    # Map variable usages
    code = re.sub(r'\btime\b', 'iTime', code)
    code = re.sub(r'\bmouse\b', 'iMouse.xy', code)
    code = re.sub(r'\bresolution\b', 'iResolution.xy', code)
    
    # Map built-in variables
    code = code.replace("gl_FragCoord", "vec4(fragCoord, 0.0, 1.0)")
    code = code.replace("gl_FragColor", "fragColor")
    
    # Map main entry point
    code = re.sub(
        r'\bvoid\s+main\s*\(\s*(?:void)?\s*\)',
        "void mainImage(out vec4 fragColor, in vec2 fragCoord)",
        code,
        count=1
    )
    
    # Forward the translated code to the shadertoy parser
    return parse_shadertoy(code, extract_params)


def _sanitize_json(json_str):
    """
    Remove trailing commas from JSON strings. 
    Skips over quoted strings to avoid corrupting data.
    """
    # Group 1: Matches double-quoted strings (handling escaped quotes)
    # Group 2: Matches trailing commas before a closing bracket or brace
    pattern = r'("(?:\\.|[^"\\])*")|(,\s*[\]}])'
    
    def replace(match):
        if match.group(1):
            return match.group(1) # Return the string as is
        else:
            return match.group(2)[1:] # Return everything but the comma (the closing bracket/brace)
            
    return re.sub(pattern, replace, json_str, flags=re.DOTALL)


def parse_isf(code: str) -> dict:
    """
    Extract and parse the ISF JSON header ( /*{ ... }*/ ) from the shader source.
    Returns a dict with:
      - 'inputs': list of sanitised input descriptors
      - 'code':   original source string
      - 'error':  only present on failure
      - 'warnings': list of non-fatal issues the builder should surface
    """
    match = re.search(r'/\*\s*\{(.*?)\}\s*\*/', code, re.DOTALL)
    if not match:
        return {"error": "No ISF JSON header found. Make sure the code contains /*{ ... }*/ (with or without spaces)",
                "inputs": [], "code": code}

    json_str = "{" + match.group(1) + "}"
    json_str = _sanitize_json(json_str)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse ISF JSON: {e}", "inputs": [], "code": code}

    is_ffmaker_export = data.get("CREDIT") == "FFMaker Export"

    # ── Multi-pass guard ──────────────────────────────────────────────────────
    # ISF PASSES with more than one entry (or any persistent buffer) require
    # render-to-texture between passes, which FFGL does not support natively.
    # Attempting to inject this into a single-pass FFGL wrapper would produce
    # undefined behaviour at best and a crash at worst.
    passes = data.get("PASSES", [])
    if len(passes) > 1:
        pass_names = [p.get("TARGET", "(unnamed)") for p in passes]
        return {
            "error": (
                f"Multi-pass ISF shaders cannot be converted to FFGL.\n"
                f"This shader has {len(passes)} passes: {', '.join(pass_names)}.\n\n"
                f"To use this effect in Resolume, load the .fs file directly via "
                f"the ISF source plugin, or flatten it into a single-pass shader first."
            ),
            "inputs": [],
            "code": code,
        }

    # ── Single-pass ISF built-in detection ───────────────────────────────────
    # Record which ISF macros appear so the builder can substitute them.
    _ISF_BUILTINS = {
        # NOTE: isf_FragNormCoord is the ISF normalized frag coordinate (vec2, 0-1).
        # After conversion, mainImage receives 'fragCoord' in pixel space. To get
        # the 0-1 equivalent we must use fragCoord/iResolution.xy. We handle this
        # as a regex substitution in the builder rather than a simple word replace.
        "isf_FragNormCoord": "(gl_FragCoord.xy / iResolution.xy)",  # normalised 0-1 frag coord (built-in, works in helpers)
        "vv_FragNormCoord":  "(gl_FragCoord.xy / iResolution.xy)",  # VIDVOX alias
        "RENDERSIZE":        "iResolution.xy",                 # viewport size vec2
        "TIME":              "iTime",                          # current time in seconds
        "TIMEDELTA":         "iTimeDelta",                     # frame delta time
        "FRAMEINDEX":        "iFrame",                         # frame counter
        "gl_FragColor":      "fragColor",                      # old-style output
        # NOTE: IMG_THIS_PIXEL, IMG_NORM_PIXEL, IMG_PIXEL are intentionally NOT here.
        # They require MaxUV-aware regex expansion in builder.py and must NOT be
        # word-substituted first (which would strip the macro arguments and bypass MaxUV).
    }
    warnings = []
    isf_subs = {}   # name -> replacement (None = unsupported)
    for macro, sub in _ISF_BUILTINS.items():
        if macro in code:
            isf_subs[macro] = sub
            if sub is None:
                warnings.append(
                    f"ISF macro '{macro}' has no FFGL equivalent and will remain "
                    f"in the shader. This will cause a compile error."
                )

    # -- IMAGE input guard ----------------------------------------------------
    sanitised_inputs = _sanitise_inputs(data.get("INPUTS", []))
    
    # ── Built-in Uniform Injection for ISF ──────────────────────────────────
    # iResolution and iTime are always needed since:
    #  - RENDERSIZE -> iResolution.xy
    #  - TIME       -> iTime
    #  - gl_FragCoord is converted to pixel coords which use iResolution
    # Always inject them for ISF shaders regardless of whether they appear literally.
    already_injected = set()
    for builtin_name, builtin_type in [("iResolution", "vec3"), ("iTime", "float")]:
        if not any(i.get("NAME") == builtin_name for i in sanitised_inputs):
            sanitised_inputs.append({
                "NAME": builtin_name,
                "TYPE": builtin_type,
                "DEFAULT": 0.0,
                "_builtin": True
            })
            already_injected.add(builtin_name)

    for macro, sub in isf_subs.items():
        if sub in _BUILTIN_SHADERTOY and sub not in already_injected:
            if not any(i.get("NAME") == sub for i in sanitised_inputs):
                # Add to sanitised_inputs so builder.py sees it and declares the uniform
                sanitised_inputs.append({
                    "NAME": sub,
                    "TYPE": _BUILTIN_SHADERTOY[sub],
                    "DEFAULT": 0.0,
                    "_builtin": True
                })

    # Detect if this is an ISF Effect (FX) shader.
    # FX shaders process an input image rather than generating one from scratch.
    # Indicators: any input of TYPE "image", OR categories containing "Filter" / "Transition".
    categories_lower = [c.lower() for c in data.get("CATEGORIES", [])]
    raw_inputs = data.get("INPUTS", [])
    swizzle_map = {}
    for inp in raw_inputs:
        name = inp.get("NAME", "")
        if name.endswith("_isf") and inp.get("TYPE", "").lower() == "color":
            base_name = name[:-4]
            swizzle_map[base_name] = name

    image_input_names = [inp["NAME"] for inp in raw_inputs if inp.get("TYPE", "").lower() == "image"]
    has_image_inputs  = len(image_input_names) > 0
    is_filter_category = any(c in categories_lower for c in ("filter", "transition", "distortion", "blur", "stylize", "color effect"))
    is_fx = has_image_inputs or is_filter_category

    if len(image_input_names) > 1:
        warnings.append(
            f"This shader has {len(image_input_names)} image inputs "
            f"({', '.join(image_input_names)}). FFGL supports only one input texture. "
            f"The first image input ('{image_input_names[0]}') will be mapped to the host "
            f"texture; remaining image inputs will not receive data."
        )

    return {
        "inputs":             sanitised_inputs,
        "code":               code,
        "isf_subs":           isf_subs,
        "warnings":           warnings,
        "is_fx":              is_fx,
        "image_input_names":  image_input_names,  # names to remap to inputTexture in builder
        "is_ffmaker_export":  is_ffmaker_export,
        "swizzle_map":        swizzle_map,
        "meta": {
            "description": data.get("DESCRIPTION", ""),
            "categories":  data.get("CATEGORIES", []),
            "credit":      data.get("CREDIT", ""),
        }
    }


# Maximum number of const-extracted params in Shadertoy mode.
# Setting this high effectively removes the previous cap of 8.
_SHADERTOY_MAX_PARAMS = 128


def parse_shadertoy(code: str, extract_params: bool = True) -> dict:
    """
    Shadertoy shaders carry built-in uniforms (iTime, iResolution...) and often
    define magic numbers as top-level `const` variables.

    This function:
      1. Notes which built-in uniforms are referenced (informational -- builder skips them).
      2. Extracts up to _SHADERTOY_MAX_PARAMS `const float/bool` declarations,
         always placing a Speed/speed param first if found.
    """
    inputs        = []
    registered    = set()

    # -- 1. Detect referenced built-ins (informational, builder skips them) ---
    for name, glsl_type in _BUILTIN_SHADERTOY.items():
        # We always register iResolution and iTime because the FFMaker wrapper explicitly uses them
        if name in code or name in ("iResolution", "iTime"):
            inputs.append({"NAME": name, "TYPE": glsl_type, "DEFAULT": 0.0, "_builtin": True})
            registered.add(name)

    # Convert old glslsandbox / early shadertoy main() to mainImage
    if "mainImage" not in code and re.search(r'\bvoid\s+main\s*\(', code):
        code = re.sub(
            r'\bvoid\s+main\s*\(\s*(?:void)?\s*\)',
            "void mainImage(out vec4 fragColor, in vec2 fragCoord)",
            code,
            count=1
        )
        code = code.replace("gl_FragColor", "fragColor")
        code = code.replace("gl_FragCoord", "vec4(fragCoord, 0.0, 1.0)")
        
    # Map legacy Shadertoy time variable to standard iTime
    code = code.replace("iGlobalTime", "iTime")

    # -- 2. Scan for const float / bool declarations -------------------------
    _CONST_RE = re.compile(
        r'\bconst\s+(float|bool|vec2|vec3)\s+([A-Za-z_]\w*)\s*=\s*([^;]+?)\s*;',
        re.MULTILINE,
    )

    candidates  = []   # all extracted, before limit applied
    speed_entry = None

    for m in _CONST_RE.finditer(code):
        glsl_type = m.group(1)
        name      = m.group(2)
        value_str = m.group(3).strip()

        if name in registered:
            continue
        registered.add(name)

        entry = {
            "NAME":        name,
            "TYPE":        glsl_type,
            "_source":     "const_extract",
            "_const_decl": m.group(0),
        }

        # Filter out common mathematical constants to prevent them from becoming UI sliders
        if name.lower() in ("pi", "e", "tau", "phi", "epsilon", "half_pi", "two_pi"):
            continue

        if glsl_type == "float":
            try:
                # If it's a simple number, parse it
                default = float(value_str.rstrip("fF"))
            except ValueError:
                # If it's an expression like 'float(glyphSize)' or '1.0 / 3.0', we can't easily
                # eval it safely in python. Skip extracting complex expressions to avoid
                # corrupting the shader logic with an incorrect fallback default of 0.5.
                continue
            entry["DEFAULT"] = default

            # Compute the linear scale so that FFGL param value 0.5 -> default.
            if default == 0.0:
                scale  = 2.0
                offset = -1.0  # slider midpoint (0.5) gives 0
                entry["MIN"] = -1.0
                entry["MAX"] = 1.0
            else:
                scale  = 2.0 * abs(default)
                offset = default - 0.5 * scale   # = 0 when default > 0
                # Create a range centered on default: [D - |D|, D + |D|]
                entry["MIN"] = default - abs(default)
                entry["MAX"] = default + abs(default)

            entry["_scale"]  = scale
            entry["_offset"] = offset

        elif glsl_type == "bool":
            entry["DEFAULT"] = value_str.lower() in ("true", "1")

        elif glsl_type == "vec3":
            entry["TYPE"] = "color"
            val_clean = value_str.replace('vec3', '').strip('() ')
            parts = [p.strip().rstrip("fF") for p in val_clean.split(',')]
            try:
                dr = float(parts[0])
                dg = float(parts[1]) if len(parts) > 1 else dr
                db = float(parts[2]) if len(parts) > 2 else dg
            except (ValueError, IndexError):
                dr, dg, db = 0.5, 0.5, 0.5
            entry["DEFAULT"] = [dr, dg, db]

        elif glsl_type == "vec2":
            entry["TYPE"] = "point2D"
            val_clean = value_str.replace('vec2', '').strip('() ')
            parts = [p.strip().rstrip("fF") for p in val_clean.split(',')]
            try:
                dx = float(parts[0])
                dy = float(parts[1]) if len(parts) > 1 else dx
            except (ValueError, IndexError):
                dx, dy = 0.5, 0.5
            
            entry["DEFAULT"] = [dx, dy]
            scales, offsets = [], []
            for d in (dx, dy):
                if d == 0.0:
                    scales.append(1.0)
                    offsets.append(-0.5)
                else:
                    s = 2.0 * abs(d)
                    scales.append(s)
                    offsets.append(d - 0.5 * s)
            entry["_scale"] = scales
            entry["_offset"] = offsets

        # Keep Speed-named params aside for priority insertion
        if name.lower() == "speed":
            speed_entry = entry
        else:
            candidates.append(entry)

    # -- 3. Apply 4-param cap, Speed always first ----------------------------
    ordered = []
    remaining_slots = _SHADERTOY_MAX_PARAMS

    if speed_entry:
        ordered.append(speed_entry)
        remaining_slots -= 1
    elif not speed_entry:
        # No Speed found -- synthesize a canonical one using iTime scaling.
        # We'll inject a uniform float Speed_p that scales iTime in the wrapper.
        # This is a no-op in the shader body itself; builder will handle it.
        ordered.append({
            "NAME":        "Speed",
            "TYPE":        "float",
            "DEFAULT":     1.0,
            "MIN":         0.1,
            "MAX":         4.0,
            "_source":     "const_extract_synthetic",
            "_scale":      4.0,
            "_offset":     0.0,
        })
        remaining_slots -= 1

    # Fill remaining slots from candidates (floats before bools, preserving order)
    if extract_params:
        float_candidates = [c for c in candidates if c["TYPE"] == "float"]
        bool_candidates  = [c for c in candidates if c["TYPE"] == "bool"]
        color_candidates = [c for c in candidates if c["TYPE"] == "color"]
        point_candidates = [c for c in candidates if c["TYPE"] == "point2D"]
        for c in float_candidates + bool_candidates + color_candidates + point_candidates:
            if remaining_slots <= 0:
                break
            ordered.append(c)
            remaining_slots -= 1

    inputs += ordered
    n_extracted = len(ordered)
    return {
        "inputs":  inputs,
        "code":    code,
        "_stats":  {"const_extracted": n_extracted},
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _sanitise_inputs(inputs: list) -> list:
    """
    Walk raw ISF INPUTS and normalise each entry to a consistent shape.
    Ensures all keys expected by builder.py are present with sane defaults.
    Unknown types are retained as-is so the builder can silently skip them.
    """
    sanitised = []
    for inp in inputs:
        name = inp.get("NAME", "").strip()
        t    = inp.get("TYPE", "float").strip().lower()

        if not name:
            continue  # skip unnamed inputs

        entry = {"NAME": name, "TYPE": t}

        if t == "float":
            entry["DEFAULT"] = float(inp.get("DEFAULT", 0.5))
            mn = inp.get("MIN")
            mx = inp.get("MAX")
            if mn is not None:
                entry["MIN"] = float(mn)
            if mx is not None:
                entry["MAX"] = float(mx)

        elif t in ("bool", "boolean"):
            entry["TYPE"]    = "bool"  # normalise "boolean" → "bool"
            entry["DEFAULT"] = bool(inp.get("DEFAULT", False))

        elif t == "event":
            pass  # no default needed

        elif t == "color":
            raw = inp.get("DEFAULT", [1.0, 1.0, 1.0, 1.0])
            if isinstance(raw, (list, tuple)):
                # Pad/truncate to 4 channels
                raw = list(raw) + [1.0] * 4
                entry["DEFAULT"] = [float(c) for c in raw[:4]]
            else:
                entry["DEFAULT"] = [1.0, 1.0, 1.0, 1.0]

        elif t == "point2d":
            entry["TYPE"] = "point2D"  # normalise casing
            raw = inp.get("DEFAULT", [0.5, 0.5])
            if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                entry["DEFAULT"] = [float(raw[0]), float(raw[1])]
            else:
                entry["DEFAULT"] = [0.5, 0.5]

        elif t == "long":
            entry["LABELS"]  = [str(l) for l in inp.get("LABELS",  [])]
            entry["VALUES"]  = [int(v) for v in inp.get("VALUES",   [])]
            entry["DEFAULT"] = int(inp.get("DEFAULT", 0))

        else:
            # Unsupported — pass through; builder.py will skip it
            entry.update({k: v for k, v in inp.items() if k not in ("NAME", "TYPE")})

        sanitised.append(entry)

    return sanitised
