/*{
  "DESCRIPTION": "Building block: a grid of dots, squares, crosses, rings or diamonds whose size, spin and colour ride a travelling wave",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Building Block"],
  "INPUTS": [
    { "NAME": "shape",       "LABEL": "Shape",        "TYPE": "long", "DEFAULT": 0, "VALUES": [0, 1, 2, 3, 4], "LABELS": ["Dot", "Square", "Cross", "Ring", "Diamond"] },
    { "NAME": "wave",        "LABEL": "Wave",         "TYPE": "long", "DEFAULT": 0, "VALUES": [0, 1, 2, 3, 4], "LABELS": ["Radial", "Horizontal", "Diagonal", "Spiral", "Noise"] },
    { "NAME": "columns",     "LABEL": "Columns",      "TYPE": "float", "DEFAULT": 12.0, "MIN": 1.0,  "MAX": 64.0 },
    { "NAME": "size",        "LABEL": "Size",         "TYPE": "float", "DEFAULT": 0.35, "MIN": 0.0,  "MAX": 0.7 },
    { "NAME": "waveAmount",  "LABEL": "Wave Amount",  "TYPE": "float", "DEFAULT": 0.8,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "waveFreq",    "LABEL": "Wave Freq",    "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,  "MAX": 8.0 },
    { "NAME": "waveSpeed",   "LABEL": "Wave Speed",   "TYPE": "float", "DEFAULT": 1.0,  "MIN": -4.0, "MAX": 4.0 },
    { "NAME": "cellSpin",    "LABEL": "Cell Spin",    "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "gridAngle",   "LABEL": "Grid Angle",   "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 360.0 },
    { "NAME": "gridSpin",    "LABEL": "Grid Spin",    "TYPE": "float", "DEFAULT": 0.0,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "softness",    "LABEL": "Softness",     "TYPE": "float", "DEFAULT": 0.02, "MIN": 0.0,  "MAX": 0.3 },
    { "NAME": "color1",      "LABEL": "Low Color",    "TYPE": "color", "DEFAULT": [0.1, 0.4, 1.0, 1.0] },
    { "NAME": "color2",      "LABEL": "High Color",   "TYPE": "color", "DEFAULT": [1.0, 0.9, 0.3, 1.0] },
    { "NAME": "transparent", "LABEL": "Transparent",  "TYPE": "bool",  "DEFAULT": false }
  ]
}*/

#define TAU 6.28318530718
#define PI  3.14159265359

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i),                  hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

float box(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    vec2 p = rot(gridAngle * PI / 180.0 + TIME * gridSpin) * uv * columns;
    vec2 id = floor(p);
    vec2 f = fract(p) - 0.5;
    vec2 c = (id + 0.5) / columns;      // cell centre, in screen units

    // The wave decides each cell's value from its position
    float v;
    if (wave == 4) {
        v = noise(c * 3.0 * max(waveFreq, 0.1) + TIME * waveSpeed * vec2(0.3, 0.2));
    } else {
        float w;
        if (wave == 1)      w = c.x;
        else if (wave == 2) w = c.x + c.y;
        else if (wave == 3) w = atan(c.y, c.x) / TAU + length(c);
        else                w = length(c);
        v = 0.5 + 0.5 * sin(TAU * w * waveFreq - TIME * waveSpeed * 2.0);
    }

    float s = size * mix(1.0, v, waveAmount);
    f = rot(cellSpin * PI * (2.0 * v - 1.0)) * f;

    float d;
    if (shape == 1)      d = box(f, vec2(s));
    else if (shape == 2) d = min(box(f, vec2(s, 0.25 * s)), box(f, vec2(0.25 * s, s)));
    else if (shape == 3) d = abs(length(f) - s) - 0.2 * s;
    else if (shape == 4) d = (abs(f.x) + abs(f.y) - s) * 0.7071;
    else                 d = length(f) - s;

    float aa = columns * 1.5 / RENDERSIZE.y;
    float m = 1.0 - smoothstep(-aa - softness, aa + softness, d);
    if (s <= 0.0) m = 0.0;

    vec3 col = mix(color1.rgb, color2.rgb, v);
    if (transparent) gl_FragColor = vec4(col, m);
    else gl_FragColor = vec4(col * m, 1.0);
}
