"""Run every shader in tests/corpus/ through the pipeline (--dir for another folder).

    python tests/run_corpus.py [--filter substr] [--no-render] [--isf]

For each file: convert -> GPU compile -> render two frames. Writes thumbnails
and a JSON report to tests/out/. Status codes:
  OK       compiled and rendered something non-black that changes over time
           (or is static by design)
  STATIC   rendered, but identical at both sample times (may be fine)
  BLACK    rendered all black / fully transparent
  COMPILE  GPU compile error
  PARSE    converter refused the file
With --isf, each export is also checked: COMPILE, FLIP (renders differently
when gl_FragCoord runs top-down, as in MadMapper on macOS), REIMPORT, DIFFn
(round-trip render differs by n), else OK.
"""
import argparse
import glob
import json
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ffstudio import pipeline, validate as V  # noqa: E402
from ffstudio.convert import ConvertError     # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default="")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--isf", action="store_true", help="also test ISF export")
    ap.add_argument("--dir", default=os.path.join(ROOT, "tests", "corpus"))
    args = ap.parse_args()

    out_dir = os.path.join(ROOT, "tests", "out")
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(f for f in glob.glob(os.path.join(args.dir, "*"))
                   if os.path.isfile(f) and args.filter in os.path.basename(f)
                   and not f.endswith(".vs"))
    print("GPU:", V.context().renderer)
    rows = []
    t0 = time.time()
    for path in files:
        fname = os.path.basename(path)
        stem = os.path.splitext(fname)[0]
        row = {"file": fname}
        try:
            code = open(path, encoding="utf-8", errors="replace").read()
            res = pipeline.convert_ffgl(code, name=stem, path=path)
            ir = res.ir
            row.update(dialect=ir.dialect, kind=ir.kind, params=len(ir.params),
                       promoted=len(ir.promoted), demoted=res.demoted, warnings=ir.warnings)
            with open(os.path.join(out_dir, stem + ".ffgl.frag"), "w", encoding="utf-8") as f:
                f.write(res.ffgl_glsl[0])
            if not res.ok:
                row["status"] = "COMPILE"
                row["detail"] = "; ".join(f"L{l}: {m}" for l, m in res.errors[:3])
            elif args.no_render:
                row["status"] = "OK"
            else:
                r = V.render(ir, res.ffgl_glsl)
                V.save_png(r["rgba"], r["size"], os.path.join(out_dir, stem + ".png"))
                a, b = r["frames"][0], r["frames"][-1]
                if b["max"] < 3 and a["max"] < 3:
                    row["status"] = "BLACK"
                elif a["mean"] == b["mean"]:
                    row["status"] = "STATIC"
                else:
                    row["status"] = "OK"
                row["detail"] = f"mean={[round(x) for x in b['mean']]} distinct={b['distinct']}"
            if args.isf and row["status"] != "COMPILE":
                row["isf"] = _check_isf(code, stem, path, out_dir)
        except ConvertError as e:
            row["status"] = "PARSE"
            row["detail"] = str(e)
        except Exception as e:
            row["status"] = "CRASH"
            row["detail"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        rows.append(row)
        isf = f" isf={row['isf']['status']}" if "isf" in row else ""
        print(f"{row['status']:8} {fname[:44]:44} {row.get('kind',''):7} p={row.get('params','-'):<3}"
              f"{isf} {row.get('detail','')[:110]}")

    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\nSummary:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
          f"of {len(rows)}  ({time.time() - t0:.1f}s)")
    if args.isf:
        ic = {}
        for r in rows:
            if "isf" in r:
                ic[r["isf"]["status"]] = ic.get(r["isf"]["status"], 0) + 1
        print("ISF export:", ", ".join(f"{k}={v}" for k, v in sorted(ic.items())))
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(rows, f, indent=1)


def _check_isf(code, stem, path, out_dir):
    from ffstudio import convert as C, emit_isf, isf_host
    ir = C.convert(code, name=stem, path=path)
    if ir.dialect == "isf":
        return {"status": "n/a"}
    ir.name = stem + ".isf"
    fs_path = emit_isf.write(ir, out_dir)        # .fs plus texture assets
    text = open(fs_path, encoding="utf-8").read()
    ok, errs = isf_host.compile_isf(text)
    if not ok:
        return {"status": "COMPILE", "errors": errs[:3]}
    # Hosts disagree on gl_FragCoord's origin (MadMapper on macOS: top-left),
    # so the export must render the same either way.
    if isf_host.origin_independent(text) is False:
        return {"status": "FLIP", "errors": ["output depends on gl_FragCoord's origin"]}
    # Round trip: re-import the exported ISF and compare renders with the original.
    try:
        a = pipeline.convert_ffgl(code, name=stem, path=path)
        b = pipeline.convert_ffgl(text, name=stem, path=os.path.join(out_dir, stem + ".isf.fs"))
        if not b.ok:
            return {"status": "REIMPORT", "errors": b.errors[:3]}
        ra = V.render(a.ir, a.ffgl_glsl, times=(1.0,), frames_between=5)["frames"][-1]["mean"]
        rb = V.render(b.ir, b.ffgl_glsl, times=(1.0,), frames_between=5)["frames"][-1]["mean"]
        diff = max(abs(x - y) for x, y in zip(ra, rb))
        return {"status": "OK" if diff < 3 else f"DIFF{diff:.0f}"}
    except Exception as e:
        return {"status": "ROUNDTRIP-ERR", "errors": [str(e)[:200]]}


if __name__ == "__main__":
    main()
