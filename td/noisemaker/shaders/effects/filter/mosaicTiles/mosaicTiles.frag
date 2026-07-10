// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Mosaic Tiles - covers two Photoshop filters via `mode`:
 *
 *   mosaic (0)  - Filter Gallery > Texture > Mosaic Tiles: a square grid
 *                 warped by value noise into wavy ceramic tiles. Each
 *                 tile shows a mildly center-flattened sample of its own
 *                 image region (see the mosaic branch below), and tiles
 *                 are separated by grout that is darkened and beveled
 *                 with S8 directional relief shading (fixed 135-degree
 *                 light, matching filter/craquelure's convention).
 *   shifted (1) - Stylize > Tiles: a REGULAR (unwarped) square grid;
 *                 each tile's content is grabbed from a randomly shifted
 *                 source position (a per-cell hash offset, up to
 *                 maxOffset% of a tile width, constant across the whole
 *                 tile so it moves as a rigid block), leaving a small
 *                 fixed gap between tiles that is filled per `gapFill`
 *                 (backgroundColor / the inverse of the tile's own home
 *                 pixel / the unaltered home pixel).
 *
 * Both modes assign pixels to cells with the same floor/fract grid math
 * on tileSize-sized cells, in GLOBAL (tile-aware) pixel coordinates so
 * the grid and its warp are continuous across CLI render tiles. `mode`
 * is a plain runtime branch (both branches always compile in), not a
 * compile-time `define`, per the task spec.
 *
 * groutWidth is a single shared uniform reused by BOTH modes for visual
 * consistency, rather than adding a second "gap width" param: in mosaic
 * it sets the grout band's HALF-width (groutWidth% of tileSize/2,
 * measured from the warped cell border - see mosaicGroutMask below); in
 * shifted it sets the FULL fixed inter-tile gap width (groutWidth% of
 * tileSize - no /2, since it is a gap between two tile faces rather than
 * a border-hugging band, and using the full tileSize keeps the default
 * (12%) gap appropriately small/subtle, matching the task spec's "a
 * fixed small gap" wording - referencing tileSize/2 instead would make
 * the default gap barely a pixel wide). Its UI control (definition.js)
 * is gated to mosaic-only: shifted's gap is meant to read as a small
 * fixed structural constant rather than a per-mode headline control, but
 * the shader still consumes whatever value the uniform currently holds
 * in BOTH branches, so a user who wants a different shifted gap width
 * can dial it in from mosaic mode's grout slider before switching modes.
 *
 * seed is mixed into the mosaic warp's vnoise lookup position (via the
 * same `seedVal * 101.7` large-offset-translation idiom filter/stipple
 * and filter/craquelure use for their hash lookups), even though the
 * task's condensed algorithm formula omits a seed term from the warp -
 * without this, `seed` would be a completely dead control in mosaic mode
 * (nothing else in that branch depends on it), which would fail the
 * task's own seed-variation responsiveness check. This mirrors
 * filter/stipple's precedent of extending a literally-scoped spec detail
 * (there: density's bias term, applied to both its mezzo AND
 * reticulation branches) to a structurally identical sibling case for a
 * consistent, non-dead control.
 */



uniform vec2 resolution;
uniform vec2 tileOffset;
uniform vec2 fullResolution;
uniform int mode;
uniform float tileSize;
uniform float groutWidth;
uniform float relief;
uniform float maxOffset;
uniform int gapFill;
uniform vec3 backgroundColor;
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

// S4 - value noise (fBm not needed here).
float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
               mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), u.x), u.y);
}

// S8 - relief shade from height (verbatim).
float reliefShade(float hC, float hR, float hT, float strength, float lightAngleDeg) {
    vec2 grad = vec2(hR - hC, hT - hC) * strength;
    vec3 n = normalize(vec3(-grad, 1.0));
    float a = radians(lightAngleDeg);
    vec3 L = normalize(vec3(cos(a), sin(a), 0.75));
    return clamp(dot(n, L), 0.0, 1.0);
}

