// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Wind - directional streak filter (Photoshop Wind: Wind / Blast / Stagger).
 *
 * For each pixel, march upwind up to L = 4 + strength/100 * 60 samples
 * looking for the brightest sample that exceeds this pixel's own
 * luminance by threshold/100. That sample is painted back onto the
 * current pixel, decayed by how far upwind it was found (blast has no
 * decay - a solid smear) and scaled by a per-scanline-segment random
 * factor, so streaks break into randomized runs instead of covering
 * every row uniformly. Final composite is max(src, streak) so the
 * effect can only brighten, never darken, the source.
 *
 * Sign convention: direction fromLeft (0) means the wind blows from the
 * left, so bright features trail streaks to their RIGHT. To paint that
 * streak onto a given pixel we must look for its bright source upwind,
 * i.e. to the LEFT, so the march step is negative (-x). fromRight (1)
 * is the mirror: streaks trail left, so the march direction is +x.
 * stagger offsets the march start by L/2 on alternating 4px-tall row
 * bands, so adjacent bands sample from different points along the
 * upwind scanline, producing a staggered/broken streak pattern.
 *
 * Horizontal-only march: no directional or rotational geometry crosses
 * the Y axis anywhere in this shader, so a GLSL/WGSL Y-origin mismatch
 * cannot mirror the output geometry. Raw Y is not absent, though:
 * globalCoord.y feeds the per-scanline hash seed and the stagger
 * band-parity test directly. A flipped Y origin there would only select
 * a different, equally valid random segmentation/band phase - not
 * corrupt the result - but that is an empirical claim, not a structural
 * one: cross-backend bit-parity of those specific branches (including
 * stagger) is established via --pixel-parity (see task-9-report.md's
 * Stagger parity close-out), not guaranteed by the shader's structure.
 *
 * Sampling offsets are plain kernel-style pixel offsets off
 * gl_FragCoord (no tile remap needed - nothing here remaps coordinates
 * in global space). Only the per-segment random-run-length hash is
 * seeded from the tile-aware global coordinate (gl_FragCoord +
 * tileOffset) so the streak-segment pattern is continuous across CLI
 * render tiles instead of restarting at each tile's local origin (see
 * filter/scatter's tile-jitter precedent, commit ff5e45f4).
 */



uniform vec2 resolution;
uniform vec2 tileOffset;
uniform int method;
uniform int direction;
uniform float strength;
uniform float threshold;

out vec4 fragColor;

#define METHOD_BLAST 1
#define METHOD_STAGGER 2

const int MAX_STEPS = 64;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

void nm_main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 globalCoord = gl_FragCoord.xy + tileOffset;

    vec4 src = texture(inputTex, uv);
    float lumBase = lum(src.rgb);

    float L = 4.0 + strength / 100.0 * 60.0;

    // fromLeft (0): wind blows left->right, streaks trail right, so the
    // upwind search direction (toward the bright source) is -x.
    float marchDir = (direction == 0) ? -1.0 : 1.0;

    // Stagger: alternate 4px-tall row bands offset their march start by
    // L/2 so adjacent bands sample different parts of the upwind
    // scanline.
    float staggerStart = 0.0;
    if (method == METHOD_STAGGER) {
        float band = floor(globalCoord.y / 4.0);
        if (mod(band, 2.0) >= 1.0) {
            staggerStart = L * 0.5;
        }
    }

    vec3 bestColor = vec3(0.0);
    float bestLum = -1.0;
    float bestStep = 0.0;
    bool found = false;

    for (int i = 1; i <= MAX_STEPS; i++) {
        if (float(i) > L) { break; }
        float marchStep = staggerStart + float(i);
        vec2 sampleUV = clamp((gl_FragCoord.xy + vec2(marchDir * marchStep, 0.0)) / resolution, 0.0, 1.0);
        vec3 sampleColor = texture(inputTex, sampleUV).rgb;
        float sampleLum = lum(sampleColor);
        if (sampleLum > lumBase + threshold / 100.0 && sampleLum > bestLum) {
            bestLum = sampleLum;
            bestColor = sampleColor;
            bestStep = float(i);
            found = true;
        }
    }

    float decay = (method == METHOD_BLAST) ? 1.0 : exp(-3.0 * bestStep / L);

    // Per-scanline-segment random run length: every pixel in the same
    // L-pixel-wide segment of a scanline shares one random scale
    // factor, so streaks break into randomized runs instead of a
    // uniform wash. +17.0 is an arbitrary decorrelation constant, not a
    // uniform.
    float runScale = hash12(vec2(floor(globalCoord.y), floor(globalCoord.x / L)) + 17.0);

    float alpha = found ? decay * runScale : 0.0;
    vec3 streak = bestColor * alpha;

    fragColor = vec4(max(src.rgb, streak), src.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
