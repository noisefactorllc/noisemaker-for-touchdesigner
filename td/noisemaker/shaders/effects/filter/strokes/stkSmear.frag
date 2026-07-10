// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Strokes - stkSmear pass: bounded directional accumulation covering
 * Photoshop's Angled Strokes, Sprayed Strokes, Dark Strokes, Sumi-e, and
 * Smudge Stick (Brush Strokes / Artistic filters). Every mode samples up
 * to MAX_TAPS taps on each side of uv along a direction dirUnit, with a
 * per-pixel jittered run length
 *   L = mix(3, 50, strokeLength/100) * (0.5 + hash12(gc))
 * (S1 hash on the tile-aware integer global pixel gc) and exponential
 * decay weights exp(-2i/L) (S3-style symmetric tap loop, task's decay
 * curve in place of a Gaussian). MODE is a compile-time define injected
 * by the runtime (definition.js globals.mode.define), same mechanism as
 * filter/oilPaint and filter/hatch.
 *
 *   angled (0)  - two smear fields (45deg, 135deg) blended by which side
 *                 of `balance` the source luminance falls on: light
 *                 tones read the 45deg field, dark tones the 135deg
 *                 field.
 *   sprayed (1) - single 45deg field; each tap gets an extra symmetric 2D
 *                 jitter (S1 hash22) scaled by `intensity`, so dabs
 *                 scatter off the stroke line instead of following it
 *                 exactly. Jitter is recentered ((hash-0.5) rather than
 *                 the raw [0,1) hash) so the scatter is unbiased in every
 *                 direction, not just skewed toward +x/+y - an
 *                 implementer clarification of the task's literal
 *                 "hash22 * intensity/100 * 6" (uncentered would bias
 *                 every dab toward one quadrant).
 *   dark (2)    - single 45deg field, then a per-pixel tone crush/lift on
 *                 the SMEARED color: shadows (lum(c) < balance/100)
 *                 darken further via pow(c, 1+intensity/50); highlights
 *                 lift slightly via pow(c, 1/(1+intensity/100)).
 *   sumiE (3)   - every texture fetch the smear loop makes (center +
 *                 taps, via srcSample) is pre-passed through a 3x3 min
 *                 filter (erode3x3, morphology-style inline op), then
 *                 accumulated at 135deg through the SAME smear() tap
 *                 loop every other mode uses - there is no separate or
 *                 additional blur pass; the erosion dilating dark
 *                 regions into that shared directional accumulation is
 *                 what produces the wide, soft, wet-ink look. A final
 *                 contrast-only pow curve (1+intensity/50, matching
 *                 dark's crush exponent since the brief gives no
 *                 explicit sumiE formula - an implementer judgment call
 *                 for consistency) darkens the result further.
 *   smudge (4)  - direction follows the LOCAL image structure instead of
 *                 a fixed angle: perpendicular to the S6 luminance
 *                 gradient (falls back to 45deg where the gradient is
 *                 ~0), applied only in shadows (source lum < 0.6, soft
 *                 gate over +-0.05 to avoid a hard seam) so highlights
 *                 stay untouched.
 *
 * Direction vectors are built by rotating the canonical (1,0) axis with
 * rotate2D, exactly like filter/hatch's strokeField/edgeAngle pattern:
 * fixed angles (45/135) and smudge's gradient-derived edgeAngle are both
 * fed through the SAME rotate2D helper. rotate2D's output feeds
 * fragment-coordinate sampling offsets (dirUnit is scaled and added to
 * the sampling position in smear()), so per the screen-truth doctrine
 * this is position-derived/fragment-offset geometry: GLSL keeps the
 * mat2(c,-s,s,c) form (see filter/pinch's rotate2D, filter/hatch's
 * rotate2D) and WGSL keeps its own native raw expanded form - no manual Y
 * compensation in either file. Each individual field's own tap loop is
 * symmetric (+dir and -dir sampled together) so a field's shape never
 * depends on handedness, but WHICH fixed angle reads as 45 vs 135 is not
 * guaranteed to agree bit-for-bit cross-backend via captureSurface
 * (conjugates for diagonal/rotation-asymmetric content per doctrine) -
 * the governing check for the two diagonals is an on-screen screenshot
 * comparison, documented in the task report. lumGradient's Sobel kernel
 * offsets are backend-agnostic constants (S6), so - like filter/hatch's
 * coloredPencil edgeAngle - they textually match between GLSL/WGSL with
 * no flip.
 */

