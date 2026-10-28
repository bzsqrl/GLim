/*{
  "DESCRIPTION": "A living Gray-Scott reaction-diffusion: two chemicals grow coral, mazes and dividing cells; the recipe wanders across space and time, so different growths compete",
  "CREDIT": "GLim original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "speed",      "LABEL": "Speed",       "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "pattern",    "LABEL": "Pattern",     "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0, "MAX": 1.0 },
    { "NAME": "drift",      "LABEL": "Drift",       "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0, "MAX": 1.0 },
    { "NAME": "drops",      "LABEL": "Drops",       "TYPE": "float", "DEFAULT": 0.5,  "MIN": 0.0, "MAX": 1.0 },
    { "NAME": "relief",     "LABEL": "Relief",      "TYPE": "float", "DEFAULT": 1.0,  "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.03, "MIN": 0.0, "MAX": 0.5 },
    { "NAME": "reset",      "LABEL": "Reseed",      "TYPE": "event" }
  ],
  "PASSES": [
    { "TARGET": "simA", "PERSISTENT": true, "FLOAT": true, "WIDTH": "$WIDTH/2", "HEIGHT": "$HEIGHT/2" },
    { "TARGET": "simB", "PERSISTENT": true, "FLOAT": true, "WIDTH": "$WIDTH/2", "HEIGHT": "$HEIGHT/2" },
    {}
  ]
}*/

#define TAU 6.28318530718

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

vec3 palette(float x) {
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.25, 0.55)));
}

// Wrap around the edges so the simulation lives on a torus
vec2 tapA(vec2 p) { return IMG_PIXEL(simA, mod(p, RENDERSIZE.xy)).xy; }
vec2 tapB(vec2 p) { return IMG_PIXEL(simB, mod(p, RENDERSIZE.xy)).xy; }

// Feed and kill rates: Pattern slides from dividing cells through coral to mazes,
// and Drift lets the recipe wander so neighbouring regions grow differently
vec2 feedKill(vec2 uv, float t) {
    float m = pattern + 0.35 * drift * sin(0.07 * t + 2.5 * uv.x) * cos(0.05 * t - 2.0 * uv.y);
    m = clamp(m, 0.0, 1.0);
    vec2 mitosis = vec2(0.0367, 0.0649);
    vec2 coral   = vec2(0.0545, 0.0620);
    vec2 maze    = vec2(0.0290, 0.0570);
    return m < 0.5 ? mix(mitosis, coral, 2.0 * m) : mix(coral, maze, 2.0 * m - 1.0);
}

// One Gray-Scott step, given the cell (a, b) and its Laplacian
vec4 simulate(vec2 c, vec2 lap, vec2 px) {
    vec2 res = RENDERSIZE.xy;
    vec2 uv = (px - 0.5 * res) / res.y;
    float t = TIME * speed;

    vec2 fk = feedKill(uv, t);
    float a = c.x;
    float b = c.y;
    float r = a * b * b;
    a += 1.0 * lap.x - r + fk.x * (1.0 - a);
    b += 0.5 * lap.y + r - (fk.x + fk.y) * b;

    // Wandering droppers switch on and off, planting fresh growth
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        vec2 pos = vec2(0.7 * sin((0.31 + 0.1 * fi) * t + 2.0 * fi),
                        0.4 * cos((0.23 + 0.07 * fi) * t + 1.1 * fi));
        float on = step(0.5, fract(0.5 * t + 0.33 * fi));
        b = max(b, 0.5 * drops * on * smoothstep(0.02, 0.0, length(uv - pos)));
    }

    if (FRAMEINDEX < 2 || reset) {
        a = 1.0;
        b = 0.5 * step(0.93, hash(floor(px / 4.0)));
    }
    return vec4(clamp(a, 0.0, 1.0), clamp(b, 0.0, 1.0), 0.0, 1.0);
}

void main() {
    vec2 px = gl_FragCoord.xy;
    if (PASSINDEX == 0) {
        vec2 c = tapB(px);
        vec2 lap = 0.2  * (tapB(px + vec2(1.0, 0.0)) + tapB(px - vec2(1.0, 0.0))
                         + tapB(px + vec2(0.0, 1.0)) + tapB(px - vec2(0.0, 1.0)))
                 + 0.05 * (tapB(px + vec2(1.0, 1.0)) + tapB(px - vec2(1.0, 1.0))
                         + tapB(px + vec2(1.0, -1.0)) + tapB(px - vec2(1.0, -1.0)))
                 - c;
        gl_FragColor = simulate(c, lap, px);
    } else if (PASSINDEX == 1) {
        vec2 c = tapA(px);
        vec2 lap = 0.2  * (tapA(px + vec2(1.0, 0.0)) + tapA(px - vec2(1.0, 0.0))
                         + tapA(px + vec2(0.0, 1.0)) + tapA(px - vec2(0.0, 1.0)))
                 + 0.05 * (tapA(px + vec2(1.0, 1.0)) + tapA(px - vec2(1.0, 1.0))
                         + tapA(px + vec2(1.0, -1.0)) + tapA(px - vec2(1.0, -1.0)))
                 - c;
        gl_FragColor = simulate(c, lap, px);
    } else {
        vec2 n = isf_FragNormCoord;
        vec2 e = 2.0 / RENDERSIZE.xy;
        float b  = IMG_NORM_PIXEL(simB, n).y;
        float bx = IMG_NORM_PIXEL(simB, n + vec2(e.x, 0.0)).y - IMG_NORM_PIXEL(simB, n - vec2(e.x, 0.0)).y;
        float by = IMG_NORM_PIXEL(simB, n + vec2(0.0, e.y)).y - IMG_NORM_PIXEL(simB, n - vec2(0.0, e.y)).y;

        // Treat the chemical as a height map and light it
        vec3 nrm = normalize(vec3(-20.0 * relief * vec2(bx, by), 1.0));
        vec3 l = normalize(vec3(-0.5, 0.6, 0.8));
        float diff = clamp(dot(nrm, l), 0.0, 1.0);
        float spec = pow(max(dot(reflect(-l, nrm), vec3(0.0, 0.0, 1.0)), 0.0), 24.0);

        float v = smoothstep(0.05, 0.4, b);
        vec3 bg = 0.08 * palette(0.5 + 0.3 * n.y + TIME * colorCycle);
        vec3 col = mix(bg, palette(0.8 * v + 0.2 * n.x + TIME * colorCycle), v);
        col = col * (0.45 + 0.65 * diff) + 0.4 * relief * spec * v;

        gl_FragColor = vec4(col, 1.0);
    }
}
