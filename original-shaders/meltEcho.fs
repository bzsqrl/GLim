/*{
  "DESCRIPTION": "Effect: the clip leaves hue-shifting echoes that melt along their own contours, drip and swirl, while fresh frames keep feeding in",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Stylize", "Psychedelic"],
  "INPUTS": [
    { "NAME": "inputImage",  "TYPE": "image" },
    { "NAME": "melt",        "LABEL": "Melt",        "TYPE": "float", "DEFAULT": 0.6,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "drip",        "LABEL": "Drip",        "TYPE": "float", "DEFAULT": 0.5,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "swirl",       "LABEL": "Swirl",       "TYPE": "float", "DEFAULT": 0.3,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "persistence", "LABEL": "Trail",       "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.8,  "MAX": 1.0 },
    { "NAME": "hueShift",    "LABEL": "Hue Shift",   "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "freshness",   "LABEL": "Fresh Frame", "TYPE": "float", "DEFAULT": 0.015, "MIN": 0.005, "MAX": 1.0 },
    { "NAME": "dry",         "LABEL": "Dry Mix",     "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "reset",       "LABEL": "Clear",       "TYPE": "event" }
  ],
  "PASSES": [
    { "TARGET": "echoBuf", "PERSISTENT": true, "FLOAT": true },
    {}
  ]
}*/

float luma(vec3 c) {
    return dot(c, vec3(0.299, 0.587, 0.114));
}

// Rotate a colour around the grey axis
vec3 hueRotate(vec3 c, float a) {
    vec3 k = vec3(0.57735);
    float ca = cos(a);
    return c * ca + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - ca);
}

void main() {
    vec2 n = isf_FragNormCoord;
    vec3 src = IMG_NORM_PIXEL(inputImage, n).rgb;
    if (PASSINDEX == 0) {
        vec2 res = RENDERSIZE.xy;
        float step = clamp(TIMEDELTA * 60.0, 0.0, 4.0);

        // Slide the echoes along their own brightness contours, so shapes smear sideways into ribbons
        vec2 e = 2.0 / res;
        float lx = luma(IMG_NORM_PIXEL(echoBuf, n + vec2(e.x, 0.0)).rgb) - luma(IMG_NORM_PIXEL(echoBuf, n - vec2(e.x, 0.0)).rgb);
        float ly = luma(IMG_NORM_PIXEL(echoBuf, n + vec2(0.0, e.y)).rgb) - luma(IMG_NORM_PIXEL(echoBuf, n - vec2(0.0, e.y)).rgb);
        vec2 disp = 0.15 * melt * vec2(-ly, lx);

        vec2 c = (n - 0.5) * vec2(res.x / res.y, 1.0);
        disp += 0.004 * drip * vec2(0.0, 1.0);
        disp += 0.006 * swirl * vec2(-c.y, c.x) * vec2(res.y / res.x, 1.0);

        vec3 prev = IMG_NORM_PIXEL(echoBuf, n + disp * step).rgb;
        prev = hueRotate(prev, 0.05 * hueShift * step) * pow(persistence, step);

        float fresh = 1.0 - pow(1.0 - freshness, step);
        vec3 col = mix(prev, src, fresh);
        if (reset || FRAMEINDEX < 2) col = src;
        gl_FragColor = vec4(clamp(col, 0.0, 2.0), 1.0);
    } else {
        vec3 col = IMG_NORM_PIXEL(echoBuf, n).rgb;
        gl_FragColor = vec4(mix(col, src, dry), 1.0);
    }
}
