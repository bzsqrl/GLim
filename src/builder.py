import os
import shutil
import subprocess
import re
import json
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


def _run_cancellable(cmd, cwd, cancel_event):
    """Run a subprocess while checking for cancellation."""
    import subprocess
    process = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW
    )
    
    stdout_lines = []
    while True:
        if cancel_event and cancel_event.is_set():
            process.terminate()
            return {"status": "cancelled"}
        
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            stdout_lines.append(line)
            
    return {
        "status": "done",
        "returncode": process.returncode,
        "stdout": "".join(stdout_lines)
    }


def remove_readonly(func, path, excinfo):
    """Helper for rmtree to handle read-only files on Windows."""
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


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
            if source == "const_extract_synthetic" or "isf_subs" not in shader_data or shader_data.get("is_ffmaker_export"):
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
            mn      = inp.get("MIN",     0.0)
            mx      = inp.get("MAX",     1.0)
            source  = inp.get("_source", "")
            
            is_const = source in ("const_extract", "const_extract_synthetic")
            needs_trampoline = is_const or (mn != 0.0 or mx != 1.0 or not (0.0 <= default <= 1.0))
            
            if needs_trampoline:
                scale  = inp.get("_scale", mx - mn if mx != mn else 1.0)
                offset = inp.get("_offset", mn)
                
                if is_const:
                    scale = 2.0 * abs(default) if default != 0 else 1.0
                    offset = default - 0.5 * scale
                elif (mx - mn) != 0:
                    if default > mx: mx = default * 2.0
                    if default < mn: mn = default / 2.0
                    scale = mx - mn
                    offset = mn

                param_name = f"{name}_p"
                uniforms_str += f"uniform float {param_name};\n"
                uniforms_str += f"float {name};\n"
                
                host_default = 0.5
                if not is_const and (mx - mn) != 0:
                    host_default = (default - mn) / (mx - mn)

                if offset == 0.0:
                    main_assigns_str += f"    {name} = {param_name} * {scale:.6f};\n"
                else:
                    main_assigns_str += f"    {name} = {offset:.6f} + {param_name} * {scale:.6f};\n"

                add_params_str += f'    AddParam( Param::Create( "{param_name}", {_format_float(host_default)} ) );\n'
            else:
                uniforms_str += f"uniform float {name};\n"
                add_params_str += f'    AddParam( Param::Create( "{name}", {_format_float(default)} ) );\n'

        elif t in ("bool", "boolean"):
            default_cpp = "true" if inp.get("DEFAULT", False) else "false"
            uniforms_str   += f"uniform bool {name};\n"
            add_params_str += f'    AddParam( ParamBool::Create( "{name}", {default_cpp} ) );\n'
        elif t == "event":
            uniforms_str   += f"uniform bool {name};\n"
            add_params_str += f'    AddParam( ParamEvent::Create( "{name}" ) );\n'
        elif t == "color":
            if inp.get("_source") in ("const_extract", "const_extract_synthetic"):
                param_name = f"{name}_p"
                uniforms_str += f"uniform vec4 {param_name};\nvec3 {name};\n"
                main_assigns_str += f"    {name} = {param_name}.rgb;\n"
                add_params_str += f'    AddHueColorParam( "{param_name}" );\n'
            else:
                uniforms_str   += f"uniform vec4 {name};\n"
                add_params_str += f'    AddHueColorParam( "{name}" );\n'
        elif t == "point2D":
            default = inp.get("DEFAULT", [0.5, 0.5])
            if not isinstance(default, list): default = [0.5, 0.5]
            uniforms_str += f"uniform float {name}_x;\n"
            uniforms_str += f"uniform float {name}_y;\n"
            deferred_macros += f"#define {name} vec2({name}_x, {name}_y)\n"
            add_params_str += f'    AddParam( Param::Create( "{name}_x", {default[0]:.6f}f ) );\n'
            add_params_str += f'    AddParam( Param::Create( "{name}_y", {default[1]:.6f}f ) );\n'
        elif t == "long":
            default = int(inp.get("DEFAULT", 0))
            mn, mx  = int(inp.get("MIN", 0)), int(inp.get("MAX", 10))
            uniforms_str   += f"uniform int {name};\n"
            add_params_str += f'    AddParam( ParamRange::Create( "{name}", {default}.0f, ParamRange::Range( {mn}.0f, {mx}.0f ) ) );\n'

    uniforms_str += deferred_macros
    return uniforms_str, add_params_str, main_assigns_str


