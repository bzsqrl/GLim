/*{
  "DESCRIPTION": "A honeycomb of hexagons with concentric rings inside each cell; waves of colour and pulsing roll across the grid",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "scale",      "LABEL": "Scale",       "TYPE": "float", "DEFAULT": 6.0,  "MIN": 2.0,  "MAX": 20.0 },
    { "NAME": "pulse",      "LABEL": "Pulse",       "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,  "MAX": 3.0 },
    { "NAME": "lineWidth",  "LABEL": "Line Width",  "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.01, "MAX": 0.25 },
    { "NAME": "waveSpread", "LABEL": "Wave Spread", "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0,  "MAX": 3.0 },
    { "NAME": "spin",       "LABEL": "Spin",        "TYPE": "float", "DEFAULT": 0.2,  "MIN": -1.0, "MAX": 1.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718

const vec2 HEX = vec2(1.0, 1.7320508);

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.15, 0.35)));
}

// xy: position inside the hexagon, zw: the hexagon's id
vec4 hexCell(vec2 p) {
    vec4 c = floor(vec4(p, p - vec2(0.5, 1.0)) / HEX.xyxy) + 0.5;
    vec4 h = vec4(p - c.xy * HEX, p - (c.zw + 0.5) * HEX);
    return dot(h.xy, h.xy) < dot(h.zw, h.zw) ? vec4(h.xy, c.xy) : vec4(h.zw, c.zw + 0.5);
}

// 0 at the centre, 0.5 at the edge
float hexDist(vec2 p) {
    p = abs(p);
    return max(dot(p, HEX * 0.5), p.x);
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    vec2 p = rot(spin * 0.2 * t) * uv * scale;
    vec4 h = hexCell(p);
    vec2 id = h.zw;
    float d = hexDist(h.xy);

    // A wave travels outward from the centre and is bent by a slow sideways drift
    float wave = sin(0.6 * waveSpread * length(id) - 2.0 * t + waveSpread * sin(0.3 * id.x + 0.4 * t));
    float phase = 0.5 + 0.5 * wave;

    float rings = 0.5 + 0.5 * sin(TAU * d * (2.0 + 2.0 * pulse * phase) - 3.0 * t);
    float edge = smoothstep(lineWidth, 0.0, 0.5 - d);

    vec3 col = palette(0.5 * phase + 0.2 * hash(id) + TIME * colorCycle);
    col *= (0.2 + 0.8 * phase) * (0.5 + 0.5 * rings);
    col += edge * palette(phase + 0.5 + TIME * colorCycle) * (0.4 + 0.8 * phase);

    col = 1.0 - exp(-1.3 * col);
    gl_FragColor = vec4(col, 1.0);
}
