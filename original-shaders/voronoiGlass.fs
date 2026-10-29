/*{
  "DESCRIPTION": "Stained glass that won't sit still: Voronoi cells drift and swap shapes, lit from behind with glowing lead lines",
  "CREDIT": "GLim - License: CC0",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.4,  "MIN": 0.0,   "MAX": 2.0 },
    { "NAME": "scale",      "LABEL": "Scale",       "TYPE": "float", "DEFAULT": 4.0,  "MIN": 1.0,   "MAX": 15.0 },
    { "NAME": "jitter",     "LABEL": "Jitter",      "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,   "MAX": 1.0 },
    { "NAME": "edge",       "LABEL": "Lead Width",  "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.005, "MAX": 0.2 },
    { "NAME": "glow",       "LABEL": "Glow",        "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,   "MAX": 3.0 },
    { "NAME": "swirl",      "LABEL": "Swirl",       "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,   "MAX": 1.5 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,   "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.33, 0.67)));
}

vec2 cellPoint(vec2 cell, float t) {
    vec2 o = hash2(cell);
    return 0.5 + 0.5 * jitter * sin(t + TAU * o);
}

// x: distance to the nearest cell border, yz: id of the nearest cell
vec3 voronoi(vec2 x, float t) {
    vec2 n = floor(x);
    vec2 f = fract(x);
    vec2 mg = vec2(0.0);
    vec2 mr = vec2(0.0);
    float md = 8.0;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 r = g + cellPoint(n + g, t) - f;
            float d = dot(r, r);
            if (d < md) {
                md = d;
                mr = r;
                mg = g;
            }
        }
    }
    md = 8.0;
    for (int j = -2; j <= 2; j++) {
        for (int i = -2; i <= 2; i++) {
            vec2 g = mg + vec2(float(i), float(j));
            vec2 r = g + cellPoint(n + g, t) - f;
            if (dot(mr - r, mr - r) > 0.00001) {
                md = min(md, dot(0.5 * (mr + r), normalize(r - mr)));
            }
        }
    }
    return vec3(md, n + mg);
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    // A gentle swirl bends the whole window so the cell borders curve over time
    vec2 p = uv * scale;
    p += swirl * vec2(sin(0.7 * p.y + 0.5 * t), cos(0.6 * p.x - 0.4 * t));

    vec3 v = voronoi(p, t);
    vec2 h = hash2(v.yz);

    vec3 glass = palette(h.x + 0.1 * t + TIME * colorCycle);
    glass *= 0.45 + 0.55 * smoothstep(0.0, 0.45, v.x);
    glass *= 0.75 + 0.25 * sin(TAU * h.y + 1.3 * t);

    float lead = smoothstep(edge, 0.5 * edge, v.x);
    vec3 col = glass * (1.0 - 0.92 * lead);
    col += glow * 0.35 * exp(-12.0 * v.x) * palette(h.x + 0.5 + TIME * colorCycle);

    col = 1.0 - exp(-1.5 * col);
    gl_FragColor = vec4(col, 1.0);
}
