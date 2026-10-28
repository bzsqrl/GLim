/*{
  "DESCRIPTION": "A cyclic cellular automaton: random noise organises itself into rotating spiral waves of colour, smoothed into flowing light",
  "CREDIT": "FFStudio original",
  "ISFVSN": "2",
  "CATEGORIES": ["Generator", "Psychedelic"],
  "INPUTS": [
    { "NAME": "rate",       "LABEL": "Steps/sec",   "TYPE": "float", "DEFAULT": 15.0, "MIN": 0.0, "MAX": 60.0 },
    { "NAME": "states",     "LABEL": "States",      "TYPE": "float", "DEFAULT": 12.0, "MIN": 3.0, "MAX": 24.0 },
    { "NAME": "threshold",  "LABEL": "Threshold",   "TYPE": "float", "DEFAULT": 1.0,  "MIN": 1.0, "MAX": 4.0 },
    { "NAME": "smoothing",  "LABEL": "Smoothing",   "TYPE": "float", "DEFAULT": 0.7,  "MIN": 0.0, "MAX": 0.98 },
    { "NAME": "edgeGlow",   "LABEL": "Edge Glow",   "TYPE": "float", "DEFAULT": 0.8,  "MIN": 0.0, "MAX": 2.0 },
    { "NAME": "colorCycle", "LABEL": "Color Cycle", "TYPE": "float", "DEFAULT": 0.05, "MIN": 0.0, "MAX": 0.5 },
    { "NAME": "reset",      "LABEL": "Reseed",      "TYPE": "event" }
  ],
  "PASSES": [
    { "TARGET": "cells", "PERSISTENT": true, "FLOAT": true, "WIDTH": "$WIDTH/4", "HEIGHT": "$HEIGHT/4" },
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
    return 0.5 + 0.5 * cos(TAU * (x + vec3(0.0, 0.33, 0.67)));
}

void main() {
    if (PASSINDEX == 0) {
        // r: the cell's state, gb: its colour phase eased towards that state
        vec2 px = gl_FragCoord.xy;
        vec2 res = RENDERSIZE.xy;
        vec4 me = IMG_PIXEL(cells, px);
        float n = floor(states + 0.5);
        float s = mod(floor(me.r + 0.5), n);
        float next = mod(s + 1.0, n);

        // A cell advances when enough neighbours are already one state ahead
        float count = 0.0;
        for (int j = -1; j <= 1; j++) {
            for (int i = -1; i <= 1; i++) {
                if (i == 0 && j == 0) continue;
                float ns = IMG_PIXEL(cells, mod(px + vec2(float(i), float(j)), res)).r;
                ns = mod(floor(ns + 0.5), n);
                count += 1.0 - step(0.5, abs(ns - next));
            }
        }
        float frame = mod(float(FRAMEINDEX), 977.0);
        // All cells step together, `rate` times a second; the phase smoothing below fills in between steps
        bool tick = floor(TIME * rate) != floor((TIME - TIMEDELTA) * rate);
        if (tick && count >= floor(threshold + 0.5)) s = next;

        vec2 phase = me.gb * 2.0 - 1.0;
        if (reset || FRAMEINDEX < 2) {
            // Seed with a few vortices (phase winds around random points): each one becomes a spiral
            vec2 uv = px / res.y;
            float w = 0.0;
            for (int k = 0; k < 5; k++) {
                float fk = float(k);
                vec2 c = vec2(hash(vec2(fk, frame)) * res.x / res.y, hash(vec2(frame, fk + 3.0)));
                vec2 d = uv - c;
                w += (mod(fk, 2.0) * 2.0 - 1.0) * atan(d.y, d.x) / TAU;
            }
            s = floor(fract(w + 0.02 * hash(px)) * n);
            phase = vec2(0.0);
        }
        vec2 target = vec2(cos(TAU * s / n), sin(TAU * s / n));
        phase = mix(target, phase, smoothing);
        gl_FragColor = vec4(s, 0.5 + 0.5 * phase, 1.0);
    } else {
        vec2 ph = IMG_NORM_PIXEL(cells, isf_FragNormCoord).gb * 2.0 - 1.0;
        float hue = atan(ph.y, ph.x) / TAU;
        float mag = length(ph);

        vec3 col = palette(hue + TIME * colorCycle) * (0.3 + 0.7 * smoothstep(0.05, 0.5, mag));
        // Where neighbouring states blend, the phase vector shrinks: light those wave fronts
        col += 0.6 * edgeGlow * (1.0 - smoothstep(0.0, 0.3, mag)) * palette(hue + 0.5 + TIME * colorCycle);

        col = 1.0 - exp(-1.5 * col);
        gl_FragColor = vec4(col, 1.0);
    }
}
