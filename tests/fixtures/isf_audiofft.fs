/*{
    "DESCRIPTION": "Fixture: ISF audioFFT input",
    "ISFVSN": "2",
    "CATEGORIES": ["Generator"],
    "INPUTS": [ { "NAME": "spectrum", "TYPE": "audioFFT" },
                { "NAME": "gain", "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.0, "MAX": 4.0 } ]
}*/
void main() {
    float v = IMG_NORM_PIXEL(spectrum, vec2(isf_FragNormCoord.x, 0.5)).r * gain;
    gl_FragColor = vec4(vec3(step(isf_FragNormCoord.y, v)), 1.0);
}
