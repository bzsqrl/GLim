/*{
  "DESCRIPTION": "Liquid colour that folds into itself: three layers of domain-warped noise drift at different speeds, so the shapes never repeat",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "scale",      "LABEL": "Scale",       "TYPE": "float", "DEFAULT": 2.5,  "MIN": 0.5, "MAX": 8.0 },
    { "NAME": "warp",       "LABEL": "Warp",        "TYPE": "float", "DEFAULT": 1.8,  "MIN": 0.0, "MAX": 4.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0, "MAX": 0.5 },
    { "NAME": "saturation", "LABEL": "Saturation",  "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0, "MAX": 1.5 }
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

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    mat2 r = mat2(0.8, 0.6, -0.6, 0.8);
    for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p = r * p * 2.03 + vec2(1.7, 9.2);
        a *= 0.5;
    }
    return v;
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.33, 0.67)));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y * scale;
    float t = TIME * speed;

    // Each warp layer moves at its own rate, so the combined shape keeps evolving
    vec2 q = vec2(fbm(uv + vec2(0.0, 0.31 * t)),
                  fbm(uv + vec2(5.2, 1.3) - 0.23 * t));
    vec2 r = vec2(fbm(uv + warp * q + vec2(1.7, 9.2) + 0.17 * t),
                  fbm(uv + warp * q + vec2(8.3, 2.8) - 0.13 * t));
    float f = fbm(uv + warp * r);

    vec3 col = palette(1.6 * f + 0.7 * length(q) - 0.4 * r.y + TIME * colorCycle);
    col *= 0.35 + 1.1 * f * f + 0.4 * length(r);
    col = mix(col, palette(f + 0.5 + TIME * colorCycle), 0.3 * smoothstep(0.6, 1.0, r.x));

    float luma = dot(col, vec3(0.299, 0.587, 0.114));
    col = mix(vec3(luma), col, saturation);
    col = 1.0 - exp(-1.4 * col);

    gl_FragColor = vec4(col, 1.0);
}
