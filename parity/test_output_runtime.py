#!/usr/bin/env python3
"""App-free regressions for output sinks and delayed TOP frame export."""

import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.runtime.frame_export import FrameExportQueue  # noqa: E402
from noisemaker.runtime.sink import SinkManager  # noqa: E402
from noisemaker.runtime import td_frame_export  # noqa: E402
from noisemaker.runtime.pipeline import Pipeline  # noqa: E402
from noisemaker.runtime.nm_renderer import NMRenderer  # noqa: E402


class RecordingSink:
    def __init__(self, *, accepted=True, fail_submit=False):
        self.configurations = []
        self.submissions = []
        self.closes = []
        self.accepted = accepted
        self.fail_submit = fail_submit

    def configure(self, descriptor):
        self.configurations.append(descriptor.copy())

    def submit(self, texture, timestamp):
        if self.fail_submit:
            raise RuntimeError("submit failed")
        self.submissions.append((texture, timestamp))
        return self.accepted

    def close(self, options=None):
        self.closes.append(options)


class SinkManagerTests(unittest.TestCase):
    def test_configuration_submission_removal_and_failure_are_isolated(self):
        errors = []
        manager = SinkManager(on_error=lambda error, sink: errors.append((str(error), sink)))
        accepted = RecordingSink()
        dropped = RecordingSink(accepted=False)
        failed = RecordingSink(fail_submit=True)
        remove_accepted = manager.add(accepted)
        manager.add(dropped)
        manager.add(failed)

        descriptor = {"width": 4, "height": 2}
        manager.configure(descriptor)
        manager.submit("top", 12.5)

        self.assertEqual(accepted.configurations, [descriptor])
        self.assertEqual(accepted.submissions, [("top", 12.5)])
        self.assertEqual(manager.stats[accepted], {"accepted": 1, "dropped": 0, "failed": 0})
        self.assertEqual(manager.stats[dropped], {"accepted": 0, "dropped": 1, "failed": 0})
        self.assertEqual(manager.stats[failed], {"accepted": 0, "dropped": 0, "failed": 1})
        self.assertEqual(errors, [("submit failed", failed)])

        remove_accepted()
        remove_accepted()
        self.assertEqual(accepted.closes, [None])
        self.assertNotIn(accepted, manager.stats)
        manager.close({"backend_lost": True})
        self.assertEqual(dropped.closes, [{"backend_lost": True}])
        self.assertEqual(failed.closes, [{"backend_lost": True}])

    def test_late_sink_is_configured_and_invalid_or_duplicate_sinks_are_rejected(self):
        manager = SinkManager()
        manager.configure({"width": 8})
        sink = RecordingSink()

        manager.add(sink)

        self.assertEqual(sink.configurations, [{"width": 8}])
        with self.assertRaises(ValueError):
            manager.add(sink)
        with self.assertRaises(TypeError):
            manager.add(object())


class FakeAdapter:
    def __init__(self):
        self.slots = []
        self.destroyed = []

    def create_slot(self, index, descriptor):
        slot = {"index": index, "descriptor": descriptor, "ready": False}
        self.slots.append(slot)
        return slot

    def begin(self, slot, texture, timestamp):
        slot.update(texture=texture, timestamp=timestamp)

    def poll(self, slot):
        return slot["ready"]

    def read(self, slot):
        return {"texture": slot["texture"]}

    def destroy_slot(self, slot):
        self.destroyed.append(slot)


class FrameExportQueueTests(unittest.TestCase):
    def test_bounded_queue_drops_when_full_then_reuses_a_completed_slot(self):
        adapter = FakeAdapter()
        queue = FrameExportQueue(adapter, slots=2)
        descriptor = {"width": 4, "height": 2}
        queue.configure(descriptor)
        completed = []

        self.assertTrue(queue.enqueue("a", 1.5, lambda *args: completed.append(args), "first"))
        self.assertTrue(queue.enqueue("b", 2.5, lambda *args: completed.append(args), "second"))
        self.assertFalse(queue.enqueue("c", 3.5, lambda *args: completed.append(args)))
        adapter.slots[0]["ready"] = True
        queue.poll()
        self.assertEqual(completed, [({"texture": "a"}, 1.5, "first")])
        self.assertTrue(queue.enqueue("c", 3.5, lambda *args: completed.append(args)))
        self.assertEqual(queue.stats, {
            "accepted": 3, "dropped": 1, "completed": 1, "failed": 0,
        })

        queue.close()
        queue.close()
        self.assertEqual(adapter.destroyed, adapter.slots)

    def test_adapter_and_slot_validation_match_the_shared_contract(self):
        with self.assertRaises(TypeError):
            FrameExportQueue(object())
        for slots in (1, 9, 2.5, True):
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                FrameExportQueue(FakeAdapter(), slots=slots)


