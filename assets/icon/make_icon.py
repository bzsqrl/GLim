"""Draw the GLim icon and write every format the app needs:

    assets/icon/GLim.png         1024 px logo
    assets/icon/GLim.ico         Windows (16-256 px; small sizes drawn separately)
    assets/icon/GLim.icns        macOS (Apple's icon grid: the tile has a margin)
    assets/icon/png/glim_N.png   window icons for Tk / GLFW

Design: a dark rounded tile (GLim's own background) with a four-point glimmer
star and smaller twinkles, split into cyan and magenta copies that add up to
white where they overlap, like an RGB split in a VJ mix. Only Pillow is needed:  python assets/icon/make_icon.py
"""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))

TILE_TOP = (31, 41, 55)       # #1f2937
TILE_BOTTOM = (11, 15, 26)    # #0b0f1a
CYAN = (0, 217, 255)
MAGENTA = (255, 0, 217)


def render(size, margin=0.06):
    """The icon at `size` px. Small sizes are drawn on the pixel grid with
    thicker strokes, a 1 px split and no glow, so they stay crisp."""
    small = size <= 48
    ss = 8 if small else 2                        # supersampling
    S = size * ss
    if small:
        margin = 0.0 if size <= 24 else 0.03

    # Tile: vertical gradient, rounded corners.
    inset = round(size * margin) * ss
    T = S - 2 * inset
    grad = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(TILE_TOP, TILE_BOTTOM)))
    tile = grad.resize((S, S), Image.BILINEAR)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((inset, inset, S - inset - 1, S - inset - 1),
                                           round(T * 0.22), fill=255)
    if not small:                                 # faint highlight along the top edge
        edge = Image.new("L", (S, S), 0)
        w = max(1, round(T * 0.012))
        ImageDraw.Draw(edge).rounded_rectangle((inset, inset, S - inset - 1, S - inset - 1),
                                               round(T * 0.22), outline=255, width=w)
        fade = Image.linear_gradient("L").resize((S, S)).point(lambda v: max(0, 255 - v * 3))
        tile = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), tile,
                               ImageChops.multiply(edge, fade).point(lambda v: v * 0.10))

    # Sparkles, in tile units: a four-point star with concave sides (a
    # superellipse with exponent k > 1), a fainter diagonal one behind it, and
    # two small ones. Small sizes keep only the main star, so it stays crisp.
    def star(cx, cy, r, k, turn=0.0, n=160):
        pts = []
        for i in range(n):
            t = 2 * math.pi * i / n
            c, s_ = math.cos(t), math.sin(t)
            x = r * math.copysign(abs(c) ** k, c)
            y = r * math.copysign(abs(s_) ** k, s_)
            xr = x * math.cos(turn) - y * math.sin(turn)
            yr = x * math.sin(turn) + y * math.cos(turn)
            pts.append((inset + (cx + xr) * T, inset + (cy + yr) * T))
        return pts
    sparkle = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(sparkle)
    if small:
        d.polygon(star(0.5, 0.5, 0.42, 3.2), fill=255)
    else:
        d.polygon(star(0.45, 0.55, 0.22, 5.0, math.pi / 4), fill=150)
        d.polygon(star(0.45, 0.55, 0.38, 4.2), fill=255)
        d.polygon(star(0.77, 0.23, 0.12, 4.0), fill=235)
        d.polygon(star(0.80, 0.80, 0.07, 3.6), fill=200)

    # RGB split: cyan up-left, magenta down-right; added, the overlap is white.
    off = ss * max(1, round(size * 0.016)) if small else S * 0.012
    def tinted(dx, dy, rgb):
        m = ImageChops.offset(sparkle, round(dx), round(dy))
        return Image.merge("RGB", [m.point(lambda v, c=c: v * c // 255) for c in rgb])
    split = ImageChops.add(tinted(-off, -off * 0.4, CYAN), tinted(off, off * 0.4, MAGENTA))
    if not small:
        glow = split.filter(ImageFilter.GaussianBlur(S * 0.03)).point(lambda v: v * 6 // 10)
        split = ImageChops.add(split, glow)
    art = ImageChops.add(tile, split)

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(art, (0, 0), mask)
    return out.resize((size, size), Image.LANCZOS) if ss > 1 else out


def main():
    os.makedirs(os.path.join(HERE, "png"), exist_ok=True)
    logo = render(1024)
    logo.save(os.path.join(HERE, "GLim.png"))

    ico_sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    imgs = [render(s) for s in ico_sizes]
    imgs[-1].save(os.path.join(HERE, "GLim.ico"), sizes=[(s, s) for s in ico_sizes],
                  append_images=imgs[:-1])
    for s, im in zip(ico_sizes, imgs):
        if s in (16, 24, 32, 48, 64, 128, 256):
            im.save(os.path.join(HERE, "png", f"glim_{s}.png"))

    # macOS: on Apple's grid the tile is 824 of 1024 px, so a ~10% margin.
    mac = render(1024, margin=0.0977)
    mac.save(os.path.join(HERE, "GLim.icns"),
             append_images=[render(s, margin=0.0977) for s in (16, 32, 64, 128, 256, 512)])
    print("wrote GLim.png, GLim.ico, GLim.icns and png/")


if __name__ == "__main__":
    main()
