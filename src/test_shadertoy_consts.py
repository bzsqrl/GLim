"""
test_shadertoy_consts.py
------------------------
Validates const float/bool extraction from Shadertoy shader code.
Tests: No-cap extraction (all 5 consts in mock should be extracted), Speed-first,
_p trampoline uniforms, default preservation, SHOW_GRID included.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_shadertoy
from builder import _build_uniforms_and_params

# 5 consts defined -- all 5 should be extracted
MOCK_SHADERTOY = r"""
// A typical Shadertoy shader with tweakable constants
const float SPEED      = 1.5;
const float ZOOM       = 2.0;
const float BRIGHTNESS = 0.75f;
const bool  INVERT     = false;
const bool  SHOW_GRID  = true;
// const int  STEPS   = 16;   <- intentionally skipped (int not supported)

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy * ZOOM;
    float t  = iTime * SPEED;
    float brt = sin(t) * BRIGHTNESS;
    vec4 col = vec4(brt, brt * 0.5, 1.0, 1.0);
    if (INVERT) col = 1.0 - col;
    fragColor = col;
}
"""

def main():
    print("=" * 60)
    print("FFMaker - Shadertoy Const Extraction Test")
    print("=" * 60)

    result = parse_shadertoy(MOCK_SHADERTOY)
    inputs = result["inputs"]
    stats  = result.get("_stats", {})

    user_inputs  = [i for i in inputs if not i.get("_builtin")]
    const_inputs = [i for i in user_inputs if i.get("_source") == "const_extract"]

    # All 5 consts should be extracted
    expected_names = {"SPEED", "ZOOM", "BRIGHTNESS", "INVERT", "SHOW_GRID"}
    actual_names   = {i["NAME"] for i in user_inputs}
    # SPEED must be first
    first_name = user_inputs[0]["NAME"] if user_inputs else None

    print(f"\n[OK] Parser: {len(user_inputs)} user param(s), "
          f"{stats.get('const_extracted', 0)} extracted from consts\n")
    for inp in user_inputs:
        src = " [const]" if inp.get("_source") == "const_extract" else ""
        print(f"  {inp['NAME']:15s}  TYPE={inp['TYPE']:6s}  DEFAULT={inp.get('DEFAULT')}{src}")

    # Build uniforms + params
    uniforms_str, add_params_str, main_assigns_str = _build_uniforms_and_params(user_inputs, {})

    print("\n" + "-" * 60)
    print("GLSL Uniforms:")
    print("-" * 60)
    print(uniforms_str or "  (empty)")

    print("-" * 60)
    print("C++ AddParam calls:")
    print("-" * 60)
    print(add_params_str or "  (empty)")

    # Simulate builder const-stripping
    shader_body = result["code"]
    n_stripped = 0
    for inp in user_inputs:
        if inp.get("_source") == "const_extract":
            decl = inp.get("_const_decl", "")
            if decl and decl in shader_body:
                shader_body = shader_body.replace(
                    decl,
                    f"// [FFMaker] '{inp['NAME']}' promoted to uniform param",
                    1
                )
                n_stripped += 1

    print("-" * 60)
    print(f"Const stripping: removed {n_stripped} declaration(s)")
    print("Modified shader (first 30 lines):")
    print("-" * 60)
    for line in shader_body.splitlines()[:30]:
        print(" ", line)

    # Assertions
    print("-" * 60)
    failures = []

    checks = [
        (lambda: stats.get("const_extracted") == 5,
         "5 consts extracted (all fit)"),
        (lambda: expected_names == actual_names,
         f"correct params chosen {expected_names}"),
        # SPEED is first
        (lambda: first_name == "SPEED",
         f"SPEED is first param (got: {first_name})"),
        # Float defaults preserved
        (lambda: any(i["NAME"] == "SPEED"      and abs(i["DEFAULT"] - 1.5)  < 1e-6 for i in const_inputs),
         "SPEED float default 1.5"),
        (lambda: any(i["NAME"] == "BRIGHTNESS" and abs(i["DEFAULT"] - 0.75) < 1e-6 for i in const_inputs),
         "BRIGHTNESS float default 0.75 (trailing f stripped)"),
        # Bool defaults
        (lambda: any(i["NAME"] == "INVERT"    and i["TYPE"] == "bool" and i["DEFAULT"] == False for i in const_inputs),
         "INVERT bool default False"),
        (lambda: any(i["NAME"] == "SHOW_GRID" and i["TYPE"] == "bool" and i["DEFAULT"] == True  for i in const_inputs),
         "SHOW_GRID bool default True"),
        # Trampoline uniforms for floats
        (lambda: "uniform float SPEED_p;"    in uniforms_str,  "SPEED -> uniform float SPEED_p (trampoline)"),
        (lambda: "float SPEED;"              in uniforms_str,  "SPEED -> float variable (trampoline)"),
        (lambda: "SPEED = "                  in main_assigns_str, "SPEED assigned in main wrapper"),
        (lambda: "uniform bool INVERT;"      in uniforms_str,  "INVERT -> uniform bool (no trampoline)"),
        (lambda: "uniform bool SHOW_GRID;"   in uniforms_str,  "SHOW_GRID -> uniform bool"),
        # C++ params at 0.5
        (lambda: 'Param::Create( "SPEED_p", 0.500000f' in add_params_str, "SPEED_p init at 0.5"),
        (lambda: 'Param::Create( "ZOOM_p", 0.500000f'  in add_params_str, "ZOOM_p init at 0.5"),
        (lambda: 'ParamBool::Create( "INVERT"'    in add_params_str, "INVERT -> ParamBool::Create"),
        (lambda: 'ParamBool::Create( "SHOW_GRID"' in add_params_str, "SHOW_GRID -> ParamBool::Create"),
        # Stripping: all 5 removed
        (lambda: n_stripped == 5,                         "5 const decls stripped"),
        (lambda: "const float SPEED"    not in shader_body, "SPEED const removed from body"),
        (lambda: "const bool INVERT"    not in shader_body, "INVERT const removed from body"),
        (lambda: "const bool  SHOW_GRID" not in shader_body, "SHOW_GRID const removed from body"),
        (lambda: "FFMaker"              in shader_body,     "Replacement comment present"),
    ]

    for fn, label in checks:
        try:
            passed = fn()
        except Exception as e:
            passed = False
            label += f" (exception: {e})"
        if passed:
            print(f"  [OK] {label}")
        else:
            print(f"  [FAIL] {label}")
            failures.append(label)

    print("-" * 60)
    if failures:
        print(f"\n[FAIL] {len(failures)} check(s) failed:")
        for f in failures:
            print(f"   - {f}")
        sys.exit(1)
    else:
        print(f"\n[PASS] All {len(checks)} checks passed.")


if __name__ == "__main__":
    main()