class FakeConnector:
    def __init__(self, owner):
        self.owner = owner
        self.source = None
        self.disconnects = 0

    def connect(self, source):
        self.source = source
        self.owner.width = source.width
        self.owner.height = source.height

    def disconnect(self):
        self.source = None
        self.disconnects += 1


class FakeTop:
    def __init__(self, name):
        self.name = name
        self.width = 0
        self.height = 0
        self.lock = False
        self.inputConnectors = [FakeConnector(self)]
        self.arrays = []
        self.numpy_calls = []
        self.cooks = []
        self.destroyed = 0

    def cook(self, force=False):
        self.cooks.append(force)

    def numpyArray(self, delayed=False):
        self.numpy_calls.append(delayed)
        result = self.arrays.pop(0) if self.arrays else None
        if isinstance(result, Exception):
            raise result
        return result

    def destroy(self):
        self.destroyed += 1


class FakeParent:
    def __init__(self):
        self.created = []

    def create(self, top_type, name):
        self.created.append(FakeTop(name))
        return self.created[-1]


class FakeSource:
    width = 2
    height = 2

    def numpyArray(self, delayed=False):
        return None


class TouchDesignerFrameExportTests(unittest.TestCase):
    def test_delayed_readback_is_top_down_rgba8_with_requested_alpha_mode(self):
        parent = FakeParent()
        adapter = td_frame_export.TouchDesignerFrameExportAdapter(parent)
        descriptor = {
            "width": 2,
            "height": 2,
            "format": "rgba8unorm",
            "colorSpace": "srgb",
            "alphaMode": "premultiplied",
            "fps": 60,
        }
        with mock.patch.object(td_frame_export, "_td", return_value="nullTOP"):
            slot = adapter.create_slot(0, descriptor)

        # TouchDesigner returns row zero at the bottom. The exported byte stream is top-down.
        bottom_up = np.array([
            [[1.0, 0.5, 0.25, 0.5], [0.0, 1.0, 0.0, 1.0]],
            [[0.25, 0.5, 0.75, 0.25], [2.0, -1.0, 0.5, 1.0]],
        ], dtype=np.float32)
        slot["top"].arrays[:] = [None, None]

        adapter.begin(slot, FakeSource(), 12.5)
        self.assertTrue(slot["top"].lock)
        self.assertFalse(adapter.poll(slot))
        slot["top"].arrays.append(bottom_up)
        self.assertTrue(adapter.poll(slot))
        frame = adapter.read(slot)

        self.assertEqual((frame["width"], frame["height"], frame["row_stride"]), (2, 2, 8))
        self.assertEqual(list(frame["data"]), [
            16, 32, 48, 64, 255, 0, 128, 255,
            128, 64, 32, 128, 0, 255, 0, 255,
        ])
        self.assertTrue(all(slot["top"].numpy_calls))
        adapter.destroy_slot(slot)
        adapter.destroy_slot(slot)
        self.assertEqual(slot["top"].destroyed, 1)
        self.assertEqual(slot["top"].inputConnectors[0].disconnects, 1)

    def test_descriptor_and_source_extent_are_validated(self):
        parent = FakeParent()
        adapter = td_frame_export.TouchDesignerFrameExportAdapter(parent)
        descriptor = {
            "width": 2, "height": 2, "format": "rgba8unorm",
            "colorSpace": "srgb", "alphaMode": "straight", "fps": 60,
        }
        with mock.patch.object(td_frame_export, "_td", return_value="nullTOP"):
            slot = adapter.create_slot(0, descriptor)
        wrong_source = FakeSource()
        wrong_source.width = 3

        with self.assertRaisesRegex(ValueError, "extent"):
            adapter.begin(slot, wrong_source, 0)
        self.assertFalse(slot["top"].lock)
        with self.assertRaises(ValueError):
            adapter.create_slot(1, {**descriptor, "alphaMode": "invalid"})

    def test_poll_and_read_failures_release_the_adapter_slot_for_reuse(self):
        parent = FakeParent()
        adapter = td_frame_export.TouchDesignerFrameExportAdapter(parent)
        descriptor = {
            "width": 2, "height": 2, "format": "rgba8unorm",
            "colorSpace": "srgb", "alphaMode": "straight", "fps": 60,
        }
        with mock.patch.object(td_frame_export, "_td", return_value="nullTOP"):
            slot = adapter.create_slot(0, descriptor)
        top = slot["top"]
        top.arrays[:] = [None, RuntimeError("download failed")]
        adapter.begin(slot, FakeSource(), 0)
        with self.assertRaisesRegex(RuntimeError, "download failed"):
            adapter.poll(slot)

        top.arrays[:] = [None, np.zeros((1, 1, 4), dtype=np.float32)]
        adapter.begin(slot, FakeSource(), 1)
        self.assertTrue(adapter.poll(slot))
        with self.assertRaisesRegex(ValueError, "shape"):
            adapter.read(slot)

        top.arrays[:] = [None, np.zeros((2, 2, 4), dtype=np.float32)]
        adapter.begin(slot, FakeSource(), 2)
        self.assertTrue(adapter.poll(slot))
        self.assertEqual(len(adapter.read(slot)["data"]), 16)


