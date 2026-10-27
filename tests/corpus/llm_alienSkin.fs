/*{
  "DESCRIPTION": "Scaly, breathing texture",
  "CREDIT": "Antigravity",
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
    
    // Breathing
    p *= 1.0 + 0.05 * sin(t); // param
    
    // Scales
    vec2 r = vec2(1.0, 1.73); // param
    vec2 h = r * 0.5;
    vec2 a = mod(p * 5.0, r) - h;
    vec2 b = mod(p * 5.0 - h, r) - h;
    vec2 g = dot(a, a) < dot(b, b) ? a : b;
    
    float d = length(g);
    
    vec3 col = vec3(0.0, 0.2, 0.1); // Dark green
    col += vec3(0.2, 0.8, 0.8) * smoothstep(0.5, 0.0, d); // Scale center
    
    // Iridescence
    col += vec3(0.0, 0.2, 0.5) * sin(d * 10.0 + t);
    
    gl_FragColor = vec4(col, 1.0);
}
