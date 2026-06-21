"""Render-graph model + assembly. Port of hlsl Compiler/Graph/.

The C# typed model (OrderedMap / Pass / Program / TextureSpec / UniformValue / Dim /
RenderGraph) collapses to native Python dicts + values here (Python dicts are insertion-ordered;
`json` handles serialization), the same way the validator's Plan/Step did. Substance that
survives: dim parse/scope (dim.py), liveness pooling (resources.py), graph assembly +
normalization (render_graph.py).
"""
