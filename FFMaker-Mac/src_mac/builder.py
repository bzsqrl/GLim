import os
import shutil
import subprocess
from paths import get_external_path

# ISF/Shadertoy built-ins that map to FFGL host uniforms.
_BUILTIN_UNIFORMS = {
    "iResolution", "iTime", "iTimeDelta", "iFrame",
    "iMouse", "iDate", "iSampleRate",
    "iChannel0", "iChannel1", "iChannel2", "iChannel3",
    "iGlobalTime"
}

def _format_float(v):
    return f"{float(v):.6f}f"

def _build_uniforms_and_params(inputs, shader_data):
    uniforms_str    = ""
    deferred_macros = ""
    add_params_str  = ""
    main_assigns_str= ""
    speed_name = None
    should_scale_time = False

    for inp in inputs:
        n = inp.get("NAME", "")
        if n.lower() == "speed":
            speed_name = n
            source = inp.get("_source", "")
            if source == "const_extract_synthetic" or "isf_subs" not in shader_data:
                should_scale_time = True
            break

    for inp in inputs:
        name = inp.get("NAME", "")
        t    = inp.get("TYPE", "float")
        is_builtin = inp.get("_builtin", False)

        if is_builtin or name in _BUILTIN_UNIFORMS:
            if name in ("iTime", "iGlobalTime"):
                if "uniform float fTime;" not in uniforms_str:
                    uniforms_str += "uniform float fTime;\n"
                if should_scale_time and speed_name:
                    deferred_macros += f"#define {name} (fTime * {speed_name})\n"
                else:
                    deferred_macros += f"#define {name} fTime\n"
            else:
                uniforms_str += f"uniform {t} {name};\n"
            continue

        if t == "float":
            default = inp.get("DEFAULT", 0.5)
            mn      = inp.get("MIN",     None)
            mx      = inp.get("MAX",     None)
            source  = inp.get("_source", "")
            is_const = source in ("const_extract", "const_extract_synthetic")

            if is_const:
                scale      = inp.get("_scale",  2.0 * abs(default) if default != 0 else 1.0)
                offset     = inp.get("_offset", 0.0)
                param_name = f"{name}_p"
                uniforms_str += f"uniform float {param_name};\n"
                uniforms_str += f"float {name};\n"
                if offset == 0.0:
                    main_assigns_str += f"    {name} = {param_name} * {scale:.6f};\n"
                else:
                    main_assigns_str += f"    {name} = {offset:.6f} + {param_name} * {scale:.6f};\n"
                add_params_str += f'    AddParam( Param::Create( "{param_name}", 0.500000f ) );\n'
            elif mn is not None and mx is not None:
                uniforms_str   += f"uniform float {name};\n"
                add_params_str += f'    AddParam( ParamRange::Create( "{name}", {_format_float(default)}, ParamRange::Range( {_format_float(mn)}, {_format_float(mx)} ) ) );\n'
            else:
                uniforms_str   += f"uniform float {name};\n"
                add_params_str += f'    AddParam( Param::Create( "{name}", {_format_float(default)} ) );\n'
        elif t in ("bool", "boolean"):
            default = inp.get("DEFAULT", False)
            default_cpp = "true" if default else "false"
            uniforms_str   += f"uniform bool {name};\n"
            add_params_str += f'    AddParam( ParamBool::Create( "{name}", {default_cpp} ) );\n'
        elif t == "event":
            uniforms_str   += f"uniform bool {name};\n"
            add_params_str += f'    AddParam( ParamEvent::Create( "{name}" ) );\n'
        elif t == "color":
            source = inp.get("_source", "")
            if source in ("const_extract", "const_extract_synthetic"):
                param_name = f"{name}_p"
                uniforms_str += f"uniform vec4 {param_name};\n"
                uniforms_str += f"vec3 {name};\n"
                main_assigns_str += f"    {name} = {param_name}.rgb;\n"
                add_params_str += f'    AddHueColorParam( "{param_name}" );\n'
            else:
                uniforms_str   += f"uniform vec4 {name};\n"
                add_params_str += f'    AddHueColorParam( "{name}" );\n'
        elif t == "point2D":
            default = inp.get("DEFAULT", [0.5, 0.5])
            if not isinstance(default, (list, tuple)) or len(default) < 2:
                default = [0.5, 0.5]
            dx, dy = default[0], default[1]
            source = inp.get("_source", "")
            is_const = source in ("const_extract", "const_extract_synthetic")
            param_x = f"{name}_X_p" if is_const else f"{name}_X"
            param_y = f"{name}_Y_p" if is_const else f"{name}_Y"
            uniforms_str += f"uniform float {param_x};\n"
            uniforms_str += f"uniform float {param_y};\n"
            if is_const:
                uniforms_str += f"vec2 {name};\n"
                scale = inp.get("_scale", [1.0, 1.0])
                offset = inp.get("_offset", [0.0, 0.0])
                ox, oy = offset[0], offset[1]
                sx, sy = scale[0], scale[1]
                vx = f"{param_x} * {sx:.6f}" if ox == 0.0 else f"{ox:.6f} + {param_x} * {sx:.6f}"
                vy = f"{param_y} * {sy:.6f}" if oy == 0.0 else f"{oy:.6f} + {param_y} * {sy:.6f}"
                main_assigns_str += f"    {name} = vec2({vx}, {vy});\n"
                add_params_str += f'    AddParam( Param::Create( "{param_x}", 0.500000f ) );\n'
                add_params_str += f'    AddParam( Param::Create( "{param_y}", 0.500000f ) );\n'
            else:
                uniforms_str += f"#define {name} vec2({param_x}, {param_y})\n"
                add_params_str += f'    AddParam( Param::Create( "{param_x}", {_format_float(dx)} ) );\n'
                add_params_str += f'    AddParam( Param::Create( "{param_y}", {_format_float(dy)} ) );\n'
        elif t == "long":
            labels  = inp.get("LABELS", [])
            values  = inp.get("VALUES", list(range(len(labels))))
            default = inp.get("DEFAULT", 0)
            try:
                default_index = values.index(default)
            except ValueError:
                default_index = 0
            if not labels:
                labels = [f"Option {i}" for i in range(len(values))]
            if not values:
                values = list(range(len(labels)))
            uniforms_str   += f"uniform float {name};\n"
            options_list = ", ".join(f'{{"{lbl}", {float(val):.1f}f}}' for lbl, val in zip(labels, values))
            add_params_str += f'    AddParam( ParamOption::Create( "{name}", {{ {options_list} }}, {default_index} ) );\n'

    return uniforms_str + deferred_macros, add_params_str, main_assigns_str