// Mosaic mode's wavy-grid warp scalar (px) at global pixel position gc,
// broadcast equally to both axes when added to gc (see main()'s mosaic
// branch) - a single continuous scalar field is enough to wave every
// cell border, because two neighboring pixels straddling a nominal
// border pick up slightly different offsets as the noise varies, which
// bends the actual floor()-quantized cell boundary between them (the
// same domain-warp-before-quantize mechanism filter/craquelure uses for
// its crack path, there applied identically to both axes for the same
// reason - see craquelure.glsl's header).
float mosaicWarp(vec2 gc, float tileSizePx, float seedVal) {
    return vnoise(gc / tileSizePx + seedVal * 101.7) * 0.25 * tileSizePx;
}

// Mosaic mode's grout mask (1 = on grout, 0 = tile interior) at global
// pixel position gc: warps gc, finds the fractional position within its
// tileSizePx cell, and turns the distance to the nearest cell edge into
// an antialiased band of half-width `groutWidthPct% of tileSizePx/2`.
float mosaicGroutMask(vec2 gc, float tileSizePx, float groutWidthPct, float seedVal) {
    float warp = mosaicWarp(gc, tileSizePx, seedVal);
    vec2 cellFrac = fract((gc + vec2(warp)) / tileSizePx);
    float edgeDistPx = min(min(cellFrac.x, 1.0 - cellFrac.x), min(cellFrac.y, 1.0 - cellFrac.y)) * tileSizePx;
    float groutHalfWidthPx = groutWidthPct / 100.0 * (tileSizePx * 0.5);
    float groutAA = 1.25;
    return 1.0 - smoothstep(groutHalfWidthPx - groutAA, groutHalfWidthPx + groutAA, edgeDistPx);
}

