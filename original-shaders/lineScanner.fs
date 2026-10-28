/*{
  "DESCRIPTION": "Building block: scrolling stripes, rings or a grid of lines, with bending waves, random widths and per-line strobing",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Building Block"],
  "INPUTS": [
    { "NAME": "mode",        "LABEL": "Mode",         "TYPE": "long", "DEFAULT": 0, "VALUES": [0, 1, 2], "LABELS": ["Lines", "Rings", "Grid"] },
    { "NAME": "count",       "LABEL": "Count",        "TYPE": "float", "DEFAULT": 8.0,  "MIN": 1.0,  "MAX": 64.0 },
    { "NAME": "width",       "LABEL": "Width",        "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.01, "MAX": 1.0 },
    { "NAME": "softness",    "LABEL": "Softness",     "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.5 },
    { "NAME": "angle",       "LABEL": "Angle",        "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 360.0 },
    { "NAME": "scroll",      "LABEL": "Scroll",       "TYPE": "float", "DEFAULT": 0.5,  "MIN": -4.0, "MAX": 4.0 },
    { "NAME": "bend",        "LABEL": "Bend",         "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "bendFreq",    "LABEL": "Bend Freq",    "TYPE": "float", "DEFAULT": 3.0,  "MIN": 0.0,  "MAX": 12.0 },
    { "NAME": "bendSpeed",   "LABEL": "Bend Speed",   "TYPE": "float", "DEFAULT": 1.0,  "MIN": -4.0, "MAX": 4.0 },
    { "NAME": "jitter",      "LABEL": "Width Jitter", "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "flicker",     "LABEL": "Flicker",      "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "flickerRate", "LABEL": "Flicker Rate", "TYPE": "float", "DEFAULT": 8.0,  "MIN": 0.5,  "MAX": 30.0 },
    { "NAME": "color1",      "LABEL": "Color A",      "TYPE": "color", "DEFAULT": [1.0, 1.0, 1.0, 1.0] },
    { "NAME": "color2",      "LABEL": "Color B",      "TYPE": "color", "DEFAULT": [1.0, 1.0, 1.0, 1.0] },
    { "NAME": "transparent", "LABEL": "Transparent",  "TYPE": "bool",  "DEFAULT": false }
  ]
}*/

#define PI 3.14159265359

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

// Brightness of the stripe pattern along coordinate v; side is the coordinate across it
vec2 stripes(float v, float side, float salt) {
    float aa = count * 1.5 / RENDERSIZE.y;
    v += 0.2 * bend * sin(side * bendFreq + TIME * bendSpeed);
    v = v * count - TIME * scroll;
    float id = floor(v);
    float d = abs(fract(v) - 0.5);
    float w = width * (1.0 - 0.8 * jitter * hash(vec2(id, salt)));
    float s = 1.0 - smoothstep(0.5 * w - 0.5 * softness - aa, 0.5 * w + 0.5 * softness + aa, d);
    // Strobe: each line is switched off at random, re-rolled flickerRate times a second
    if (flicker > 0.0 && hash(vec2(id + 17.0 * salt, floor(TIME * flickerRate))) < flicker) s = 0.0;
    return vec2(s, id);
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    vec2 p = rot(angle * PI / 180.0) * uv;

    vec2 s;
    if (mode == 1) {
        s = stripes(length(uv), atan(uv.y, uv.x) * 2.0, 0.0);
    } else if (mode == 2) {
        vec2 a = stripes(p.y, p.x, 0.0);
        vec2 b = stripes(p.x, p.y, 1.0);
        s = a.x > b.x ? a : vec2(b.x, b.y + 1.0);
    } else {
        s = stripes(p.y, p.x, 0.0);
    }

    vec3 col = mix(color1.rgb, color2.rgb, mod(s.y, 2.0));
    if (transparent) gl_FragColor = vec4(col, s.x);
    else gl_FragColor = vec4(col * s.x, 1.0);
}
