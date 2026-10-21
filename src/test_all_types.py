"""
test_all_types.py
-----------------
Validates that parser + builder correctly processes a mock ISF shader
containing every supported input type:
  float (with range), bool, event, color, point2D, long

Runs the parser and prints the generated C++ snippets.
Does NOT invoke CMake — that's a separate manual verify step.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_isf
from builder import _build_uniforms_and_params

MOCK_ISF = r'''/*{
    "DESCRIPTION": "All-types test shader",
    "INPUTS": [
        {
            "NAME": "speed",
            "TYPE": "float",
            "DEFAULT": 0.5,
            "MIN": 0.0,
            "MAX": 2.0
        },
        {
            "NAME": "amplitude",
            "TYPE": "float",
            "DEFAULT": 0.3
        },
        {
            "NAME": "invert",
            "TYPE": "bool",
            "DEFAULT": false
        },
        {
            "NAME": "flash",
            "TYPE": "event"
        },
        {
            "NAME": "tintColor",
            "TYPE": "color",
            "DEFAULT": [1.0, 0.5, 0.0, 1.0]
        },
        {
            "NAME": "center",
            "TYPE": "point2D",
            "DEFAULT": [0.5, 0.5]
        },
        {
            "NAME": "blendMode",
            "TYPE": "long",
            "LABELS": ["Add", "Multiply", "Screen"],
            "VALUES": [0, 1, 2],
            "DEFAULT": 0
        }
    ]
}*/
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    uv -= center;

    float t = iTime * speed;
    float wave = sin(uv.x * 10.0 + t) * amplitude;

    vec4 col = tintColor * (0.5 + 0.5 * wave);

    // blend mode switch
    float bm = blendMode;

    if (invert) col = vec4(1.0) - col;
    if (flash)  col = vec4(1.0);

    fragColor = col;
}
'''

def main():
    print("=" * 60)
    print("FFMaker - Full Type Parser + Builder Test")
    print("=" * 60)

    # ── Parse ─────────────────────────────────────────────────────
    result = parse_isf(MOCK_ISF)
    if "error" in result:
        print(f"[FAIL] Parser error: {result['error']}")
        sys.exit(1)

    inputs = result["inputs"]
    print(f"\n[OK] Parser found {len(inputs)} inputs:\n")
    for inp in inputs:
        print(f"  {inp['NAME']:20s}  TYPE={inp['TYPE']:10s}  ", end="")
        extras = {k: v for k, v in inp.items() if k not in ("NAME", "TYPE")}
        print(extras)

    # ── Build ──────────────────────────────────────────────────────
    uniforms_str, add_params_str = _build_uniforms_and_params(inputs)

    print("\n" + "-" * 60)
    print("GLSL Uniforms block:")
    print("-" * 60)
    print(uniforms_str or "  (empty)")

    print("-" * 60)
    print("C++ AddParam calls:")
    print("-" * 60)
    print(add_params_str or "  (empty)")

    # ── Validation checks ──────────────────────────────────────────
    print("-" * 60)
    failures = []

    checks = [
        ("uniform float speed",        uniforms_str,   "float uniform"),
        ("ParamRange::Create",         add_params_str, "float with range -> ParamRange"),
        ("uniform float amplitude",    uniforms_str,   "float no-range uniform"),
        ("Param::Create",              add_params_str, "float no-range -> Param"),
        ("uniform bool invert",        uniforms_str,   "bool uniform"),
        ("ParamBool::Create",          add_params_str, "bool -> ParamBool"),
        ("uniform bool flash",         uniforms_str,   "event uniform"),
        ("ParamEvent::Create",         add_params_str, "event -> ParamEvent"),
        ("uniform vec4 tintColor",     uniforms_str,   "color uniform"),
        ('AddHueColorParam( "tintColor"', add_params_str, "color -> AddHueColorParam"),
        ("uniform float center_X",     uniforms_str,   "point2D X uniform"),
        ("uniform float center_Y",     uniforms_str,   "point2D Y uniform"),
        ("#define center vec2",        uniforms_str,   "point2D #define"),
        ("uniform float blendMode",    uniforms_str,   "long uniform"),
        ("ParamOption::Create",        add_params_str, "long -> ParamOption"),
        ('"Add"',                      add_params_str, "long label Add"),
        ('"Screen"',                   add_params_str, "long label Screen"),
    ]

    for needle, haystack, label in checks:
        if needle in haystack:
            print(f"  [OK] {label}")
        else:
            print(f"  [FAIL] {label}  (missing: {repr(needle)})")
            failures.append(label)

    print("-" * 60)
    if failures:
        print(f"\n[FAIL] {len(failures)} check(s) failed:\n")
        for f in failures:
            print(f"   - {f}")
        sys.exit(1)
    else:
        print(f"\n[PASS] All {len(checks)} checks passed.")


if __name__ == "__main__":
    main()
