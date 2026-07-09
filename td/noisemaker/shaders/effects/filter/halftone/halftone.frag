// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Halftone - rotated-screen halftone reproduction. Covers Photoshop's
 * Color Halftone (mode: color) and Halftone Pattern (mode: mono).
 *
 * Screen geometry: global (tile-aware) pixel coordinates are rotated by
 * the screen's angle and tiled into `frequency`-px cells; a fragment's
 * distance to the cell's ink feature (dot center / line midline / ring
 * band) drives an antialiased coverage value via smoothstep against
 * fwidth(), so the screen stays crisp at any resolution.
 *
 * mode == 0 (color): drives three independent screens, one per RGB
 * channel, at angle + {108, 162, 90} - Photoshop's default Color
 * Halftone screen angles - and multiplies their ink coverage into the
 * output so overlapping dots darken like overprinted ink (rosette). Each
 * screen's dot SIZE comes from that channel's own value, sampled with a
 * light 3x3 box blur at the CENTER of the current fragment's screen cell
 * (not the fragment itself) so a cell's dot has one flat size - the
 * posterized "true halftone" look - rather than wobbling with in-cell
 * image detail.
 *
 * mode == 1 (mono): drives a single screen from image luminance. The
 * `pattern` dropdown selects the spot function: dot (radial distance
 * within the rotated cell), line (distance to the cell's rotated
 * midline - parallel engraving-style lines along the screen angle), or
 * circle (concentric rings measured from the image center, unrotated).
 * dot/line reuse the same cell-center sampling as color mode; circle has
 * no natural grid cell to center on, so it uses a mild local blur at the
 * fragment itself. Output is tonemapped between `paperColor` (no ink)
 * and `inkColor` (full ink).
 *
 * All cell math uses GLSL's `fract`, which is already floor-based
 * (`fract(x) = x - floor(x)`) and therefore safe for the negative
 * coordinates a rotated screen produces off-origin - no manual
 * floored-mod needed.
 */



uniform vec2 resolution;
uniform vec2 tileOffset;
uniform vec2 fullResolution;
uniform int mode;
uniform int pattern;
uniform float frequency;
uniform float angle;
uniform float sharpness;
uniform vec3 inkColor;
uniform vec3 paperColor;

out vec4 fragColor;

float lum(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

vec3 tonemap2(float t, vec3 ink, vec3 paper) {
    return mix(ink, paper, clamp(t, 0.0, 1.0));
}

// Rotates a position-derived (global pixel space) vector by angleDeg.
// GLSL uses this mat2(c,-s,s,c) form for position-derived geometry per
// the screen-truth doctrine (see filter/pinch's rotate2D, filter/
// pondRipples) - no manual Y compensation. Because this matrix is
// orthonormal, calling it with -angleDeg gives the exact inverse
// rotation (its transpose), which cellSampleFromRuv relies on below.
vec2 rotate2D(vec2 v, float angleDeg) {
    float a = radians(angleDeg);
    float co = cos(a);
    float si = sin(a);
    return mat2(co, -si, si, co) * v;
}

vec3 boxBlur3(vec2 uv, vec2 texel) {
    vec3 sum = vec3(0.0);
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 o = vec2(float(x), float(y)) * texel;
            sum += texture(inputTex, clamp(uv + o, 0.0, 1.0)).rgb;
        }
    }
    return sum / 9.0;
}

// Blurred RGB sampled at the center of the rotated screen cell whose
// already-rotated-and-scaled coordinate is `ruv` (= rotate2D(gc,
// angleDeg) / frequency). Sampling the cell CENTER instead of the
// current fragment gives every dot in the cell one flat size - see file
// header.
vec3 cellSampleFromRuv(vec2 ruv, float angleDeg, vec2 texel) {
    vec2 cellId = floor(ruv) + 0.5;
    vec2 cellCenterGc = rotate2D(cellId * frequency, -angleDeg);
    vec2 cellUV = clamp((cellCenterGc - tileOffset) / resolution, 0.0, 1.0);
    return boxBlur3(cellUV, texel);
}

// Antialiased ink coverage (1 = full ink, 0 = bare paper) for a spot
// whose size is set by `value` (0..1, larger = more ink) at normalized
// distance `d` from the spot's feature. `sharpnessPct` is the user-facing
// 0-100 uniform; higher values narrow the antialiased transition for
// crisper edges (internally this is "1 - sharpness" worth of softness,
// mixing a wide constant fallback with the fwidth-derived crisp width).
float halftoneCoverage(float d, float value, float sharpnessPct) {
    float spot = sqrt(clamp(value, 0.0, 1.0)) * 0.7071;
    float softness = 1.0 - clamp(sharpnessPct / 100.0, 0.0, 1.0);
    float aa = mix(fwidth(d) * 1.5, 0.35, softness);
    return smoothstep(spot + aa, spot - aa, d);
}

void nm_main() {
    vec2 globalCoord = gl_FragCoord.xy + tileOffset;
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 texel = 1.0 / resolution;
    float alpha = texture(inputTex, uv).a;

    if (mode == 0) {
        // Color Halftone.
        vec2 ruvR = rotate2D(globalCoord, angle + 108.0) / frequency;
        vec2 ruvG = rotate2D(globalCoord, angle + 162.0) / frequency;
        vec2 ruvB = rotate2D(globalCoord, angle + 90.0) / frequency;
        float valR = 1.0 - cellSampleFromRuv(ruvR, angle + 108.0, texel).r;
        float valG = 1.0 - cellSampleFromRuv(ruvG, angle + 162.0, texel).g;
        float valB = 1.0 - cellSampleFromRuv(ruvB, angle + 90.0, texel).b;
        float inkR = halftoneCoverage(length(fract(ruvR) - 0.5), valR, sharpness);
        float inkG = halftoneCoverage(length(fract(ruvG) - 0.5), valG, sharpness);
        float inkB = halftoneCoverage(length(fract(ruvB) - 0.5), valB, sharpness);
        fragColor = vec4(1.0 - inkR, 1.0 - inkG, 1.0 - inkB, alpha);
        return;
    }

    // Halftone Pattern (mono).
    float value;
    float d;
    if (pattern == 2) {
        // circle: concentric rings from the fixed image center, unrotated.
        vec2 center = fullResolution * 0.5;
        value = 1.0 - lum(boxBlur3(uv, texel));
        float rd = length(globalCoord - center) / frequency;
        d = abs(fract(rd) - 0.5);
    } else {
        vec2 ruv = rotate2D(globalCoord, angle) / frequency;
        value = 1.0 - lum(cellSampleFromRuv(ruv, angle, texel));
        vec2 off = fract(ruv) - 0.5;
        d = (pattern == 1) ? abs(off.y) : length(off); // 1 = line, else dot
    }
    float ink = halftoneCoverage(d, value, sharpness);
    fragColor = vec4(tonemap2(1.0 - ink, inkColor, paperColor), alpha);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
