// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
// Grain: blend the source image with animated noise. GRAIN_TYPE selects the
// noise kernel (Photoshop Texture>Grain's 10 types); intensity/contrast/mono
// reshape whichever kernel is active before it is mixed with the source.
//
// grainType 0 (regular) is the ORIGINAL implementation: it mirrors
// noisemaker.effects.grain, which calls value.values() using simplex-based
// value noise with bicubic interpolation. At grainType=regular, intensity=40,
// contrast=50, mono=true (all defaults), the extended pipeline reduces
// algebraically to the exact pre-existing formula -- see apply_intensity()
// and apply_contrast() below for the identity proof at each stage.
//
// GRAIN_TYPE is a compile-time define injected by the runtime (see
// definition.js `globals.grainType.define`), same mechanism/rationale as
// filter/texture's MODE.
#ifndef GRAIN_TYPE
#define GRAIN_TYPE 0
#endif

const float PI = 3.14159265358979323846;
const float TAU = 6.28318530717958647692;
const float UINT32_TO_FLOAT = 1.0 / 4294967296.0;
const uint CHANNEL_COUNT = 4u;
const uint INTERPOLATION_CONSTANT = 0u;
const uint INTERPOLATION_LINEAR = 1u;
const uint INTERPOLATION_COSINE = 2u;
const uint INTERPOLATION_BICUBIC = 3u;
const uint BASE_SEED = 0x1234u;
const vec3 LUMA_WEIGHTS = vec3(0.2126, 0.7152, 0.0722);
// Per-channel seed/coordinate salts for mono=false (chromatic) noise. Channel
// 0 (red) always gets a zero salt so the mono=true path (channel 0 only) is
// byte-identical to the pre-existing single-hash behavior.
const uint CHANNEL_SEED_STEP = 0x01000193u;
const vec2 CHANNEL_COORD_STEP = vec2(131.0, 71.0);


uniform vec2 resolution;
uniform vec2 tileOffset;
uniform vec2 fullResolution;
uniform float renderScale;
uniform float alpha;
uniform float time;
uniform float pause;
uniform float intensity;
uniform float contrast;
uniform float mono;

out vec4 fragColor;

uint as_u32(float value) {
    return uint(max(round(value), 0.0));
}

float clamp01(float value) {
    return clamp(value, 0.0, 1.0);
}

uvec3 pcg3d(uvec3 v_in) {
    uvec3 v = v_in * 1664525u + 1013904223u;
    v.x = v.x + v.y * v.z;
    v.y = v.y + v.z * v.x;
    v.z = v.z + v.x * v.y;
    v = v ^ (v >> uvec3(16u));
    v.x = v.x + v.y * v.z;
    v.y = v.y + v.z * v.x;
    v.z = v.z + v.x * v.y;
    return v;
}

float random_from_cell_3d(ivec3 cell, uint seed) {
    uvec3 hashed = uvec3(
        uint(cell.x) ^ seed,
        uint(cell.y) ^ (seed * 0x9e3779b9u + 0x7f4a7c15u),
        uint(cell.z) ^ (seed * 0x632be59bu + 0x5bf03635u)
    );
    uvec3 noise = pcg3d(hashed);
    return float(noise.x) * UINT32_TO_FLOAT;
}

float periodic_value(float time_value, float sample_val) {
    return (sin((time_value - sample_val) * TAU) + 1.0) * 0.5;
}

float interpolation_weight(float value, uint spline_order) {
    if (spline_order == INTERPOLATION_COSINE) {
        float clamped = clamp(value, 0.0, 1.0);
        float angle = clamped * PI;
        float cos_value = cos(angle);
        return (1.0 - cos_value) * 0.5;
    }
    return value;
}

float blend_cubic(float a, float b, float c, float d, float g) {
    float t = clamp(g, 0.0, 1.0);
    float t2 = t * t;
    float a0 = ((d - c) - a) + b;
    float a1 = (a - b) - a0;
    float a2 = c - a;
    float a3 = b;
    float term1 = (a0 * t) * t2;
    float term2 = a1 * t2;
    float term3 = (a2 * t) + a3;
    return (term1 + term2) + term3;
}