#ifndef MODE
#define MODE 0
#endif



uniform vec2 resolution;
uniform vec2 tileOffset;
uniform float strokeLength;
uniform float balance;
uniform float intensity;

out vec4 fragColor;

const int MAX_TAPS = 24;

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
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

// S6 - gradient (Sobel on luminance); smudge (MODE 4) only. Backend-
// agnostic constant kernel offsets - textually identical in WGSL, no
// flip (see file header).
vec2 lumGradient(vec2 uv) {
    vec2 px = 1.0 / resolution;
    float tl = lum(texture(inputTex, uv + px * vec2(-1.0,  1.0)).rgb);
    float  l = lum(texture(inputTex, uv + px * vec2(-1.0,  0.0)).rgb);
    float bl = lum(texture(inputTex, uv + px * vec2(-1.0, -1.0)).rgb);
    float tr = lum(texture(inputTex, uv + px * vec2( 1.0,  1.0)).rgb);
    float  r = lum(texture(inputTex, uv + px * vec2( 1.0,  0.0)).rgb);
    float br = lum(texture(inputTex, uv + px * vec2( 1.0, -1.0)).rgb);
    float  t = lum(texture(inputTex, uv + px * vec2( 0.0,  1.0)).rgb);
    float  b = lum(texture(inputTex, uv + px * vec2( 0.0, -1.0)).rgb);
    return vec2(tr + 2.0 * r + br - tl - 2.0 * l - bl,
                tl + 2.0 * t + tr - bl - 2.0 * b - br);
}

// Rotates a fragment-offset direction vector by angleDeg. Position-
// derived/fragment-offset geometry -> GLSL keeps the mat2(c,-s,s,c) form
// per the screen-truth doctrine (see file header, filter/pinch's
// rotate2D, filter/hatch's rotate2D).
vec2 rotate2D(vec2 v, float angleDeg) {
    float a = radians(angleDeg);
    float co = cos(a);
    float si = sin(a);
    return mat2(co, -si, si, co) * v;
}

// MODE 3 (sumiE) only: 3x3 min filter (erode, morphology-style, inline
// per the task's "op inline" note - see filter/morphology's mode==1
// disc/square min for the non-inline precedent). Declared unconditionally
// (harmless dead code in every other compiled variant).
vec4 erode3x3(vec2 sampleUV) {
    vec2 px = 1.0 / resolution;
    vec4 m = texture(inputTex, sampleUV);
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            if (dx == 0 && dy == 0) { continue; }
            m = min(m, texture(inputTex, sampleUV + vec2(float(dx), float(dy)) * px));
        }
    }
    return m;
}

// Every smear fetch (center + taps) routes through here so sumiE's
// pre-erode applies uniformly across the whole smeared field, not just
// the base pixel. #if-gated so every other mode's compiled variant is a
// plain texture() call at zero extra cost (confirmed dead by
// construction, not just by luck: MODE is a compile-time define).
vec4 srcSample(vec2 sampleUV) {
#if MODE == 3
    return erode3x3(sampleUV);
#else
    return texture(inputTex, sampleUV);
#endif
}

// Bounded directional accumulation, up to MAX_TAPS taps on each side of
// uv along dirUnit, weights exp(-2i/L). jitterPx > 0 (sprayed, MODE 1
// only) adds a symmetric per-tap 2D hash jitter to the sample position so
// dabs scatter off the stroke line; jitterPx == 0 keeps every other
// mode's tap path a clean, un-jittered comb.
//
// L is per-pixel (jittered by hash12(gc) in main()), so `if (fi > L)
// break` makes every srcSample() call after the break non-uniform
// control flow across invocations -- harmless in GLSL (no uniformity
// requirement on texture()), so the early exit stays as a plain break
// here. The WGSL port can't do the same with plain textureSample (hard
// validation error, "must only be called from uniform control flow",
// caught by the real-browser harness, not MCP's compile check); it keeps
// this identical break/loop-bound structure but routes every fetch
// through textureSampleLevel (explicit LOD, no uniformity requirement)
// instead, rather than removing the break -- see wgsl/stkSmear.wgsl's
// srcSample/smear comments. Both forms are the same algorithm; only the
// texture-sampling call WGSL needs differs.
vec4 smear(vec2 uv, vec2 gc, vec2 dirUnit, float L, float jitterPx) {
    vec2 px = 1.0 / resolution;
    vec4 sum = srcSample(uv);
    float wsum = 1.0;
    for (int i = 1; i <= MAX_TAPS; i++) {
        float fi = float(i);
        if (fi > L) { break; }
        float w = exp(-2.0 * fi / L);
        vec2 jp = vec2(0.0);
        vec2 jn = vec2(0.0);
        if (jitterPx > 0.0) {
            jp = (hash22(gc + vec2(fi * 3.71, 7.0)) - 0.5) * jitterPx;
            jn = (hash22(gc + vec2(7.0, fi * 3.71) + 91.7) - 0.5) * jitterPx;
        }
        vec2 sampP = uv + (dirUnit * fi) * px + jp * px;
        vec2 sampN = uv - (dirUnit * fi) * px + jn * px;
        sum += (srcSample(sampP) + srcSample(sampN)) * w;
        wsum += 2.0 * w;
    }
    return sum / wsum;
}

