/*{
  "DESCRIPTION": "Ripples from five wandering wave sources interfere into shifting moire contours with a chromatic split",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",        "TYPE": "float", "DEFAULT": 0.5,   "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "frequency",  "LABEL": "Frequency",    "TYPE": "float", "DEFAULT": 14.0,  "MIN": 2.0, "MAX": 40.0 },
    { "NAME": "bands",      "LABEL": "Bands",        "TYPE": "float", "DEFAULT": 1.5,   "MIN": 0.2, "MAX": 5.0 },
    { "NAME": "wander",     "LABEL": "Wander",       "TYPE": "float", "DEFAULT": 0.7,   "MIN": 0.0, "MAX": 1.5 },
    { "NAME": "chroma",     "LABEL": "Chroma Split", "TYPE": "float", "DEFAULT": 0.015, "MIN": 0.0, "MAX": 0.08 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle",  "TYPE": "float", "DEFAULT": 0.06,  "MIN": 0.0, "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

float field(vec2 p, float t) {
    float v = 0.0;
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        // Each source orbits on its own slightly detuned path
        vec2 c = wander * vec2(sin(0.37 * t * (1.0 + 0.21 * fi) + 1.7 * fi),
                               cos(0.29 * t * (1.0 + 0.13 * fi) + 2.9 * fi));
        v += sin(length(p - c) * frequency - 2.0 * t + fi);
    }
    return v / 5.0;
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    // Sample the field three times, pushed apart radially, one per colour channel
    vec2 dir = uv * chroma / max(length(uv), 0.001);
    vec3 v = vec3(field(uv - dir, t), field(uv, t), field(uv + dir, t));

    vec3 col = 0.5 + 0.5 * cos(TAU * (v * bands + vec3(0.0, 0.33, 0.67) + TIME * colorCycle));
    // Bright crests where the waves reinforce each other
    col += 0.35 * smoothstep(0.55, 1.0, abs(v));
    col *= 0.85 + 0.15 * sin(TAU * v.g * 3.0);

    gl_FragColor = vec4(col, 1.0);
}
