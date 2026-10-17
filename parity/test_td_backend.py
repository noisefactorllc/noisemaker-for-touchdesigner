#!/usr/bin/env python3
"""App-free regressions for TouchDesigner runtime helpers."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.runtime import td_backend  # noqa: E402


class BoolDefineScanTests(unittest.TestCase):
    def test_block_comment_boolean_patterns_do_not_classify_numeric_define(self):
        source = (
            "/* legacy: #define COUNT true\n"
            "void old_main() { if (COUNT) {} } */\n"
            "#define COUNT 5\n"
            "void main() { int n = COUNT; }\n"
        )

        self.assertEqual(td_backend._bool_define_keys(source), set())

    def test_line_comment_boolean_patterns_do_not_classify_numeric_define(self):
        source = (
            "// legacy: #define COUNT false\n"
            "// void old_main() { if (COUNT) {} }\n"
            "#define COUNT 5\n"
            "void main() { int n = COUNT; }\n"
        )

        self.assertEqual(td_backend._bool_define_keys(source), set())

    def test_live_fallback_and_bare_if_are_still_detected(self):
        source = (
            "#ifndef RIDGES\n"
            "#define RIDGES true\n"
            "#endif\n"
            "void main() { if (RIDGES) {} if (!INVERT) {} }\n"
        )

        self.assertEqual(td_backend._bool_define_keys(source), {"RIDGES", "INVERT"})

    def test_arithmetic_comparison_and_loop_bound_uses_stay_numeric(self):
        source = (
            "#define COUNT 5\n"
            "void main() {\n"
            "  int doubled = COUNT * 2;\n"
            "  if (COUNT == 1) {}\n"
            "  for (int i = 0; i < COUNT; ++i) {}\n"
            "}\n"
        )

        self.assertEqual(td_backend._bool_define_keys(source), set())

    def test_effect_assembly_preserves_commented_source_byte_for_byte(self):
        source = "/* #define COUNT true */\n#define COUNT 5\nvoid main() {}\n"

        assembled = td_backend._assemble_effect_source(source, {"COUNT": 5})

        self.assertTrue(assembled.endswith(source))
        self.assertEqual("#define COUNT 5\n" + source, assembled)


class MrtStorageFormatTests(unittest.TestCase):
    @staticmethod
    def graph(formats):
        specs = {name: SimpleNamespace(fmt=fmt) for name, fmt in formats.items()}
        return SimpleNamespace(spec_for=lambda tex_id: specs.get(tex_id))

    def test_three_buffer_particle_state_uses_half_float_under_32_byte_budget(self):
        pass_ = SimpleNamespace(outputs={
            "outXYZ": "xyz", "outVel": "vel", "outRGBA": "rgba",
        })
        graph = self.graph({"xyz": "rgba32f", "vel": "rgba32f", "rgba": "rgba8"})

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph, 32), "rgba16float")

    def test_default_native_budget_preserves_full_float_particle_state(self):
        pass_ = SimpleNamespace(outputs={
            "outXYZ": "xyz", "outVel": "vel", "outRGBA": "rgba",
        })
        graph = self.graph({"xyz": "rgba32f", "vel": "rgba32f", "rgba": "rgba8"})

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph), "rgba32float")

    def test_two_full_float_buffers_fit_the_same_budget(self):
        pass_ = SimpleNamespace(outputs={"outA": "a", "outB": "b"})
        graph = self.graph({"a": "rgba32f", "b": "rgba32float"})

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph, 32), "rgba32float")

    def test_larger_budget_preserves_three_full_float_buffers(self):
        pass_ = SimpleNamespace(outputs={"outA": "a", "outB": "b", "outC": "c"})
        graph = self.graph({"a": "rgba32f", "b": "rgba32f", "c": "rgba8"})

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph, 64), "rgba32float")

    def test_four_buffer_life_state_fits_exactly_at_half_float(self):
        pass_ = SimpleNamespace(outputs={
            "outXYZ": "xyz", "outVel": "vel", "outRGBA": "rgba", "outState": "state",
        }, draw_buffers=4)
        graph = self.graph({
            "xyz": "rgba32f", "vel": "rgba32f", "rgba": "rgba8", "state": "rgba16f",
        })

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph, 32), "rgba16float")

    def test_render_select_converts_storage_back_to_logical_attachment_format(self):
        class FakeParent:
            def create(self, _operator_type, name):
                return SimpleNamespace(name=name, par=SimpleNamespace())

        backend = td_backend.TDBackend(FakeParent(), "/unused")
        spec = SimpleNamespace(fmt="rgba8")
        with mock.patch.object(td_backend, "_td", return_value="renderselectTOP"):
            select = backend._register_mrt_buffer(object(), 2, "rgba", "points", spec)

        self.assertEqual(select.par.format, "rgba8fixed")


class DepositRefreshEngineUniformsTests(unittest.TestCase):
    """set_time must keep the engine globals a deposit MAT's shader declares.

    _build_points merges engine uniforms into the deposit binding (the deposit
    vertex shader declares `resolution`), so its refresh record must resolve
    against the same engine+pass source at refresh time; otherwise the
    re-binding silently drops `resolution` and truncates the last Vectors slot.
    """

    @staticmethod
    def _fake_op(name):
        class FakeConnector:
            def connect(self, _op):
                pass

            def disconnect(self):
                pass

        op = SimpleNamespace(name=name, par=SimpleNamespace(), children=[],
                             inputConnectors=[FakeConnector()])

        def create(_operator_type, child_name):
            child = DepositRefreshEngineUniformsTests._fake_op(child_name)
            op.children.append(child)
            return child

        op.create = create
        return op

    def test_set_time_keeps_declared_engine_resolution_on_deposit_mat(self):
        from noisemaker.runtime.render_graph import Pass

        class FakeParent:
            def create(self, _operator_type, name):
                return self._fake_op(name)

            @staticmethod
            def _fake_op(name):
                return DepositRefreshEngineUniformsTests._fake_op(name)

        backend = td_backend.TDBackend(FakeParent(), "/unused", width=256, height=256, time=0)
        backend.tex_top = {
            "xyz": self._fake_op("xyz_top"),
            "rgba": self._fake_op("rgba_top"),
        }
        backend._tex_res["xyz"] = (16, 16)
        render_pass = Pass.from_dict({
            "id": "agents_deposit", "drawMode": "points",
            "inputs": {"xyzTex": "xyz", "rgbaTex": "rgba"},
            "outputs": {"fragColor": "trail"},
        })
        graph = SimpleNamespace(spec_for=lambda tex_id: None)

        with mock.patch.object(td_backend, "_td", return_value="op"):
            backend._build_points(render_pass, graph)

        record = backend._dynamic_uniforms[-1]
        # Build-time precondition: the deposit shader declares `resolution` and
        # it was bound from the engine merge.
        self.assertIn("resolution", record["bound"])
        self.assertEqual(record["bound"]["resolution"], [256.0, 256.0])

        with mock.patch.object(td_backend, "_td", return_value="op"):
            backend.refresh_uniforms(0.5)

        self.assertIn("resolution", record["bound"])
        self.assertEqual(record["bound"]["resolution"], [256.0, 256.0])


class DepositRenderSettingsTests(unittest.TestCase):
    """The deposit operators must receive values TouchDesigner 2025.32820 accepts.

    The backend sets operator parameters through `_try`, which hides a rejected menu name. The
    expected values are the installed menu names: GLSL MAT src/destblend use `sa`/`omsa`, and
    Render TOP `antialias` uses `aa1` (a bare `'1'` selects menu index 1, 2x multisampling).
    """

    TD_BLEND_MENU = ("zero", "dcol", "omdcol", "sa", "omsa", "da", "omda", "sas", "one",
                     "constantcol", "omconstantcol", "constanta", "omconstanta")

    def _build(self, pass_dict, prior=False):
        from noisemaker.runtime.render_graph import Pass

        created = {}

        def fake_op(name):
            op = DepositRefreshEngineUniformsTests._fake_op(name)
            created[name] = op
            return op

        class FakeParent:
            def create(self, _operator_type, name):
                return fake_op(name)

        backend = td_backend.TDBackend(FakeParent(), "/unused", width=256, height=256, time=0)
        backend.tex_top = {"xyz": fake_op("xyz_top"), "rgba": fake_op("rgba_top")}
        if prior:
            backend.tex_top["trail"] = fake_op("trail_prior")
        backend._tex_res["xyz"] = (16, 16)
        graph = SimpleNamespace(spec_for=lambda tex_id: None)
        with mock.patch.object(td_backend, "_td", return_value="op"):
            backend._build_points(Pass.from_dict(pass_dict), graph)
        return created

    @staticmethod
    def _billboard(name, blend, blur_layer, blend_mode):
        return {
            "id": name, "drawMode": "billboards", "blend": blend,
            "nodeId": "node_7", "progName": "deposit",
            "program": "node_7_deposit__BLEND_MODE_%d__BLUR_LAYER_%d__VIEW_MODE_2" % (
                blend_mode, blur_layer),
            "inputs": {"xyzTex": "xyz", "rgbaTex": "rgba", "spriteMeanTex": "mean"},
            "outputs": {"fragColor": "trail"},
        }

    @staticmethod
    def _one(created, suffix):
        matches = [op for name, op in created.items() if name.endswith(suffix)]
        assert len(matches) == 1, (suffix, sorted(created))
        return matches[0]

    def test_blend_factor_map_uses_installed_menu_names(self):
        for value in td_backend._BLEND_FACTOR_MAP.values():
            self.assertIn(value, self.TD_BLEND_MENU)

    def test_alpha_deposit_sets_premultiplied_over_factors(self):
        created = self._build(self._billboard("alpha", ["ONE", "ONE_MINUS_SRC_ALPHA"], 0, 1))
        mat = self._one(created, "_mat")
        self.assertEqual((mat.par.srcblend, mat.par.destblend), ("one", "omsa"))

    def test_deposit_render_disables_multisampling(self):
        created = self._build({
            "id": "points", "drawMode": "points", "blend": True,
            "inputs": {"xyzTex": "xyz", "rgbaTex": "rgba"}, "outputs": {"fragColor": "trail"},
        })
        self.assertEqual(self._one(created, "_render").par.antialias, "aa1")

    def test_billboard_clones_compile_their_blur_layer(self):
        for layer in (0, 1):
            created = self._build(self._billboard("bb", True, layer, 0))
            self.assertTrue(self._one(created, "_vert").text.startswith(
                "#define BLUR_LAYER %d\n" % layer))

    def test_billboard_instances_one_quad_per_agent(self):
        created = self._build(self._billboard("bb", True, 0, 0))
        geo = self._one(created, "_geo")
        self.assertEqual([child.name.rsplit("_", 1)[-1] for child in geo.children], ["quad"])
        quad = geo.children[0]
        self.assertEqual((quad.par.sizex, quad.par.sizey), (2, 2))
        self.assertEqual((geo.par.instancing, geo.par.instancecountmode, geo.par.numinstances),
                         (True, "manual", 16 * 16))

    def test_narrow_mrt_attachment_is_copied_in_its_logical_format(self):
        class FakeParent:
            def create(self, _operator_type, name):
                return DepositRefreshEngineUniformsTests._fake_op(name)

        backend = td_backend.TDBackend(FakeParent(), "/unused")
        with mock.patch.object(td_backend, "_td", return_value="op"):
            rgba = backend._register_mrt_buffer(object(), 2, "rgba", "agent",
                                                SimpleNamespace(fmt="rgba8"), "rgba32float")
            xyz = backend._register_mrt_buffer(object(), 0, "xyz", "agent",
                                               SimpleNamespace(fmt="rgba32f"), "rgba32float")
        self.assertEqual((rgba.name, rgba.par.format), ("agent_b2_fmt", "rgba8fixed"))
        self.assertEqual(xyz.name, "agent_b0")

    def test_billboard_binds_sprite_mean_texture(self):
        created = self._build(self._billboard("bb", True, 1, 0))
        self.assertEqual(self._one(created, "_mat").par.sampler4name, "spriteMeanTex")

    def test_alpha_deposit_composites_over_prior_trail(self):
        created = self._build(self._billboard("alpha", ["ONE", "ONE_MINUS_SRC_ALPHA"], 0, 1),
                              prior=True)
        self.assertIn("(1.0 - texture(sTD2DInputs[1], vUV.st).a)",
                      self._one(created, "_acc_src").text)

    def test_additive_deposit_adds_onto_prior_trail(self):
        created = self._build(self._billboard("bb", True, 0, 0), prior=True)
        text = self._one(created, "_acc_src").text
        self.assertIn("texture(sTD2DInputs[0], vUV.st) + texture(sTD2DInputs[1], vUV.st)", text)
        self.assertNotIn(".a)", text)


class VolumeFoldTests(unittest.TestCase):
    """Volume atlases taller than TD's 1280 cook cap are stored folded into bands."""

    PRODUCER = (
        "uniform int volumeSize;\n"
        "layout(location = 0) out vec4 fragColor;\n"
        "void main() {\n"
        "    ivec2 atlas = ivec2(gl_FragCoord.xy);\n"
        "    fragColor = vec4(atlas, 0.0, 1.0);\n"
        "}\n"
    )

    def test_atlases_under_the_cap_are_not_folded(self):
        self.assertIsNone(td_backend._volume_fold(32))
        self.assertEqual(td_backend._apply_volume_fold(self.PRODUCER, None, None), self.PRODUCER)

    def test_volume_size_64_folds_into_four_bands(self):
        self.assertEqual(td_backend._volume_fold(64),
                         {"vs": 64, "m": 16, "bands": 4, "w": 257, "h": 1024})

    def test_fold_layout_round_trips_every_voxel(self):
        fold = td_backend._volume_fold(64)
        vs, m = fold["vs"], fold["m"]
        seen = set()
        for z in range(vs):
            for y in range(0, vs, 7):
                for x in range(0, vs, 9):
                    r = y + z * vs                                  # reference atlas row
                    zz = r // vs                                    # nm_volumeFetch
                    px, py = x + (zz // m) * vs, r - zz * vs + (zz % m) * vs
                    self.assertTrue(px < fold["w"] - 1 and py < fold["h"])
                    band = px // vs                                 # folded main()
                    uz = band * m + py // vs
                    self.assertEqual((px - band * vs, py % vs + uz * vs), (x, r))
                    seen.add((px, py))
        self.assertEqual(len(seen), vs * len(range(0, vs, 7)) * len(range(0, vs, 9)))

    def test_writer_runs_original_main_on_unfolded_coordinates(self):
        fold = td_backend._volume_fold(64)
        source = td_backend._apply_volume_fold(self.PRODUCER, fold, None)
        self.assertIn("void nm_volumeMain() {", source)
        self.assertIn("ivec2 atlas = ivec2(nm_FragCoord.xy);", source)
        self.assertEqual(source.count("void main()"), 1)
        self.assertIn("#define NM_FOLD_W 257\n", source)
        self.assertNotIn("#define texelFetch", source)

    def test_reader_routes_texel_fetch_through_the_fold(self):
        fold = td_backend._volume_fold(64)
        reader = "void main() { vec4 v = texelFetch(volumeCache, ivec2(1, 2 + 3 * 64), 0); }\n"
        source = td_backend._apply_volume_fold(reader, None, fold)
        self.assertIn("#define texelFetch(s, c, l) nm_volumeFetch(s, c, l)", source)
        self.assertTrue(source.endswith(reader))

    def test_flow3d_graph_keeps_the_unfolded_cap(self):
        from noisemaker.runtime.render_graph import Pass

        deposit = Pass.from_dict({"id": "dep", "drawMode": "points", "uniforms": {"volumeSize": 64},
                                  "inputs": {"stateTex1": "s1", "stateTex2": "s2"},
                                  "outputs": {"fragColor": "trail"}})
        effect = Pass.from_dict({"id": "fx", "uniforms": {"volumeSize": 64}, "outputs": {}})
        backend = td_backend.TDBackend(SimpleNamespace(), "/unused")
        backend._cap_volume_size(SimpleNamespace(passes=[deposit, effect]))
        self.assertEqual(effect.uniforms["volumeSize"], 32)
        effect.uniforms["volumeSize"] = 64
        backend._cap_volume_size(SimpleNamespace(passes=[effect]))
        self.assertEqual(effect.uniforms["volumeSize"], 64)


class DepositShaderSourceTests(unittest.TestCase):
    """The hand-written deposit shaders keep the reference's expressions."""

    def setUp(self):
        from noisemaker.runtime import deposit_shaders
        self.shaders = deposit_shaders

    def test_density_cull_uses_reference_float32_expression(self):
        self.assertIn("return fract(float(vid) * 0.618033988749895);", self.shaders._VERT_PROLOGUE)
        self.assertIn("fract(float(particleID) * 0.618033988749895)", self.shaders.BILLBOARD_VERT)

    def test_billboard_draws_reference_quads_per_instance(self):
        vert = self.shaders.BILLBOARD_VERT
        self.assertIn("int particleID = TDInstanceID();", vert)
        self.assertIn("vec2 offset = TDPos().xy;", vert)
        self.assertIn("vSpriteUV = offset * (0.5 + blurPadding + supportRadius) + 0.5;", vert)
        self.assertNotIn("gl_PointSize", vert)
        self.assertNotIn("TDPointCoord", self.shaders.BILLBOARD_FRAG)

    def test_billboard_splits_energy_between_blur_layers(self):
        vert = self.shaders.BILLBOARD_VERT
        self.assertIn("float layerWeight = BLUR_LAYER == 1 ? lowWeight : 1.0 - lowWeight;", vert)
        self.assertIn("vColor = col * brightnessFade * layerWeight;", vert)
        self.assertIn("blurWeight(vSpriteUV, center, expansion)", self.shaders.BILLBOARD_FRAG)


class TexturePolicyFieldsTests(unittest.TestCase):
    """GAP-004: mipmaps/persistent/filter ride through the graph data model."""

    def test_texture_spec_carries_policy_fields(self):
        from noisemaker.runtime.render_graph import TextureSpec

        spec = TextureSpec.from_dict({
            "width": 64, "height": 64, "format": "rgba16f",
            "mipmaps": True, "persistent": True,
        })

        self.assertTrue(spec.mipmaps)
        self.assertTrue(spec.persistent)
        self.assertIsNone(spec.filter)

    def test_texture_spec_carries_3d_filter(self):
        from noisemaker.runtime.render_graph import TextureSpec

        spec = TextureSpec.from_dict({
            "width": 8, "height": 8, "depth": 8, "is3D": True,
            "format": "rgba16f", "filter": "nearest",
        })

        self.assertEqual(spec.filter, "nearest")
        self.assertIsNone(spec.mipmaps)
        self.assertIsNone(spec.persistent)

    def test_plain_specs_keep_policy_fields_absent(self):
        from noisemaker.runtime.render_graph import TextureSpec

        spec = TextureSpec.from_dict({"width": 64, "height": 64})

        self.assertIsNone(spec.mipmaps)
        self.assertIsNone(spec.persistent)
        self.assertIsNone(spec.filter)


if __name__ == "__main__":
    unittest.main()
