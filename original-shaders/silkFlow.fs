/*{
  "DESCRIPTION": "Silky ribbons of colour: the plane is pushed through layered rotating sine currents, with a sheen that slides across the folds",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.35, "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "scale",      "LABEL": "Scale",       "TYPE": "float", "DEFAULT": 3.0,  "MIN": 0.5, "MAX": 10.0 },
    { "NAME": "flow",       "LABEL": "Flow",        "TYPE": "float", "DEFAULT": 0.8,  "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "sheen",      "LABEL": "Sheen",       "TYPE": "float", "DEFAULT": 0.6,  "MIN": 0.0, "MAX": 1.5 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.04, "MIN": 0.0, "MAX": 0.5 },
    { "NAME": "tint",       "LABEL": "Tint",        "TYPE": "color", "DEFAULT": [1.0, 1.0, 1.0, 1.0] }
  ]
}*/

#define TAU 6.28318530718

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.8, 0.55, 0.3)));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    vec2 p = uv * scale;
    for (int i = 1; i < 8; i++) {
        float fi = float(i);
        // Every layer is turned a little more, and the turn itself drifts slowly
        p = rot(0.4 + 0.05 * sin(0.11 * t + fi)) * p;
        p += flow / fi * vec2(sin(fi * p.y + t + 0.9 * fi),
                              cos(fi * p.x - 0.8 * t + 1.3 * fi));
    }

    float band = 0.5 + 0.5 * sin(p.x + p.y);
    vec3 col = palette(0.12 * (p.x - p.y) + 0.3 * band + TIME * colorCycle);
    col *= 0.45 + 0.55 * band;

    // Highlight that rides along the ribbon crests
    float shine = pow(abs(sin(0.5 * (p.x - p.y) + 0.6 * t)), 12.0);
    col += sheen * shine * vec3(1.0, 0.95, 0.9);

    col *= tint.rgb;
    col = 1.0 - exp(-1.5 * col);
    gl_FragColor = vec4(col, 1.0);
}
