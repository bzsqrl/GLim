/*{
  "DESCRIPTION": "Fractal feedback: every frame the last one is folded into a kaleidoscope, scaled and offset, so a few moving rings are copied into ever smaller echoes that form a morphing fractal mandala",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",    "LABEL": "Speed",     "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "segments", "LABEL": "Segments",  "TYPE": "float", "DEFAULT": 6.0,  "MIN": 2.0,  "MAX": 12.0 },
    { "NAME": "zoom",     "LABEL": "Zoom",      "TYPE": "float", "DEFAULT": 1.6,  "MIN": 1.1,  "MAX": 3.0 },
    { "NAME": "spin",     "LABEL": "Spin",      "TYPE": "float", "DEFAULT": 0.2,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "shift",    "LABEL": "Shift",     "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 1.2 },
    { "NAME": "decay",    "LABEL": "Depth",     "TYPE": "float", "DEFAULT": 0.9,  "MIN": 0.5,  "MAX": 0.97 },
    { "NAME": "hueDrift", "LABEL": "Hue Drift", "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "reset",    "LABEL": "Clear",     "TYPE": "event" }
  ],
  "PASSES": [
    { "TARGET": "echo", "PERSISTENT": true, "FLOAT": true },
    {}
  ]
}*/

#define TAU 6.28318530718

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.2, 0.5)));
}

// Rotate a colour around the grey axis
vec3 hueRotate(vec3 c, float a) {
    vec3 k = vec3(0.57735);
    float ca = cos(a);
    return c * ca + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - ca);
}

void main() {
    vec2 res = RENDERSIZE.xy;
    if (PASSINDEX == 0) {
        vec2 uv = (gl_FragCoord.xy - 0.5 * res) / res.y;
        float t = TIME * speed;

        // One step of an iterated function system per frame: fold into a mirrored wedge,
        // turn, enlarge and offset. Each frame adds one more generation of smaller copies.
        vec2 q = uv;
        float wedge = TAU / floor(segments + 0.5);
        float a = mod(atan(q.y, q.x), wedge);
        a = abs(a - 0.5 * wedge);
        q = vec2(cos(a), sin(a)) * length(q);
        q = rot(0.4 * sin(0.1 * t) + 0.3 * spin * t) * q;
        q = q * zoom - vec2(shift * (1.0 + 0.25 * sin(0.13 * t)), 0.1 * sin(0.17 * t));

        vec2 coord = q * res.y / res + 0.5;
        vec3 prev = IMG_NORM_PIXEL(echo, coord).rgb;
        prev *= step(abs(coord.x - 0.5), 0.5) * step(abs(coord.y - 0.5), 0.5);
        // Every generation is a little dimmer and shifted in hue, so depth reads as colour
        prev = hueRotate(prev, 0.6 * hueDrift) * decay;

        // Seeds: a wandering, breathing ring and two orbiting sparks
        vec2 centre = 0.12 * vec2(sin(0.7 * t), cos(0.9 * t));
        float rr = 0.3 + 0.08 * sin(1.3 * t);
        float ring = smoothstep(0.035, 0.0, abs(length(uv - centre) - rr));
        float sparks = 0.0;
        for (int i = 0; i < 2; i++) {
            float fi = float(i);
            vec2 pos = 0.35 * vec2(sin((1.1 + 0.4 * fi) * t + 3.0 * fi), cos((0.8 + 0.5 * fi) * t));
            sparks += smoothstep(0.07, 0.0, length(uv - pos));
        }
        vec3 seed = ring * palette(0.1 * t) + sparks * palette(0.1 * t + 0.5);

        vec3 col = prev + seed;
        if (reset || FRAMEINDEX < 2) col = vec3(0.0);
        gl_FragColor = vec4(clamp(col, 0.0, 4.0), 1.0);
    } else {
        vec3 col = IMG_NORM_PIXEL(echo, isf_FragNormCoord).rgb;
        col = 1.0 - exp(-2.0 * col);
        gl_FragColor = vec4(col, 1.0);
    }
}
