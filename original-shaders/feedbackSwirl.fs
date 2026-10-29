/*{
  "DESCRIPTION": "Video-feedback swirl: glowing seeds paint into a buffer that keeps zooming, spinning and shifting hue, leaving trails that never repeat",
  "CREDIT": "GLim - License: CC0",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",    "LABEL": "Speed",     "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "zoom",     "LABEL": "Zoom",      "TYPE": "float", "DEFAULT": 0.6,  "MIN": -1.0, "MAX": 2.0 },
    { "NAME": "spin",     "LABEL": "Spin",      "TYPE": "float", "DEFAULT": 0.3,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "warp",     "LABEL": "Warp",      "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "decay",    "LABEL": "Trail",     "TYPE": "float", "DEFAULT": 0.988, "MIN": 0.8,  "MAX": 0.998 },
    { "NAME": "hueDrift", "LABEL": "Hue Drift", "TYPE": "float", "DEFAULT": 0.3,   "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "seedSize", "LABEL": "Seed Size", "TYPE": "float", "DEFAULT": 0.05,  "MIN": 0.01, "MAX": 0.15 },
    { "NAME": "reset",    "LABEL": "Clear",     "TYPE": "event" }
  ],
  "PASSES": [
    { "TARGET": "trails", "PERSISTENT": true, "FLOAT": true },
    {}
  ]
}*/

#define TAU 6.28318530718

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.33, 0.67)));
}

// Rotate a colour around the grey axis
vec3 hueRotate(vec3 c, float a) {
    vec3 k = vec3(0.57735);
    float ca = cos(a);
    return c * ca + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - ca);
}

void main() {
    if (PASSINDEX == 0) {
        vec2 res = RENDERSIZE.xy;
        vec2 uv = (gl_FragCoord.xy - 0.5 * res) / res.y;
        float t = TIME * speed;
        // Scale the per-frame steps by frame time so the motion is the same at any frame rate
        float step = clamp(TIMEDELTA * 60.0, 0.0, 4.0);

        // Pull the previous frame inward, turn it and bend it a little
        float ang = 0.01 * spin * step;
        float c = cos(ang), s = sin(ang);
        vec2 q = mat2(c, s, -s, c) * uv;
        q *= 1.0 - 0.01 * zoom * step;
        q += 0.008 * warp * step * vec2(sin(6.0 * q.y + t), cos(6.0 * q.x - 0.8 * t));
        vec2 coord = q * res.y / res + 0.5;

        vec3 prev = IMG_NORM_PIXEL(trails, coord).rgb;
        prev = hueRotate(prev, 0.03 * hueDrift * step) * pow(decay, step);
        if (reset || FRAMEINDEX < 2) prev = vec3(0.0);

        // Four seeds trace Lissajous paths and paint fresh colour
        vec3 seed = vec3(0.0);
        for (int i = 0; i < 4; i++) {
            float fi = float(i);
            vec2 pos = 0.4 * vec2(sin((0.7 + 0.2 * fi) * t + 2.1 * fi), cos((0.5 + 0.3 * fi) * t + 1.3 * fi));
            float d = length(uv - pos);
            seed += smoothstep(seedSize, 0.3 * seedSize, d) * palette(0.25 * fi + 0.1 * t);
        }

        vec3 col = prev + 0.5 * seed;
        gl_FragColor = vec4(clamp(col, 0.0, 4.0), 1.0);
    } else {
        vec3 col = IMG_NORM_PIXEL(trails, isf_FragNormCoord).rgb;
        col = 1.0 - exp(-1.5 * col);
        gl_FragColor = vec4(col, 1.0);
    }
}