float sample_bicubic_layer(
    ivec2 cell,
    vec2 frac,
    int z_cell,
    uint base_seed
) {
    float row0 = blend_cubic(
        random_from_cell_3d(ivec3(cell.x - 1, cell.y - 1, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 0, cell.y - 1, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 1, cell.y - 1, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 2, cell.y - 1, z_cell), base_seed),
        frac.x
    );
    float row1 = blend_cubic(
        random_from_cell_3d(ivec3(cell.x - 1, cell.y + 0, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 0, cell.y + 0, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 1, cell.y + 0, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 2, cell.y + 0, z_cell), base_seed),
        frac.x
    );
    float row2 = blend_cubic(
        random_from_cell_3d(ivec3(cell.x - 1, cell.y + 1, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 0, cell.y + 1, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 1, cell.y + 1, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 2, cell.y + 1, z_cell), base_seed),
        frac.x
    );
    float row3 = blend_cubic(
        random_from_cell_3d(ivec3(cell.x - 1, cell.y + 2, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 0, cell.y + 2, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 1, cell.y + 2, z_cell), base_seed),
        random_from_cell_3d(ivec3(cell.x + 2, cell.y + 2, z_cell), base_seed),
        frac.x
    );
    return blend_cubic(row0, row1, row2, row3, frac.y);
}

float sample_raw_value_noise(
    vec2 uv,
    vec2 freq,
    uint base_seed,
    float time_value,
    float speed_value,
    uint spline_order
) {
    vec2 scaled_freq = max(freq, vec2(1.0, 1.0));
    vec2 scaled_uv = uv * scaled_freq;
    vec2 cell_f = floor(scaled_uv);
    ivec2 cell = ivec2(int(cell_f.x), int(cell_f.y));
    vec2 frac = fract(scaled_uv);
    float angle = time_value * TAU;
    float time_coord = cos(angle) * speed_value;
    float time_floor = floor(time_coord);
    int time_cell = int(time_floor);
    float time_frac = fract(time_coord);

    if (spline_order == INTERPOLATION_CONSTANT) {
        return random_from_cell_3d(ivec3(cell.x, cell.y, time_cell), base_seed);
    }

    if (spline_order == INTERPOLATION_LINEAR) {
        float tl = random_from_cell_3d(ivec3(cell.x, cell.y, time_cell), base_seed);
        float tr = random_from_cell_3d(ivec3(cell.x + 1, cell.y, time_cell), base_seed);
        float bl = random_from_cell_3d(ivec3(cell.x, cell.y + 1, time_cell), base_seed);
        float br = random_from_cell_3d(ivec3(cell.x + 1, cell.y + 1, time_cell), base_seed);
        float weight_x = interpolation_weight(frac.x, spline_order);
        float top = mix(tl, tr, weight_x);
        float bottom = mix(bl, br, weight_x);
        float weight_y = interpolation_weight(frac.y, spline_order);
        return mix(top, bottom, weight_y);
    }

    if (spline_order == INTERPOLATION_COSINE) {
        float weight_x = interpolation_weight(frac.x, spline_order);
        float weight_y = interpolation_weight(frac.y, spline_order);
        float tl = random_from_cell_3d(ivec3(cell.x, cell.y, time_cell), base_seed);
        float tr = random_from_cell_3d(ivec3(cell.x + 1, cell.y, time_cell), base_seed);
        float bl = random_from_cell_3d(ivec3(cell.x, cell.y + 1, time_cell), base_seed);
        float br = random_from_cell_3d(ivec3(cell.x + 1, cell.y + 1, time_cell), base_seed);
        float top = mix(tl, tr, weight_x);
        float bottom = mix(bl, br, weight_x);
        return mix(top, bottom, weight_y);
    }

    float slice0 = sample_bicubic_layer(cell, frac, time_cell - 1, base_seed);
    float slice1 = sample_bicubic_layer(cell, frac, time_cell + 0, base_seed);
    float slice2 = sample_bicubic_layer(cell, frac, time_cell + 1, base_seed);
    float slice3 = sample_bicubic_layer(cell, frac, time_cell + 2, base_seed);
    return blend_cubic(slice0, slice1, slice2, slice3, time_frac);
}

float sample_value_noise(
    vec2 uv,
    vec2 freq,
    uint seed,
    float time_value,
    float speed_value,
    uint spline_order
) {
    uint base_seed = seed;
    float base_value = sample_raw_value_noise(
        uv,
        freq,
        base_seed,
        time_value,
        speed_value,
        spline_order
    );

    if (speed_value == 0.0 || time_value == 0.0) {
        return base_value;
    }

    uint time_seed = base_seed + 0x9e3779b1u;
    float time_field = sample_raw_value_noise(
        uv,
        freq,
        time_seed,
        0.0,
        1.0,
        spline_order
    );
    float scaled_time = periodic_value(time_value, time_field) * speed_value;
    return periodic_value(scaled_time, base_value);
}

