// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Directional Blur - linear motion blur along a fixed angle (Photoshop
 * Motion Blur). Averages a fixed N-tap comb stepped along
 * dir = (cos(angle), sin(angle)), spanning blurDistance px total
 * (t ranges over [-blurDistance/2, blurDistance/2]). A per-pixel hash
 * shifts the whole tap comb by up to half a tap-step to hide banding
 * from the fixed tap count.
 */



uniform vec2 resolution;
uniform float angle;
uniform float blurDistance;

out vec4 fragColor;

const int N = 32;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void nm_main() {
    vec2 dir = vec2(cos(radians(angle)), sin(radians(angle)));

    float tapStep = blurDistance / float(N - 1);
    float jitter = (hash12(gl_FragCoord.xy) - 0.5) * tapStep;

    vec4 sum = vec4(0.0);
    for (int i = 0; i < N; i++) {
        float t = (float(i) / float(N - 1) - 0.5) * blurDistance + jitter;
        vec2 offset = dir * t;
        sum += texture(inputTex, (gl_FragCoord.xy + offset) / resolution);
    }
    fragColor = sum / float(N);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
