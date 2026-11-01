import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NOISE = 'float periodicFunction(float p) {\n    return map(cos(p * TAU), -1.0, 1.0, 0.0, 1.0);\n}'
NOISE_CONTRACT = '#define TAU 6.28318530718\nfloat map(float value, float inMin, float inMax, float outMin, float outMax) {\n    return outMin + (outMax - outMin) * (value - inMin) / (inMax - inMin);\n}\nfloat periodicFunction(float p) {\n    return map(cos(p * TAU), -1.0, 1.0, 0.0, 1.0);\n}\nvec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }\nvec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }\nvec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }\nfloat simplexValue(vec2 st, vec2 freq, float s, float blend) {\n    const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);\n    vec2 uv = st * freq;\n    uv.x += s;\n\n    vec2 i  = floor(uv + dot(uv, C.yy));\n    vec2 x0 = uv - i + dot(i, C.xx);\n    vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);\n    vec4 x12 = x0.xyxy + C.xxzz;\n    x12.xy -= i1;\n\n    i = mod289(i);\n    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));\n    vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);\n    m = m*m;\n    m = m*m;\n\n    vec3 x = 2.0 * fract(p * C.www) - 1.0;\n    vec3 h = abs(x) - 0.5;\n    vec3 ox = floor(x + 0.5);\n    vec3 a0 = x - ox;\n    m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);\n\n    vec3 g;\n    g.x = a0.x * x0.x + h.x * x0.y;\n    g.yz = a0.yz * x12.xz + h.yz * x12.yw;\n    float v = 130.0 * dot(m, g);\n\n    return periodicFunction(map(v, -1.0, 1.0, 0.0, 1.0) - blend);\n}\nfloat value(vec2 st, vec2 freq, float s, float blend) {\n#if NOISE_TYPE == 3\n    return catmullRom3x3ValueNoise(st, freq, s, blend);\n#elif NOISE_TYPE == 4\n    return catmullRom4x4ValueNoise(st, freq, s, blend);\n#elif NOISE_TYPE == 5\n    return cubic3x3ValueNoise(st, freq, s, blend);\n#elif NOISE_TYPE == 6\n    return bicubicValue(st, freq, s, blend);\n#elif NOISE_TYPE == 10\n    return simplexValue(st, freq, s, blend);\n#elif NOISE_TYPE == 11\n    return sineNoise(st, freq, s, blend);\n#elif NOISE_TYPE == 0\n    return constantFromLattice(st * freq, freq, s, blend);\n#else\n    // NOISE_TYPE == 1 (linear) or NOISE_TYPE == 2 (hermite/cosine)\n    vec2 lattice = st * freq;\n    float x1y1 = constantFromLattice(lattice, freq, s, blend);\n    float x2y1 = constantOffset(lattice, freq, s, blend, ivec2(1, 0));\n    float x1y2 = constantOffset(lattice, freq, s, blend, ivec2(0, 1));\n    float x2y2 = constantOffset(lattice, freq, s, blend, ivec2(1, 1));\n    vec2 frac = fract(lattice);\n    float a = blendLinearOrCosine(x1y1, x2y1, frac.x, NOISE_TYPE);\n    float b = blendLinearOrCosine(x1y2, x2y2, frac.x, NOISE_TYPE);\n    return blendLinearOrCosine(a, b, frac.y, NOISE_TYPE);\n#endif\n}\nfloat offset(vec2 st, vec2 freq) {\n#if LOOP_OFFSET == 10\n    return circles(st, freq.x);\n#elif LOOP_OFFSET == 20\n    return shape(st, 3, freq.x * 0.5);\n#elif LOOP_OFFSET == 30\n    return (abs(st.x - 0.5 * aspectRatio) + abs(st.y - 0.5)) * freq.x * 0.5;\n#elif LOOP_OFFSET == 40\n    return shape(st, 4, freq.x * 0.5);\n#elif LOOP_OFFSET == 50\n    return shape(st, 5, freq.x * 0.5);\n#elif LOOP_OFFSET == 60\n    return shape(st, 6, freq.x * 0.5);\n#elif LOOP_OFFSET == 70\n    return shape(st, 7, freq.x * 0.5);\n#elif LOOP_OFFSET == 80\n    return shape(st, 8, freq.x * 0.5);\n#elif LOOP_OFFSET == 90\n    return shape(st, 9, freq.x * 0.5);\n#elif LOOP_OFFSET == 100\n    return shape(st, 10, freq.x * 0.5);\n#elif LOOP_OFFSET == 110\n    return shape(st, 11, freq.x * 0.5);\n#elif LOOP_OFFSET == 120\n    return shape(st, 12, freq.x * 0.5);\n#elif LOOP_OFFSET == 200\n    return st.x * freq.x * 0.5;\n#elif LOOP_OFFSET == 210\n    return st.y * freq.x * 0.5;\n#elif LOOP_OFFSET == 300\n    st -= vec2(aspectRatio * 0.5, 0.5);\n    return value(st, freq, float(seed) + 50.0, 0.0);\n#elif LOOP_OFFSET == 400\n    return 1.0 - rings(st, freq.x);\n#elif LOOP_OFFSET == 410\n    return 1.0 - diamonds(st, freq.x);\n#else\n    return 0.0;\n#endif\n}'
MEDIAN = '/*\n * Exact dense whole-color Median / Dust & Scratches.\n *\n * RADIUS is a compile-time definition. The 3x3, 5x5, and 7x7 variants make\n * exactly 9, 25, and 49 clamped integer texture reads. A bounded in-place\n * selection partitions packed RGB/luminance records around the middle rank,\n * avoiding the work and register pressure of fully sorting the neighborhood.\n */\n\n#ifdef GL_ES\nprecision highp float;\n#endif\n\n#if RADIUS == 1\n#define REAL_COUNT 9\n#elif RADIUS == 2\n#define REAL_COUNT 25\n#else\n#define REAL_COUNT 49\n#endif\n\nuniform sampler2D inputTex;\nuniform float threshold;\n\nout vec4 fragColor;\n\nbool lessRecord(uvec2 a, uint blueA, uvec2 b, uint blueB) {\n    if (a.x != b.x) return a.x < b.x;\n    if (a.y != b.y) return a.y < b.y;\n    return blueA < blueB;\n}\n\nuvec2 packRecordMajor(vec4 sampleColor) {\n    float brightness = dot(sampleColor.rgb, vec3(0.2126, 0.7152, 0.0722));\n    uint packedRg = packHalf2x16(sampleColor.rg);\n    uint orderedRg = ((packedRg & 0xffffu) << 16) | (packedRg >> 16);\n    return uvec2(floatBitsToUint(brightness), orderedRg);\n}\n\nuint packRecordBlue(vec4 sampleColor) {\n    return packHalf2x16(vec2(sampleColor.b, 0.0)) & 0xffffu;\n}\n\nvec3 unpackRecordRgb(uvec2 major, uint blue) {\n    uint packedRg = (major.y << 16) | (major.y >> 16);\n    vec2 rg = unpackHalf2x16(packedRg);\n    float b = unpackHalf2x16(blue).x;\n    return vec3(rg, b);\n}\n\nvec4 readRecord(ivec2 center, ivec2 dimensions, int x, int y) {\n    ivec2 coord = clamp(center + ivec2(x, y), ivec2(0), dimensions - ivec2(1));\n    return texelFetch(inputTex, coord, 0);\n}\n\nvoid main() {\n    uvec2 majorRecords[REAL_COUNT];\n    uint blueRecords[REAL_COUNT];\n    ivec2 dimensions = textureSize(inputTex, 0);\n    ivec2 center = ivec2(gl_FragCoord.xy);\n    vec3 originalRgb = vec3(0.0);\n    float centerAlpha = 1.0;\n    int index = 0;\n    for (int y = -RADIUS; y <= RADIUS; y++) {\n        for (int x = -RADIUS; x <= RADIUS; x++) {\n            vec4 sampleColor = readRecord(center, dimensions, x, y);\n            majorRecords[index] = packRecordMajor(sampleColor);\n            blueRecords[index] = packRecordBlue(sampleColor);\n            if (x == 0 && y == 0) {\n                originalRgb = sampleColor.rgb;\n                centerAlpha = sampleColor.a;\n            }\n            index++;\n        }\n    }\n\n    int medianIndex = REAL_COUNT / 2;\n    int left = 0;\n    int right = REAL_COUNT - 1;\n    while (left < right) {\n        uvec2 pivotMajor = majorRecords[medianIndex];\n        uint pivotBlue = blueRecords[medianIndex];\n        int scanLeft = left;\n        int scanRight = right;\n        while (scanLeft <= scanRight) {\n            while (lessRecord(majorRecords[scanLeft], blueRecords[scanLeft], pivotMajor, pivotBlue)) { scanLeft++; }\n            while (lessRecord(pivotMajor, pivotBlue, majorRecords[scanRight], blueRecords[scanRight])) { scanRight--; }\n            if (scanLeft <= scanRight) {\n                uvec2 temporaryMajor = majorRecords[scanLeft];\n                majorRecords[scanLeft] = majorRecords[scanRight];\n                majorRecords[scanRight] = temporaryMajor;\n                uint temporaryBlue = blueRecords[scanLeft];\n                blueRecords[scanLeft] = blueRecords[scanRight];\n                blueRecords[scanRight] = temporaryBlue;\n                scanLeft++;\n                scanRight--;\n            }\n        }\n        if (scanRight < medianIndex) { left = scanLeft; }\n        if (medianIndex < scanLeft) { right = scanRight; }\n    }\n\n    vec3 medianRgb = unpackRecordRgb(majorRecords[medianIndex], blueRecords[medianIndex]);\n    vec3 difference = abs(originalRgb - medianRgb);\n    float maxDifference = max(max(difference.r, difference.g), difference.b);\n    bool replaceCenter = threshold <= 0.0 || maxDifference >= threshold / 100.0;\n    fragColor = vec4(replaceCenter ? medianRgb : originalRgb, centerAlpha);\n}\n'