def build_plugin(shader_data, boilerplates_dir, log_callback, plugin_name, cancel_event=None):
    try:
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', plugin_name)
        import time
        build_dir = os.path.join(boilerplates_dir, f"build_temp_{int(time.time())}_{safe_name}")
        os.makedirs(build_dir, exist_ok=True)
        
        src_tpl = os.path.join(boilerplates_dir, "ffmaker_plugin")
        for item in os.listdir(src_tpl):
            s, d = os.path.join(src_tpl, item), os.path.join(build_dir, item)
            if os.path.isdir(s): shutil.copytree(s, d)
            else: shutil.copy2(s, d)

        inputs = shader_data.get("inputs", [])
        shader_body = shader_data.get("code", "")
        
        # Strip markers
        import re as _re2
        shader_body = _re2.sub(r'// <FFMAKER_ISF_SHIMS>.*?// </FFMAKER_ISF_SHIMS>', '// [FFMaker] removed ISF shims', shader_body, flags=_re2.DOTALL)

        # Strip built-ins
        for v in _BUILTIN_UNIFORMS:
            shader_body = _re2.sub(rf'^\s*(?:uniform\s+)?(?:vec[234]|float|int|sampler2D)\s+{v}\b\s*(?:=[^;]+)?;\s*$', f'// [FFMaker] removed {v} shim', shader_body, flags=_re2.MULTILINE)

        shader_body = shader_body.replace("gl_FragColor", "fragColor")
        
        for macro, sub in shader_data.get("isf_subs", {}).items():
            if sub: shader_body = _re2.sub(rf'\b{macro}\b', sub, shader_body)

        # Texture macros
        shader_body = _re2.sub(r'\bIMG_THIS_PIXEL\s*\(\s*(\w+)\s*\)', r'textureLod(\1, v_texCoord, 0.0)', shader_body)
        shader_body = _re2.sub(r'\bIMG_NORM_PIXEL\s*\(\s*(\w+)\s*,\s*(.*?)\s*\)', r'textureLod(\1, (\2) * MaxUV, 0.0)', shader_body)
        shader_body = _re2.sub(r'\bIMG_PIXEL\s*\(\s*(\w+)\s*,\s*(.*?)\s*\)', r'textureLod(\1, ((\2) / iResolution.xy) * MaxUV, 0.0)', shader_body)

        uniforms_str, add_params_str, main_assigns_str = _build_uniforms_and_params(inputs, shader_data)

        # Re-inject swizzle defines for colors (if needed)
        # This handles FFMaker-exported ISF files where color uniforms were renamed to _isf.
        swizzle_map = shader_data.get("swizzle_map", {})
        for base_name, full_name in swizzle_map.items():
            if f"#define {base_name}" not in uniforms_str:
                uniforms_str += f"#define {base_name} ({full_name}.rgb)\n"

        # Injection
        paths = ["CMakeLists.txt", "Plugin.h", "Plugin.cpp", "Plugin.def"]
        contents = {}
        for p in paths:
            with open(os.path.join(build_dir, p), "r", encoding="utf-8", errors="replace") as f:
                contents[p] = f.read()

        import hashlib
        plugin_id = hashlib.md5(plugin_name.encode()).hexdigest()[:4].upper()
        
        contents["CMakeLists.txt"] = contents["CMakeLists.txt"].replace("/* FFM_PLUGIN_NAME */", safe_name)
        contents["Plugin.h"] = contents["Plugin.h"].replace("/* FFM_PLUGIN_NAME */", safe_name)
        contents["Plugin.def"] = contents["Plugin.def"].replace("Plugin", safe_name)
        
        c = contents["Plugin.cpp"]
        c = c.replace("/* FFM_PLUGIN_ID */", plugin_id).replace("/* FFM_PLUGIN_NAME */", plugin_name)
        c = c.replace("/* FFM_SHADER_UNIFORMS */", uniforms_str).replace("/* FFM_SHADER_BODY */", shader_body)
        c = c.replace("/* FFM_ADD_PARAMS */", add_params_str)
        
        if shader_data.get("is_fx"):
            c = c.replace("/* FFM_PLUGIN_TYPE */", "FF_EFFECT").replace("/* FFM_INPUTS_SETUP */", "SetMinInputs(1);\n\tSetMaxInputs(1);")
            img_name = shader_data.get("image_input_names", ["inputImage"])[0]
            c = c.replace("inputTexture", img_name)
        else:
            c = c.replace("/* FFM_PLUGIN_TYPE */", "FF_SOURCE").replace("/* FFM_INPUTS_SETUP */", "SetMinInputs(0);\n\tSetMaxInputs(0);")

        c = c.replace("/* FFM_SHADER_MAIN_CALL */", (main_assigns_str + "    mainImage(finalColor, fragCoord);") if "mainImage" in shader_body else main_assigns_str)
        contents["Plugin.cpp"] = c

        for p, text in contents.items():
            with open(os.path.join(build_dir, p), "w", encoding="utf-8") as f:
                f.write(text)

        # GLEW
        deps_dir = get_external_path("deps")
        glew_dir = os.path.join(deps_dir, "glew-2.2.0")
        if not os.path.exists(glew_dir):
            log_callback("Downloading GLEW…")
            os.makedirs(deps_dir, exist_ok=True)
            import urllib.request, zipfile
            zip_path = os.path.join(deps_dir, "glew.zip")
            urllib.request.urlretrieve("https://github.com/nigels-com/glew/releases/download/glew-2.2.0/glew-2.2.0-win32.zip", zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf: zf.extractall(deps_dir)
            os.remove(zip_path)

        log_callback("CMake configuration…")
        res = _run_cancellable(["cmake", "-B", "build", f"-DGLEW_ROOT={glew_dir}", "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded"], build_dir, cancel_event)
        if res["status"] == "cancelled": return {"status": "cancelled"}
        if res.get("returncode") != 0: 
            log_callback(res.get("stdout", "")); return {"status": "error"}
            
        log_callback("CMake build…")
        res = _run_cancellable(["cmake", "--build", "build", "--config", "Release"], build_dir, cancel_event)
        if res["status"] == "cancelled": return {"status": "cancelled"}
        if res.get("returncode") != 0: 
            log_callback(res.get("stdout", "")); return {"status": "error"}

        dll_src = os.path.join(build_dir, "build", "Release", f"{safe_name}.dll")
        out_dir = get_external_path("output")
        os.makedirs(out_dir, exist_ok=True)
        shutil.copy2(dll_src, os.path.join(out_dir, f"{safe_name}.dll"))
        
        try: shutil.rmtree(build_dir, onerror=remove_readonly)
        except: pass
        
        return {"status": "success", "dll_name": f"{safe_name}.dll"}

    except Exception as e:
        log_callback(f"Build error: {e}")
        return {"status": "error"}
