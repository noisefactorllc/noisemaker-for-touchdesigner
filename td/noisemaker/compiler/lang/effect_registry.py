"""effect_registry.py — loads effect definitions and exposes the op/spec/starter/namespace
tables the Validator and Expander need. Port of hlsl Compiler/Lang/EffectRegistry.cs
(reference/02 §10, reference/03 §3).

Effect definitions ship as JSON under td/noisemaker/effects/<ns>/<func>.json (generated from
shaders/effects/<ns>/<effect>/definition.js by tools/convert-definitions.mjs). The C# JsonValue
ceremony collapses to native Python `json` + insertion-ordered dicts. This class:
  1. Holds the EffectDefinition fields the Expander reads.
  2. Derives the op `args` list the Validator consumes (ordered over globals; `vec4`->`color`;
     choices with no enum synthesize `<ns>.<func>.<key>` and register as project enums).
  3. Tracks valid namespaces (builtin set) and starter ops (derived from pass inputs).
  4. Registers param aliases / effect aliases.

get_effect / get_op resolve the FULLY-QUALIFIED "<ns>.<func>" AND the bare func, mirroring the
reference registry's multi-key registration (canvas.js registerEffectWithRuntime).
"""
import os

from . import enums

# Builtin namespace IDs, reference order (shaders/src/runtime/tags.js _builtinDescriptors).
# FIXED bootstrap metadata — NOT derived from loaded effects: `io`/`user` carry no effects but
# ARE valid `search` namespaces (the blaster corpus searches `user`).
_BUILTIN_NAMESPACES = [
    'io', 'classicNoisedeck', 'synth', 'mixer', 'filter',
    'render', 'points', 'synth3d', 'filter3d', 'user',
]

# Pipeline inputs whose presence in a pass `inputs` value makes an effect a non-starter
# (reference scripts/generate-shader-manifest.mjs PIPELINE_INPUTS + agent surfaces).
_PIPELINE_INPUTS = frozenset([
    'inputTex', 'inputTex3d', 'inputXyz', 'inputVel', 'inputRgba',
    'o0', 'o1', 'o2', 'o3', 'o4', 'o5', 'o6', 'o7',
    'global_xyz0', 'global_vel0', 'global_rgba0',
])


class ParamDef:
    """The op param spec the Validator iterates (reference/02 §5.5)."""
    __slots__ = ('name', 'type', 'default', 'has_min', 'min', 'has_max', 'max',
                 'uniform', 'enum', 'enum_path', 'choices', 'default_from')

    def __init__(self):
        self.name = None
        self.type = None
        self.default = None
        self.has_min = False
        self.min = 0.0
        self.has_max = False
        self.max = 0.0
        self.uniform = None
        self.enum = None
        self.enum_path = None
        self.choices = None      # dict name->value, or None
        self.default_from = None


class OpSpec:
    __slots__ = ('name', 'op_name', 'args', 'effect')

    def __init__(self, name, op_name, effect):
        self.name = name        # bare func
        self.op_name = op_name  # "<ns>.<func>"
        self.args = []          # list[ParamDef]
        self.effect = effect


class EffectDefinition:
    """The structured effect fields the Expander consumes (reference/03 §3). `raw` keeps the
    full JSON dict so passes/textures/globals read with their exact insertion order."""
    __slots__ = ('name', 'namespace', 'func', 'starter', 'globals', 'passes', 'textures',
                 'textures3d', 'shaders', 'uniform_layout', 'uniform_layouts', 'external_texture',
                 'output_tex', 'output_tex3d', 'output_geo', 'output_xyz', 'output_vel',
                 'output_rgba', 'raw')

    def __init__(self):
        for s in self.__slots__:
            setattr(self, s, None)


def _str(obj, key):
    v = obj.get(key)
    return v if isinstance(v, str) else None


def _num(obj, key):
    v = obj.get(key)
    if isinstance(v, bool):
        return None
    return v if isinstance(v, (int, float)) else None


