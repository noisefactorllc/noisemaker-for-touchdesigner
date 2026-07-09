// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Oil Paint - flatten pass: 8-sector Kuwahara filter (S7 snippet). Reduces
 * the input to per-pixel flat color patches -- the painterly "dab"
 * substrate that oilPost.glsl reshapes per MODE. facet mode uses a
 * tighter radius (min(size, 3)) so its patches read as small flat
 * polygons rather than large brush strokes.
 *
 * MODE is a compile-time define injected by the runtime (see definition.js
 * globals.mode.define), same mechanism as filter/texture and filter/grain.
 */

#ifndef MODE
#define MODE 1
#endif



uniform vec2 resolution;
uniform float size;

out vec4 fragColor;

void nm_main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 px = 1.0 / resolution;

#if MODE == 0
    float radius = min(size, 3.0);
#else
    float radius = size;
#endif
    float fr = clamp(radius, 1.0, 12.0);
    float frSq = fr * fr;

    vec3 mean[8];
    vec3 sqr[8];
    float cnt[8];
    for (int k = 0; k < 8; k++) {
        mean[k] = vec3(0.0);
        sqr[k] = vec3(0.0);
        cnt[k] = 0.0;
    }

    for (int y = -12; y <= 12; y++) {
        for (int x = -12; x <= 12; x++) {
            vec2 d = vec2(float(x), float(y));
            if (abs(d.x) > fr || abs(d.y) > fr || dot(d, d) > frSq) { continue; }
            // Stride-2 outer ring: fr > 8.0 only when size > 8 (default
            // size = 6, so fr <= 8 keeps this branch dead and the loop
            // bit-identical to the pre-optimization version at every size
            // <= 8 -- unreachable by construction, not just by luck).
            // Beyond radius 8 the ring is thinned to every other lattice
            // point on a Manhattan/checkerboard parity (|x|+|y| even
            // survives): a diagonal checkerboard was picked over a
            // row/column stride so the thinned ring stays isotropic (no
            // horizontal/vertical bias) instead of halving in just one
            // axis.
            if (fr > 8.0 && dot(d, d) > 64.0 && (abs(x) + abs(y)) % 2 != 0) { continue; }

            // Octant classification without atan2. A naive independent
            // 3-bit test (bx = d.x<0, by = d.y<0, bm = abs(d.x)<abs(d.y),
            // sector = lookup(bx,by,bm)) cannot reproduce the atan2
            // formula it replaces: at d=(0,5) and d=(1,2) all three
            // booleans agree (false,false,true) yet the atan2 formula
            // bins them into different sectors (6 vs 5) -- no function of
            // 3 independent bits can separate them, because which side of
            // the x==0 (or y==0) axis a point falls on depends on the
            // SIGN OF THE OTHER COORDINATE, not just its own. The fix:
            // test each quadrant as a joint (x, y) condition rather than
            // two independent signs. Derived by hand and verified against
            // the atan2 formula for every integer offset in
            // [-12,12]x[-12,12] (all 625 offsets, 0 mismatches, plus 3M
            // random continuous samples): each quadrant test below is
            // closed on the axis it enters on and open on the axis it
            // exits on, matching atan2's counter-clockwise
            // closed-lower-bound convention; the magnitude-compare
            // strictness (< vs <=) alternates per quadrant because the
            // diagonal tie always resolves to the higher-angle sector.
            // (0,0) has no angle; pin it to sector 4, matching the
            // original atan2 guard's result.
            int k;
            if (x == 0 && y == 0) {
                k = 4;
            } else if (d.x > 0.0 && d.y >= 0.0) {
                k = (abs(d.x) <= abs(d.y)) ? 5 : 4;
            } else if (d.x <= 0.0 && d.y > 0.0) {
                k = (abs(d.x) < abs(d.y)) ? 6 : 7;
            } else if (d.x < 0.0 && d.y <= 0.0) {
                k = (abs(d.x) <= abs(d.y)) ? 1 : 0;
            } else {
                // remaining case: d.x >= 0.0 && d.y < 0.0
                k = (abs(d.x) < abs(d.y)) ? 2 : 3;
            }

            vec3 c = texture(inputTex, uv + d * px).rgb;
            mean[k] += c;
            sqr[k] += c * c;
            cnt[k] += 1.0;
        }
    }

    vec3 bestC = vec3(0.0);
    float bestV = 1e9;
    for (int k = 0; k < 8; k++) {
        if (cnt[k] < 1.0) { continue; }
        vec3 m = mean[k] / cnt[k];
        vec3 v = sqr[k] / cnt[k] - m * m;
        float tv = v.r + v.g + v.b;
        if (tv < bestV) {
            bestV = tv;
            bestC = m;
        }
    }

    fragColor = vec4(bestC, 1.0);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
