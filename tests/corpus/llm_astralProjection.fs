/*{
  "DESCRIPTION": "Ethereal, out-of-body visual",
  "CREDIT": "GLim - License: CC0",
  "ISFVSN": "2.0",
  "CATEGORIES": [
    "Generator",
    "Spiritual"
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
    v += sin(p.x * 5.0 + t);
    v += sin(p.y * 5.0 + t * 1.2);
    v += sin((p.x + p.y) * 5.0 - t);
    
    vec3 col = vec3(0.8, 0.9, 1.0); // White/Blue light
    col *= 0.5 + 0.5 * v;
    
    // Ghostly trail
    col += vec3(0.5, 0.0, 0.5) * smoothstep(0.8, 1.0, sin(v * 2.0 + t));
    
    gl_FragColor = vec4(col, 1.0);
}
