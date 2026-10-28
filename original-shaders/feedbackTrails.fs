/*{
  "DESCRIPTION": "Building block effect: classic video feedback on the clip: trails that zoom, turn, drift and shift hue, layered by lighten, smear or luma key",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Stylize", "Building Block"],
  "INPUTS": [
    { "NAME": "inputImage", "TYPE": "image" },
    { "NAME": "mode",       "LABEL": "Blend",      "TYPE": "long", "DEFAULT": 0, "VALUES": [0, 1, 2], "LABELS": ["Lighten", "Smear", "Luma Key"] },
    { "NAME": "trail",      "LABEL": "Trail",      "TYPE": "float", "DEFAULT": 0.92, "MIN": 0.0,  "MAX": 0.995 },
    { "NAME": "zoom",       "LABEL": "Zoom",       "TYPE": "float", "DEFAULT": 0.3,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "rotate",     "LABEL": "Rotate",     "TYPE": "float", "DEFAULT": 0.0,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "driftX",     "LABEL": "Drift X",    "TYPE": "float", "DEFAULT": 0.0,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "driftY",     "LABEL": "Drift Y",    "TYPE": "float", "DEFAULT": 0.0,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "hueShift",   "LABEL": "Hue Shift",  "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "threshold",  "LABEL": "Key Level",  "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "center",     "LABEL": "Center",     "TYPE": "point2D", "DEFAULT": [0.5, 0.5], "MIN": [0.0, 0.0], "MAX": [1.0, 1.0] },
    { "NAME": "reset",      "LABEL": "Clear",      "TYPE": "event" }
  ],
  "PASSES": [
    { "TARGET": "trails", "PERSISTENT": true, "FLOAT": true },
    {}
  ]
}*/

vec3 hueRotate(vec3 c, float a) {
    vec3 k = vec3(0.57735);
    float ca = cos(a);
    return c * ca + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - ca);
}

void main() {
    vec2 n = isf_FragNormCoord;
    vec4 src = IMG_NORM_PIXEL(inputImage, n);
    if (PASSINDEX == 0) {
        float aspect = RENDERSIZE.x / RENDERSIZE.y;
        float frames = clamp(TIMEDELTA * 60.0, 0.0, 4.0);

        // Transform last frame around the centre point: zoom, turn, then drift
        vec2 q = (n - center) * vec2(aspect, 1.0);
        float a = 0.02 * rotate * frames;
        q = mat2(cos(a), sin(a), -sin(a), cos(a)) * q;
        q *= 1.0 - 0.02 * zoom * frames;
        q -= 0.005 * frames * vec2(driftX, driftY);
        vec2 coord = q / vec2(aspect, 1.0) + center;

        vec3 prev = IMG_NORM_PIXEL(trails, coord).rgb;
        prev *= step(abs(coord.x - 0.5), 0.5) * step(abs(coord.y - 0.5), 0.5);
        prev = max(hueRotate(prev, 0.1 * hueShift * frames), 0.0) * pow(trail, frames);

        vec3 col;
        if (mode == 1) {
            // Smear: a running average, so brightness stays even however long the trail
            col = prev + src.rgb * (1.0 - pow(trail, frames));
        } else if (mode == 2) {
            float l = dot(src.rgb, vec3(0.299, 0.587, 0.114));
            col = mix(prev, src.rgb, smoothstep(threshold, threshold + 0.1, l));
        } else {
            col = max(prev, src.rgb);
        }

        if (reset || FRAMEINDEX < 2) col = src.rgb;
        gl_FragColor = vec4(col, 1.0);
    } else {
        gl_FragColor = vec4(IMG_NORM_PIXEL(trails, n).rgb, src.a);
    }
}
