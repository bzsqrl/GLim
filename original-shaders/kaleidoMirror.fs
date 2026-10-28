/*{
  "DESCRIPTION": "Building block effect: mirror the clip left/right, top/bottom, into four, or into a spinning kaleidoscope, choosing which part of the clip lands in the centre",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Stylize", "Building Block"],
  "INPUTS": [
    { "NAME": "inputImage",  "TYPE": "image" },
    { "NAME": "mode",        "LABEL": "Mode",         "TYPE": "long", "DEFAULT": 3, "VALUES": [0, 1, 2, 3], "LABELS": ["Mirror Left/Right", "Mirror Top/Bottom", "Quad", "Kaleidoscope"] },
    { "NAME": "segments",    "LABEL": "Segments",     "TYPE": "float", "DEFAULT": 6.0, "MIN": 2.0,  "MAX": 16.0 },
    { "NAME": "angle",       "LABEL": "Angle",        "TYPE": "float", "DEFAULT": 0.0, "MIN": 0.0,  "MAX": 360.0 },
    { "NAME": "spin",        "LABEL": "Spin",         "TYPE": "float", "DEFAULT": 0.1, "MIN": -2.0, "MAX": 2.0 },
    { "NAME": "zoom",        "LABEL": "Zoom",         "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.25, "MAX": 4.0 },
    { "NAME": "source",      "LABEL": "Source Point", "TYPE": "point2D", "DEFAULT": [0.5, 0.5], "MIN": [0.0, 0.0], "MAX": [1.0, 1.0] },
    { "NAME": "sourceSpin",  "LABEL": "Source Orbit", "TYPE": "float", "DEFAULT": 0.0, "MIN": -2.0, "MAX": 2.0 },
    { "NAME": "orbitRadius", "LABEL": "Orbit Radius", "TYPE": "float", "DEFAULT": 0.0, "MIN": 0.0,  "MAX": 0.5 },
    { "NAME": "mirrorEdges", "LABEL": "Mirror Edges", "TYPE": "bool",  "DEFAULT": true }
  ]
}*/

#define TAU 6.28318530718
#define PI  3.14159265359

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

void main() {
    float aspect = RENDERSIZE.x / RENDERSIZE.y;
    vec2 uv = (isf_FragNormCoord - 0.5) * vec2(aspect, 1.0);
    uv = rot(angle * PI / 180.0 + TIME * spin) * uv;

    if (mode == 0) {
        uv.x = abs(uv.x);
    } else if (mode == 1) {
        uv.y = abs(uv.y);
    } else if (mode == 2) {
        uv = abs(uv);
    } else {
        float wedge = TAU / floor(segments + 0.5);
        float a = mod(atan(uv.y, uv.x), wedge);
        a = abs(a - 0.5 * wedge);
        uv = vec2(cos(a), sin(a)) * length(uv);
    }

    // The source point (optionally orbiting) is the part of the clip that lands in the centre
    vec2 src = source + orbitRadius * vec2(cos(TIME * sourceSpin), sin(TIME * sourceSpin));
    vec2 n = uv / zoom / vec2(aspect, 1.0) + src;
    if (mirrorEdges) n = 1.0 - abs(1.0 - mod(n, 2.0));

    gl_FragColor = IMG_NORM_PIXEL(inputImage, clamp(n, 0.0, 1.0));
}
