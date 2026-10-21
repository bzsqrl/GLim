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

EXTS = {".fs", ".frag", ".glsl", ".txt", ".shader"}


def collect(inputs):
    files = []
    for p in inputs:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in sorted(names) if os.path.splitext(n)[1].lower() in EXTS]
        else:
            files.append(p)
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ffmaker", description="Convert GLSL shaders to FFGL plugins and ISF files.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--to", choices=["ffgl", "isf", "both", "check"], default="ffgl",
                    help="'check' only validates (no files written)")
    ap.add_argument("--out", default=None, help="output folder (default: FFMaker/output)")
    ap.add_argument("--no-params", action="store_true", help="don't turn constants into sliders")
    ap.add_argument("--prefix", default="", help="prefix for plugin names (e.g. 'FFM ')")
    ap.add_argument("--test", action="store_true", help="load each built plugin in a test host")
    args = ap.parse_args(argv)

    out_dir = args.out or paths.default_output_dir()
    files = collect(args.inputs)
    ok_count = 0
    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        name = args.prefix + stem
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
            os.makedirs(out_dir, exist_ok=True)
            isf_path = os.path.join(out_dir, stem + ".fs")
            if ir.dialect == "isf":
                print(f"  (ISF source: no ISF export needed)")
            else:
                with open(isf_path, "w", encoding="utf-8") as f:
                    f.write(emit_isf.emit(ir))
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
                from . import ffgl_host
                n = {"source": 0, "effect": 1, "mixer": 2}[ir.kind]
                try:
                    r = ffgl_host.smoke_test(dst, num_inputs=n, frames=10)
                    b = r["frames"][-1]
                    print(f"    test host: OK, {len(r['params'])} host params, mean colour "
                          f"{[round(x) for x in b['mean'][:3]]}")
                except Exception as e:
                    print(f"    test host: FAILED: {e}")
                    continue
        ok_count += 1
    print(f"\n{ok_count}/{len(files)} converted.")
    return 0 if ok_count == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
