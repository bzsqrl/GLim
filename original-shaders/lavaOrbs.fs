/*{
  "DESCRIPTION": "Eight gooey orbs orbit, merge and pull apart, their skins shimmering like soap film",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",       "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.4,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "size",        "LABEL": "Size",        "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.3,  "MAX": 2.0 },
    { "NAME": "orbit",       "LABEL": "Orbit",       "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "softness",    "LABEL": "Softness",    "TYPE": "float", "DEFAULT": 0.2,  "MIN": 0.02, "MAX": 1.0 },
    { "NAME": "iridescence", "LABEL": "Iridescence", "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,  "MAX": 3.0 },
    { "NAME": "rim",         "LABEL": "Rim Glow",    "TYPE": "float", "DEFAULT": 0.8,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "colorCycle",  "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.33, 0.67)));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    float f = 0.0;
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        vec2 c = 0.55 * orbit * vec2(1.5, 1.0) * vec2(sin((0.3 + 0.07 * fi) * t + 1.9 * fi),
                                                       cos((0.4 + 0.05 * fi) * t + 1.3 * fi));
        float r = 0.13 * size * (1.0 + 0.3 * sin(t + 2.0 * fi));
        vec2 d = uv - c;
        f += r * r / max(dot(d, d), 0.00001);
    }

    float inside = smoothstep(1.0 - 0.5 * softness, 1.0 + 0.5 * softness, f);

    // Thin-film colour: hue depends on how deep we are inside the field (0 at the skin, 1 deep inside)
    float depth = 1.0 - 1.0 / max(f, 1.0);
    vec3 film = palette(0.6 * iridescence * depth + 0.15 * uv.y + 0.1 * sin(3.0 * uv.x + t) + TIME * colorCycle);
    float shade = 0.55 + 0.45 * depth;

    vec3 bg = 0.12 * palette(0.5 + 0.2 * uv.x + TIME * colorCycle) * (1.0 - 0.5 * length(uv));
    vec3 col = mix(bg, film * shade, inside);
    col += rim * exp(-6.0 * abs(f - 1.0)) * palette(0.5 + 0.3 * depth + TIME * colorCycle) * 0.5;

    col = 1.0 - exp(-1.5 * col);
    gl_FragColor = vec4(col, 1.0);
}