// grainType=regular's noise source. seed_offset generalizes the original
// hardcoded BASE_SEED to support per-channel (mono=false) variation; at
// seed_offset=0u this is exactly BASE_SEED (uint addition of zero is exact),
// so sample_grain_noise() below is unchanged in behavior.
float sample_grain_noise_seeded(
    uvec2 pixel_coords,
    vec2 dims,
    float time_value,
    float speed_value,
    uint seed_offset
) {
    float width = max(dims.x, 1.0);
    float height = max(dims.y, 1.0);
    vec2 uv = vec2(float(pixel_coords.x) / width, float(pixel_coords.y) / height);
    vec2 freq = vec2(width, height);
    return sample_value_noise(uv, freq, BASE_SEED + seed_offset, time_value, speed_value, INTERPOLATION_BICUBIC);
}

float sample_grain_noise(
    uvec2 pixel_coords,
    vec2 dims,
    float time_value,
    float speed_value
) {
    return sample_grain_noise_seeded(pixel_coords, dims, time_value, speed_value, 0u);
}

// ---------------------------------------------------------------------------
// S1 hash / S4 value-noise+fbm (shared shader snippet library) -- used by the
// non-regular grain kernels below.
// ---------------------------------------------------------------------------

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

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
    // 5-octave amplitude sum is 0.96875; rescale so the field reaches ~[0, 1].
    return v * 1.032258065;
}

// ---------------------------------------------------------------------------
// Post-processing: intensity (deviation-from-neutral scale) and contrast
// (post S-curve). Both are algebraic no-ops at their defaults (40 and 50) --
// see the identity comments inline.
// ---------------------------------------------------------------------------

float s_curve01(float x) {
    float c = clamp(x, 0.0, 1.0);
    return c * c * (3.0 - 2.0 * c);
}

vec3 apply_intensity(vec3 raw, float intensityPct) {
    // intensityPct=40 (default) => k=1.0 exactly => raw*1.0 + 0.5*(1.0-1.0)
    // = raw + 0.0 = raw, bit-exact (IEEE754 multiply-by-one/multiply-by-zero
    // are exact; no clamp here so any cubic-interpolation overshoot in `raw`
    // is preserved exactly, matching the pre-existing unclamped noise_value).
    float k = intensityPct / 40.0;
    return raw * k + vec3(0.5) * (1.0 - k);
}

vec3 apply_contrast(vec3 shaped, float contrastPct) {
    // contrastPct=50 (default) => t=0.5 exactly => the steepened branch is
    // selected with mix weight 0.0 => mix(shaped, x, 0.0) = shaped, bit-exact
    // regardless of the S-curve operand (0.0 * finite = 0.0 exactly).
    float t = clamp(contrastPct, 0.0, 100.0) / 100.0;
    vec3 flattened = mix(vec3(0.5), shaped, clamp(t * 2.0, 0.0, 1.0));
    vec3 steepened = mix(
        shaped,
        vec3(s_curve01(shaped.x), s_curve01(shaped.y), s_curve01(shaped.z)),
        clamp((t - 0.5) * 2.0, 0.0, 1.0)
    );
    return t < 0.5 ? flattened : steepened;
}

// ---------------------------------------------------------------------------
// Grain kernels (grainType 1..9). grainType 0 (regular) is
// sample_grain_noise_seeded() above.
// ---------------------------------------------------------------------------

// soft: regular noise through a 3x3 tent filter.
float grain_soft(uvec2 pixel_coords, vec2 dims, float t, uint seed_offset) {
    ivec2 hi = max(ivec2(dims) - ivec2(1), ivec2(0));
    float sum = 0.0;
    float wsum = 0.0;
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            float w = (dx == 0 ? 2.0 : 1.0) * (dy == 0 ? 2.0 : 1.0);
            ivec2 npix = clamp(ivec2(pixel_coords) + ivec2(dx, dy), ivec2(0), hi);
            sum += sample_grain_noise_seeded(uvec2(npix), dims, t, 100.0, seed_offset) * w;
            wsum += w;
        }
    }
    return sum / wsum;
}

