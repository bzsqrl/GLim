/*{
  "DESCRIPTION": "Iridescent metallic surface",
  "CREDIT": "Antigravity",
  "ISFVSN": "2.0",
  "CATEGORIES": [
    "Generator",
    "Abstract"
  ],
  "INPUTS": [
    {
      "NAME": "speed",
      "TYPE": "float",
      "DEFAULT": 1.0,
      "MIN": 0.1,
      "MAX": 10.0
    }
  ]
}*/

void main() {
    vec2 p = (2.0 * gl_FragCoord.xy - RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;
    
    float v = sin(length(p) * 10.0 - t * 2.0);
    v += sin(atan(p.y, p.x) * 10.0 + t);
    
    vec3 col = 0.5 + 0.5 * cos(v + vec3(0, 2, 4));
    col = pow(col, vec3(0.5)); // Metallic sheen
    col += vec3(0.2) * smoothstep(0.8, 1.0, sin(v * 5.0)); // Ridges
    
    gl_FragColor = vec4(col, 1.0);
}
