"""Command line: python -m ffmaker <files or folders> [options]

Examples:
  python -m ffmaker sample-shaders/vv_brokenLCD.fs --to ffgl
  python -m ffmaker sample-shaders --to both --out output/batch --test
"""
import argparse
import os
import sys

from . import convert as C
from . import emit_isf, pipeline, paths

EXTS = {".fs", ".frag", ".glsl", ".txt", ".shader", ".json"}


def collect(inputs):
    files = []
    for p in inputs:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in sorted(names) if os.path.splitext(n)[1].lower() in EXTS]
        else:
            files.append(p)
    return files


def smoke_test_subprocess(plugin_path, num_inputs, timeout=60):
    """Load the plugin in a separate process so crashes or file locks can't
    affect the caller."""
    import json
    import subprocess
    cmd = [sys.executable, "-m", "ffmaker.ffgl_host", plugin_path, str(num_inputs)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=paths.bundle_dir())
    except subprocess.TimeoutExpired:
        return False, "timed out"
    if p.returncode != 0:
        err = (p.stderr.strip().splitlines() or ["crashed"])[-1]
        return False, f"exit {p.returncode}: {err}"
    r = json.loads(p.stdout.strip().splitlines()[-1])
    return True, f"{r['params']} host params, mean colour {[round(x) for x in r['mean'][:3]]}"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ffmaker", description="Convert GLSL shaders to FFGL plugins and ISF files.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--to", choices=["ffgl", "isf", "both", "check"], default="ffgl",
                    help="'check' only validates (no files written)")
    ap.add_argument("--out", default=None, help="output folder (default: the output folder next to FFStudio)")
    ap.add_argument("--no-params", action="store_true", help="don't turn constants into sliders")
    ap.add_argument("--prefix", default="", help="prefix for plugin names (e.g. 'FFM ')")
    ap.add_argument("--test", action="store_true", help="load each built plugin in a test host")
    args = ap.parse_args(argv)

    out_dir = args.out or paths.default_output_dir()
    files = collect(args.inputs)
    ok_count = 0
    used_names = set()
    visible_names = set()
    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        if stem.lower() in used_names:      # e.g. foo.fs and foo.txt
            stem += "_" + os.path.splitext(path)[1].lstrip(".")
        used_names.add(stem.lower())
        from .build_ffgl import unique_plugin_name
        name = unique_plugin_name(args.prefix + stem, visible_names)
        try:
            code = open(path, encoding="utf-8", errors="replace").read()
            res = pipeline.convert_ffgl(code, name=name, path=path, extract_params=not args.no_params)
        except C.ConvertError as e:
            print(f"✗ {stem}: {e}")
            continue
        ir = res.ir
        for w in ir.warnings:
            print(f"  ! {w}")
        if not res.ok:
            print(f"✗ {stem}: shader does not compile")
            for ln, msg in res.errors[:5]:
                print(f"    line {ln}: {msg}")
            continue
        note = f"{ir.dialect} {ir.kind}, {len(ir.params)} params"
        if res.demoted:
            note += f", kept as constants: {', '.join(res.demoted)}"
        if args.to == "check":
            print(f"✓ {stem} ({note})")
            ok_count += 1
            continue
        if args.to in ("isf", "both"):
            if ir.dialect == "isf":
                from . import settings as S
                if S.load(path):
                    os.makedirs(out_dir, exist_ok=True)
                    dst = os.path.join(out_dir, stem + ".fs")
                    with open(dst, "w", encoding="utf-8") as f:
                        f.write(emit_isf.apply_settings_to_isf(code, ir))
                    print(f"✓ {stem} → {dst} (ISF header updated from saved settings)")
                else:
                    print(f"  (ISF source: no ISF export needed)")
            else:
                ir.name = stem
                isf_path = emit_isf.write(ir, out_dir)
                ir.name = name
                print(f"✓ {stem} → {isf_path}")
        if args.to in ("ffgl", "both"):
            from . import build_ffgl
            try:
                dst = build_ffgl.build(ir, res.ffgl_glsl, name, out_dir=out_dir, log=lambda m: print("    " + m))
            except build_ffgl.BuildError as e:
                print(f"✗ {stem}: build failed: {e}")
                continue
            print(f"✓ {stem} → {dst} ({note})")
            if args.test:
                ok, msg = smoke_test_subprocess(dst, {"source": 0, "effect": 1, "mixer": 2}[ir.kind])
                print(f"    test host: {'OK' if ok else 'FAILED'}, {msg}")
                if not ok:
                    continue
        ok_count += 1
    print(f"\n{ok_count}/{len(files)} converted.")
    return 0 if ok_count == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