// contrasty: regular noise, then an extra baked-in S-curve pass (independent
// of the user-facing `contrast` uniform, which is still applied afterward).
float grain_contrasty(uvec2 pixel_coords, vec2 dims, float t, uint seed_offset) {
    float n = sample_grain_noise_seeded(pixel_coords, dims, t, 100.0, seed_offset);
    return s_curve01(s_curve01(n));
}

// sprinkles: sparse bright specks on a neutral field.
float grain_sprinkles(vec2 p, float t, vec2 chOff) {
    float h = hash12(p + chOff + vec2(t * 41.0, t * 23.0));
    return h > 0.98 ? 1.0 : 0.5;
}

// clumped: low-frequency fbm blobs.
float grain_clumped(vec2 p, float t, vec2 chOff) {
    vec2 q = (p + chOff) * 0.045 + vec2(t * 6.0, t * 4.0);
    return clamp01(fbm(q));
}

// enlarged: single-octave value noise at a ~2-3px cell scale.
float grain_enlarged(vec2 p, float t, vec2 chOff) {
    vec2 q = (p + chOff) / 2.5 + vec2(t * 17.0, t * 11.0);
    return vnoise(q);
}

// stippled: hard-threshold ink/paper dither.
float grain_stippled(vec2 p, float t, vec2 chOff) {
    float h = hash12(p + chOff + vec2(t * 29.0, t * 13.0));
    return step(0.5, h);
}

// horizontal / vertical: anisotropic streaked fbm (S4 stretch pattern).
float grain_horizontal(vec2 p, float t, vec2 chOff) {
    vec2 q = (p + chOff) * vec2(1.0 / 18.0, 1.0) * 0.12 + vec2(t * 9.0, t * 5.0);
    return clamp01(fbm(q));
}

float grain_vertical(vec2 p, float t, vec2 chOff) {
    vec2 q = (p + chOff) * vec2(1.0, 1.0 / 18.0) * 0.12 + vec2(t * 5.0, t * 9.0);
    return clamp01(fbm(q));
}

// speckle: noise masked to edge areas (S6 gradient magnitude of the input).
vec2 grain_edge_gradient(ivec2 coords, ivec2 texDims) {
    ivec2 hi = max(texDims - ivec2(2), ivec2(1));
    ivec2 c = clamp(coords, ivec2(1), hi);
    float tl = dot(texelFetch(inputTex, c + ivec2(-1,  1), 0).rgb, LUMA_WEIGHTS);
    float l  = dot(texelFetch(inputTex, c + ivec2(-1,  0), 0).rgb, LUMA_WEIGHTS);
    float bl = dot(texelFetch(inputTex, c + ivec2(-1, -1), 0).rgb, LUMA_WEIGHTS);
    float tr = dot(texelFetch(inputTex, c + ivec2( 1,  1), 0).rgb, LUMA_WEIGHTS);
    float r  = dot(texelFetch(inputTex, c + ivec2( 1,  0), 0).rgb, LUMA_WEIGHTS);
    float br = dot(texelFetch(inputTex, c + ivec2( 1, -1), 0).rgb, LUMA_WEIGHTS);
    float tt = dot(texelFetch(inputTex, c + ivec2( 0,  1), 0).rgb, LUMA_WEIGHTS);
    float b  = dot(texelFetch(inputTex, c + ivec2( 0, -1), 0).rgb, LUMA_WEIGHTS);
    return vec2(tr + 2.0 * r + br - tl - 2.0 * l - bl,
                tl + 2.0 * tt + tr - bl - 2.0 * b - br);
}

float grain_speckle(vec2 p, ivec2 localCoords, ivec2 texDims, float t, vec2 chOff) {
    float base = hash12(p + chOff + vec2(t * 41.0, t * 23.0));
    vec2 g = grain_edge_gradient(localCoords, texDims);
    float mag = clamp01(length(g) * 6.0);
    return mix(0.5, base, mag);
}

// ---------------------------------------------------------------------------
// Dispatch. GRAIN_TYPE is baked at compile time, so only one branch's code
// ever executes per compiled variant (same mechanism as filter/texture).
// ---------------------------------------------------------------------------

