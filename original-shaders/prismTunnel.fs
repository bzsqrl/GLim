/*{
  "DESCRIPTION": "Fly down an endless tunnel that morphs between round and square, its striped walls twisting and the vanishing point swaying",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "shape",      "LABEL": "Round/Square","TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "twist",      "LABEL": "Twist",       "TYPE": "float", "DEFAULT": 0.5,  "MIN": -2.0, "MAX": 2.0 },
    { "NAME": "stripes",    "LABEL": "Stripes",     "TYPE": "float", "DEFAULT": 8.0,  "MIN": 2.0,  "MAX": 24.0 },
    { "NAME": "rings",      "LABEL": "Rings",       "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.2,  "MAX": 4.0 },
    { "NAME": "wobble",     "LABEL": "Wobble",      "TYPE": "float", "DEFAULT": 0.4,  "MIN": 0.0,  "MAX": 1.5 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718
#define PI  3.14159265359

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.9, 0.6, 0.2)));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    // Sway the vanishing point
    uv -= 0.12 * wobble * vec2(sin(0.7 * t), cos(0.53 * t));

    float r = mix(length(uv), max(abs(uv.x), abs(uv.y)), shape);
    float a = atan(uv.y, uv.x) / TAU;
    float z = 1.0 / max(r, 0.001) + 2.0 * t;

    float n = floor(stripes + 0.5);
    float u = a + 0.05 * twist * z + 0.04 * wobble * sin(0.5 * z + t);
    float walls = sin(TAU * n * u);
    float bands = sin(PI * rings * z);
    float tiles = walls * bands;

    vec3 col = palette(0.02 * z + 0.15 * walls + TIME * colorCycle);
    col *= 0.3 + 0.7 * smoothstep(-0.3, 0.3, tiles);
    col += 0.5 * smoothstep(0.08, 0.0, abs(tiles)) * palette(0.02 * z + 0.5 + TIME * colorCycle);

    // Darken towards the far end so the tunnel has depth
    col *= smoothstep(0.0, 0.3, r);
    col = 1.0 - exp(-1.5 * col);
    gl_FragColor = vec4(col, 1.0);
}
