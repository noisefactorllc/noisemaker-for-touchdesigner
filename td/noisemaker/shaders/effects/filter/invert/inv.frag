// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Invert brightness effect
 * mode 0 (full, default): simple RGB inversion, 1.0 - value
 * mode 1 (solarize): Photoshop Solarize parity, min(v, 1.0 - v) per channel
 *   (PS: output = v <= 128 ? v : 255 - v, equivalent to min(v, 1-v) in 0..1)
 */


uniform vec2 tileOffset;
uniform vec2 fullResolution;

uniform int mode;

out vec4 fragColor;

void nm_main() {
    vec2 globalCoord = gl_FragCoord.xy + tileOffset;
    ivec2 texSize = textureSize(inputTex, 0);
    vec2 uv = gl_FragCoord.xy / vec2(texSize);
    vec4 color = texture(inputTex, uv);

    if (mode == 1) {
        color.rgb = min(color.rgb, 1.0 - color.rgb);
    } else {
        color.rgb = 1.0 - color.rgb;
    }

    fragColor = color;
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
