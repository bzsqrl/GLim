/*{
  "DESCRIPTION": "A Truchet maze of quarter-circle arcs with colour flowing along the paths; tiles quietly cross-fade to new orientations, rewiring the maze",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0,  "MAX": 2.0 },
    { "NAME": "scale",      "LABEL": "Scale",       "TYPE": "float", "DEFAULT": 6.0,  "MIN": 2.0,  "MAX": 20.0 },
    { "NAME": "lineWidth",  "LABEL": "Line Width",  "TYPE": "float", "DEFAULT": 0.14, "MIN": 0.03, "MAX": 0.3 },
    { "NAME": "stripes",    "LABEL": "Stripes",     "TYPE": "float", "DEFAULT": 3.0,  "MIN": 1.0,  "MAX": 10.0 },
    { "NAME": "flipRate",   "LABEL": "Flip Rate",   "TYPE": "float", "DEFAULT": 0.15, "MIN": 0.0,  "MAX": 1.0 },
    { "NAME": "drift",      "LABEL": "Drift",       "TYPE": "float", "DEFAULT": 0.3,  "MIN": 0.0,  "MAX": 1.5 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0,  "MAX": 0.5 }
  ]
}*/

#define TAU 6.28318530718
#define PI  3.14159265359

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.6, 0.3, 0.0)));
}

// Colour of one tile drawn with orientation `flip` (0 or 1)
vec3 tile(vec2 f, vec2 id, float flip, float t) {
    float parity = mod(id.x + id.y, 2.0) * 2.0 - 1.0;
    if (flip > 0.5) {
        f.x = -f.x;
        parity = -parity;
    }
    vec2 c = (f.x + f.y > 0.0) ? vec2(0.5) : vec2(-0.5);
    vec2 q = f - c;
    float d = abs(length(q) - 0.5);
    float along = atan(q.y, q.x);

    float line = smoothstep(lineWidth, lineWidth - 0.03, d);
    float flow = 0.5 + 0.5 * sin(4.0 * floor(stripes + 0.5) * along + parity * 3.0 * t);
    float shade = 1.0 - d / lineWidth;

    vec3 col = palette(along / PI + 0.1 * (id.x - id.y) + 0.2 * t + TIME * colorCycle);
    col *= line * (0.35 + 0.65 * flow) * (0.4 + 0.6 * shade);
    return col;
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * RENDERSIZE.xy) / RENDERSIZE.y;
    float t = TIME * speed;

    vec2 p = uv * scale + drift * vec2(0.6 * t, 0.4 * sin(0.3 * t));
    vec2 id = floor(p);
    vec2 f = fract(p) - 0.5;

    // Each tile has its own clock; near the end of each tick it fades to its next orientation
    float h = hash(id);
    float phase = t * flipRate + 7.0 * h;
    float k = floor(phase);
    float blend = smoothstep(0.75, 1.0, fract(phase));
    float flipA = step(0.5, hash(id + k));
    float flipB = step(0.5, hash(id + k + 1.0));

    vec3 col = mix(tile(f, id, flipA, t), tile(f, id, flipB, t), blend);
    col += 0.06 * palette(h + TIME * colorCycle);

    gl_FragColor = vec4(col, 1.0);
}
