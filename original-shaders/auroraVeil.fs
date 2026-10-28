/*{
  "DESCRIPTION": "Six curtains of aurora light ripple and shimmer over a starry sky, each one drifting on its own currents",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "height",     "LABEL": "Height",      "TYPE": "float", "DEFAULT": -0.1, "MIN": -0.5, "MAX": 0.4 },
    { "NAME": "shimmer",    "LABEL": "Shimmer",     "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,  "MAX": 3.0 },
    { "NAME": "spread",     "LABEL": "Spread",      "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.2,  "MAX": 3.0 },
    { "NAME": "intensity",  "LABEL": "Intensity",   "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.2,  "MAX": 3.0 },
    { "NAME": "stars",      "LABEL": "Stars",       "TYPE": "float", "DEFAULT": 0.6,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.03, "MIN": 0.0,  "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i),                  hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.45, 0.25, 0.75)));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    // Night sky with a faint horizon glow
    vec3 col = mix(vec3(0.02, 0.04, 0.09), vec3(0.0, 0.0, 0.02), smoothstep(-0.5, 0.5, uv.y));
    vec2 sp = gl_FragCoord.xy / RENDERSIZE.y * 250.0;
    float star = step(0.995, hash(floor(sp))) * (0.5 + 0.5 * sin(3.0 * TIME + TAU * hash(floor(sp) + 7.0)));
    col += stars * star * vec3(0.8, 0.85, 1.0);

    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float x = uv.x * spread * (1.0 + 0.25 * fi) + 1.7 * fi;

        // The lower edge of the curtain: slow folds plus a noisy flutter
        float curve = height + 0.06 * fi
                    + 0.14 * sin(1.3 * x + 0.6 * t + fi)
                    + 0.07 * sin(3.1 * x - 0.9 * t + 2.0 * fi)
                    + 0.12 * (noise(vec2(0.8 * x, 0.2 * t + fi)) - 0.5);
        float dy = uv.y - curve;

        float mask = smoothstep(-0.025, 0.0, dy) * exp(-max(dy, 0.0) * (3.0 + fi));
        // Vertical rays sliding along the curtain
        float rays = 0.4 + 0.6 * noise(vec2(18.0 * x + 2.0 * shimmer * t, 0.5 * fi));
        rays *= 0.7 + 0.3 * sin(40.0 * x + 3.0 * shimmer * t);

        vec3 tint = palette(0.12 * fi + 0.05 * x + 0.6 * dy + TIME * colorCycle);
        col += 0.35 * intensity * tint * mask * rays;
    }

    col = 1.0 - exp(-1.6 * col);
    gl_FragColor = vec4(col, 1.0);
}
