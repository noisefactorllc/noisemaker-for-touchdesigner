"""dim.py — texture dimension parse / scope. Port of the Dim handling in hlsl
Compiler/Graph/{Dim,GraphLoader}.cs + Expander.ScopeDimSpec (reference/03 §2.4, §6).

A dimension is kept as its native JSON value (the compiler only parses, scopes, and re-emits
it — it never resolves to pixels):
    number | "screen"/"auto"/<literal> | "N%" | {param,...} | {screenDivide,...} | {scale,...}
This matches the reference's parse+re-emit identity for canonical forms; the only transform the
expander applies is param/screenDivide name-scoping.
"""


def parse_dim(v):
    """Identity for the compiler (None stays None). The texture-spec default 'screen' for an
    absent width/height is applied by the caller (mirrors compiler.js extractTextureSpecs)."""
    return v


def dim_references_param(d):
    """reference/03 §6.3 — a {param} or {screenDivide} dim carries a scopable param name."""
    return isinstance(d, dict) and ('param' in d or 'screenDivide' in d)


def scope_dim(d, scope_suffix, scoped_map):
    """Rewrite a {param}/{screenDivide} dim to a scoped param name and record old->new in
    scoped_map (reference/03 §6.3 ScopeDimSpec). Other dims pass through unchanged."""
    if not isinstance(d, dict):
        return d
    if 'param' in d:
        scoped = d['param'] + '_' + scope_suffix
        scoped_map[d['param']] = scoped
        nd = dict(d)
        nd['param'] = scoped
        return nd
    if 'screenDivide' in d:
        scoped = d['screenDivide'] + '_' + scope_suffix
        scoped_map[d['screenDivide']] = scoped
        nd = dict(d)
        nd['screenDivide'] = scoped
        return nd
    return d
