/*{
  "DESCRIPTION": "Building block effect: recolour the clip by its brightness: a three-colour gradient map, a rainbow map, a hue rotation or a solarize, with cycling, banding and posterizing",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Color Effect", "Building Block"],
  "INPUTS": [
    { "NAME": "inputImage", "TYPE": "image" },
    { "NAME": "mode",       "LABEL": "Mode",        "TYPE": "long", "DEFAULT": 0, "VALUES": [0, 1, 2, 3], "LABELS": ["Gradient Map", "Rainbow Map", "Hue Rotate", "Solarize"] },
    { "NAME": "shadow",     "LABEL": "Shadows",     "TYPE": "color", "DEFAULT": [0.05, 0.0, 0.2, 1.0] },
    { "NAME": "midtone",    "LABEL": "Midtones",    "TYPE": "color", "DEFAULT": [0.9, 0.1, 0.5, 1.0] },
    { "NAME": "highlight",  "LABEL": "Highlights",  "TYPE": "color", "DEFAULT": [1.0, 0.9, 0.4, 1.0] },
    { "NAME": "contrast",   "LABEL": "Contrast",    "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.0,  "MAX": 4.0 },
    { "NAME": "bands",      "LABEL": "Bands",       "TYPE": "float", "DEFAULT": 1.0, "MIN": 1.0,  "MAX": 12.0 },
    { "NAME": "cycle",      "LABEL": "Cycle",       "TYPE": "float", "DEFAULT": 0.1, "MIN": -2.0, "MAX": 2.0 },
    { "NAME": "offset",     "LABEL": "Offset",      "TYPE": "float", "DEFAULT": 0.0, "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "posterize",  "LABEL": "Posterize",   "TYPE": "float", "DEFAULT": 0.0, "MIN": 0.0,  "MAX": 16.0 },
    { "NAME": "threshold",  "LABEL": "Solarize At", "TYPE": "float", "DEFAULT": 0.5, "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "amount",     "LABEL": "Amount",      "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.0,  "MAX": 1.0 }
  ]
}*/

#define TAU 6.28318530718

vec3 hueRotate(vec3 c, float a) {
    vec3 k = vec3(0.57735);
    float ca = cos(a);
    return c * ca + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - ca);
}

float quantize(float x) {
    float levels = floor(posterize + 0.5);
    return levels >= 2.0 ? floor(x * levels * 0.9999) / (levels - 1.0) : x;
}

void main() {
    vec4 src = IMG_NORM_PIXEL(inputImage, isf_FragNormCoord);
    float l = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    l = clamp((l - 0.5) * contrast + 0.5, 0.0, 1.0);

    // Ping-pong rather than wrap, so banding and cycling never create hard seams
    float x = l * floor(bands + 0.5) + TIME * cycle + offset;
    float t = 1.0 - abs(fract(0.5 * x) * 2.0 - 1.0);
    t = quantize(t);

    vec3 col;
    if (mode == 1) {
        col = 0.5 + 0.5 * cos(TAU * (t + vec3(0.0, 0.33, 0.67)));
    } else if (mode == 2) {
        col = clamp(hueRotate(src.rgb, TAU * (offset + TIME * cycle)), 0.0, 1.0);
        col = vec3(quantize(col.r), quantize(col.g), quantize(col.b));
    } else if (mode == 3) {
        vec3 s = clamp((src.rgb - 0.5) * contrast + 0.5, 0.0, 1.0);
        col = mix(s, 1.0 - s, step(threshold, s));
        col = hueRotate(col, TAU * (offset + TIME * cycle));
    } else {
        col = t < 0.5 ? mix(shadow.rgb, midtone.rgb, 2.0 * t) : mix(midtone.rgb, highlight.rgb, 2.0 * t - 1.0);
    }

    gl_FragColor = vec4(mix(src.rgb, col, amount), src.a);
}
