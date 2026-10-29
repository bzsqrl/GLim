/*{
  "DESCRIPTION": "A mirrored kaleidoscope of glowing rings whose folds open and close like a flower over time",
  "CREDIT": "GLim - License: CC0",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.4,  "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "segments",   "LABEL": "Segments",    "TYPE": "float", "DEFAULT": 6.0,  "MIN": 2.0, "MAX": 16.0 },
    { "NAME": "zoom",       "LABEL": "Zoom",        "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.3, "MAX": 3.0 },
    { "NAME": "morph",      "LABEL": "Morph",       "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "glow",       "LABEL": "Glow",        "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.2, "MAX": 3.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.08, "MIN": 0.0, "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.1, 0.4, 0.7)));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    // Kaleidoscope: fold the angle into one mirrored wedge
    vec2 p = rot(0.1 * t) * uv;
    float n = floor(segments + 0.5);
    float wedge = TAU / n;
    float a = mod(atan(p.y, p.x), wedge);
    a = abs(a - 0.5 * wedge);
    p = vec2(cos(a), sin(a)) * length(p) * zoom * 2.0;

    vec2 p0 = p;
    vec3 col = vec3(0.0);
    for (int i = 0; i < 4; i++) {
        float fi = float(i);
        // The fold offset breathes slowly, so the petals open and close
        p = abs(p) - 0.5 - 0.25 * morph * sin(0.3 * t + 1.3 * fi);
        p = rot(0.15 * t + 0.7 * fi) * p * 1.35;

        float d = length(p) * exp(-0.8 * length(p0));
        float ring = abs(sin(7.0 * d - 1.5 * t + fi)) / 7.0;
        float line = pow(0.012 * glow / max(ring, 0.0005), 1.25);
        col += palette(0.4 * length(p0) + 0.25 * fi + 0.2 * t + TIME * colorCycle) * line;
    }

    col *= smoothstep(1.6, 0.2, length(uv));
    col = 1.0 - exp(-col);
    gl_FragColor = vec4(col, 1.0);
}
