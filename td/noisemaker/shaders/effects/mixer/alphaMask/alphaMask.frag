// NM_INPUTS: inputTex=0 tex=1 baseTex=2
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
#define tex sTD2DInputs[1]
#define baseTex sTD2DInputs[2]
uniform vec2 resolution;
uniform vec2 tileOffset;
uniform vec2 fullResolution;
uniform float mixAmt;
uniform bool maskMode;
out vec4 fragColor;

float map(float value, float inMin, float inMax, float outMin, float outMax) {
    return outMin + (outMax - outMin) * (value - inMin) / (inMax - inMin);
}

void nm_main() {
    vec2 uv = gl_FragCoord.xy / vec2(textureSize(inputTex, 0));
    vec4 color1 = texture(inputTex, uv);
    vec4 color2 = texture(tex, uv);

    // Inputs use premultiplied RGBA: masking must scale color and coverage.
    if (maskMode) {
        float maskVal = dot(color2.rgb, vec3(0.299, 0.587, 0.114));
        vec4 background = texture(baseTex, uv);
        fragColor = mix(background, color1, maskVal);
        return;
    }

    // Premultiplied source-over. Slider direction selects which input is on top, so either slot
    // can serve as the alpha source — slide negative for A-on-top, positive for
    // B-on-top. each half reaches a full Porter-Duff source-over at the midpoint.
    vec4 color;
    if (mixAmt < 0.0) {
        vec4 AoverB = color2 * (1.0 - color1.a) + color1;
        color = mix(color1, AoverB, map(mixAmt, -100.0, 0.0, 0.0, 1.0));
    } else {
        vec4 BoverA = color1 * (1.0 - color2.a) + color2;
        color = mix(BoverA, color2, map(mixAmt, 0.0, 100.0, 0.0, 1.0));
    }

    fragColor = color;
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