void nm_main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 src = texture(inputTex, uv);
    vec2 gc = floor(gl_FragCoord.xy) + tileOffset;

    float runBase = mix(3.0, 50.0, strokeLength / 100.0);
    float L = runBase * (0.5 + hash12(gc));

    vec4 outc;

#if MODE == 0
    // Angled Strokes: two diagonal fields, blended by tone side of
    // `balance`. Matches the task's literal formula exactly.
    vec2 dir45 = rotate2D(vec2(1.0, 0.0), 45.0);
    vec2 dir135 = rotate2D(vec2(1.0, 0.0), 135.0);
    vec4 field45 = smear(uv, gc, dir45, L, 0.0);
    vec4 field135 = smear(uv, gc, dir135, L, 0.0);
    float b = balance / 100.0;
    float side = smoothstep(b - 0.1, b + 0.1, lum(src.rgb));
    outc = mix(field135, field45, side);
#elif MODE == 1
    // Sprayed Strokes: single 45deg field, per-tap jitter scaled by
    // intensity (see file header for the recentering rationale).
    vec2 dir45 = rotate2D(vec2(1.0, 0.0), 45.0);
    float jitterPx = intensity / 100.0 * 6.0;
    outc = smear(uv, gc, dir45, L, jitterPx);
#elif MODE == 2
    // Dark Strokes: single 45deg field, then tone-dependent crush/lift.
    vec2 dir45 = rotate2D(vec2(1.0, 0.0), 45.0);
    vec4 c = smear(uv, gc, dir45, L, 0.0);
    float t = lum(c.rgb);
    float bAmt = balance / 100.0;
    float exponent = (t < bAmt) ? (1.0 + intensity / 50.0) : (1.0 / (1.0 + intensity / 100.0));
    c.rgb = pow(max(c.rgb, vec3(0.0)), vec3(exponent));
    outc = c;
#elif MODE == 3
    // Sumi-e: srcSample() erodes every fetch this smear makes (see
    // srcSample above) before it's accumulated at 135deg through the same
    // tap loop every mode uses (no separate/additional blur pass); then a
    // contrast-only pow curve darkens the result.
    vec2 dir135 = rotate2D(vec2(1.0, 0.0), 135.0);
    vec4 c = smear(uv, gc, dir135, L, 0.0);
    c.rgb = pow(max(c.rgb, vec3(0.0)), vec3(1.0 + intensity / 50.0));
    outc = c;
#else
    // Smudge Stick (4) - fallback arm of the #if chain (MODE always
    // 0-4, injected by the runtime, so the last value needs no explicit
    // check). Direction follows local structure instead of a fixed
    // angle; only applied in shadows.
    vec2 grad = lumGradient(uv);
    float gradMag = length(grad);
    float edgeAngle = (gradMag > 1e-5) ? (degrees(atan(grad.y, grad.x)) + 90.0) : 45.0;
    vec2 dir = rotate2D(vec2(1.0, 0.0), edgeAngle);
    vec4 smeared = smear(uv, gc, dir, L, 0.0);
    float shadowMask = 1.0 - smoothstep(0.55, 0.65, lum(src.rgb));
    outc = mix(src, smeared, shadowMask);
#endif

    fragColor = vec4(clamp(outc.rgb, 0.0, 1.0), src.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
