import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.compiler.dsl_compiler import compile_graph  # noqa: E402
from noisemaker.compiler.lang.effect_registry import EffectRegistry  # noqa: E402

_REG = EffectRegistry.load_from_directory()


def build(chain):
    return compile_graph("search synth, mixer, filter, render\n%s\nrender(o0)" % chain, _REG)


def instances(graph, effect_func, state_prefix):
    """One entry per node whose passes touch a texture under state_prefix, asserting every
    pass of an instance uses the same state texture (reference instances())."""
    nodes = {}
    order = []
    for pass_ in graph['passes']:
        if pass_.get('func') != effect_func:
            continue
        node_id = pass_.get('nodeId')
        if node_id not in nodes:
            nodes[node_id] = {'passes': [], 'textures': set(), 'stepIndex': pass_.get('stepIndex')}
            order.append(node_id)
        node = nodes[node_id]
        node['passes'].append(pass_)
        for texture in list(pass_.get('inputs', {}).values()) + list(pass_.get('outputs', {}).values()):
            if isinstance(texture, str) and texture.startswith(state_prefix):
                node['textures'].add(texture)
    result = []
    for node_id in order:
        node = nodes[node_id]
        assert node['textures'], 'instance must touch %s*' % state_prefix
        assert len(node['textures']) == 1, 'all passes in an instance must use the same state'
        node['texture'] = next(iter(node['textures']))
        result.append(node)
    return result


def state_width_param(graph, texture):
    return graph['textures'][texture]['width'].get('screenDivide')


