// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Stipple - discrete random marks reproducing image tone. Covers three
 * Photoshop filters via `mode`:
 *
 *   pointillize (0)  - Pixelate > Pointillize: colored dots on a paper
 *                       background, one dot per jittered-grid Voronoi
 *                       cell (S5), sized by that cell's own darkness.
 *                       Inside the dot the color is the image sampled at
 *                       the cell's seed point (flat per dot, like real
 *                       pointillism); outside is paperColor.
 *   mezzoDots/Lines/Strokes (1/2/3) - Pixelate > Mezzotint's dots/lines/
 *                       strokes conversion types: each RGB channel is
 *                       independently hard-thresholded against a shaped
 *                       value-noise field, producing the harsh per-
 *                       channel black/white/primary speckle real
 *                       mezzotint conversion has. No AA is applied to the
 *                       threshold - mezzotint is a hard binary process in
 *                       Photoshop, and softening it would blur the per-
 *                       channel color separation that makes the effect
 *                       read as mezzotint rather than an ordered dither.
 *   reticulation (4) - Filter Gallery > Sketch > Reticulation: a two-tone
 *                       ink/paper tonemap driven by fBm "clump" noise
 *                       whose amplitude is modulated by local luminance,
 *                       so shadows fill in with dense broad clumps and
 *                       highlights break up into fine grain.
 *
 * Single pass on global (tile-aware) pixel coordinates so every pattern
 * (Voronoi grid, noise field) is continuous across CLI render tiles.
 *
 * `density` biases the ink/paper balance in BOTH the mezzo branch (its
 * threshold n) and the reticulation branch (its threshold clumpNoise)
 * with the identical (density-50)/100 term - the task spec's algorithm
 * only spells this out for mezzo, but its params table documents density
 * as "reticulation balance / mezzo bias", and clumpNoise-vs-lum is
 * structurally the same threshold-vs-value pairing as mezzo's n-vs-
 * channel, so the same bias mechanism was extended there for a
 * consistent, non-dead control across every mode that enables it.
 *
 * mezzoStrokes rotates the sampling position 45 degrees before shaping
 * the anisotropic (line) noise. That rotation is applied to
 * position-derived geometry (the fragment's own global coordinate), so
 * per the screen-truth doctrine GLSL uses the mat2(c,-s,s,c) rotation
 * form here (see rotate2D, matching filter/pinch and filter/halftone).
 * The rotation can push the noise-lookup position negative even though
 * globalCoord itself never is; every noise/hash function below is built
 * from `floor`/`fract`, which are floor-based (not truncated) in GLSL
 * for negative inputs, so no separate floored-mod wrap is needed here
 * (same reasoning as filter/halftone's rotated cell math).
 */



uniform vec2 resolution;
uniform vec2 tileOffset;
uniform vec2 fullResolution;
uniform int mode;
uniform float cellSize;
uniform float grainSize;
uniform float density;
uniform vec3 paperColor;
uniform int seed;

out vec4 fragColor;

// S1 - hash / jitter.
float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xx + p3.yz) * p3.zy);
}

// S2 - luminance.
float lum(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

// S4 - value noise + fBm.
float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
               mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 5; i++) {
        v += a * vnoise(p);
        p *= 2.03;
        a *= 0.5;
    }
    return v;
}

// S5 - jittered-grid Voronoi cell: returns xy = seed point in the same
// cell-space units as `p`, zw = integer cell id. Search radius is one
// ring of neighbor cells, so jitter must stay within [0, 1] for the
// nearest seed to always be found within the search window.
vec4 voronoiCell(vec2 p, float jitter, float seedVal) {
    vec2 g = floor(p);
    vec2 f = p - g;
    float best = 1e9;
    vec4 res = vec4(0.0);
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 cell = vec2(float(x), float(y));
            vec2 pt = cell + 0.5 + (hash22(g + cell + seedVal * 101.7) - 0.5) * jitter;
            float d = dot(pt - f, pt - f);
            if (d < best) {
                best = d;
                res = vec4(g + pt, g + cell);
            }
        }
    }
    return res;
}

