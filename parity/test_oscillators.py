#!/usr/bin/env python3
"""Runtime and validator parity for the DSL osc() oscillator kinds.

Pins the pre-existing kinds (0-5), and the oscKind.noise2d addition
(upstream eabb537e + 5e68552a): kind 6 is the osc2d effect's two-stage
periodic noise with both stages sampled at a fixed seed-derived position,
speed applied exactly once after the first periodic wrap.
"""

import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "td"))

from noisemaker.compiler.lang.effect_registry import EffectRegistry  # noqa: E402
from noisemaker.compiler.lang.lexer import lex  # noqa: E402
from noisemaker.compiler.lang.parser import parse  # noqa: E402
from noisemaker.compiler.lang.validator import validate  # noqa: E402
from noisemaker.runtime.automation import resolve_uniform_value  # noqa: E402

REGISTRY = EffectRegistry.load_from_directory()


def oscillator(osc_type=0, **overrides):
    value = {
        "type": "Oscillator",
        "oscType": osc_type,
        "min": 0,
        "max": 1,
        "speed": 1,
        "offset": 0,
        "seed": 1,
    }
    value.update(overrides)
    return value


def sample(config, times):
    return [resolve_uniform_value(config, time) for time in times]


def max_abs_diff(left, right):
    return max(abs(left[i] - right[i]) for i in range(len(left)))


class OscKindValidationTests(unittest.TestCase):
    """oscKind members resolve to their kind numbers without diagnostics."""

    def compile_scale_x(self, expression):
        source = (
            "search synth\nnoise(scaleX: %s).write(o0)\nrender(o0)" % expression
        )
        result = validate(parse(lex(source), REGISTRY), REGISTRY)
        self.assertEqual([], result["diagnostics"])
        return result["plans"][0]["chain"][0]["args"]["scaleX"]

    def test_member_names_resolve_to_their_kind_numbers(self):
        members = [
            ("sine", 0),
            ("tri", 1),
            ("saw", 2),
            ("sawInv", 3),
            ("square", 4),
            ("noise", 5),
        ]
        for name, number in members:
            with self.subTest(kind=name):
                descriptor = self.compile_scale_x("osc(type: oscKind.%s)" % name)
                self.assertEqual(number, descriptor["oscType"])

    def test_noise2d_member_compiles_without_diagnostics(self):
        # Kind 6 used to fall through to the S002 fallback and animated as a
        # sine; the member (and the literal) must now be accepted as noise2d.
        descriptor = self.compile_scale_x("osc(type: oscKind.noise2d, seed: 42)")
        self.assertEqual(6, descriptor["oscType"])
        self.assertEqual(42, descriptor["seed"])

    def test_numeric_kind_6_is_accepted(self):
        descriptor = self.compile_scale_x("osc(type: 6, seed: 7)")
        self.assertEqual(6, descriptor["oscType"])

    def test_oscillator_defaults_are_applied(self):
        descriptor = self.compile_scale_x("osc(type: oscKind.sine)")
        self.assertEqual(0, descriptor["min"])
        self.assertEqual(1, descriptor["max"])
        self.assertEqual(1, descriptor["speed"])
        self.assertEqual(0, descriptor["offset"])
        self.assertEqual(1, descriptor["seed"])


class OscillatorPinTests(unittest.TestCase):
    """Kinds 0-5 keep their pinned outputs (recorded from the implementation
    before noise2d support was added, upstream test_oscillators.js)."""

    PIN_TIMES = [0, 0.25, 0.5, 0.75]
    PINS = [
        (7, 0, [0, 0.5, 1, 0.5]),
        (7, 1, [0, 0.5, 1, 0.5]),
        (7, 2, [0, 0.25, 0.5, 0.75]),
        (7, 3, [1, 0.75, 0.5, 0.25]),
        (7, 4, [0, 0, 1, 1]),
        (7, 5, [0.378248872499931, 0.7515301125166395,
                0.269999372498686, 0.549302812511977]),
        (42, 5, [0.06935776014230743, 0.5376382001337624,
                 0.40049026022115086, 0.6929954000587877]),
    ]

    def test_kinds_0_to_5_keep_their_pinned_outputs(self):
        for seed, kind, values in self.PINS:
            with self.subTest(kind=kind, seed=seed):
                curve = sample(oscillator(kind, seed=seed), self.PIN_TIMES)
                for i, expected in enumerate(values):
                    self.assertLessEqual(abs(curve[i] - expected), 1e-9,
                                         "t=%r: %r != %r" % (self.PIN_TIMES[i], curve[i], expected))