class FakeOutput:
    def __init__(self):
        self.cooks = []
        self.saves = []

    def cook(self, force=False):
        self.cooks.append(force)

    def save(self, path, createFolders=False):
        self.saves.append((path, createFolders))
        return path


class PipelineAndRendererTests(unittest.TestCase):
    def test_pipeline_rebinds_in_place_when_automated_repeat_changes(self):
        pipeline = Pipeline.__new__(Pipeline)
        pipeline._time = 0
        pipeline._external_state = {"midi": None, "audio": None}
        pipeline.backend = mock.Mock()

        pipeline.set_time(0.25)
        pipeline.set_time(0.5)

        self.assertEqual([
            mock.call(0.25, pipeline._external_state),
            mock.call(0.5, pipeline._external_state),
        ], pipeline.backend.refresh_uniforms.call_args_list)

    def test_pipeline_configures_and_submits_output_and_render_to_preserves_save(self):
        pipeline = Pipeline.__new__(Pipeline)
        pipeline.width = 4
        pipeline.height = 2
        pipeline.output = FakeOutput()
        pipeline.sink_manager = SinkManager()
        pipeline._time = 0.25
        pipeline._effect_tops = []
        pipeline.backend = mock.Mock()
        pipeline.surfaces = mock.Mock(ops=[])
        sink = RecordingSink()
        pipeline.add_sink(sink)
        pipeline._configure_sinks()

        self.assertTrue(pipeline.submit_frame(42.25))
        self.assertEqual(sink.submissions, [(pipeline.output, 42.25)])
        self.assertEqual(pipeline.render_to("frame.png"), "frame.png")
        self.assertEqual(len(sink.submissions), 2)
        self.assertEqual(pipeline.output.saves, [("frame.png", True)])

    def test_renderer_delegates_sink_and_frame_export_apis(self):
        renderer = NMRenderer.__new__(NMRenderer)
        renderer.pipeline = None
        with self.assertRaisesRegex(RuntimeError, "active pipeline"):
            renderer.add_sink(RecordingSink())
        with self.assertRaisesRegex(RuntimeError, "active pipeline"):
            renderer.create_frame_export_queue(slots=2)

        queue = object()
        pipeline = mock.Mock()
        pipeline.add_sink.return_value = "remove"
        pipeline.create_frame_export_queue.return_value = queue
        renderer.pipeline = pipeline
        sink = RecordingSink()
        self.assertEqual(renderer.add_sink(sink), "remove")
        self.assertIs(renderer.create_frame_export_queue(slots=2), queue)
        pipeline.add_sink.assert_called_once_with(sink)
        pipeline.create_frame_export_queue.assert_called_once_with(slots=2, on_error=None)

    def test_renderer_persists_and_delegates_external_input_and_time_controls(self):
        renderer = NMRenderer.__new__(NMRenderer)
        renderer.pipeline = mock.Mock()
        renderer._midi_state = None
        renderer._audio_state = None
        renderer.time = 0.25
        midi = object()
        audio = object()
        requirements = {"needsLegacy": True, "needsLegacyRaw": False, "selected": []}
        renderer.pipeline.get_audio_input_requirements.return_value = requirements

        renderer.set_midi_state(midi)
        renderer.set_audio_state(audio)
        renderer.set_time(0.75)

        self.assertIs(renderer._midi_state, midi)
        self.assertIs(renderer._audio_state, audio)
        self.assertEqual(0.75, renderer.time)
        self.assertEqual(requirements, renderer.get_audio_input_requirements())
        renderer.pipeline.set_midi_state.assert_called_once_with(midi)
        renderer.pipeline.set_audio_state.assert_called_once_with(audio)
        renderer.pipeline.set_time.assert_called_once_with(0.75)


if __name__ == "__main__":
    unittest.main()
