/*{
  "DESCRIPTION": "Building block: one geometric shape (polygon, star or circle) drawn as outline, fill and glow, repeated in concentric copies that spin, twist and pulse",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Building Block"],
  "INPUTS": [
    { "NAME": "sides",       "LABEL": "Sides",        "TYPE": "float", "DEFAULT": 6.0,  "MIN": 3.0,   "MAX": 12.0 },
    { "NAME": "star",        "LABEL": "Star",         "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,   "MAX": 0.9 },
    { "NAME": "roundness",   "LABEL": "Roundness",    "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,   "MAX": 1.0 },
    { "NAME": "size",        "LABEL": "Size",         "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.02,  "MAX": 1.0 },
    { "NAME": "thickness",   "LABEL": "Line Width",   "TYPE": "float", "DEFAULT": 0.02, "MIN": 0.002, "MAX": 0.3 },
    { "NAME": "fill",        "LABEL": "Fill",         "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,   "MAX": 1.0 },
    { "NAME": "glow",        "LABEL": "Glow",         "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,   "MAX": 2.0 },
    { "NAME": "copies",      "LABEL": "Copies",       "TYPE": "float", "DEFAULT": 4.0,  "MIN": 1.0,   "MAX": 12.0 },
    { "NAME": "spacing",     "LABEL": "Spacing",      "TYPE": "float", "DEFAULT": 0.08, "MIN": -0.2,  "MAX": 0.3 },
    { "NAME": "spin",        "LABEL": "Spin",         "TYPE": "float", "DEFAULT": 0.2,  "MIN": -3.0,  "MAX": 3.0 },
    { "NAME": "twist",       "LABEL": "Twist",        "TYPE": "float", "DEFAULT": 0.15,  "MIN": -1.0,  "MAX": 1.0 },
    { "NAME": "pulse",       "LABEL": "Pulse",        "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,   "MAX": 1.0 },
    { "NAME": "pulseRate",   "LABEL": "Pulse Rate",   "TYPE": "float", "DEFAULT": 2.0,  "MIN": 0.0,   "MAX": 10.0 },
    { "NAME": "center",      "LABEL": "Position",     "TYPE": "point2D", "DEFAULT": [0.5, 0.5], "MIN": [0.0, 0.0], "MAX": [1.0, 1.0] },
    { "NAME": "color1",      "LABEL": "Inner Color",  "TYPE": "color", "DEFAULT": [1.0, 0.3, 0.8, 1.0] },
    { "NAME": "color2",      "LABEL": "Outer Color",  "TYPE": "color", "DEFAULT": [0.2, 0.7, 1.0, 1.0] },
    { "NAME": "transparent", "LABEL": "Transparent",  "TYPE": "bool",  "DEFAULT": false }
  ]
}*/

#define TAU 6.28318530718
#define PI  3.14159265359

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

// Signed distance (approximate) to a polygon / star / circle of radius r
float shapeDist(vec2 p, float r) {
    float n = floor(sides + 0.5);
    float sector = TAU / n;
    float a = mod(atan(p.y, p.x) + 0.5 * sector, sector) - 0.5 * sector;
    float poly = r * cos(PI / n) / cos(a);
    poly *= 1.0 - star * abs(a) / (0.5 * sector);
    float edge = mix(poly, r, roundness);
    return (length(p) - edge) * mix(cos(a), 1.0, roundness);
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    vec2 c = (center - 0.5) * vec2(RENDERSIZE.x / RENDERSIZE.y, 1.0);
    vec2 p = uv - c;
    float aa = 1.5 / RENDERSIZE.y;

    float n = floor(copies + 0.5);
    vec3 col = vec3(0.0);
    float alpha = 0.0;
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        if (fi >= n) break;
        // Each copy is a step bigger, turned a little further, and pulses a little later
        float r = size + fi * spacing + 0.1 * pulse * size * sin(TIME * pulseRate - 0.8 * fi);
        if (r <= 0.0) continue;
        vec2 q = rot(TIME * spin + fi * twist) * p;
        float d = shapeDist(q, r);

        float line = 1.0 - smoothstep(0.5 * thickness - aa, 0.5 * thickness + aa, abs(d));
        float inside = fill * (1.0 - smoothstep(-aa, aa, d));
        float halo = glow * 0.6 * exp(-abs(d) * 40.0 / max(glow, 0.05));
        float a = clamp(line + inside + halo, 0.0, 1.0);

        vec3 tint = mix(color1.rgb, color2.rgb, n > 1.0 ? fi / (n - 1.0) : 0.0);
        col = max(col, tint * a);
        alpha = max(alpha, a);
    }

    if (transparent) gl_FragColor = vec4(col / max(alpha, 0.0001), alpha);
    else gl_FragColor = vec4(col, 1.0);
}
