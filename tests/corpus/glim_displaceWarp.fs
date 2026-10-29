/*{
  "DESCRIPTION": "Building block effect: bend the clip with a moving displacement field (waves, noise, swirl, ripple or shattered cells), with optional RGB split along the bend",
  "CREDIT": "GLim - License: CC0",
  "ISFVSN": "2",
  "CATEGORIES": ["Distortion Effect", "Building Block"],
  "INPUTS": [
    { "NAME": "inputImage",  "TYPE": "image" },
    { "NAME": "field",       "LABEL": "Field",        "TYPE": "long", "DEFAULT": 0, "VALUES": [0, 1, 2, 3, 4], "LABELS": ["Waves", "Noise", "Swirl", "Ripple", "Shatter"] },
    { "NAME": "amount",      "LABEL": "Amount",       "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.5 },
    { "NAME": "scale",       "LABEL": "Scale",        "TYPE": "float", "DEFAULT": 6.0,  "MIN": 0.5,  "MAX": 40.0 },
    { "NAME": "speed",       "LABEL": "Speed",        "TYPE": "float", "DEFAULT": 1.0,  "MIN": -4.0, "MAX": 4.0 },
    { "NAME": "angle",       "LABEL": "Wave Angle",   "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 360.0 },
    { "NAME": "center",      "LABEL": "Center",       "TYPE": "point2D", "DEFAULT": [0.5, 0.5], "MIN": [0.0, 0.0], "MAX": [1.0, 1.0] },
    { "NAME": "chroma",      "LABEL": "RGB Split",    "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "mirrorEdges", "LABEL": "Mirror Edges", "TYPE": "bool",  "DEFAULT": true }
  ]
}*/

#define TAU 6.28318530718
#define PI  3.14159265359

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

// Nearest-cell id for the shatter field
vec2 cellId(vec2 p) {
    vec2 n = floor(p);
    vec2 f = fract(p);
    vec2 best = n;
    float md = 8.0;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            float d = length(g + hash2(n + g) - f);
            if (d < md) {
                md = d;
                best = n + g;
            }
        }
    }
    return best;
}

vec2 mirrorWrap(vec2 n) {
    return mirrorEdges ? 1.0 - abs(1.0 - mod(n, 2.0)) : clamp(n, 0.0, 1.0);
}

void main() {
    float aspect = RENDERSIZE.x / RENDERSIZE.y;
    vec2 n = isf_FragNormCoord;
    vec2 p = (n - 0.5) * vec2(aspect, 1.0);
    vec2 q = p - (center - 0.5) * vec2(aspect, 1.0);

    // d: displacement direction and strength, roughly -1..1, in screen units
    vec2 d;
    if (field == 1) {
        vec2 s = p * scale * 0.3;
        d = 2.0 * vec2(noise(s + TIME * speed * vec2(0.3, 0.1)),
                       noise(s + vec2(5.2, 1.3) - TIME * speed * vec2(0.1, 0.3))) - 1.0;
    } else if (field == 2) {
        float r = length(q);
        d = vec2(-q.y, q.x) / max(r, 0.001) * exp(-r * scale * 0.3) * 3.0 * sin(TIME * speed);
    } else if (field == 3) {
        float r = length(q);
        d = q / max(r, 0.001) * sin(r * scale * 4.0 - TIME * speed * 4.0);
    } else if (field == 4) {
        vec2 id = cellId(p * scale * 0.5);
        float h = hash(id);
        d = (2.0 * hash2(id + 3.7) - 1.0) * (0.5 + 0.5 * sin(TIME * speed + TAU * h));
    } else {
        float a = angle * PI / 180.0;
        vec2 dir = vec2(cos(a), sin(a));
        d = vec2(-dir.y, dir.x) * sin(dot(p, dir) * scale * 2.0 + TIME * speed * 2.0);
    }

    vec2 off = amount * d / vec2(aspect, 1.0);
    vec4 g = IMG_NORM_PIXEL(inputImage, mirrorWrap(n + off));
    vec4 col = g;
    if (chroma > 0.0) {
        col.r = IMG_NORM_PIXEL(inputImage, mirrorWrap(n + off * (1.0 + chroma))).r;
        col.b = IMG_NORM_PIXEL(inputImage, mirrorWrap(n + off * (1.0 - chroma))).b;
    }
    gl_FragColor = col;
}