float raw_grain_value(
    uvec2 pixel_coords,
    vec2 dims,
    vec2 hashCoord,
    ivec2 localCoords,
    ivec2 texDims,
    float t,
    uint channelIndex
) {
    uint seed_offset = channelIndex * CHANNEL_SEED_STEP;
    vec2 chOff = float(channelIndex) * CHANNEL_COORD_STEP;

#if GRAIN_TYPE == 1
    return grain_soft(pixel_coords, dims, t, seed_offset);
#elif GRAIN_TYPE == 2
    return grain_sprinkles(hashCoord, t, chOff);
#elif GRAIN_TYPE == 3
    return grain_clumped(hashCoord, t, chOff);
#elif GRAIN_TYPE == 4
    return grain_contrasty(pixel_coords, dims, t, seed_offset);
#elif GRAIN_TYPE == 5
    return grain_enlarged(hashCoord, t, chOff);
#elif GRAIN_TYPE == 6
    return grain_stippled(hashCoord, t, chOff);
#elif GRAIN_TYPE == 7
    return grain_horizontal(hashCoord, t, chOff);
#elif GRAIN_TYPE == 8
    return grain_vertical(hashCoord, t, chOff);
#elif GRAIN_TYPE == 9
    return grain_speckle(hashCoord, localCoords, texDims, t, chOff);
#else
    return sample_grain_noise_seeded(pixel_coords, dims, t, 100.0, seed_offset);
#endif
}

vec3 grain_rgb(
    uvec2 pixel_coords,
    vec2 dims,
    vec2 hashCoord,
    ivec2 localCoords,
    ivec2 texDims,
    float t
) {
    // mono=true (default): one hash reused for R/G/B -- channelIndex=0u always,
    // so this is exactly the grainType=regular scalar path replicated to vec3,
    // matching the pre-existing noise_rgb = vec3(noise_value) construction.
    if (mono > 0.5) {
        float n = raw_grain_value(pixel_coords, dims, hashCoord, localCoords, texDims, t, 0u);
        return vec3(n);
    }
    // mono=false: independent per-channel hash/seed -- chromatic grain.
    return vec3(
        raw_grain_value(pixel_coords, dims, hashCoord, localCoords, texDims, t, 0u),
        raw_grain_value(pixel_coords, dims, hashCoord, localCoords, texDims, t, 1u),
        raw_grain_value(pixel_coords, dims, hashCoord, localCoords, texDims, t, 2u)
    );
}

void nm_main() {
    uvec3 global_id = uvec3(uint(gl_FragCoord.x), uint(gl_FragCoord.y), 0u);

    vec2 res = fullResolution.x > 0.0 ? fullResolution : resolution;
    uint u_width = max(as_u32(res.x), 1u);
    uint u_height = max(as_u32(res.y), 1u);
    uvec2 global_pixel = uvec2(uint(gl_FragCoord.x + tileOffset.x), uint(gl_FragCoord.y + tileOffset.y));
    if (global_pixel.x >= u_width || global_pixel.y >= u_height) {
        return;
    }

    ivec2 coords = ivec2(int(global_id.x), int(global_id.y));
    vec4 texel = texelFetch(inputTex, coords, 0);

    float blend_alpha = clamp(alpha, 0.0, 1.0);
    if (blend_alpha <= 0.0) {
        fragColor = texel;
        return;
    }

    float effective_time = pause > 0.5 ? 0.0 : time;

    float rs = max(renderScale, 1.0);
    vec2 dims = vec2(float(u_width) / rs, float(u_height) / rs);
    // hashCoord must derive from the integer, tile-aware pixel index (global_pixel),
    // NOT gl_FragCoord directly -- gl_FragCoord carries a +0.5 pixel-center offset
    // that the WGSL compute side's gid.xy does not have. Using gl_FragCoord here
    // decorrelated the pure-hash kernels and shifted the noise kernels cross-backend.
    vec2 hashCoord = vec2(global_pixel) / rs;
    ivec2 texDims = textureSize(inputTex, 0);

    vec3 raw_noise = grain_rgb(global_pixel, dims, hashCoord, coords, texDims, effective_time);
    vec3 shaped = apply_intensity(raw_noise, intensity);
    vec3 curved = apply_contrast(shaped, contrast);

    vec3 mixed_rgb = mix(texel.rgb, curved, blend_alpha);
    fragColor = vec4(
        clamp01(mixed_rgb.x),
        clamp01(mixed_rgb.y),
        clamp01(mixed_rgb.z),
        texel.a
    );
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
