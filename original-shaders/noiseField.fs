/*{
  "DESCRIPTION": "Building block: a tunable noise texture (smooth, ridged, turbulent or cellular) that drifts and evolves; threshold it into a mask or use it as a soft wash",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Building Block"],
  "INPUTS": [
    { "NAME": "noiseType",   "LABEL": "Type",         "TYPE": "long", "DEFAULT": 0, "VALUES": [0, 1, 2, 3], "LABELS": ["Smooth", "Ridged", "Turbulent", "Cells"] },
    { "NAME": "scale",       "LABEL": "Scale",        "TYPE": "float", "DEFAULT": 3.0,  "MIN": 0.2,  "MAX": 20.0 },
    { "NAME": "octaves",     "LABEL": "Detail",       "TYPE": "float", "DEFAULT": 4.0,  "MIN": 1.0,  "MAX": 8.0 },
    { "NAME": "warp",        "LABEL": "Warp",         "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 3.0 },
    { "NAME": "driftX",      "LABEL": "Drift X",      "TYPE": "float", "DEFAULT": 0.1,  "MIN": -2.0, "MAX": 2.0 },
    { "NAME": "driftY",      "LABEL": "Drift Y",      "TYPE": "float", "DEFAULT": 0.05, "MIN": -2.0, "MAX": 2.0 },
    { "NAME": "evolve",      "LABEL": "Evolve",       "TYPE": "float", "DEFAULT": 0.2,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "contrast",    "LABEL": "Contrast",     "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,  "MAX": 4.0 },
    { "NAME": "brightness",  "LABEL": "Brightness",   "TYPE": "float", "DEFAULT": 0.0,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "threshold",   "LABEL": "Threshold",    "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "edge",        "LABEL": "Edge Softness","TYPE": "float", "DEFAULT": 0.1,  "MIN": 0.0,  "MAX": 0.5 },
    { "NAME": "invert",      "LABEL": "Invert",       "TYPE": "bool",  "DEFAULT": false },
    { "NAME": "color1",      "LABEL": "High Color",   "TYPE": "color", "DEFAULT": [1.0, 1.0, 1.0, 1.0] },
    { "NAME": "color2",      "LABEL": "Low Color",    "TYPE": "color", "DEFAULT": [0.0, 0.0, 0.0, 1.0] },
    { "NAME": "transparent", "LABEL": "Transparent",  "TYPE": "bool",  "DEFAULT": false }
  ]
}*/

#define TAU 6.28318530718

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i),                  hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// Distance to the nearest of a field of slowly orbiting points
float cells(vec2 p) {
    vec2 n = floor(p);
    vec2 f = fract(p);
    float md = 8.0;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 o = 0.5 + 0.45 * sin(TIME * evolve + TAU * hash2(n + g));
            md = min(md, length(g + o - f));
        }
    }
    return md;
}

// One octave of the chosen noise type, 0..1
float layer(vec2 p) {
    if (noiseType == 3) return clamp(cells(p), 0.0, 1.0);
    float v = noise(p);
    if (noiseType == 1) return pow(1.0 - abs(2.0 * v - 1.0), 2.0);
    if (noiseType == 2) return abs(2.0 * v - 1.0);
    return v;
}

float field(vec2 p) {
    float v = 0.0;
    float amp = 0.5;
    float total = 0.0;
    mat2 r = mat2(0.8, 0.6, -0.6, 0.8);
    float n = floor(octaves + 0.5);
    for (int i = 0; i < 8; i++) {
        if (float(i) >= n) break;
        // Each octave slides its own way, so the texture evolves instead of just scrolling
        vec2 e = TIME * evolve * 0.3 * vec2(cos(1.7 * float(i)), sin(1.7 * float(i)));
        v += amp * layer(p + e);
        total += amp;
        p = r * p * 2.02 + vec2(1.7, 9.2);
        amp *= 0.5;
    }
    return v / total;
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    vec2 p = uv * scale + vec2(TIME * driftX, TIME * driftY);
    if (warp > 0.0) {
        p += warp * vec2(field(p + vec2(3.1, 7.4)), field(p + vec2(8.3, 2.8))) - 0.5 * warp;
    }

    float v = field(p);
    v = clamp((v - 0.5) * contrast + 0.5 + brightness, 0.0, 1.0);
    if (threshold > 0.0) v = smoothstep(threshold - 0.5 * edge - 0.001, threshold + 0.5 * edge + 0.001, v);
    if (invert) v = 1.0 - v;

    if (transparent) gl_FragColor = vec4(color1.rgb, v);
    else gl_FragColor = vec4(mix(color2.rgb, color1.rgb, v), 1.0);
}
