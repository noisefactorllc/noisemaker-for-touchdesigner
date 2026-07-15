#!/usr/bin/env python3
"""Require parity fixtures for every interacting artistic-release branch."""

import re
import unittest
from pathlib import Path


PROGRAMS = Path(__file__).with_name("programs")
DEFAULTS = {
    "extrude": {"type": "blocks", "depthSource": "luminance"},
    "halftone": {"mode": "color", "pattern": "dot"},
    "morphology": {"mode": "dilate", "shape": "square"},
    "wind": {"method": "blast", "direction": "fromLeft"},
    "dither": {"type": "bayer4x4"},
}
CHOICES = {
    ("extrude", "type"): {"0": "blocks", "1": "pyramids"},
    ("extrude", "depthSource"): {"0": "luminance", "1": "random"},
    ("halftone", "mode"): {"0": "color", "1": "mono"},
    ("halftone", "pattern"): {"0": "dot", "1": "line", "2": "circle"},
    ("morphology", "mode"): {"0": "dilate", "1": "erode"},
    ("morphology", "shape"): {"0": "square", "1": "round"},
    ("wind", "method"): {"0": "wind", "1": "blast", "2": "stagger"},
    ("wind", "direction"): {"0": "fromLeft", "1": "fromRight"},
    ("dither", "type"): {
        "0": "bayer2x2", "1": "bayer4x4", "2": "bayer8x8", "3": "dot",
        "4": "line", "5": "crosshatch", "6": "noise", "7": "errorDiffusion",
    },
    ("hatch", "mode"): {"0": "pen", "1": "charcoal", "2": "chalkCharcoal", "3": "conte", "4": "crosshatch", "5": "coloredPencil"},
    ("hatch", "direction"): {"0": "rightDiag", "1": "horizontal", "2": "leftDiag", "3": "vertical"},
    ("lensFlare", "lensType"): {"0": "zoom50_300", "1": "prime35", "2": "prime105", "3": "moviePrime"},
    ("mosaicTiles", "mode"): {"0": "mosaic", "1": "shifted"},
    ("oilPaint", "mode"): {"0": "facet", "1": "daubs", "2": "dryBrush", "3": "fresco", "4": "knife", "5": "sponge"},
    ("pondRipples", "style"): {"0": "aroundCenter", "1": "outFromCenter", "2": "pondRipples"},
    ("pondRipples", "wrap"): {"0": "mirror", "1": "repeat", "2": "clamp"},
    ("relief", "mode"): {"0": "basRelief", "1": "plaster", "2": "notePaper"},
    ("scatter", "mode"): {"0": "normal", "1": "darkenOnly", "2": "lightenOnly", "3": "anisotropic", "4": "clumped"},
    ("stipple", "mode"): {"0": "pointillize", "1": "mezzoDots", "2": "mezzoLines", "3": "mezzoStrokes", "4": "reticulation"},
    ("strokes", "mode"): {"0": "angled", "1": "sprayed", "2": "dark", "3": "sumiE", "4": "smudge"},
    ("edge", "kernel"): {"0": "fine", "1": "bold", "2": "contour"},
    ("edge", "contourSide"): {"0": "lower", "1": "upper"},
    ("edge", "invert"): {"0": "off", "1": "on"},
    ("emboss", "style"): {"0": "color", "1": "gray"},
    ("invert", "mode"): {"0": "full", "1": "solarize"},
    ("lowPoly", "mode"): {"0": "flat", "1": "edges", "2": "distance2", "3": "distance3"},
    ("texture", "mode"): {str(i): value for i, value in enumerate(("canvas", "crosshatch", "halftone", "paper", "stucco", "regular", "soft", "sprinkles", "clumped", "contrasty", "enlarged", "stippled", "horizontal", "vertical", "speckle"))},
}


def normalize(effect, param, value):
    return CHOICES.get((effect, param), {}).get(value, value)


def fixture_values(effect, params):
    found = set()
    pattern = re.compile(rf"\.{effect}\(([^()]*)\)")
    for path in PROGRAMS.glob("*.dsl"):
        match = pattern.search(path.read_text())
        if not match:
            continue
        args = dict(DEFAULTS[effect])
        for item in match.group(1).split(","):
            if ":" not in item:
                continue
            key, value = (part.strip() for part in item.split(":", 1))
            args[key] = normalize(effect, key, value)
        found.add(tuple(args[param] for param in params))
    return found


def effect_sources(effect):
    marker = f".{effect}("
    return [path.read_text() for path in PROGRAMS.glob("*.dsl") if marker in path.read_text()]


def call_arguments(effect):
    calls = []
    marker = f".{effect}("
    for source in effect_sources(effect):
        start = source.index(marker) + len(marker)
        depth = 0
        items = []
        current = []
        for char in source[start:]:
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    if current:
                        items.append("".join(current))
                    break
                depth -= 1
            if char == "," and depth == 0:
                items.append("".join(current))
                current = []
            else:
                current.append(char)
        args = {}
        for item in items:
            if ":" in item:
                key, value = (part.strip() for part in item.split(":", 1))
                args[key] = normalize(effect, key, value)
        calls.append(args)
    return calls


