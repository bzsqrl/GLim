import json
import re

def export_to_isf(shader_data, plugin_name="Exported ISF"):
    """
    Converts Shadertoy or ISF data back into a canonical ISF .fs file.
    Takes shader_data (dict) as returned by parser.parse_isf or parser.parse_shadertoy.
    """
    inputs = shader_data.get("inputs", [])
    code = shader_data.get("code", "")
    
    # -- 1. Prepare ISF Header -----------------------------------------------
    isf_inputs = []
    swizzle_shims = []
    
    # We only include non-builtin inputs in the ISF header.
    for inp in inputs:
        if inp.get("_builtin"):
            continue
        
        name = inp["NAME"]
        t = inp.get("TYPE", "float")
        
        # Normalise types for ISF
        isf_type = t
        actual_name = name
        if t == "point2D":
            isf_type = "point2D"
        elif t == "color":
            isf_type = "color"
            # ISF color is vec4, but Shadertoy const vec3 extraction expects vec3.
            # We rename the uniform to avoid collision and shim it back as vec3.
            actual_name = name + "_isf"
            swizzle_shims.append(f"#define {name} ({actual_name}.rgb)")
        elif t in ("bool", "boolean"):
            isf_type = "bool"
            
        entry = {
            "NAME": actual_name,
            "TYPE": isf_type,
            "DEFAULT": inp.get("DEFAULT", 0.5)
        }
        
        # Add MIN/MAX if available
        if "MIN" in inp:
            entry["MIN"] = inp["MIN"]
        if "MAX" in inp:
            entry["MAX"] = inp["MAX"]
        
        # Special case: add sensible MIN/MAX for 'speed' if missing
        if name.lower() == "speed":
            if "MIN" not in entry: entry["MIN"] = 0.1
            if "MAX" not in entry: entry["MAX"] = 4.0
        
        isf_inputs.append(entry)
        
    # Detect if we need image inputs (e.g. for Shadertoy textures)
    has_textures = any(name.startswith("iChannel") for name in [inp["NAME"] for inp in inputs])
    if has_textures and not any(inp["TYPE"] == "image" for i in isf_inputs):
        # Add a default image input if Shadertoy textures are used
        isf_inputs.insert(0, {
            "NAME": "inputImage",
            "TYPE": "image"
        })

    meta = shader_data.get("meta", {})
    categories = meta.get("categories", ["Generator"])
    if has_textures and "Filter" not in categories:
        categories.append("Filter")

    header = {
        "DESCRIPTION": meta.get("description", plugin_name),
        "CREDIT": meta.get("credit", "FFMaker Export"),
        "CATEGORIES": categories,
        "INPUTS": isf_inputs
    }
    
    # -- 2. Process Shader Body ----------------------------------------------
    # Strip const declarations that were promoted to uniforms
    for inp in inputs:
        if inp.get("_source") == "const_extract":
            decl = inp.get("_const_decl", "")
            if decl and decl in code:
                code = code.replace(
                    decl,
                    f"// [FFMaker] '{inp['NAME']}' promoted to ISF input",
                    1
                )
    
    # -- 3. Assemble Final File ----------------------------------------------
    # ISF header is wrapped in /*{ ... }*/
    json_str = json.dumps(header, indent=4)
    
    # Detect speed parameter name (case-insensitive)
    speed_name = next((i["NAME"] for i in inputs if i["NAME"].lower() == "speed"), None)

    # Shadertoy-compatibility shims
    texture_shims = ""
    if has_textures:
        texture_shims = """
#define iChannel0 inputImage
#define iChannel1 inputImage
#define iChannel2 inputImage
#define iChannel3 inputImage
"""

    shims = f"""
// <FFMAKER_ISF_SHIMS>
// Shadertoy -> ISF Compatibility Shims
vec3  iResolution;
float iTime;
float iGlobalTime;
vec4  iMouse;
vec4  iDate;
float iSampleRate;
int   iFrame;
{texture_shims}
// </FFMAKER_ISF_SHIMS>
{chr(10).join(swizzle_shims)}"""

    # Prepare assignments (with optional speed scaling)
    # Use mod(TIME, 1000.0) to prevent precision loss (shaking/jittering) at large time values.
    assign_time = "mod(TIME, 1000.0)"
    assigns = f"    iResolution = vec3(RENDERSIZE, 1.0);\n    iTime = {assign_time}"
    if speed_name:
        assigns += f" * {speed_name}"
    assigns += ";\n    iGlobalTime = iTime;\n"
    assigns += "    iMouse = vec4(0.0);\n    iDate = vec4(2026.0, 5.0, 13.0, iTime);\n"
    assigns += "    iSampleRate = 44100.0;\n    iFrame = 0;\n"

    # Check if we need to map void mainImage() -> void main()
    footer = ""
    undefs = "#undef TIME\n#undef RENDERSIZE\n#undef iTime\n#undef iGlobalTime\n#undef iResolution\n#undef iMouse\n#undef iDate\n#undef iSampleRate\n#undef iFrame\n"
    if "mainImage" in code and not re.search(r'\bvoid\s+main\s*\(', code):
        footer = f"\n\n// <FFMAKER_ISF_SHIMS>\n{undefs}void main(void) {{\n{assigns}    mainImage(gl_FragColor, gl_FragCoord.xy);\n}}\n// </FFMAKER_ISF_SHIMS>\n"
    else:
        # If we injected into an existing main, we wrap the injected part
        code = re.sub(
            r'(\bvoid\s+main\s*\(\s*(?:void)?\s*\)\s*\{)',
            rf'\1\n// <FFMAKER_ISF_SHIMS>\n{undefs}{assigns}// </FFMAKER_ISF_SHIMS>\n',
            code,
            count=1
        )

    # -- Final Cleanup: Convert 'const' or global aliases to '#define' --------
    # If we keep them as globals, they won't update when uniforms change.
    # We target 'const type name = ...' AND 'type name = ...' if it uses built-ins.
    builtins_pat = r'\b(iTime|iGlobalTime|iResolution|iMouse|iDate|iFrame|TIME|RENDERSIZE)\b'
    def global_to_macro(m):
        qual, t, n, v = m.group(1), m.group(2), m.group(3), m.group(4)
        qual = qual or ""
        
        is_const = "const" in qual
        uses_builtins = re.search(builtins_pat, v)
        
        # We always convert 'const' globals to macros to ensure they can be replaced by uniforms.
        # For non-const globals, we only convert them if they depend on Shadertoy built-ins,
        # which indicates they are intended to be dynamic. This avoids breaking mutable
        # globals (l-values) like 'vec2 g_pos = vec2(0);' which are common in Shadertoy.
        if is_const or uses_builtins:
            return f"#define {n} ({v}) // [FFMaker] dynamic global"
        return m.group(0)

    # Match: [const] <type> <name> = <value>;
    # We only match if it starts at the beginning of the line (no indentation)
    # to avoid incorrectly converting local variables inside functions.
    code = re.sub(
        r'^(const\s+)?([a-z0-9]+)\s+([a-zA-Z0-9_]+)\s*=\s*([^;]+);',
        global_to_macro,
        code,
        flags=re.MULTILINE
    )

    # Remove 'const' from local variables (any line with indentation).
    # This prevents 'non constant expression in initialization' errors when a local
    # variable depends on a macro-replaced uniform.
    code = re.sub(r'^(\s+)const\b', r'\1', code, flags=re.MULTILINE)

    full_output = f"/*{json_str}*/\n\n{shims}\n\n{code}{footer}"
    
    return full_output