def _bool(obj, key):
    return obj.get(key) is True


def _parse_choices(choices):
    """{name: number} dict; skip keys ending ':' (UI separators) and non-numeric values."""
    if not isinstance(choices, dict):
        return None
    out = {}
    for k, v in choices.items():
        if k.endswith(':'):
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out[k] = v
    return out


class EffectRegistry:
    def __init__(self):
        self._ops = {}
        self._effects = {}
        self._starter_ops = set()
        self._namespaces = list(_BUILTIN_NAMESPACES)
        self._ns_set = set(_BUILTIN_NAMESPACES)
        self._effect_aliases = {}        # "<ns>.<func>" -> replacement name
        self._param_aliases = {}         # opName -> ordered dict {oldParam: newParam}

    # --- public API -----------------------------------------------------

    @property
    def namespaces(self):
        return self._namespaces

    def is_valid_namespace(self, ns):
        return ns in self._ns_set

    def register_namespace(self, ns):
        if ns not in self._ns_set:
            self._ns_set.add(ns)
            self._namespaces.append(ns)

    def get_op(self, op_name):
        return self._ops.get(op_name)

    def get_effect(self, name):
        return self._effects.get(name)

    def is_starter_op(self, name):
        # reference/02 §9 isStarterOp.
        if name is None:
            return False
        if name == 'particles' or name == 'render.particles':
            return False  # hard override
        if name in self._starter_ops:
            return True
        parts = name.split('.')
        if len(parts) > 1:
            canonical = parts[-1]
            if canonical in self._starter_ops:
                for op in self._starter_ops:
                    if op.endswith('.' + canonical):
                        return False
                return True
        return False

    def check_effect_alias(self, op_name):
        # reference/01 §8.4.
        new_name = self._effect_aliases.get(op_name)
        if new_name is None:
            return None
        old_name = op_name[op_name.rfind('.') + 1:] if '.' in op_name else op_name
        return ("effect '" + old_name + "' is deprecated, use '" + new_name +
                "' instead. Aliases will be removed on 2026-09-01.")

    def resolve_param_aliases(self, op_name, kwargs):
        # reference/01 §8.5 — mutates kwargs in place; returns warnings.
        warnings = []
        aliases = self._param_aliases.get(op_name)
        if aliases is None:
            return warnings
        for old_name in list(aliases.keys()):
            if old_name not in kwargs:
                continue
            new_name = aliases[old_name]
            if new_name not in kwargs:
                kwargs[new_name] = kwargs[old_name]
            del kwargs[old_name]
            warnings.append("param '" + old_name + "' is deprecated, use '" + new_name +
                            "' instead. Aliases will be removed on 2026-09-01.")
        return warnings

    # --- loading --------------------------------------------------------

    @staticmethod
    def default_effects_root():
        return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'effects'))

    @classmethod
    def load_from_directory(cls, effects_root=None):
        import json
        reg = cls()
        if effects_root is None:
            effects_root = cls.default_effects_root()
        if not os.path.isdir(effects_root):
            return reg
        files = []
        for dirpath, _dirs, names in os.walk(effects_root):
            for nm in names:
                if nm.endswith('.json'):
                    files.append(os.path.join(dirpath, nm))
        files.sort()  # deterministic (ordinal) registration order
        for f in files:
            with open(f) as fh:
                reg.register(json.load(fh))
        return reg

    def register(self, definition):
        if not isinstance(definition, dict):
            return

        e = EffectDefinition()
        e.name = _str(definition, 'name')
        e.namespace = _str(definition, 'namespace')
        e.func = _str(definition, 'func')
        e.starter = self._derive_starter(definition)
        e.globals = definition.get('globals')
        e.passes = definition.get('passes')
        e.textures = definition.get('textures')
        e.textures3d = definition.get('textures3d')
        e.shaders = definition.get('shaders')
        e.uniform_layout = definition.get('uniformLayout')
        e.uniform_layouts = definition.get('uniformLayouts')
        e.external_texture = _str(definition, 'externalTexture')
        e.output_tex = _str(definition, 'outputTex')
        e.output_tex3d = _str(definition, 'outputTex3d')
        e.output_geo = _str(definition, 'outputGeo')
        e.output_xyz = _str(definition, 'outputXyz')
        e.output_vel = _str(definition, 'outputVel')
        e.output_rgba = _str(definition, 'outputRgba')
        e.raw = definition

        ns = e.namespace
        func = e.func
        if not func:
            return
        if ns:
            self.register_namespace(ns)

        # Multi-key effect registration (canvas.js registerEffectWithRuntime).
        self._effects[func] = e
        if ns:
            self._effects[ns + '.' + func] = e
            self._effects[ns + '.' + e.name] = e

        # Build the op spec exactly like registerEffectWithRuntime.
        spec = OpSpec(func, (ns + '.' + func) if ns else func, e)
        globals_ = e.globals
        if isinstance(globals_, dict):
            for key, g in globals_.items():
                gtype = _str(g, 'type')
                enum_path = _str(g, 'enum')
                if enum_path is None:
                    enum_path = _str(g, 'enumPath')

                choices = _parse_choices(g.get('choices'))
                if choices and enum_path is None and ns is not None:
                    # choices with no explicit enum: synthesize an enum path and register the
                    # choices as project enums (canvas.js parity).
                    enum_path = ns + '.' + func + '.' + key
                    for cname, cval in choices.items():
                        enums.register_choice([ns, func, key, cname], cval)

                pd = ParamDef()
                pd.name = key
                pd.type = 'color' if gtype == 'vec4' else gtype  # vec4->color is the ONLY rewrite
                pd.default = g.get('default')
                pd.uniform = _str(g, 'uniform')
                pd.enum = enum_path
                pd.enum_path = enum_path
                pd.choices = choices
                pd.default_from = _str(g, 'defaultFrom')
                mn = _num(g, 'min')
                mx = _num(g, 'max')
                if mn is not None:
                    pd.has_min = True
                    pd.min = mn
                if mx is not None:
                    pd.has_max = True
                    pd.max = mx
                spec.args.append(pd)

        if ns is not None:
            self._ops[ns + '.' + func] = spec
            if func not in self._ops:
                self._ops[func] = spec  # bare resolution fallback
        else:
            self._ops[func] = spec

        # Starter flag (derived): register bare + namespaced.
        if e.starter:
            self._starter_ops.add(func)
            if ns is not None:
                self._starter_ops.add(ns + '.' + func)

        # paramAliases: { oldParam: newParam }
        pa = definition.get('paramAliases')
        if isinstance(pa, dict) and ns is not None:
            amap = {}
            for k, v in pa.items():
                if isinstance(v, str):
                    amap[k] = v
            if amap:
                self._param_aliases[ns + '.' + func] = amap

        # deprecatedBy + hidden -> effect alias (reference/01 §8.4).
        deprecated_by = _str(definition, 'deprecatedBy')
        if _bool(definition, 'hidden') and deprecated_by is not None and ns is not None:
            self._effect_aliases[ns + '.' + func] = deprecated_by

    # --- starter derivation ---------------------------------------------

    @staticmethod
    def _derive_starter(definition):
        # Starter iff NO pass `inputs` value is a pipeline input; a pass-less effect is a starter
        # (reference canvas.js isStarterEffect). The explicit `starter` flag is ignored.
        return not EffectRegistry._reads_pipeline_input(definition)

    @staticmethod
    def _reads_pipeline_input(definition):
        passes = definition.get('passes')
        if not isinstance(passes, list):
            return False  # no passes => starter
        for p in passes:
            if not isinstance(p, dict):
                continue
            inputs = p.get('inputs')
            if not isinstance(inputs, dict):
                continue
            for v in inputs.values():
                if isinstance(v, str) and v in _PIPELINE_INPUTS:
                    return True
        return False
