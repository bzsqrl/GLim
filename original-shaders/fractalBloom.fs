/*{
  "DESCRIPTION": "An inversion fractal whose constant wanders on a slow orbit, so filigree flowers grow, dissolve and regrow",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.2,  "MIN": 0.0,  "MAX": 1.5 },
    { "NAME": "zoom",       "LABEL": "Zoom",        "TYPE": "float", "DEFAULT": 1.6,  "MIN": 0.3,  "MAX": 5.0 },
    { "NAME": "morph",      "LABEL": "Morph",       "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "spin",       "LABEL": "Spin",        "TYPE": "float", "DEFAULT": 0.3,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "contrast",   "LABEL": "Contrast",    "TYPE": "float", "DEFAULT": 2.0,  "MIN": 0.5,  "MAX": 6.0 },
    { "NAME": "brightness", "LABEL": "Brightness",  "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.2,  "MAX": 3.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.2, 0.45)));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    vec2 p = rot(spin * t) * uv * zoom;
    // Two detuned oscillators move the constant, so the shape seldom repeats
    vec2 c = vec2(-0.62, -0.48) + 0.14 * morph * vec2(sin(0.37 * t) + 0.4 * sin(0.91 * t),
                                                     cos(0.29 * t) + 0.4 * cos(0.73 * t));
    vec3 col = vec3(0.0);
    float prev = length(p);
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        p = abs(p) / max(dot(p, p), 0.001) + c;
        float l = length(p);
        float m = exp(-contrast * abs(l - prev));
        col += m * palette(0.15 * l + 0.06 * fi + 0.1 * t + TIME * colorCycle);
        prev = l;
    }

    col *= 0.3 * brightness;
    col = 1.0 - exp(-1.4 * col);
    gl_FragColor = vec4(col, 1.0);
}
