/*{
  "DESCRIPTION": "Building block effect: repeat the clip in a grid of tiles, or slice it into tiles, with flips, sliding rows, spinning tiles, gaps and glitchy jumps",
  "CREDIT": "GLim - License: CC0",
  "ISFVSN": "2",
  "CATEGORIES": ["Stylize", "Building Block"],
  "INPUTS": [
    { "NAME": "inputImage", "TYPE": "image" },
    { "NAME": "tilesX",     "LABEL": "Tiles X",      "TYPE": "float", "DEFAULT": 4.0,  "MIN": 1.0,  "MAX": 16.0 },
    { "NAME": "tilesY",     "LABEL": "Tiles Y",      "TYPE": "float", "DEFAULT": 4.0,  "MIN": 1.0,  "MAX": 16.0 },
    { "NAME": "wholeImage", "LABEL": "Whole Clip per Tile", "TYPE": "bool", "DEFAULT": true },
    { "NAME": "mirror",     "LABEL": "Mirror Tiles", "TYPE": "bool",  "DEFAULT": false },
    { "NAME": "slide",      "LABEL": "Row Slide",    "TYPE": "float", "DEFAULT": 0.2,  "MIN": -2.0, "MAX": 2.0 },
    { "NAME": "columnSlide","LABEL": "Column Slide", "TYPE": "float", "DEFAULT": 0.0,  "MIN": -2.0, "MAX": 2.0 },
    { "NAME": "tileSpin",   "LABEL": "Tile Spin",    "TYPE": "float", "DEFAULT": 0.0,  "MIN": -3.0, "MAX": 3.0 },
    { "NAME": "tileZoom",   "LABEL": "Tile Zoom",    "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.3,  "MAX": 3.0 },
    { "NAME": "gap",        "LABEL": "Gap",          "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 0.25 },
    { "NAME": "gapColor",   "LABEL": "Gap Color",    "TYPE": "color", "DEFAULT": [0.0, 0.0, 0.0, 1.0] },
    { "NAME": "glitch",     "LABEL": "Glitch",       "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "glitchRate", "LABEL": "Glitch Rate",  "TYPE": "float", "DEFAULT": 4.0,  "MIN": 0.5,  "MAX": 30.0 }
  ]
}*/

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

void main() {
    vec2 tiles = vec2(floor(tilesX + 0.5), floor(tilesY + 0.5));
    vec2 g = isf_FragNormCoord * tiles;

    // Alternate rows (and columns) slide in opposite directions
    g.x += (mod(floor(g.y), 2.0) * 2.0 - 1.0) * TIME * slide;
    g.y += (mod(floor(g.x), 2.0) * 2.0 - 1.0) * TIME * columnSlide;
    vec2 id = floor(g);
    vec2 f = fract(g);

    if (any(lessThan(f, vec2(gap))) || any(greaterThan(f, vec2(1.0 - gap)))) {
        gl_FragColor = gapColor;
        return;
    }
    f = (f - gap) / (1.0 - 2.0 * gap);

    // Glitch: some tiles jump to a random offset, re-rolled glitchRate times a second
    float tick = floor(TIME * glitchRate);
    if (hash(id + 0.37 * tick) < glitch) {
        f = fract(f + vec2(hash(id + tick + 1.3), hash(id - tick + 7.1)) - 0.5);
    }

    if (mirror) {
        if (mod(id.x, 2.0) > 0.5) f.x = 1.0 - f.x;
        if (mod(id.y, 2.0) > 0.5) f.y = 1.0 - f.y;
    }

    // Spin each tile's content, neighbours turning opposite ways
    float dir = mod(id.x + id.y, 2.0) * 2.0 - 1.0;
    vec2 aspect = vec2(RENDERSIZE.x / tiles.x, RENDERSIZE.y / tiles.y);
    aspect /= aspect.y;
    vec2 q = (f - 0.5) * aspect;
    q = rot(TIME * tileSpin * dir) * q / tileZoom;
    f = q / aspect + 0.5;
    f = 1.0 - abs(1.0 - mod(f, 2.0));

    vec2 n = wholeImage ? f : (mod(id, tiles) + f) / tiles;
    gl_FragColor = IMG_NORM_PIXEL(inputImage, n);
}