def _run_cancellable(cmd, cwd, cancel_event):
    import subprocess, tempfile, os, time
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as f:
        log_file = f.name
    try:
        with open(log_file, "w") as f_out:
            proc = subprocess.Popen(cmd, cwd=cwd, stdout=f_out, stderr=subprocess.STDOUT, text=True)
        while proc.poll() is None:
            if cancel_event and cancel_event.is_set():
                proc.kill()
                proc.wait()
                return {"status": "cancelled", "stdout": ""}
            time.sleep(0.1)
        with open(log_file, "r") as f_in:
            stdout_text = f_in.read()
        return {"status": "success", "returncode": proc.returncode, "stdout": stdout_text}
    finally:
        try: os.remove(log_file)
        except: pass

def build_plugin(shader_data, output_dir_base, log_callback=None, plugin_name=None, cancel_event=None):
    if not log_callback: log_callback = print
    if "error" in shader_data:
        for line in shader_data["error"].splitlines():
            log_callback(f"ERROR: {line}" if line.strip() else "")
        return {"status": "error", "message": shader_data["error"]}

    import re as _re
    raw_name = (plugin_name or "FFMakerPlugin").strip()
    safe_name = _re.sub(r'[^A-Za-z0-9_]', '_', raw_name)
    safe_name = _re.sub(r'^[0-9]+', '', safe_name)
    if not safe_name: safe_name = "FFMakerPlugin"

    import random as _random
    import string as _string
    plugin_id = "".join(_random.choices(_string.ascii_uppercase + _string.digits, k=4))
    log_callback(f"Plugin name: {safe_name}  (ID: {plugin_id})")

    build_dir = os.path.join(output_dir_base, f"build_temp_{plugin_id}")
    if os.path.exists(build_dir): shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)

    boilerplate_dir = os.path.join(output_dir_base, "ffmaker_plugin")
    with open(os.path.join(boilerplate_dir, "CMakeLists.txt"), "r") as f: cmake_content = f.read()
    with open(os.path.join(boilerplate_dir, "Plugin.h"), "r") as f: h_content = f.read()
    with open(os.path.join(boilerplate_dir, "Plugin.cpp"), "r") as f: cpp_content = f.read()

    cmake_content = cmake_content.replace("/* FFM_PLUGIN_NAME */", safe_name)
    cpp_content   = cpp_content.replace("/* FFM_PLUGIN_NAME */", safe_name)
    cpp_content   = cpp_content.replace("/* FFM_PLUGIN_ID */",   plugin_id)

    inputs = shader_data.get("inputs", [])
    uniforms_str, add_params_str, main_assigns_str = _build_uniforms_and_params(inputs, shader_data)
    shader_body = shader_data.get("code", "")

    # Post-process shader body (same logic as Windows version)
    import re as _re2
    isf_subs = shader_data.get("isf_subs", {})
    if "isf_subs" in shader_data:
        shader_body, n_renames = _re2.subn(r'\bvoid\s+main\s*\(\s*(?:void)?\s*\)', "void mainImage(out vec4 fragColor, in vec2 fragCoord)", shader_body, count=1)
        for macro, replacement in isf_subs.items():
            if replacement: shader_body = _re2.sub(r'\b' + _re2.escape(macro) + r'\b', replacement, shader_body)
        image_input_names = shader_data.get("image_input_names", [])
        for img_name in image_input_names:
            shader_body = _re2.sub(r'\b' + _re2.escape(img_name) + r'\b', 'inputTexture', shader_body)
        shader_body = _re2.sub(r'\bPASSINDEX\b', '0', shader_body)
        shader_body = shader_body.replace("gl_FragColor", "fragColor")
        shader_body = _re2.sub(r'#\s*ifdef\s+GL_ES\b.*?#\s*endif\b', '', shader_body, flags=_re2.DOTALL)
        shader_body = _re2.sub(r'\bprecision\s+\w+\s+\w+\s*;', '', shader_body)
        shader_body = _re2.sub(r'\bIMG_THIS_PIXEL\s*\(\s*(\w+)\s*\)', r'textureLod(\1, v_texCoord, 0.0)', shader_body)
        shader_body = _re2.sub(r'\bIMG_NORM_PIXEL\s*\(\s*(\w+)\s*,\s*(.*?)\s*\)', r'textureLod(\1, (\2) * MaxUV, 0.0)', shader_body)
        shader_body = _re2.sub(r'\bIMG_PIXEL\s*\(\s*(\w+)\s*,\s*(.*?)\s*\)', r'textureLod(\1, ((\2) / iResolution.xy) * MaxUV, 0.0)', shader_body)
        shader_body = shader_body.replace('iResolution.xy.xy', 'iResolution.xy')
        shader_body = _re2.sub(r'/\*\s*\{.*?\}\s*\*/', '', shader_body, flags=_re2.DOTALL)

    cpp_content = cpp_content.replace("/* FFM_SHADER_UNIFORMS */", uniforms_str.strip())
    cpp_content = cpp_content.replace("/* FFM_ADD_PARAMS */",      add_params_str)
    cpp_content = cpp_content.replace("/* FFM_SHADER_BODY */",     shader_body)

    is_fx = shader_data.get("is_fx", False)
    if is_fx:
        cpp_content = cpp_content.replace("/* FFM_PLUGIN_TYPE */", "FF_EFFECT")
        cpp_content = cpp_content.replace("/* FFM_INPUTS_SETUP */", "SetMinInputs(1);\n\tSetMaxInputs(1);")
        fx_texture_bind = "if( pGL->numInputTextures < 1 || pGL->inputTextures[0] == NULL ) return FF_FAIL;\nScopedSamplerActivation activateSampler0( 0 );\nScoped2DTextureBinding textureBinding0( pGL->inputTextures[0]->Handle );\nshader.Set( \"inputTexture\", 0 );\nFFGLTexCoords maxCoords = GetMaxGLTexCoords( *pGL->inputTextures[0] );\nshader.Set( \"MaxUV\", maxCoords.s, maxCoords.t );"
        cpp_content = cpp_content.replace("/* FFM_FX_TEXTURE_BIND */", fx_texture_bind)
    else:
        cpp_content = cpp_content.replace("/* FFM_PLUGIN_TYPE */", "FF_SOURCE")
        cpp_content = cpp_content.replace("/* FFM_INPUTS_SETUP */", "SetMinInputs(0);\n\tSetMaxInputs(0);")
        cpp_content = cpp_content.replace("/* FFM_FX_TEXTURE_BIND */", "shader.Set( \"MaxUV\", 1.0f, 1.0f );")

    if "mainImage" in shader_body:
        cpp_content = cpp_content.replace("/* FFM_SHADER_MAIN_CALL */", main_assigns_str + "    mainImage(finalColor, fragCoord);")
    else:
        cpp_content = cpp_content.replace("/* FFM_SHADER_MAIN_CALL */", main_assigns_str + "    // ISF main body injected above")

    with open(os.path.join(build_dir, "CMakeLists.txt"), "w") as f: f.write(cmake_content)
    with open(os.path.join(build_dir, "Plugin.h"), "w") as f: f.write(h_content)
    with open(os.path.join(build_dir, "Plugin.cpp"), "w") as f: f.write(cpp_content)

    # MacOS Build logic
    log_callback("Running CMake configuration (macOS)...")
    try:
        # Homebrew GLEW path on Apple Silicon
        glew_dir = "/opt/homebrew/opt/glew"
        res_conf = _run_cancellable(["cmake", "-B", "build", f"-DGLEW_ROOT={glew_dir}"], cwd=build_dir, cancel_event=cancel_event)
        if res_conf.get("status") == "cancelled": return {"status": "cancelled"}
        if res_conf.get("returncode", -1) != 0:
            log_callback(f"CMake config FAILED:\n{res_conf.get('stdout', '')}")
            return {"status": "error", "message": "CMake config failed"}

        log_callback("Running CMake build (macOS)...")
        res_build = _run_cancellable(["cmake", "--build", "build", "--config", "Release"], cwd=build_dir, cancel_event=cancel_event)
        if res_build.get("status") == "cancelled": return {"status": "cancelled"}
        if res_build.get("returncode", -1) != 0:
            log_callback(f"Build FAILED:\n{res_build.get('stdout', '')}")
            return {"status": "error", "message": "Build failed"}

        # On macOS, CMake with BUNDLE property puts output in build/Release/Name.bundle
        bundle_src = os.path.join(build_dir, "build", f"{safe_name}.bundle")
        if not os.path.exists(bundle_src):
             # Fallback if it didn't create a bundle for some reason
             bundle_src = os.path.join(build_dir, "build", "Release", f"{safe_name}.bundle")

        if os.path.exists(bundle_src):
            out_dir = get_external_path("output")
            os.makedirs(out_dir, exist_ok=True)
            dst = os.path.join(out_dir, f"{safe_name}.bundle")
            if os.path.exists(dst): shutil.rmtree(dst)
            shutil.copytree(bundle_src, dst)
            log_callback(f"Output: {dst}")
            return {"status": "success", "message": "Build complete", "dll_name": f"{safe_name}.bundle"}
        else:
            log_callback(f"(Bundle not found at expected path: {bundle_src})")
            return {"status": "error", "message": "Output bundle not found"}
    except Exception as e:
        log_callback(f"Subprocess error: {e}")
        return {"status": "error", "message": str(e)}
