"""Image data for embedded textures (ISF IMPORTED, Shadertoy channel files).

The plugin decodes PNG/JPG/BMP/TGA with stb_image; other formats are
re-encoded to PNG here. Missing images fall back to the same deterministic
RGBA noise the plugin runtime generates, so offline renders match.
"""
import io
import os

NATIVE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tga"}
MAX_EMBED_SIZE = 2048  # longest side; larger images are downscaled before embedding


def available(image):
    return bool(image.path) and os.path.isfile(image.path)


def encoded_bytes(image):
    """Bytes to embed in the plugin, or None for generated noise."""
    if not available(image):
        return None
    ext = os.path.splitext(image.path)[1].lower()
    with open(image.path, "rb") as f:
        data = f.read()
    try:
        from PIL import Image as PILImage
        im = PILImage.open(io.BytesIO(data))
        too_big = max(im.size) > MAX_EMBED_SIZE
    except Exception:
        im, too_big = None, False
    if ext in NATIVE_EXTS and not too_big:
        return data
    if im is None:
        return None
    im = im.convert("RGBA")
    if too_big:
        im.thumbnail((MAX_EMBED_SIZE, MAX_EMBED_SIZE))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def noise_rgba(index, size=256):
    """Same LCG as Plugin.cpp."""
    state = (0x12345678 + 7919 * index) & 0xFFFFFFFF
    out = bytearray(size * size * 4)
    for k in range(len(out)):
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        out[k] = state >> 24
    return size, size, bytes(out)


def rgba(image, index):
    """(w, h, bytes) bottom-up RGBA for the validator."""
    data = encoded_bytes(image)
    if data:
        from PIL import Image as PILImage
        im = PILImage.open(io.BytesIO(data)).convert("RGBA").transpose(PILImage.FLIP_TOP_BOTTOM)
        return im.size[0], im.size[1], im.tobytes()
    return noise_rgba(index, image.noise_size)
