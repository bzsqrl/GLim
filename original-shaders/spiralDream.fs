/*{
  "DESCRIPTION": "An endless log-polar spiral tunnel: two counter-turning spirals weave a lattice that zooms in forever and slowly re-twists itself",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.4,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "arms",       "LABEL": "Arms",        "TYPE": "float", "DEFAULT": 5.0,  "MIN": 1.0,  "MAX": 12.0 },
    { "NAME": "twist",      "LABEL": "Twist",       "TYPE": "float", "DEFAULT": 4.0,  "MIN": 0.0,  "MAX": 10.0 },
    { "NAME": "wobble",     "LABEL": "Wobble",      "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "softness",   "LABEL": "Softness",    "TYPE": "float", "DEFAULT": 0.35, "MIN": 0.02, "MAX": 1.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.1,  "MIN": 0.0,  "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * x * vec3(1.0, 0.9, 0.8) + vec3(0.0, 1.0, 2.0));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    float r = length(uv);
    float a = atan(uv.y, uv.x);
    // Log radius makes every ring look the same size: subtracting time zooms inward forever
    float lr = log(max(r, 1e-4)) - t;
    lr += 0.3 * wobble * sin(3.0 * a + 2.0 * lr + 0.7 * t);

    // The twist drifts on its own slow cycle, so the lattice re-forms over time
    float tw = twist * (1.0 + 0.35 * sin(0.17 * t));
    float n = floor(arms + 0.5);
    float s1 = sin(n * a + tw * lr);
    float s2 = sin((n + 1.0) * a - 1.3 * tw * lr + 1.5 * t);

    float cells = s1 * s2;
    float edge = smoothstep(softness, 0.0, abs(cells));
    float fill = 0.5 + 0.5 * cells;

    vec3 col = palette(0.15 * lr + 0.25 * fill + TIME * colorCycle) * (0.35 + 0.65 * fill);
    col += 0.8 * edge * palette(0.15 * lr + 0.5 + TIME * colorCycle);

    // Fade the centre to black so the singularity becomes a vanishing point
    col *= smoothstep(0.0, 0.25, r);
    gl_FragColor = vec4(col, 1.0);
}
