/*{
  "DESCRIPTION": "Building block: a sunburst of rays that can spin, bend into spirals, breathe and vary in length, from any point on screen",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Building Block"],
  "INPUTS": [
    { "NAME": "rays",         "LABEL": "Rays",          "TYPE": "float", "DEFAULT": 12.0, "MIN": 1.0,  "MAX": 64.0 },
    { "NAME": "width",        "LABEL": "Width",         "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.01, "MAX": 1.0 },
    { "NAME": "softness",     "LABEL": "Softness",      "TYPE": "float", "DEFAULT": 0.1,  "MIN": 0.0,  "MAX": 0.5 },
    { "NAME": "spin",         "LABEL": "Spin",          "TYPE": "float", "DEFAULT": 0.2,  "MIN": -3.0, "MAX": 3.0 },
    { "NAME": "twist",        "LABEL": "Twist",         "TYPE": "float", "DEFAULT": 0.0,  "MIN": -8.0, "MAX": 8.0 },
    { "NAME": "breathe",      "LABEL": "Breathe",       "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "breatheRate",  "LABEL": "Breathe Rate",  "TYPE": "float", "DEFAULT": 2.0,  "MIN": 0.0,  "MAX": 10.0 },
    { "NAME": "lengthJitter", "LABEL": "Length Jitter", "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "jitterRate",   "LABEL": "Jitter Rate",   "TYPE": "float", "DEFAULT": 0.0,  "MIN": 0.0,  "MAX": 4.0 },
    { "NAME": "innerRadius",  "LABEL": "Inner Radius",  "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.8 },
    { "NAME": "outerFade",    "LABEL": "Outer Fade",    "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "center",       "LABEL": "Position",      "TYPE": "point2D", "DEFAULT": [0.5, 0.5], "MIN": [0.0, 0.0], "MAX": [1.0, 1.0] },
    { "NAME": "color1",       "LABEL": "Color A",       "TYPE": "color", "DEFAULT": [1.0, 0.8, 0.2, 1.0] },
    { "NAME": "color2",       "LABEL": "Color B",       "TYPE": "color", "DEFAULT": [1.0, 0.3, 0.1, 1.0] },
    { "NAME": "transparent",  "LABEL": "Transparent",   "TYPE": "bool",  "DEFAULT": false }
  ]
}*/

#define TAU 6.28318530718

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    vec2 c = (center - 0.5) * vec2(RENDERSIZE.x / RENDERSIZE.y, 1.0);
    vec2 q = uv - c;
    float r = length(q);

    float n = floor(rays + 0.5);
    float a = atan(q.y, q.x) + TIME * spin + twist * r;
    float v = a / TAU * n;
    float id = mod(floor(v), n);
    float d = abs(fract(v) - 0.5);

    // Angular anti-aliasing: a ray's edge gets thinner in angle further from the centre
    float aa = n / (TAU * max(r, 0.001)) * 1.5 / RENDERSIZE.y;
    float w = width * (1.0 + 0.5 * breathe * sin(TIME * breatheRate + 1.7 * id));
    float ray = 1.0 - smoothstep(0.5 * w - 0.5 * softness - aa, 0.5 * w + 0.5 * softness + aa, d);

    // Ray length: full screen, or a random length per ray that drifts at jitterRate
    float h = mix(hash(vec2(id, floor(TIME * jitterRate))), hash(vec2(id, floor(TIME * jitterRate) + 1.0)),
                  smoothstep(0.0, 1.0, fract(TIME * jitterRate)));
    float len = mix(1.5, 0.15 + 0.9 * h, lengthJitter);
    float m = ray * smoothstep(innerRadius, innerRadius + 0.01, r)
                  * (1.0 - smoothstep(len * (1.0 - outerFade), len, r));

    vec3 col = mix(color1.rgb, color2.rgb, mod(id, 2.0));
    if (transparent) gl_FragColor = vec4(col, m);
    else gl_FragColor = vec4(col * m, 1.0);
}