void nm_main() {
    vec2 globalCoord = gl_FragCoord.xy + tileOffset;
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 srcHome = texture(inputTex, uv);
    float seedF = float(seed);

    vec3 result;

    if (mode == 0) {
        // Mosaic: wavy tiles with beveled grout.
        float warp = mosaicWarp(globalCoord, tileSize, seedF);
        vec2 warpedCoord = globalCoord + vec2(warp);
        vec2 cellSpace = warpedCoord / tileSize;
        vec2 cellId = floor(cellSpace);
        vec2 cellFrac = fract(cellSpace);

        // Flattened sample position: bias this pixel's (warped) position
        // toward its cell's center by flattenAmount, entirely in
        // cell-space (cellFrac and the mix target 0.5 are both always in
        // [0,1], so the mixed result is too) - this is what makes the
        // sample "cell-clamped" per the task spec: it can never cross
        // into a neighboring cell regardless of how close to an edge the
        // source pixel sits. The warp is undone with the SAME scalar
        // computed at this pixel's own position rather than
        // re-evaluated at the flattened position - warp varies smoothly
        // at the tileSize noise period, so reusing it as a constant
        // across the small flatten displacement is a good approximation
        // without a second noise lookup.
        float flattenAmount = 0.4;
        vec2 flattenedCellFrac = mix(cellFrac, vec2(0.5), flattenAmount);
        vec2 flattenedGc = (cellId + flattenedCellFrac) * tileSize - vec2(warp);
        vec2 sampleUV = clamp((flattenedGc - tileOffset) / resolution, 0.0, 1.0);
        vec3 tileColor = texture(inputTex, sampleUV).rgb;

        // True central-difference gradient of the grout mask (5 bounded
        // evaluations total), fed into S8's reliefShade exactly like
        // filter/craquelure's crack wall shading.
        float kC = mosaicGroutMask(globalCoord, tileSize, groutWidth, seedF);
        float kR = mosaicGroutMask(globalCoord + vec2(1.0, 0.0), tileSize, groutWidth, seedF);
        float kL = mosaicGroutMask(globalCoord - vec2(1.0, 0.0), tileSize, groutWidth, seedF);
        float kT = mosaicGroutMask(globalCoord + vec2(0.0, 1.0), tileSize, groutWidth, seedF);
        float kB = mosaicGroutMask(globalCoord - vec2(0.0, 1.0), tileSize, groutWidth, seedF);

        // Central-difference gradient of the grout mask k; feeds
        // reliefShade's synthetic height samples below.
        vec2 gradK = vec2((kR - kL) * 0.5, (kT - kB) * 0.5);

        // Height fed to reliefShade is -k, NOT +k: grout is a carved
        // groove (a dip), not a raised ridge, so height must FALL toward
        // the grout center. Negating hC/hR/hT flips the sign of the
        // gradient/normal reliefShade sees, which puts the lit wall on
        // the correct (concave-groove) side of the grout - mirrors
        // filter/craquelure's crack-wall fix, see its 83a0731c commit
        // for the full derivation.
        float hC = -kC;
        float hR = hC - gradK.x;
        float hT = hC - gradK.y;
        float shadeStrength = 6.0;
        float shade = reliefShade(hC, hR, hT, shadeStrength, 135.0);

        // reliefShade's flat-ground (zero-gradient) value is exactly 0.6
        // for ANY lightAngleDeg (L's z-component is a fixed 0.75 before
        // normalizing by a length that always works out to 1.25
        // regardless of angle, since cos^2+sin^2=1), so centering the
        // bevel multiplier there - rather than filter/craquelure's
        // literal 0.5 - makes relief contribute EXACTLY zero shading
        // away from any grout, not just at relief=0 (a small correctness
        // improvement; craquelure's 0.5 centering leaves a faint uniform
        // tint across its whole image that this avoids). Unlike
        // craquelure's wallMask, no additional gradient gate is needed
        // here: the grout mask k already saturates to an exact flat
        // plateau (0) away from any grout band by construction
        // (mosaicGroutMask's smoothstep has a clamped range), so gradK -
        // and therefore shade's departure from flatShade - is already
        // exactly zero there.
        float flatShade = 0.6;
        vec3 darkened = tileColor * mix(1.0, 0.35, kC);
        float shadeMul = 1.0 + (shade - flatShade) * 2.0 * (relief / 100.0);
        result = clamp(darkened * shadeMul, 0.0, 1.0);
    } else {
        // Shifted: regular grid, each tile's content grabbed from a
        // randomly shifted source position, small fixed gap between
        // tiles filled per gapFill.
        vec2 cellSpace = globalCoord / tileSize;
        vec2 cellId = floor(cellSpace);
        vec2 cellFrac = fract(cellSpace);
        float edgeDistPx = min(min(cellFrac.x, 1.0 - cellFrac.x), min(cellFrac.y, 1.0 - cellFrac.y)) * tileSize;

        float gapWidthPx = groutWidth / 100.0 * tileSize;
        float gapAA = 1.25;
        float gapMask = 1.0 - smoothstep(gapWidthPx * 0.5 - gapAA, gapWidthPx * 0.5 + gapAA, edgeDistPx);

        // x2.0: expands the hash's +/-0.5 span to +/-1.0 so offsetPx spans the full +/-maxOffset% of tileSize the params table describes (the brief's literal formula lacks this factor).
        vec2 offsetPx = (hash22(cellId + seedF * 101.7) - 0.5) * 2.0 * (maxOffset / 100.0) * tileSize;
        vec2 shiftedGc = globalCoord + offsetPx;
        vec2 shiftedUV = clamp((shiftedGc - tileOffset) / resolution, 0.0, 1.0);
        vec3 tileColor = texture(inputTex, shiftedUV).rgb;

        vec3 gapColor;
        if (gapFill == 0) {
            // background
            gapColor = backgroundColor;
        } else if (gapFill == 1) {
            // inverse of the tile's own home pixel
            gapColor = 1.0 - srcHome.rgb;
        } else {
            // unaltered home pixel
            gapColor = srcHome.rgb;
        }

        result = mix(tileColor, gapColor, gapMask);
    }

    // Alpha always comes from the pixel's own unmodified home position,
    // matching filter/stipple's precedent - true in the gapFill/unaltered
    // path too, since it already samples srcHome for its color.
    fragColor = vec4(result, srcHome.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
