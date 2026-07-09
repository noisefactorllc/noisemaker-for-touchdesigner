// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * High pass - vertical Gaussian pass
 */



uniform vec2 resolution;
uniform float radius;

out vec4 fragColor;

void nm_main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec2 dirPx = vec2(0.0, 1.0);
    float sigma = max(radius * 0.5, 0.001);
    float fTaps = min(radius, 32.0);
    // Beyond 32 taps we can't add more samples (bounded loop), so widen the
    // spacing between them to keep the kernel reaching the full radius.
    float stride = radius > 32.0 ? radius / 32.0 : 1.0;
    vec4 sum = texture(inputTex, uv);
    float wsum = 1.0;
    for (int i = 1; i <= 32; i++) {
        if (float(i) > fTaps) { break; }
        float w = exp(-float(i * i) / (2.0 * sigma * sigma));
        vec2 o = dirPx * float(i) * stride / resolution;
        sum += (texture(inputTex, uv + o) + texture(inputTex, uv - o)) * w;
        wsum += 2.0 * w;
    }
    fragColor = sum / wsum;
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
