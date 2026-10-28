/*{
  "DESCRIPTION": "Ink dropped into moving water: wandering emitters release colour that is carried, stretched and marbled by a swirling flow field",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",       "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.4,   "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "flow",        "LABEL": "Flow",        "TYPE": "float", "DEFAULT": 1.0,   "MIN": 0.0,  "MAX": 3.0 },
    { "NAME": "turbulence",  "LABEL": "Turbulence",  "TYPE": "float", "DEFAULT": 2.5,   "MIN": 0.5,  "MAX": 8.0 },
    { "NAME": "swirl",       "LABEL": "Swirl",       "TYPE": "float", "DEFAULT": 0.3,   "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "inject",      "LABEL": "Ink",         "TYPE": "float", "DEFAULT": 0.6,   "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "persistence", "LABEL": "Persistence", "TYPE": "float", "DEFAULT": 0.999, "MIN": 0.95, "MAX": 1.0 },
    { "NAME": "colorCycle",  "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05,  "MIN": 0.0,  "MAX": 0.5 },
    { "NAME": "reset",       "LABEL": "Clear",       "TYPE": "event" }
  ],
  "PASSES": [
    { "TARGET": "ink", "PERSISTENT": true, "FLOAT": true },
    {}
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
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.1, 0.35, 0.6)));
}

float stream(vec2 p, float t) {
    return noise(p + vec2(0.0, 0.3 * t)) + 0.5 * noise(2.03 * p - vec2(0.2 * t, 0.0));
}

// Curl of a moving noise field: swirls without sources or sinks, like water
vec2 velocity(vec2 p, float t) {
    float e = 0.01;
    vec2 q = p * turbulence;
    float dx = stream(q + vec2(e, 0.0), t) - stream(q - vec2(e, 0.0), t);
    float dy = stream(q + vec2(0.0, e), t) - stream(q - vec2(0.0, e), t);
    vec2 curl = vec2(dy, -dx) / (2.0 * e);
    return 0.15 * curl + 0.5 * swirl * vec2(-p.y, p.x);
}

void main() {
    vec2 res = RENDERSIZE.xy;
    if (PASSINDEX == 0) {
        vec2 uv = (gl_FragCoord.xy - 0.5 * res) / res.y;
        float t = TIME * speed;
        float step = clamp(TIMEDELTA * 60.0, 0.0, 4.0);

        // Look upstream: whatever ink was there last frame flows here now
        vec2 back = uv - 0.02 * flow * step * velocity(uv, t);
        vec2 coord = back * res.y / res + 0.5;
        vec3 col = IMG_NORM_PIXEL(ink, coord).rgb * pow(persistence, step);

        for (int i = 0; i < 4; i++) {
            float fi = float(i);
            vec2 pos = vec2(0.75 * sin((0.23 + 0.06 * fi) * t + 1.7 * fi),
                            0.38 * cos((0.31 + 0.05 * fi) * t + 2.6 * fi));
            float m = inject * smoothstep(0.09, 0.02, length(uv - pos));
            col = mix(col, palette(0.25 * fi + 0.05 * t + TIME * colorCycle), clamp(0.5 * m * step, 0.0, 1.0));
        }

        if (reset || FRAMEINDEX < 2) col = vec3(0.0);
        gl_FragColor = vec4(col, 1.0);
    } else {
        vec3 col = IMG_NORM_PIXEL(ink, isf_FragNormCoord).rgb;
        col = mix(vec3(0.02, 0.02, 0.04), col, smoothstep(0.0, 0.3, max(col.r, max(col.g, col.b))));
        gl_FragColor = vec4(col, 1.0);
    }
}
