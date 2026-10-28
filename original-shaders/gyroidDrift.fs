/*{
  "DESCRIPTION": "A flat slice travelling through a 3D gyroid lattice: contour lines bloom, merge and split as the slice moves deeper",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "scale",      "LABEL": "Scale",       "TYPE": "float", "DEFAULT": 6.0,  "MIN": 1.0,  "MAX": 20.0 },
    { "NAME": "contours",   "LABEL": "Contours",    "TYPE": "float", "DEFAULT": 3.0,  "MIN": 1.0,  "MAX": 8.0 },
    { "NAME": "thickness",  "LABEL": "Thickness",   "TYPE": "float", "DEFAULT": 0.25, "MIN": 0.02, "MAX": 1.0 },
    { "NAME": "detail",     "LABEL": "Detail",      "TYPE": "float", "DEFAULT": 0.35, "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "tilt",       "LABEL": "Tilt",        "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 1.5 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718
#define PI  3.14159265359

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.3, 0.5, 0.7)) + vec3(0.0, 0.5, 1.0));
}

float gyroid(vec3 p) {
    return dot(sin(p), cos(p.yzx));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    vec3 p = vec3(uv * scale, 1.5 * t);
    // The slice plane slowly rocks, so the lattice is seen from changing angles
    p.xz = rot(tilt * 0.5 * sin(0.13 * t)) * p.xz;
    p.yz = rot(tilt * 0.4 * cos(0.11 * t)) * p.yz;

    float g = gyroid(p);
    g += detail * 0.5 * gyroid(2.1 * p.zxy + vec3(0.0, 0.0, t));

    float line = smoothstep(thickness, 0.0, abs(sin(PI * g * contours + t)));
    float fill = smoothstep(-1.5, 1.5, g);

    vec3 col = palette(0.25 * g + 0.04 * p.z + TIME * colorCycle) * (0.15 + 0.6 * fill);
    col += line * palette(0.25 * g + 0.5 + TIME * colorCycle);

    col *= smoothstep(1.4, 0.3, length(uv));
    col = 1.0 - exp(-1.5 * col);
    gl_FragColor = vec4(col, 1.0);
}
