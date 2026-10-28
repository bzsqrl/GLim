/*{
  "DESCRIPTION": "Three grids of overlapping circles turn against each other, weaving flower-of-life patterns and moire interference",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.3,   "MIN": 0.0,   "MAX": 2.0 },
    { "NAME": "scale",      "LABEL": "Scale",       "TYPE": "float", "DEFAULT": 4.0,   "MIN": 1.0,   "MAX": 15.0 },
    { "NAME": "lineWidth",  "LABEL": "Line Width",  "TYPE": "float", "DEFAULT": 0.035, "MIN": 0.005, "MAX": 0.15 },
    { "NAME": "spread",     "LABEL": "Spread",      "TYPE": "float", "DEFAULT": 0.5,   "MIN": 0.0,   "MAX": 1.5 },
    { "NAME": "breathe",    "LABEL": "Breathe",     "TYPE": "float", "DEFAULT": 0.15,  "MIN": 0.0,   "MAX": 0.4 },
    { "NAME": "ripples",    "LABEL": "Ripples",     "TYPE": "float", "DEFAULT": 0.3,   "MIN": 0.0,   "MAX": 1.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05,  "MIN": 0.0,   "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.33, 0.67)));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    vec3 col = vec3(0.0);
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        // Each layer has its own angle, size and drift direction
        vec2 p = rot(spread * fi + 0.1 * (fi - 1.0) * t) * uv;
        p = p * scale * (1.0 + 0.15 * fi) + 0.2 * t * vec2(cos(2.1 * fi), sin(2.1 * fi));
        vec2 f = fract(p) - 0.5;

        float rr = 0.5 * (1.0 - breathe + breathe * sin(t + 2.0 * fi));
        float dCentre = length(f);
        float dCorner = length(abs(f) - 0.5);
        float ring = min(abs(dCentre - rr), abs(dCorner - rr));

        float line = smoothstep(lineWidth, 0.0, ring);
        float wave = 0.5 + 0.5 * cos(30.0 * min(dCentre, dCorner) - 2.0 * t);

        vec3 tint = palette(0.33 * fi + 0.3 * dCentre + 0.1 * t + TIME * colorCycle);
        col += tint * (line + ripples * 0.15 * wave);
    }

    col *= smoothstep(1.5, 0.3, length(uv));
    col = 1.0 - exp(-1.2 * col);
    gl_FragColor = vec4(col, 1.0);
}