class ShaderRegeneration(unittest.TestCase):
    def convert(self, effect, source):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program = effect.split('/')[-1]
            shader = root / 'shaders' / 'effects' / effect / 'glsl' / (program + '.glsl')
            shader.parent.mkdir(parents=True)
            shader.write_text(source)
            out = root / 'output'
            env = dict(os.environ, NM_REFERENCE_ROOT=str(root), NM_OUT_DIR=str(out))
            result = subprocess.run(['node', str(REPO / 'tools/convert-shaders.mjs'), effect],
                                    env=env, capture_output=True, text=True)
            target = out / effect / (program + '.frag')
            return result, target.read_text() if target.exists() else None

    def test_noise_phase_precision_survives_regeneration(self):
        result, output = self.convert('synth/noise', NOISE_CONTRACT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('precise ' + NOISE, output)
        self.assertIn('float simplexOffset(', output)
        self.assertIn('simplexDot(st, freq, s) * (130.0 * 0.5 * TAU) + (0.5 * TAU)', output)
        self.assertIn('#if NOISE_TYPE == 10\n    return simplexOffset(st, freq, float(seed) + 50.0);', output)

    def test_changed_noise_offset_contract_is_rejected(self):
        result, output = self.convert('synth/noise', NOISE_CONTRACT.replace('float(seed) + 50.0', 'float(seed) + 51.0'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source shape changed', result.stderr)
        self.assertIsNone(output)

    def test_changed_noise_simplex_scale_is_rejected(self):
        result, output = self.convert('synth/noise', NOISE_CONTRACT.replace('130.0 * dot(m, g)', '129.0 * dot(m, g)'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source shape changed', result.stderr)
        self.assertIsNone(output)

    def test_changed_noise_tau_expression_is_rejected(self):
        changed = NOISE_CONTRACT.replace('#define TAU 6.28318530718', '#define TAU 6.28318530718 + 1.0')
        result, output = self.convert('synth/noise', changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source shape changed', result.stderr)
        self.assertIsNone(output)

    def test_median_selection_survives_regeneration(self):
        result, output = self.convert('filter/median', MEDIAN)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = (REPO / 'td' / 'noisemaker' / 'shaders' / 'effects' / 'filter' / 'median' / 'median.frag').read_text()
        self.assertEqual(output, expected)
        self.assertIn('for (int j = i + 1; j < REAL_COUNT; j++)', output)
        self.assertNotIn('while (insertAt > 0)', output)
        self.assertIn('majorRecords[minimum] = temporaryMajor;', output)
        self.assertIn('blueRecords[minimum] = temporaryBlue;', output)

    def test_changed_noise_function_is_rejected_without_output(self):
        result, output = self.convert('synth/noise', NOISE.replace('p * TAU', 'p * TAU + 1.0'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source shape changed', result.stderr)
        self.assertIsNone(output)

    def test_duplicate_noise_function_is_rejected_without_output(self):
        result, output = self.convert('synth/noise', NOISE + '\n' + NOISE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source shape changed', result.stderr)
        self.assertIsNone(output)

    def test_changed_median_function_is_rejected_without_output(self):
        result, output = self.convert('filter/median', MEDIAN.replace('threshold / 100.0', 'threshold / 99.0'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source shape changed', result.stderr)
        self.assertIsNone(output)

    def test_changed_median_comparator_contract_is_rejected(self):
        changed = MEDIAN.replace('return blueA < blueB;', 'return true;')
        self.assertNotEqual(changed, MEDIAN)
        result, output = self.convert('filter/median', changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source shape changed', result.stderr)
        self.assertIsNone(output)

    def test_changed_median_packing_contract_is_rejected(self):
        changed = MEDIAN.replace('return uvec2(floatBitsToUint(brightness), orderedRg);',
                                'return uvec2(0u, orderedRg);')
        self.assertNotEqual(changed, MEDIAN)
        result, output = self.convert('filter/median', changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source shape changed', result.stderr)
        self.assertIsNone(output)

    def test_unrelated_program_is_not_adapted(self):
        result, output = self.convert('synth/other', NOISE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(NOISE, output)
        self.assertNotIn('precise float', output)