class StatefulInstancesTest(unittest.TestCase):
    def _assert_independent_rd_instances(self, chain, zooms):
        graph = build(chain + '.write(o0)')
        nodes = instances(graph, 'reactionDiffusion', 'global_rd_state')
        self.assertEqual(len(nodes), 2)
        self.assertNotEqual(nodes[0]['texture'], nodes[1]['texture'],
                            'state textures must be distinct')
        for index, node in enumerate(nodes):
            sizing_param = state_width_param(graph, node['texture'])
            for pass_ in node['passes']:
                self.assertEqual((pass_.get('scopedParams') or {}).get('zoom'), sizing_param)
                self.assertEqual(pass_['uniforms'][sizing_param], zooms[index])
        # The zooms must own independent parameters: renaming one must not move the other.
        self.assertNotEqual(state_width_param(graph, nodes[0]['texture']),
                            state_width_param(graph, nodes[1]['texture']),
                            'size parameters must be distinct')
        return graph, nodes

    def test_repeated_reaction_diffusion_instances_independent(self):
        self._assert_independent_rd_instances(
            'reactionDiffusion(zoom: x4).blendMode(tex: reactionDiffusion(zoom: x16))',
            [4, 16])

    def test_repeated_reaction_diffusion_instances_with_middleware(self):
        self._assert_independent_rd_instances(
            'perlin().blendMode(tex: reactionDiffusion(zoom: x4))'
            '.blendMode(tex: reactionDiffusion(zoom: x16))',
            [4, 16])

    def test_repeated_state_preserves_each_explicit_or_default_zoom(self):
        graph = build('reactionDiffusion(zoom: x4).blendMode(tex: reactionDiffusion())'
                      '.blendMode(tex: reactionDiffusion(zoom: x16)).write(o0)')
        nodes = instances(graph, 'reactionDiffusion', 'global_rd_state')
        self.assertEqual(len({node['texture'] for node in nodes}), 3)
        for index, (node, zoom) in enumerate(zip(nodes, [4, 8, 16])):
            sizing_param = state_width_param(graph, node['texture'])
            self.assertEqual([node['passes'][0]['uniforms'][sizing_param]], [zoom],
                             'instance %d must keep its own zoom' % index)

    def test_different_stateful_effects_size_from_their_own_zoom(self):
        for chain in ('reactionDiffusion(zoom: x4).blendMode(tex: cellularAutomata(zoom: x16)).write(o0)',
                      'perlin().blendMode(tex: reactionDiffusion(zoom: x4))'
                      '.blendMode(tex: cellularAutomata(zoom: x16)).write(o0)'):
            graph = build(chain)
            rd, = instances(graph, 'reactionDiffusion', 'global_rd_state')
            ca, = instances(graph, 'cellularAutomata', 'global_ca_state')
            self.assertEqual(rd['texture'], 'global_rd_state_chain_0')
            self.assertEqual(ca['texture'], 'global_ca_state_chain_0')
            rd_param = state_width_param(graph, rd['texture'])
            ca_param = state_width_param(graph, ca['texture'])
            self.assertNotEqual(rd_param, ca_param, 'size parameters must be distinct')
            self.assertEqual(graph['textures'][rd['texture']]['width'].get('screenDivide'), rd_param)
            self.assertEqual(graph['textures'][ca['texture']]['width'].get('screenDivide'), ca_param)

    def test_repeated_watercolor_instances_ping_pong_independently(self):
        graph = build('perlin().watercolor().watercolor().write(o0)')
        nodes = instances(graph, 'watercolor', 'global_wc_state')
        self.assertEqual(len(nodes), 2)
        self.assertNotEqual(nodes[0]['texture'], nodes[1]['texture'],
                            'state textures must be distinct')
        self.assertEqual(nodes[0]['texture'], 'global_wc_state_chain_0')
        self.assertEqual(nodes[1]['texture'], 'global_wc_state_chain_0_node_2')

    def test_loop_begin_and_loop_end_retain_their_shared_accumulator(self):
        for chain in ('perlin().loopBegin().loopEnd().write(o0)',
                      'perlin().loopBegin().loopEnd().loopBegin().loopEnd().write(o0)'):
            graph = build(chain)
            for pass_ in graph['passes']:
                if pass_.get('effectKey') == 'loopBegin':
                    self.assertEqual(pass_['inputs'].get('accumTex'), 'global_accum_chain_0')
                if pass_.get('effectKey') == 'loopEnd':
                    frag_color = pass_['outputs'].get('fragColor', '')
                    if frag_color.startswith('global_'):
                        self.assertEqual(frag_color, 'global_accum_chain_0')

    def test_mesh_loader_and_mesh_render_retain_their_shared_mesh_buffers(self):
        graph = build('meshLoader().meshRender().meshRender().write(o0)')
        loader = next(p for p in graph['passes'] if p.get('func') == 'meshLoader')
        renderers = [p for p in graph['passes']
                     if p.get('func') == 'meshRender' and 'meshPositions' in p['inputs']]
        self.assertEqual(len(renderers), 2)
        self.assertEqual(loader['inputs']['positionsTex'], 'global_mesh0_positions_chain_0')
        self.assertEqual(loader['inputs']['normalsTex'], 'global_mesh0_normals_chain_0')
        for renderer in renderers:
            self.assertEqual(renderer['inputs']['meshPositions'], loader['inputs']['positionsTex'])
            self.assertEqual(renderer['inputs']['meshNormals'], loader['inputs']['normalsTex'])

    def test_repeated_mesh_renderers_keep_external_buffers_across_chains(self):
        graph = compile_graph(
            "search synth, render\nmeshLoader().write(o0)\nread(o0).meshRender().meshRender().write(o1)\nrender(o0)",
            _REG)
        renderers = [p for p in graph['passes']
                     if p.get('func') == 'meshRender' and 'meshPositions' in p['inputs']]
        self.assertEqual(len(renderers), 2)
        for renderer in renderers:
            self.assertEqual(renderer['inputs']['meshPositions'], 'global_mesh0_positions_chain_1')
            self.assertEqual(renderer['inputs']['meshNormals'], 'global_mesh0_normals_chain_1')

    def test_single_instances_retain_their_existing_texture_ids(self):
        graph = compile_graph(
            "search synth, filter, render\nperlin().write(o0)\n"
            "reactionDiffusion(zoom: x4).watercolor().write(o1)\nrender(o0)",
            _REG)
        rd, = instances(graph, 'reactionDiffusion', 'global_rd_state')
        wc, = instances(graph, 'watercolor', 'global_wc_state')
        self.assertEqual(rd['texture'], 'global_rd_state_chain_1')
        self.assertEqual(wc['texture'], 'global_wc_state_chain_1')
        self.assertIn('global_rd_state_chain_1', graph['textures'])
        self.assertIn('global_wc_state_chain_1', graph['textures'])


if __name__ == '__main__':
    unittest.main()
