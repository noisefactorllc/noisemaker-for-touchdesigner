// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Spin Blur - rotational blur around a center point (Photoshop Radial
 * Blur, Spin mode). Averages a fixed N-tap comb; each tap resamples the
 * input after rotating the pixel's offset-from-center by
 * theta_i = (i/(N-1) - 0.5) * radians(amount) around (centerX, centerY),
 * aspect-corrected exactly the way filter/pinch's rotate2D corrects its
 * own distortion (multiply x by aspect before rotating, divide after).
 * A per-pixel hash shifts the whole tap comb by up to half an angular
 * step to hide banding from the fixed tap count.
 *
 * Y-convention note: the tap arc is symmetric about theta=0, so the
 * zero-jitter effect is Y-mirror invariant (negating every tap angle
 * maps the tap set onto itself). Per-pixel jitter shifts the whole arc
 * by a bounded sub-step offset, which does not preserve that symmetry
 * exactly - it bounds the residual cross-backend difference by the
 * jitter magnitude rather than eliminating it outright, so this is
 * weaker than "structurally immune." End-to-end coordinate-convention
 * match (GLSL gl_FragCoord vs WGSL @builtin(position), both used
 * unflipped) was verified empirically on this pipeline in task-5's
 * Y-orientation verification (filter/directionalBlur, a strictly harder
 * asymmetric case); see task-6's fix report (F4) for a centerY-specific
 * non-default-value re-check of this effect.
 */



uniform vec2 resolution;
uniform vec2 tileOffset;
uniform vec2 fullResolution;
uniform float amount;
uniform float centerX;
uniform float centerY;

out vec4 fragColor;

const int N = 32;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// Rotate uv around center by angle, aspect-corrected exactly as
// filter/pinch's rotate2D corrects its own distortion.
vec2 rotateAround(vec2 uv, vec2 center, float angle, float aspectRatio) {
    vec2 p = uv;
    p.x *= aspectRatio;
    vec2 c = center;
    c.x *= aspectRatio;
    p -= c;
    float s = sin(angle);
    float co = cos(angle);
    p = mat2(co, -s, s, co) * p;
    p += c;
    p.x /= aspectRatio;
    return p;
}

void nm_main() {
    float aspectRatio = fullResolution.x / fullResolution.y;
    vec2 globalCoord = gl_FragCoord.xy + tileOffset;
    vec2 uv = globalCoord / fullResolution;
    vec2 center = vec2(centerX, centerY);

    float arc = radians(amount);
    float angularStep = arc / float(N - 1);
    // Seed with globalCoord (tile-space + tileOffset), not gl_FragCoord.xy
    // alone, so the dither field is continuous across CLI render tiles
    // instead of restarting at each tile's local origin.
    float jitter = (hash12(globalCoord) - 0.5) * angularStep;

    vec4 sum = vec4(0.0);
    for (int i = 0; i < N; i++) {
        float theta = (float(i) / float(N - 1) - 0.5) * arc + jitter;
        vec2 distorted = clamp(rotateAround(uv, center, theta, aspectRatio), 0.0, 1.0);
        vec2 sampleUV = clamp((distorted * fullResolution - tileOffset) / resolution, 0.0, 1.0);
        sum += texture(inputTex, sampleUV);
    }
    fragColor = sum / float(N);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
