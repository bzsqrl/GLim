/*{
    "DESCRIPTION": "Test shader: ISF transition. A soft-edged wipe from startImage to endImage at any angle, with a glowing edge.",
    "CREDIT": "GLim - License: CC0",
    "ISFVSN": "2",
    "CATEGORIES": ["Transition"],
    "INPUTS": [
        { "NAME": "startImage", "TYPE": "image" },
        { "NAME": "endImage", "TYPE": "image" },
        { "NAME": "progress", "TYPE": "float", "DEFAULT": 0.0, "MIN": 0.0, "MAX": 1.0 },
        { "NAME": "angle", "LABEL": "Angle", "TYPE": "float", "DEFAULT": 0.25, "MIN": 0.0, "MAX": 1.0 },
        { "NAME": "softness", "LABEL": "Softness", "TYPE": "float", "DEFAULT": 0.15, "MIN": 0.0, "MAX": 0.5 },
        { "NAME": "edgeColor", "LABEL": "Edge Color", "TYPE": "color", "DEFAULT": [1.0, 0.8, 0.3, 1.0] }
    ]
}*/

void main() {
    vec2 uv = isf_FragNormCoord;
    float ang = angle * 6.2831853;
    vec2 dir = vec2(cos(ang), sin(ang));
    // Project onto the wipe direction, scaled so 0..1 crosses the whole frame.
    float span = abs(dir.x) + abs(dir.y);
    float x = dot(uv - 0.5, dir) / span + 0.5;
    // The edge travels from just before 0 to just past 1, so both ends are clean.
    float edge = progress * (1.0 + 2.0 * softness) - softness;
    float m = smoothstep(edge - softness, edge + softness, x);
    vec4 col = mix(IMG_NORM_PIXEL(endImage, uv), IMG_NORM_PIXEL(startImage, uv), m);
    float glow = 1.0 - abs(m - 0.5) * 2.0;
    col.rgb += edgeColor.rgb * edgeColor.a * glow * 0.6;
    gl_FragColor = col;
}
