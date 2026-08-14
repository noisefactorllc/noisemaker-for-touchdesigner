"""TouchDesigner delayed-TOP-readback adapter for :class:`FrameExportQueue`."""

import math

from .td_backend import _td


_ALPHA_MODES = {"straight", "opaque", "premultiplied"}
_COLOR_SPACES = {"srgb", "display-p3"}


def _validate_descriptor(descriptor):
    if not isinstance(descriptor, dict):
        raise TypeError("Frame export descriptor must be a dict")
    for key in ("width", "height"):
        value = descriptor.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("Frame export %s must be a positive integer" % key)
    if descriptor.get("format") != "rgba8unorm":
        raise ValueError("TouchDesigner frame export format must be 'rgba8unorm'")
    if descriptor.get("colorSpace") not in _COLOR_SPACES:
        raise ValueError("TouchDesigner frame export colorSpace must be 'srgb' or 'display-p3'")
    if descriptor.get("alphaMode") not in _ALPHA_MODES:
        raise ValueError(
            "TouchDesigner frame export alphaMode must be 'opaque', 'straight', or 'premultiplied'"
        )
    fps = descriptor.get("fps")
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
        raise ValueError("Frame export fps must be finite and positive")


class TouchDesignerFrameExportAdapter:
    """Use one Null TOP per slot to keep delayed downloads independent and reusable."""

    def __init__(self, parent_comp):
        if parent_comp is None or not callable(getattr(parent_comp, "create", None)):
            raise TypeError("TouchDesigner frame export requires a parent COMP")
        self.parent = parent_comp
        self._name_prefix = "nm_frame_export_%x" % id(self)

    def create_slot(self, index, descriptor):
        _validate_descriptor(descriptor)
        data = bytearray(descriptor["width"] * descriptor["height"] * 4)
        top = self.parent.create(_td("nullTOP"), "%s_%d" % (self._name_prefix, index))
        return {
            "top": top,
            "width": descriptor["width"],
            "height": descriptor["height"],
            "alpha_mode": descriptor["alphaMode"],
            "pixels": None,
            "pending": False,
            "ready": False,
            "destroyed": False,
            "frame": {
                "width": descriptor["width"],
                "height": descriptor["height"],
                "row_stride": descriptor["width"] * 4,
                "data": data,
            },
        }

    def begin(self, slot, texture, _timestamp):
        self._assert_usable(slot)
        if slot["pending"]:
            raise RuntimeError("TouchDesigner frame export slot is already pending")
        if texture is None or not callable(getattr(texture, "numpyArray", None)):
            # A real TOP and the test double both expose numpyArray; checking it before wiring
            # produces a useful error instead of an opaque connector failure.
            raise TypeError("TouchDesigner frame export source must be a TOP")
        top = slot["top"]
        top.lock = False
        top.inputConnectors[0].connect(texture)
        top.cook(force=True)
        extent = (int(top.width), int(top.height))
        expected = (slot["width"], slot["height"])
        if extent != expected:
            top.inputConnectors[0].disconnect()
            raise ValueError(
                "TouchDesigner frame export source extent %dx%d does not match configured extent %dx%d"
                % (extent[0], extent[1], expected[0], expected[1])
            )
        # Freeze this slot's cooked GPU texture. Polling delayed numpy downloads can take more
        # than one host frame; without the lock, a later poll could capture a newer source frame.
        top.lock = True
        slot["pixels"] = None
        slot["pending"] = True
        slot["ready"] = False
        try:
            # The first delayed call schedules the GPU download. Its return value belongs to an
            # older request if this reusable Null TOP has been polled before, so it is discarded.
            top.numpyArray(delayed=True)
        except Exception:
            slot["pending"] = False
            raise

    def poll(self, slot):
        self._assert_usable(slot)
        if not slot["pending"]:
            raise RuntimeError("TouchDesigner frame export slot has no pending download")
        if slot["ready"]:
            return True
        try:
            pixels = slot["top"].numpyArray(delayed=True)
        except Exception:
            slot["pixels"] = None
            slot["pending"] = False
            slot["ready"] = False
            raise
        if pixels is None:
            return False
        slot["pixels"] = pixels
        slot["ready"] = True
        return True

    def read(self, slot):
        self._assert_usable(slot)
        if not slot["pending"] or not slot["ready"] or slot["pixels"] is None:
            raise RuntimeError("TouchDesigner frame export slot is not ready")

        import numpy as np

        try:
            pixels = np.asarray(slot["pixels"])
            expected_shape = (slot["height"], slot["width"], 4)
            if pixels.shape != expected_shape:
                raise ValueError(
                    "TouchDesigner frame export returned shape %r, expected %r"
                    % (pixels.shape, expected_shape)
                )
            output = np.clip(pixels.astype(np.float32, copy=True), 0.0, 1.0)
            if slot["alpha_mode"] == "opaque":
                output[:, :, 3] = 1.0
            elif slot["alpha_mode"] == "premultiplied":
                output[:, :, :3] *= output[:, :, 3:4]
            # TOP.numpyArray() row zero is TouchDesigner's bottom row. Export frames use row zero
            # at top.
            packed = np.floor(output[::-1] * 255.0 + 0.5).astype(np.uint8)
            slot["frame"]["data"][:] = packed.tobytes()
            return slot["frame"]
        finally:
            slot["pixels"] = None
            slot["pending"] = False
            slot["ready"] = False

    def destroy_slot(self, slot):
        if not slot or slot.get("destroyed"):
            return
        slot["destroyed"] = True
        top = slot.get("top")
        slot["pixels"] = None
        slot["pending"] = False
        slot["ready"] = False
        if top is None:
            return
        try:
            top.inputConnectors[0].disconnect()
        finally:
            top.destroy()

    @staticmethod
    def _assert_usable(slot):
        if not slot or slot.get("destroyed") or slot.get("top") is None:
            raise RuntimeError("TouchDesigner frame export slot is not usable")
