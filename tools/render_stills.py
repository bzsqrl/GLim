"""Render a still of each shader in original-shaders/ for the website gallery.

    python tools/render_stills.py [out_dir]     (default: docs/img/shaders)

Each shader runs for a few seconds first, so the feedback shaders have built up.
Transparent pixels are laid over the site's background colour.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from glim import pipeline, validate as V  # noqa: E402

W, H = 960, 540
SECONDS = 6.0
BACKGROUND = (11, 13, 18)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "img", "shaders")
    os.makedirs(out, exist_ok=True)
    src = os.path.join(ROOT, "original-shaders")
    for fname in sorted(os.listdir(src)):
        if not fname.endswith(".fs"):
            continue
        stem = os.path.splitext(fname)[0]
        path = os.path.join(src, fname)
        res = pipeline.convert_ffgl(open(path, encoding="utf-8").read(), name=stem, path=path)
        if not res.ok:
            print("FAILED", fname, res.errors[:2])
            continue
        r = V.render(res.ir, res.ffgl_glsl, W, H, times=(SECONDS,), frames_between=int(SECONDS * 60))
        img = Image.frombytes("RGBA", r["size"], bytes(r["rgba"])).transpose(Image.FLIP_TOP_BOTTOM)
        flat = Image.new("RGB", img.size, BACKGROUND)
        flat.paste(img, mask=img.getchannel("A"))
        dst = os.path.join(out, stem + ".jpg")
        flat.save(dst, quality=84, optimize=True, progressive=True)
        print(f"{stem:16} {os.path.getsize(dst) // 1024} KB")


if __name__ == "__main__":
    main()
