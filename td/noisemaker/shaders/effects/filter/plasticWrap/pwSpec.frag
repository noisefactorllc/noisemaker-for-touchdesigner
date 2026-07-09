// NM_INPUTS: inputTex=0 blurTex=1
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
#define blurTex sTD2DInputs[1]
/*
 * Plastic Wrap - specular pass.
 *
 * The blurred image (_pwBlur, written by pwBlurH/pwBlurV) supplies a height
 * field h via its luminance. A 1px central-difference gradient of h gives a
 * per-pixel surface normal, which is lit by a fixed key light and raised to
 * a gloss exponent to produce a specular term. A curvature term boosts the
 * specular energy on ridges, so the sheen hugs raised contours rather than
 * washing evenly over plain slopes -- the "shrink-wrapped" look. The
 * specular term is screened onto the original image.
 *
 * Y-orientation note: the gradient taps (uv +/- 1px in x and y) and the key
 * light vector L below are fixed, backend-agnostic constants -- unlike e.g.
 * spinBlur's rotation of a fragment-position-derived offset, nothing here is
 * built from the fragment's own coordinate relative to a center parameter.
 * Per the screen-truth doctrine (shared-context.md; verified for emboss's
 * analogous fixed kernel-tap case in orientation-groundtruth.md), that means
 * the WGSL port must TEXTUALLY MATCH this file exactly, with no manual Y
 * compensation, rather than following spinBlur/pondRipples' raw-convention
 * pattern.
 *
 * L's xy signs were determined empirically, not by armchair Y-up reasoning:
 * a standalone Playwright on-screen probe (radial gradient dome, quadrant +
 * weighted-centroid analysis of the specular diff, both backends -- see
 * task-22-report.md) showed the naive "light from upper-left" literal
 * (-0.4, 0.6, 0.7) actually lands the brightest region at screen
 * lower-right on webgl2 (bit-exact reproducible, confirmed by direct visual
 * inspection of an amplified diff, not just the metric). The xy signs below
 * are flipped from that literal so the measured brightest region is
 * upper-left on screen for webgl2, matching the requirement; z (dominant,
 * toward-viewer) is untouched. webgl2 and webgpu were re-confirmed to land
 * on the identical screen-side after this change.
 */




uniform vec2 resolution;
uniform float highlight;
uniform float smoothness;

out vec4 fragColor;

float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

void nm_main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 texel = 1.0 / resolution;
    vec4 src = texture(inputTex, uv);

    float hC = lum(texture(blurTex, uv).rgb);
    float hL = lum(texture(blurTex, uv - vec2(texel.x, 0.0)).rgb);
    float hR = lum(texture(blurTex, uv + vec2(texel.x, 0.0)).rgb);
    float hB = lum(texture(blurTex, uv - vec2(0.0, texel.y)).rgb);
    float hT = lum(texture(blurTex, uv + vec2(0.0, texel.y)).rgb);

    vec2 grad = vec2(hR - hL, hT - hB);

    // Gradient-to-slope scale: documented constant. 8.0 turns a full 0..1
    // luminance swing over a ~2px span into a strongly tilted facet
    // (grad ~0.5 * 8 = 4, well past the point where the normal is mostly
    // sideways) while leaving gentle/smoothed contours near-flat.
    float strength = 8.0;
    vec3 n = normalize(vec3(-grad * strength, 1.0));
    // Fixed key light, empirically signed so the lit side reads as
    // upper-left on screen (see header note) -- matches Photoshop Plastic
    // Wrap's default glossy look. z stays dominant/positive (toward viewer).
    vec3 L = normalize(vec3(0.4, -0.6, 0.7));

    float gloss = mix(24.0, 6.0, smoothness / 100.0);
    float spec = pow(clamp(dot(n, L), 0.0, 1.0), gloss);

    // Ridge boost: h_c*2 - h_l - h_r is the discrete negative second
    // derivative along x -- positive at a local maximum (a ridge crest).
    // Boosting spec there concentrates the sheen on contour crests instead
    // of spreading evenly across plain slopes.
    float curv = hC * 2.0 - hL - hR;
    float ridge = clamp(curv * strength, 0.0, 1.0);
    spec *= 1.0 + ridge * 2.0;

    vec3 specColor = clamp(vec3(spec) * (highlight / 100.0), 0.0, 1.0);
    // Screen blend: 1 - (1-a)(1-b). highlight=0 -> specColor=0 -> out=src exactly.
    vec3 outc = vec3(1.0) - (vec3(1.0) - src.rgb) * (vec3(1.0) - specColor);

    fragColor = vec4(outc, src.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
