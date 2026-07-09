// NM_INPUTS: inputTex=0 medTex=1
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
#define medTex sTD2DInputs[1]
/*
 * Median - final pass: threshold-gated mix between the original image and
 * the fully-iterated median result. threshold == 0 always uses the plain
 * median (classic Photoshop Median filter); threshold > 0 only replaces
 * pixels whose original/median difference exceeds the threshold (Dust &
 * Scratches behavior), leaving larger detail untouched.
 */




uniform vec2 resolution;
uniform float threshold;

out vec4 fragColor;

void nm_main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 orig = texture(inputTex, uv);
    vec4 med = texture(medTex, uv);

    vec3 d = abs(orig.rgb - med.rgb);
    float maxDiff = max(max(d.r, d.g), d.b);
    float gate = (threshold <= 0.0) ? 1.0 : step(threshold / 100.0, maxDiff);

    fragColor = vec4(mix(orig.rgb, med.rgb, gate), orig.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
