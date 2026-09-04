#!/usr/bin/env python3
"""App-free parity tests for recursive runtime automation."""

import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.runtime.automation import (  # noqa: E402
    get_audio_input_requirements,
    resolve_uniform_value,
)
from noisemaker.runtime.td_backend import TDBackend  # noqa: E402


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


class AutomationRuntimeTests(unittest.TestCase):
    def test_nested_oscillator_rate_is_seekable_and_deterministic(self):
        carrier = oscillator(2, speed=oscillator(0))

        first = resolve_uniform_value(carrier, 0.25)
        repeated = resolve_uniform_value(carrier, 0.25)

        self.assertAlmostEqual((-20 / (math.pi * 2)) % 1, first, places=9)
        self.assertEqual(first, repeated)

    def test_plain_selected_midi_and_audio_snapshots_resolve_exact_identity(self):
        external_state = {
            "midi": {
                "ports": {
                    "port-a": {
                        "name": "Controller",
                        "channels": {"1": {"gate": 1, "key": 0, "velocity": 127}},
                    },
                },
            },
            "audio": {
                "devices": {
                    "device-a": {
                        "name": "Interface",
                        "channels": {"2": {"raw": 1, "rawReady": True}},
                    },
                },
            },
        }
        midi = {
            "type": "Midi", "channel": 1.0, "mode": 2, "min": 0, "max": 1,
            "sensitivity": 1, "name": "Controller", "id": "port-a",
        }
        audio = {
            "type": "Audio", "band": 4, "min": 0.25, "max": 0.75,
            "channel": 2.0, "name": "Interface", "id": "device-a",
        }

        self.assertEqual(1, resolve_uniform_value(midi, 0.5, external_state=external_state))
        self.assertEqual(0.75, resolve_uniform_value(audio, 0.5, external_state=external_state))
        midi["id"] = "missing"
        audio["id"] = "missing"
        self.assertEqual(0, resolve_uniform_value(midi, 0.5, external_state=external_state))
        self.assertEqual(0.25, resolve_uniform_value(audio, 0.5, external_state=external_state))

    def test_runtime_cycle_guard_fails_closed(self):
        cyclic = oscillator(2)
        cyclic["speed"] = cyclic

        self.assertEqual(0, resolve_uniform_value(cyclic, 0.5))

    def test_repeat_uses_automated_uniform_at_the_current_time(self):
        backend = TDBackend(None, "/unused", time=0.25)
        backend.external_state = {}
        render_pass = SimpleNamespace(
            repeat="iterations",
            uniforms={"iterations": oscillator(2, min=0, max=1)},
            uniform_specs={"iterations": {"min": 1, "max": 9}},
        )

        self.assertEqual(3, backend._resolve_repeat(render_pass))
        self.assertEqual(9, backend._repeat_stage_count(render_pass))

    def test_repeat_selector_changes_stage_without_rebuilding_the_graph(self):
        backend = TDBackend(None, "/unused", time=0.25)
        selector = SimpleNamespace(par=SimpleNamespace(index=None))
        render_pass = SimpleNamespace(
            repeat="iterations",
            uniforms={"iterations": oscillator(2, min=0, max=1)},
            uniform_specs={"iterations": {"min": 1, "max": 9}},
        )
        backend._repeat_selectors.append({
            "op": selector, "pass": render_pass, "stage_count": 9,
        })

        backend.refresh_uniforms(0.75)

        self.assertEqual(6, selector.par.index)

    def test_backend_refresh_rebinds_resolved_values_without_losing_static_uniforms(self):
        backend = TDBackend(None, "/unused", width=64, height=32, time=0)
        operator = object()
        bound = {"amount": 0, "gain": 2, "time": 0}
        render_pass = object()
        backend._dynamic_uniforms.append({
            "op": operator,
            "bound": bound,
            "pass": render_pass,
            "source": {"amount": oscillator(), "gain": 2},
            "specs": {"amount": {"min": 10, "max": 20}},
            "declared": {"amount", "gain", "time"},
            "engine": True,
        })

        with mock.patch(
            "noisemaker.runtime.automation.clock.time", return_value=1
        ), mock.patch(
            "noisemaker.runtime.td_backend.uniform_binder.bind_uniforms"
        ) as bind:
            backend.refresh_uniforms(0.25)

        self.assertEqual({"amount": 15, "gain": 2, "time": 0.25}, bound)
        bind.assert_called_once_with(operator, bound)

    def test_repeated_stages_and_selector_share_one_external_input_snapshot(self):
        backend = TDBackend(None, "/unused", time=0.5)
        render_pass = SimpleNamespace(
            repeat="iterations",
            uniforms={"amount": {"type": "Midi"}, "iterations": {"type": "Midi"}},
            uniform_specs={"amount": {}, "iterations": {"min": 1, "max": 4}},
        )
        first_bound = {}
        second_bound = {}
        for operator, bound in ((object(), first_bound), (object(), second_bound)):
            backend._dynamic_uniforms.append({
                "op": operator, "bound": bound, "pass": render_pass,
                "source": render_pass.uniforms, "specs": render_pass.uniform_specs,
                "declared": {"amount", "iterations"}, "engine": False,
            })
        selector = SimpleNamespace(par=SimpleNamespace(index=None))
        backend._repeat_selectors.append({
            "op": selector, "pass": render_pass, "stage_count": 4,
        })

        with mock.patch(
            "noisemaker.runtime.td_backend.automation.resolve_uniforms",
            side_effect=[{"amount": 0.49, "iterations": 2},
                         {"amount": 0.51, "iterations": 3}],
        ) as resolve, mock.patch(
            "noisemaker.runtime.td_backend.automation.resolve_uniform_value"
        ) as resolve_one, mock.patch(
            "noisemaker.runtime.td_backend.uniform_binder.bind_uniforms"
        ):
            backend.refresh_uniforms(0.5)

        resolve.assert_called_once_with(
            render_pass.uniforms, render_pass.uniform_specs, 0.5, backend.external_state
        )
        resolve_one.assert_not_called()
        self.assertEqual(first_bound, second_bound)
        self.assertEqual({"amount": 0.49, "iterations": 2}, first_bound)
        self.assertEqual(1, selector.par.index)

    def test_audio_capture_requirements_include_nested_and_tagged_sources(self):
        inner = {
            "type": "Audio", "band": 4, "min": 0, "max": 1,
            "channel": 2, "name": "Inner Interface", "id": "inner-id",
        }
        outer = {
            "type": "Audio", "band": 0, "min": inner, "max": 1,
            "channel": 1, "name": "Outer Interface", "id": "outer-id",
        }
        graph = SimpleNamespace(passes=[
            SimpleNamespace(namespace="synth", func="scope", uniforms={"amount": outer}),
        ])
        effects_root = REPO / "td" / "noisemaker" / "effects"

        requirements = get_audio_input_requirements(graph, effects_root)

        self.assertTrue(requirements["needsLegacy"])
        self.assertEqual(["inner-id", "outer-id"], [
            item["id"] for item in requirements["selected"]
        ])
        self.assertTrue(requirements["selected"][0]["needsRaw"])

        outer["_invalid"] = True
        requirements = get_audio_input_requirements(graph, effects_root)
        self.assertEqual([], requirements["selected"])


if __name__ == "__main__":
    unittest.main()
