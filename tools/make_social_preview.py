"""Make the GitHub social preview image (1280x640): the app icon, name and
tagline on the left, a strip of shader stills on the right.

    python tools/make_social_preview.py [out.png]   (default: assets/social-preview.png)

Needs the stills from tools/render_stills.py (docs/img/shaders) and, for the
lettering, Segoe UI (Windows) or Helvetica (macOS).
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 640
BG = (11, 13, 18)
FG = (232, 234, 240)
DIM = (154, 163, 178)
STILLS = ["kaleidoBloom", "reactionBloom", "voronoiGlass", "gyroidDrift", "spiralDream", "circleWeave"]


def font(bold, size):
    for name in (["segoeuib.ttf", "Helvetica.ttc"] if bold else ["segoeui.ttf", "Helvetica.ttc"]):
        for folder in ("C:/Windows/Fonts", "/System/Library/Fonts"):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *img.size), radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, mask=mask)
    return out


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "social-preview.png")
    canvas = Image.new("RGBA", (W, H), BG)

    # Right: a 2 x 3 grid of stills, tilted slightly, fading into the background on the left.
    tile_w, tile_h, gap = 300, 169, 14
    grid = Image.new("RGBA", (2 * tile_w + gap, 3 * tile_h + 2 * gap), (0, 0, 0, 0))
    for i, name in enumerate(STILLS):
        still = Image.open(os.path.join(ROOT, "docs", "img", "shaders", name + ".jpg")).convert("RGB")
        tile = rounded(still.resize((tile_w, tile_h), Image.LANCZOS), 12)
        grid.paste(tile, ((i % 2) * (tile_w + gap), (i // 2) * (tile_h + gap)), tile)
    grid = grid.rotate(-8, resample=Image.BICUBIC, expand=True)
    gx, gy = W - grid.width + 70, (H - grid.height) // 2
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow.paste((61, 224, 240, 70), (gx + 40, gy + 40, gx + grid.width - 40, gy + grid.height - 40))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    canvas.alpha_composite(grid, (gx, gy))
    fade = Image.new("L", (W, 1))
    for x in range(W):
        fade.putpixel((x, 0), 255 if x < 560 else max(0, int(255 * (1 - (x - 560) / 220))))
    shade = Image.new("RGBA", (W, H), BG)
    shade.putalpha(fade.resize((W, H)))
    canvas.alpha_composite(shade)

    # Left: icon, name, tagline, address.
    icon = Image.open(os.path.join(ROOT, "assets", "icon", "GLim.png")).convert("RGBA").resize((132, 132), Image.LANCZOS)
    canvas.alpha_composite(icon, (80, 112))
    d = ImageDraw.Draw(canvas)
    d.text((76, 262), "GLim", font=font(True, 112), fill=FG)
    tag = font(False, 34)
    d.text((80, 400), "Play GLSL shaders live.", font=tag, fill=FG)
    d.text((80, 444), "Make FFGL plugins and ISF files.", font=tag, fill=DIM)
    d.text((80, 528), "glim.sqrl.biz  ·  free and open source", font=font(False, 24), fill=(123, 123, 240))

    canvas.convert("RGB").save(out, optimize=True)
    print(f"wrote {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
