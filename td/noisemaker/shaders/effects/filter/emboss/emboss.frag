// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Emboss convolution effect
 * Creates a raised relief appearance
 *
 * angle/height rotate and scale the kernel's fixed 3x3 sampling geometry
 * about its own built-in axis instead of replacing it outright: this kernel
 * has no neutral (0.5) bias term (its weights sum to 1, so flat regions pass
 * through as the original color, not mid-gray), so a literal Photoshop-style
 * "0.5 + directional diff" formula cannot reproduce this shader's pre-existing
 * output and was rejected on that basis (see help.md).
 *
 * At angle=135, height=1 the rotation is identity and the scale is 1x, so
 * every sample offset below equals the original hard-coded +/-texelSize grid
 * exactly (byte-identical old-defaults output, for any amount).
 */


uniform vec2 tileOffset;
uniform vec2 fullResolution;

uniform float amount;
uniform float angle;
uniform float height;
uniform float renderScale;

out vec4 fragColor;

void nm_main() {
    vec2 globalCoord = gl_FragCoord.xy + tileOffset;
    ivec2 texSize = textureSize(inputTex, 0);
    vec2 resolution = vec2(texSize);
    vec2 uv = globalCoord / fullResolution;
    vec2 texelSize = 1.0 / resolution;

    vec4 origColor = texture(inputTex, gl_FragCoord.xy / vec2(textureSize(inputTex, 0)));

    // Emboss kernel
    // -2 -1  0
    // -1  1  1
    //  0  1  2
    float kernel[9];
    kernel[0] = -2.0; kernel[1] = -1.0; kernel[2] = 0.0;
    kernel[3] = -1.0; kernel[4] = 1.0;  kernel[5] = 1.0;
    kernel[6] = 0.0;  kernel[7] = 1.0;  kernel[8] = 2.0;

    // Base kernel tap positions, 1px units. angle/height rotate+scale this
    // fixed geometry about its own built-in axis (see header above).
    vec2 baseOffsetsPx[9];
    baseOffsetsPx[0] = vec2(-1.0, -1.0);
    baseOffsetsPx[1] = vec2( 0.0, -1.0);
    baseOffsetsPx[2] = vec2( 1.0, -1.0);
    baseOffsetsPx[3] = vec2(-1.0,  0.0);
    baseOffsetsPx[4] = vec2( 0.0,  0.0);
    baseOffsetsPx[5] = vec2( 1.0,  0.0);
    baseOffsetsPx[6] = vec2(-1.0,  1.0);
    baseOffsetsPx[7] = vec2( 0.0,  1.0);
    baseOffsetsPx[8] = vec2( 1.0,  1.0);

    // Reference angle 135 is the pre-existing kernel's own implicit
    // direction, so theta=0 (identity rotation) lands exactly there.
    float theta = radians(angle - 135.0);
    float ct = cos(theta);
    float st = sin(theta);

    vec3 conv = vec3(0.0);

    for (int i = 0; i < 9; i++) {
        vec2 basePx = baseOffsetsPx[i];
        // R(-theta) rotation, matching the spinBlur/pinch handedness convention;
        // the theta=0 identity point is unaffected by handedness.
        vec2 rotatedPx = vec2(ct * basePx.x + st * basePx.y, -st * basePx.x + ct * basePx.y) * height;
        vec2 offsetUV = rotatedPx * texelSize * amount * renderScale;
        vec3 texSample = texture(inputTex, ((uv + offsetUV) * fullResolution - tileOffset) / vec2(textureSize(inputTex, 0))).rgb;
        conv += texSample * kernel[i];
    }

    fragColor = vec4(clamp(conv, 0.0, 1.0), origColor.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
