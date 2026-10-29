/*{
    "DESCRIPTION": "Test shader: multi-pass ISF effect without persistent buffers (bright pass, then two blur passes at quarter size), with long, bool and event inputs.",
    "CREDIT": "GLim - License: CC0",
    "ISFVSN": "2",
    "CATEGORIES": ["Blur", "Glow"],
    "INPUTS": [
        { "NAME": "inputImage", "TYPE": "image" },
        { "NAME": "threshold", "LABEL": "Threshold", "TYPE": "float", "DEFAULT": 0.6, "MIN": 0.0, "MAX": 1.0 },
        { "NAME": "radius", "LABEL": "Radius", "TYPE": "float", "DEFAULT": 2.0, "MIN": 0.5, "MAX": 6.0 },
        { "NAME": "strength", "LABEL": "Strength", "TYPE": "float", "DEFAULT": 1.2, "MIN": 0.0, "MAX": 4.0 },
        { "NAME": "blendMode", "LABEL": "Blend", "TYPE": "long", "DEFAULT": 0, "VALUES": [0, 1, 2], "LABELS": ["Add", "Screen", "Bloom Only"] },
        { "NAME": "tintBloom", "LABEL": "Warm Tint", "TYPE": "bool", "DEFAULT": true },
        { "NAME": "flash", "LABEL": "Flash", "TYPE": "event" }
    ],
    "PASSES": [
        { "TARGET": "brightH", "WIDTH": "$WIDTH/4", "HEIGHT": "$HEIGHT/4" },
        { "TARGET": "brightV", "WIDTH": "$WIDTH/4", "HEIGHT": "$HEIGHT/4" },
        { }
    ]
}*/

const float W[5] = float[5](0.227, 0.194, 0.122, 0.054, 0.016);

vec3 brightPart(vec2 uv) {
    vec3 c = IMG_NORM_PIXEL(inputImage, uv).rgb;
    float l = dot(c, vec3(0.299, 0.587, 0.114));
    return c * smoothstep(threshold, threshold + 0.1, l);
}

void main() {
    vec2 uv = isf_FragNormCoord;
    if (PASSINDEX == 0) {
        // Bright parts of the clip, blurred horizontally.
        vec2 offs = vec2(radius / RENDERSIZE.x, 0.0);
        vec3 sum = brightPart(uv) * W[0];
        for (int i = 1; i < 5; i++)
            sum += (brightPart(uv + offs * float(i)) + brightPart(uv - offs * float(i))) * W[i];
        gl_FragColor = vec4(sum, 1.0);
    } else if (PASSINDEX == 1) {
        // Then vertically.
        vec2 offs = vec2(0.0, radius / IMG_SIZE(brightH).y);
        vec3 sum = IMG_NORM_PIXEL(brightH, uv).rgb * W[0];
        for (int i = 1; i < 5; i++)
            sum += (IMG_NORM_PIXEL(brightH, uv + offs * float(i)).rgb
                  + IMG_NORM_PIXEL(brightH, uv - offs * float(i)).rgb) * W[i];
        gl_FragColor = vec4(sum, 1.0);
    } else {
        vec4 src = IMG_NORM_PIXEL(inputImage, uv);
        vec3 bloom = IMG_NORM_PIXEL(brightV, uv).rgb * strength;
        if (tintBloom)
            bloom *= vec3(1.0, 0.75, 0.55);
        if (flash)
            bloom += 0.5;
        vec3 col;
        if (blendMode == 0)
            col = src.rgb + bloom;
        else if (blendMode == 1)
            col = 1.0 - (1.0 - src.rgb) * (1.0 - clamp(bloom, 0.0, 1.0));
        else
            col = bloom;
        gl_FragColor = vec4(col, src.a);
    }
}
