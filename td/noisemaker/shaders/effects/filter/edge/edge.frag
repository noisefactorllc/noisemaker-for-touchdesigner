// NM_INPUTS: inputTex=0
// NM_OUTPUT: fragColor
#define inputTex sTD2DInputs[0]
/*
 * Edge detection with multiple kernels, sizes, and blend modes
 */


uniform vec2 tileOffset;
uniform vec2 fullResolution;

uniform float kernel;
uniform float size;
uniform float renderScale;
uniform float blend;
uniform float invert;
uniform float channel;
uniform float threshold;
uniform float amount;
uniform float mixAmt;
uniform float level;

out vec4 fragColor;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);

float getWeight(int dx, int dy, int kernelType) {
    if (dx == 0 && dy == 0) return 0.0;

    if (kernelType == 0) {
        // fine: cardinal neighbors only (cross Laplacian)
        if (dx == 0 || dy == 0) return -1.0;
        return 0.0;
    } else {
        // bold: all neighbors equally
        return -1.0;
    }
}

vec4 applyBlend(vec4 edge, vec4 orig, int mode) {
    if (mode == 0) return min(orig + edge, vec4(1.0));                        // add
    if (mode == 1) return min(orig, edge);                                     // darken
    if (mode == 2) return abs(orig - edge);                                    // difference
    if (mode == 3) return min(orig / max(1.0 - edge, vec4(0.001)), vec4(1.0)); // dodge
    if (mode == 4) return max(orig, edge);                                     // lighten
    if (mode == 5) return orig * edge;                                         // multiply
    if (mode == 7) {                                                           // overlay
        vec4 result;
        result.r = orig.r < 0.5 ? 2.0 * orig.r * edge.r : 1.0 - 2.0 * (1.0 - orig.r) * (1.0 - edge.r);
        result.g = orig.g < 0.5 ? 2.0 * orig.g * edge.g : 1.0 - 2.0 * (1.0 - orig.g) * (1.0 - edge.g);
        result.b = orig.b < 0.5 ? 2.0 * orig.b * edge.b : 1.0 - 2.0 * (1.0 - orig.b) * (1.0 - edge.b);
        result.a = orig.a;
        return result;
    }
    if (mode == 8) return 1.0 - (1.0 - orig) * (1.0 - edge);                 // screen
    return edge;                                                                // normal (6)
}

// Contour: mark a level-crossing where sign(c - level) differs from any of
// the 4 cardinal neighbors (Photoshop Trace Contour). Returns a binary vec3:
// 1.0 = background (white), 0.0 = contour line (dark).
vec3 contourConv(vec2 fragCoord, vec2 texelSize, vec3 centerRGB, float lvl, bool useLuma) {
    vec3 northRGB = texture(inputTex, (fragCoord + vec2(0.0,  1.0)) * texelSize).rgb;
    vec3 southRGB = texture(inputTex, (fragCoord + vec2(0.0, -1.0)) * texelSize).rgb;
    vec3 eastRGB  = texture(inputTex, (fragCoord + vec2( 1.0, 0.0)) * texelSize).rgb;
    vec3 westRGB  = texture(inputTex, (fragCoord + vec2(-1.0, 0.0)) * texelSize).rgb;

    if (useLuma) {
        float centerL = dot(centerRGB, LUMA);
        float centerSign = sign(centerL - lvl);
        bool crossing = centerSign != sign(dot(northRGB, LUMA) - lvl) ||
                         centerSign != sign(dot(southRGB, LUMA) - lvl) ||
                         centerSign != sign(dot(eastRGB, LUMA) - lvl)  ||
                         centerSign != sign(dot(westRGB, LUMA) - lvl);
        return vec3(crossing ? 0.0 : 1.0);
    }

    vec3 centerSign = sign(centerRGB - lvl);
    bvec3 crossing = bvec3(
        centerSign.r != sign(northRGB.r - lvl) || centerSign.r != sign(southRGB.r - lvl) ||
        centerSign.r != sign(eastRGB.r - lvl)  || centerSign.r != sign(westRGB.r - lvl),
        centerSign.g != sign(northRGB.g - lvl) || centerSign.g != sign(southRGB.g - lvl) ||
        centerSign.g != sign(eastRGB.g - lvl)  || centerSign.g != sign(westRGB.g - lvl),
        centerSign.b != sign(northRGB.b - lvl) || centerSign.b != sign(southRGB.b - lvl) ||
        centerSign.b != sign(eastRGB.b - lvl)  || centerSign.b != sign(westRGB.b - lvl)
    );
    return vec3(crossing.r ? 0.0 : 1.0, crossing.g ? 0.0 : 1.0, crossing.b ? 0.0 : 1.0);
}

void nm_main() {
    ivec2 texSize = textureSize(inputTex, 0);
    vec2 resolution = vec2(texSize);
    vec2 texelSize = 1.0 / resolution;

    vec4 origColor = texture(inputTex, gl_FragCoord.xy * texelSize);

    int kernelType = int(kernel);
    int radius = min(int((size + 1.0) * renderScale), 256);
    int blendMode = int(blend);
    bool doInvert = invert > 0.5;
    bool useLuma = channel > 0.5;

    // Convolution
    vec3 conv = vec3(0.0);
    float centerWeight = 0.0;

    if (kernelType == 2) {
        // Contour: level-crossing trace, not a weighted convolution.
        conv = contourConv(gl_FragCoord.xy, texelSize, origColor.rgb, level / 100.0, useLuma);
    } else {
        for (int dy = -3; dy <= 3; dy++) {
            for (int dx = -3; dx <= 3; dx++) {
                if (abs(dx) > radius || abs(dy) > radius) continue;
                if (dx == 0 && dy == 0) continue;

                float w = getWeight(dx, dy, kernelType);
                if (w == 0.0) continue;

                vec2 sampleCoord = gl_FragCoord.xy + vec2(float(dx), float(dy));
                vec2 localUV = sampleCoord * texelSize;
                vec3 s = texture(inputTex, localUV).rgb;

                if (useLuma) {
                    conv += vec3(dot(s, LUMA)) * w;
                } else {
                    conv += s * w;
                }

                centerWeight -= w;
            }
        }

        // Center sample
        vec3 centerSample = origColor.rgb;
        if (useLuma) {
            centerSample = vec3(dot(centerSample, LUMA));
        }
        conv += centerSample * centerWeight;
    }

    // Amount
    conv *= amount / 50.0;
    conv = clamp(conv, 0.0, 1.0);

    // Threshold (before invert so it measures actual edge strength)
    if (threshold > 0.0) {
        float thresh = threshold / 100.0;
        float edge;
        if (useLuma) {
            edge = conv.r;
        } else {
            edge = dot(conv, LUMA);
        }
        float mask = smoothstep(thresh - 0.01, thresh + 0.01, edge);
        conv *= mask;
    }

    // Invert
    if (doInvert) {
        conv = 1.0 - conv;
    }

    // Blend
    vec4 edgeColor = vec4(conv, origColor.a);
    vec4 blended = applyBlend(edgeColor, origColor, blendMode);

    // Mix
    float m = mixAmt / 100.0;
    fragColor = vec4(mix(origColor.rgb, blended.rgb, m), origColor.a);
}
void main() {
    nm_main();
    fragColor = TDOutputSwizzle(fragColor);
}
