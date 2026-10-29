/*{
  "DESCRIPTION": "Blobs merging and splitting",
  "CREDIT": "GLim - License: CC0",
  "ISFVSN": "2.0",
  "CATEGORIES": [
    "Generator",
    "Organic"
  ],
  "INPUTS": [
    {
      "NAME": "speed",
      "TYPE": "float",
      "DEFAULT": 1.0,
      "MIN": 0.1,
      "MAX": 5.0
    }
  ]
}*/

void main() {
    vec2 p = (2.0 * gl_FragCoord.xy - RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;
    
    float v = 0.0;
    for(int i = 0; i < 5; i++) {
        float fi = float(i);
        vec2 c = vec2(sin(t * 0.5 + fi), cos(t * 0.4 + fi * 2.0));
        v += 0.1 / length(p - c * 0.8);
    }
    
    vec3 col = vec3(0.0);
    if (v > 1.0) {
        col = vec3(0.2, 0.8, 0.4); // Green blob
        col *= v * 0.5;
    }
     
    // Nucleus
    if (v > 2.0) col = vec3(1.0);
    //col += vec3(0.5, 0.0, 0.5) * smoothstep(0.8, 1.0, sin(v * 2.0 + t)); // ghost trail
    
    gl_FragColor = vec4(col, 1.0);
}
