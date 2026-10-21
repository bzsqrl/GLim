/*{
    "DESCRIPTION": "Fixture: ISF effect with a companion .vs vertex shader (VIDVOX blur pattern)",
    "ISFVSN": "2",
    "CATEGORIES": ["Blur"],
    "INPUTS": [
        { "NAME": "inputImage", "TYPE": "image" },
        { "NAME": "width", "TYPE": "float", "DEFAULT": 8.0, "MIN": 0.0, "MAX": 32.0 }
    ]
}*/
varying vec2 left_coord;
varying vec2 right_coord;
varying vec2 above_coord;
varying vec2 below_coord;

void main() {
    vec4 c = IMG_THIS_PIXEL(inputImage);
    vec4 l = IMG_NORM_PIXEL(inputImage, left_coord);
    vec4 r = IMG_NORM_PIXEL(inputImage, right_coord);
    vec4 a = IMG_NORM_PIXEL(inputImage, above_coord);
    vec4 b = IMG_NORM_PIXEL(inputImage, below_coord);
    gl_FragColor = (c + l + r + a + b) / 5.0;
}