class Noise2dRuntimeTests(unittest.TestCase):
    def test_noise2d_stays_in_0_to_1_and_is_deterministic(self):
        times = [i / 64 for i in range(65)]
        for seed in (7, 42, 123):
            for speed in (1, 2, 3):
                with self.subTest(seed=seed, speed=speed):
                    probe = oscillator(6, seed=seed, speed=speed)
                    curve = sample(probe, times)
                    for i, value in enumerate(curve):
                        self.assertGreaterEqual(value, 0, "t=%r" % times[i])
                        self.assertLessEqual(value, 1, "t=%r" % times[i])
                    self.assertEqual(curve, sample(probe, times))

    def test_noise2d_differs_from_sine_and_noise1d(self):
        times = [i / 32 for i in range(33)]
        noise2d = sample(oscillator(6, seed=42), times)
        sine = sample(oscillator(0, seed=42), times)
        noise1d = sample(oscillator(5, seed=42), times)
        self.assertGreater(max_abs_diff(noise2d, sine), 0.01)
        self.assertGreater(max_abs_diff(noise2d, noise1d), 0.01)

    def test_noise2d_varies_with_seed(self):
        times = [i / 32 for i in range(33)]
        curve_a = sample(oscillator(6, seed=42), times)
        curve_b = sample(oscillator(6, seed=7), times)
        self.assertGreater(max_abs_diff(curve_a, curve_b), 0.01)

    def test_noise2d_loops_seamlessly_at_whole_number_speeds(self):
        for speed in (1, 2, 3):
            for offset in (0, 0.25):
                for seed in (7, 42):
                    with self.subTest(speed=speed, offset=offset, seed=seed):
                        config = oscillator(6, speed=speed, offset=offset, seed=seed)
                        start = resolve_uniform_value(config, 0)
                        end = resolve_uniform_value(config, 1)
                        self.assertLessEqual(abs(end - start), 1e-9)

    def test_noise2d_matches_the_osc2d_reference_formula_at_non_unit_speeds(self):
        # Independent re-implementation of the osc2d effect's formula,
        # including the runtime's fixed seed-derived sampling position, so the
        # expected values pin that speed is applied exactly once (after the
        # first periodic wrap), not again on top of the phase.
        period = math.tau

        def periodic_value(x, v):
            return (math.sin((x - v) * period) + 1) * 0.5

        def js_remainder(value, divisor):
            remainder = math.fmod(value, divisor)
            return remainder

        def hash21(px, py, s):
            x = js_remainder(px * 234.34 + s, 1)
            y = js_remainder(py * 435.345 + s, 1)
            if x < 0:
                x += 1
            if y < 0:
                y += 1
            p = x + y + (x + y) * 34.23
            return js_remainder(x * y * p, 1)

        def noise_2d(px, py, s):
            ix = math.floor(px)
            iy = math.floor(py)
            fx = px - ix
            fy = py - iy
            fx = fx * fx * (3 - 2 * fx)
            fy = fy * fy * (3 - 2 * fy)
            a = hash21(ix, iy, s)
            b = hash21(ix + 1, iy, s)
            c = hash21(ix, iy + 1, s)
            d = hash21(ix + 1, iy + 1, s)
            return (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy)
                    + c * (1 - fx) * fy + d * fx * fy)

        for seed, speed in ((42, 2), (7, 3.5), (123, 1)):
            px = (abs(js_remainder(seed, 16)) + 0.5) / 16
            py = (abs(js_remainder(math.floor(seed / 16), 16)) + 0.5) / 16
            time_noise = noise_2d(px, py, seed + 12345)
            value_noise = noise_2d(px, py, seed)
            config = oscillator(6, speed=speed, offset=0.25, seed=seed)
            for normalized_time in (0, 0.3, 0.5, 0.77, 1):
                with self.subTest(seed=seed, speed=speed, time=normalized_time):
                    expected = periodic_value(
                        periodic_value(normalized_time + 0.25, time_noise) * speed,
                        value_noise,
                    )
                    actual = resolve_uniform_value(config, normalized_time)
                    self.assertLessEqual(abs(actual - expected), 1e-12)


if __name__ == "__main__":
    unittest.main()
