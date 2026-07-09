// NM_INPUTS: inputTex=0 blurTex=1
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
#define blurTex sTD2DInputs[1]
/*
 * High pass - combine pass: hp = src - blur + 0.5 gray, optional luminance-only
 */




uniform vec2 resolution;
uniform bool mono;

out vec4 fragColor;

float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

void nm_main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 src = texture(inputTex, uv);
    vec4 blur = texture(blurTex, uv);
    vec3 diff = src.rgb - blur.rgb;
    vec3 hp = mono ? vec3(lum(diff) + 0.5) : (diff + 0.5);
    fragColor = vec4(clamp(hp, 0.0, 1.0), src.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
