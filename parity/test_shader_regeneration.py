import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NOISE = 'float periodicFunction(float p) {\n    return map(cos(p * TAU), -1.0, 1.0, 0.0, 1.0);\n}'
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
        result, output = self.convert('synth/noise', NOISE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('precise ' + NOISE, output)

    def test_median_selection_survives_regeneration(self):
        result, output = self.convert('filter/median', MEDIAN)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = (REPO / 'td' / 'noisemaker' / 'shaders' / 'effects' / 'filter' / 'median' / 'median.frag').read_text()
        self.assertEqual(output, expected)

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

    def test_unrelated_program_is_not_adapted(self):
        result, output = self.convert('synth/other', NOISE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(NOISE, output)
        self.assertNotIn('precise float', output)
