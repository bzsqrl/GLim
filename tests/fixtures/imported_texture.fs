/*{
    "DESCRIPTION": "Fixture: IMPORTED image must appear upright (red band at top)",
    "ISFVSN": "2",
    "INPUTS": [],
    "IMPORTED": { "tex": { "PATH": "img/topred.png" } }
}*/
void main() {
    gl_FragColor = IMG_NORM_PIXEL(tex, isf_FragNormCoord);
}