// S9 - ink/paper tonemap.
vec3 tonemap2(float t, vec3 ink, vec3 paper) {
    return mix(ink, paper, clamp(t, 0.0, 1.0));
}

// Rotates a position-derived (global pixel space) vector by angleDeg.
// GLSL uses this mat2(c,-s,s,c) form for position-derived geometry per
// the screen-truth doctrine (see filter/pinch's rotate2D, filter/
// halftone's rotate2D) - no manual Y compensation.
vec2 rotate2D(vec2 v, float angleDeg) {
    float a = radians(angleDeg);
    float co = cos(a);
    float si = sin(a);
    return mat2(co, -si, si, co) * v;
}

void nm_main() {
    vec2 globalCoord = gl_FragCoord.xy + tileOffset;
    vec2 uv = gl_FragCoord.xy / resolution;
    float alpha = texture(inputTex, uv).a;
    vec3 result;

    if (mode == 0) {
        // Pointillize: one dot per jittered Voronoi cell (cellSize px),
        // colored and sized from the image at that cell's own seed
        // point; darker seed colors get bigger dots. Background is
        // paperColor. fwidth-based AA on the dot edge.
        vec2 p = globalCoord / cellSize;
        vec4 cell = voronoiCell(p, 0.9, float(seed));
        vec2 seedGc = cell.xy * cellSize;
        vec2 seedUV = clamp((seedGc - tileOffset) / resolution, 0.0, 1.0);
        vec3 seedColor = texture(inputTex, seedUV).rgb;
        float radius = 0.35 + 0.4 * (1.0 - lum(seedColor));
        float d = length(p - cell.xy);
        float aa = fwidth(d) * 1.5;
        float inside = smoothstep(radius + aa, radius - aa, d);
        result = mix(paperColor, seedColor, inside);
    } else if (mode == 1 || mode == 2 || mode == 3) {
        // Mezzotint dots/lines/strokes: per-channel hard threshold
        // against shaped value noise. density biases the threshold (n)
        // directly, so higher density raises n and lowers the fraction
        // of channel values that clear it - i.e. more ink.
        vec2 gc = globalCoord;
        if (mode == 3) {
            gc = rotate2D(gc, 45.0);
        }
        vec2 noiseP;
        if (mode == 1) {
            noiseP = gc / grainSize;
        } else {
            // Anisotropic (line) noise: the Y component keeps the coarse
            // (grainSize*8) scale and X keeps the fine (grainSize) scale,
            // so the field is coherent/slowly-varying down each column
            // and decorrelates quickly across a row - i.e. streaks
            // elongated along Y (vertical), matching the brief's
            // "vertical streaks" acceptance target. Swapped from a
            // literal x-coarse/y-fine reading of the spec, which was
            // verified (lag-1 luma autocorrelation on a solid-color
            // source region: 0.94 along X vs 0.49 along Y before this
            // swap) to render HORIZONTAL streaks instead.
            noiseP = gc * vec2(1.0 / grainSize, 1.0 / (grainSize * 8.0));
        }
        float n = vnoise(noiseP + float(seed) * 101.7);
        n += (density - 50.0) / 100.0;
        vec3 src = texture(inputTex, uv).rgb;
        result = vec3(step(n, src.r), step(n, src.g), step(n, src.b));
    } else {
        // Reticulation: two-tone ink/paper tonemap against clumped fBm
        // noise; the noise amplitude is luminance-modulated so shadows
        // fill in with broad dense clumps and highlights break into
        // fine grain. density biases the ink/paper balance using the
        // exact same (density-50)/100 term the mezzo branch applies to
        // its threshold, since clumpNoise vs l is structurally the same
        // threshold-vs-value pairing as mezzo's n vs channel.
        vec3 src = texture(inputTex, uv).rgb;
        float l = lum(src);
        float clumpNoise = fbm(globalCoord / (grainSize * 4.0) + float(seed) * 101.7) * mix(1.2, 0.6, l);
        clumpNoise += (density - 50.0) / 100.0;
        result = tonemap2(step(clumpNoise, l), vec3(0.05), vec3(0.97));
    }

    fragColor = vec4(result, alpha);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