NEW_EFFECTS = (
    "chrome", "craquelure", "directionalBlur", "extrude", "halftone",
    "hatch", "highPass", "lensFlare", "median", "morphology",
    "mosaicTiles", "oilPaint", "patchwork", "photocopy", "plasticWrap",
    "pondRipples", "relief", "scatter", "spinBlur", "stamp", "stipple",
    "strokes", "unsharpMask", "watercolor", "wind",
)
REFERENCE_CASES = {
    "hatch": [{"mode": mode, "direction": "rightDiag"} for mode in ("pen", "charcoal", "chalkCharcoal", "conte", "crosshatch", "coloredPencil")]
             + [{"mode": "coloredPencil", "direction": "leftDiag"}],
    "lensFlare": [{"lensType": lens, "centerX": "0.31", "centerY": "0.67"} for lens in ("zoom50_300", "prime35", "prime105", "moviePrime")],
    "mosaicTiles": [{"mode": mode} for mode in ("mosaic", "shifted")],
    "oilPaint": [{"mode": mode} for mode in ("facet", "daubs", "dryBrush", "fresco", "knife", "sponge")],
    "pondRipples": [{"style": style, "amount": "70"} for style in ("aroundCenter", "outFromCenter", "pondRipples")]
                   + [{"style": "pondRipples", "wrap": wrap, "amount": "70"} for wrap in ("repeat", "clamp")],
    "relief": [{"mode": mode, "lightAngle": "37"} for mode in ("basRelief", "plaster", "notePaper")],
    "scatter": [{"mode": mode} for mode in ("normal", "darkenOnly", "lightenOnly", "anisotropic", "clumped")],
    "stipple": [{"mode": mode} for mode in ("pointillize", "mezzoDots", "mezzoLines", "mezzoStrokes", "reticulation")],
    "strokes": [{"mode": mode} for mode in ("angled", "sprayed", "dark", "sumiE", "smudge")],
    "edge": [{"kernel": "contour", "contourSide": "upper", "invert": "on"}],
    "emboss": [{"style": "gray", "angle": "37", "height": "4", "colorAmount": "55"}],
    "invert": [{"mode": "solarize"}],
    "lowPoly": [{"mode": mode} for mode in ("flat", "edges", "distance2", "distance3")],
    "texture": [{"mode": mode} for mode in ("regular", "soft", "sprinkles", "clumped", "contrasty", "enlarged", "stippled", "horizontal", "vertical", "speckle")],
}



class ArtisticMatrixTests(unittest.TestCase):

    def test_all_new_effect_defaults(self):
        missing = [effect for effect in NEW_EFFECTS if {} not in call_arguments(effect)]
        self.assertEqual([], missing)

    def test_frozen_reference_cases(self):
        missing = []
        for effect, cases in REFERENCE_CASES.items():
            actual = call_arguments(effect)
            for expected in cases:
                if expected not in actual:
                    missing.append(f"{effect}:{expected}")
        self.assertEqual([], missing)

    def assert_matrix(self, effect, params, expected):
        actual = fixture_values(effect, params)
        self.assertTrue(expected <= actual, f"{effect} missing {sorted(expected - actual)}")

    def test_extrude_type_by_depth_source(self):
        self.assert_matrix(
            "extrude", ("type", "depthSource"),
            {(t, d) for t in ("blocks", "pyramids") for d in ("luminance", "random")},
        )

    def test_halftone_live_mode_by_pattern(self):
        self.assert_matrix(
            "halftone", ("mode", "pattern"),
            {("color", "dot"), ("mono", "dot"), ("mono", "line"), ("mono", "circle")},
        )

    def test_morphology_mode_by_shape(self):
        self.assert_matrix(
            "morphology", ("mode", "shape"),
            {(m, s) for m in ("dilate", "erode") for s in ("square", "round")},
        )

    def test_wind_method_by_direction(self):
        self.assert_matrix(
            "wind", ("method", "direction"),
            {(m, d) for m in ("wind", "blast", "stagger") for d in ("fromLeft", "fromRight")},
        )

    def test_error_diffusion_branch(self):
        actual = {row[0] for row in fixture_values("dither", ("type",))}
        self.assertIn("errorDiffusion", actual)

    def test_directional_blur_nondefault_parameters(self):
        self.assertTrue(any("angle: 37" in source and "distance: 75" in source for source in effect_sources("directionalBlur")))

    def test_plastic_wrap_nondefault_light_direction(self):
        self.assertTrue(any("lightDirection: vec3(" in source for source in effect_sources("plasticWrap")))

    def test_spin_blur_off_center(self):
        self.assertTrue(any("centerX: 0.35" in source and "centerY: 0.3" in source for source in effect_sources("spinBlur")))


if __name__ == "__main__":
    unittest.main()
