// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Scatter - smooth pass: re-blends the jittered result from scatterJitter
 * with a 3x3 tent blur, mixed in by smoothness/100 (Spatter's
 * Smoothness parameter). smoothness = 0 leaves the pure per-pixel jitter
 * untouched; higher values soften the granular scatter into smoother
 * frosted streaks.
 */



uniform vec2 resolution;
uniform float smoothness;

out vec4 fragColor;

void nm_main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 texel = 1.0 / resolution;

    vec4 src = texture(inputTex, uv);

    // 3x3 tent kernel: weight (2 - |x|) * (2 - |y|) for x, y in {-1, 0, 1},
    // giving weights 1/2/1 / 2/4/2 / 1/2/1 (sum 16).
    vec4 sum = vec4(0.0);
    float wsum = 0.0;
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            float w = (2.0 - abs(float(x))) * (2.0 - abs(float(y)));
            sum += texture(inputTex, uv + vec2(float(x), float(y)) * texel) * w;
            wsum += w;
        }
    }
    vec4 blurred = sum / wsum;

    fragColor = mix(src, blurred, clamp(smoothness / 100.0, 0.0, 1.0));
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
