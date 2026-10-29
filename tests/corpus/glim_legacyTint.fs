/*{
    "DESCRIPTION": "Test shader: ISF version 1 effect (no ISFVSN, IDENTITY values, vv_FragNormCoord, IMG_THIS_PIXEL, DATE). Tints the clip inside a band that sweeps with the clock.",
    "CREDIT": "GLim - License: CC0",
    "CATEGORIES": ["Color Effect"],
    "INPUTS": [
        { "NAME": "inputImage", "TYPE": "image" },
        { "NAME": "amount", "TYPE": "float", "DEFAULT": 0.5, "MIN": 0.0, "MAX": 1.0, "IDENTITY": 0.0 },
        { "NAME": "tint", "TYPE": "color", "DEFAULT": [0.2, 0.6, 1.0, 1.0], "IDENTITY": [1.0, 1.0, 1.0, 1.0] },
        { "NAME": "bandWidth", "TYPE": "float", "DEFAULT": 0.2, "MIN": 0.02, "MAX": 1.0 }
    ]
}*/

void main() {
    vec4 src = IMG_THIS_PIXEL(inputImage);
    // DATE.w is seconds since midnight: one sweep every 4 seconds.
    float sweep = fract(DATE.w / 4.0);
    float d = abs(vv_FragNormCoord.x - sweep);
    d = min(d, 1.0 - d);
    float band = 1.0 - smoothstep(0.0, bandWidth * 0.5, d);
    vec3 tinted = mix(src.rgb, src.rgb * tint.rgb * 1.5, amount);
    gl_FragColor = vec4(mix(src.rgb, tinted, band), src.a);
}
