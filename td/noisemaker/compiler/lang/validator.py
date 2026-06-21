"""validator.py — semantic analysis: AST -> flattened plans. Port of hlsl Compiler/Lang/Validator.cs
(shaders/src/lang/validator.js, reference/02).

Produces `{plans, diagnostics, render, searchNamespaces}` where each plan is
`{chain:[step], write, write3d, final, states}` and each step is
`{op, args, from, temp[, builtin]}`. Step args are NATIVE values (number / bool / [r,g,b] /
{kind,name} surface / oscillator config) — the C# ArgValue/StepArgs/JsonValue ceremony collapses
to Python dicts; Clone is copy.deepcopy (the reference's JSON deep-clone).

PARITY-CRITICAL behaviors replicated (reference/02):
  - GLOBAL monotonic tempIndex across all plans; the effect step's temp is allocated AFTER arg
    resolution (which may recurse into process_chain for inline surface subchains) — H1.
  - Op-name resolution is FIRST-MATCH over [explicit-resolved, ...searchOrder] — §5.2 H8.
  - clamp via double comparisons; S002 warns; out-of-range silently clamped — §2.1 H13.
  - member resolution falls back to 0 — §6.6 H14.
  - args keyed by def.name (DSL name), NOT uniform — H9.
  - errors are collected, not thrown, except missing-search — §1.2 H11.

Unimplemented paths raise UnsupportedDsl (mirrors hlsl NotImplementedException) — FAIL LOUDLY:
  if/elif/else, break/continue/return, midi/audio automation args, Func, state-value args.
"""
import copy

from . import enum_paths
from . import enums
from .ast import NodeKind as K


class UnsupportedDsl(Exception):
    """A DSL feature not implemented in this first-cut frontend. Never silently wrong."""


_STATE_SURFACES = frozenset(['time', 'frame', 'mouse', 'resolution', 'seed', 'a'])
_STATE_VALUES = frozenset([
    'time', 'frame', 'mouse', 'resolution', 'seed', 'a', 'u1', 'u2', 'u3', 'u4',
    's1', 's2', 'b1', 'b2', 'a1', 'a2', 'deltaTime',
])
_ALLOWED_STRING_PARAMS = frozenset(['text.text', 'text.font', 'text.justify'])
_SURFACE_PASSTHROUGH_CALLS = frozenset(['read'])

from . import diagnostics as _diag  # noqa: E402


def validate(ast, registry):
    return _Validator(registry)._run(ast)


class _Validator:
    def __init__(self, reg):
        self._reg = reg
        self._diagnostics = []
        self._symbols = {}
        self._search_order = None
        self._temp_index = 0

    def _run(self, ast):
        render = ast['render']['name'] if ast.get('render') else None
        ns_meta = ast.get('namespace')
        self._search_order = ns_meta.get('searchOrder') if ns_meta else None
        if not self._search_order:
            raise Exception("Missing required 'search' directive. Every program must start with "
                            "'search <namespace>, ...' to specify namespace search order.")

        self._process_vars(ast.get('vars'))

        plans = []
        for stmt in (ast.get('plans') or []):
            p = self._compile_stmt(stmt)
            if p is not None:
                plans.append(p)

        return {
            'plans': plans,
            'diagnostics': self._diagnostics,
            'render': render,
            'searchNamespaces': list(self._search_order),
        }

    # --- diagnostics ----------------------------------------------------

    def _push_diag(self, code, node, message=None):
        if message is None:
            message = _diag.default_message(code)
        ident_name = self._extract_identifier_name(node)
        enriched = message
        if ident_name is not None and ident_name not in message and "'" not in message:
            enriched = message + ": '" + ident_name + "'"
        d = {'code': code, 'message': enriched, 'severity': _diag.severity(code),
             'identifier': ident_name}
        if node is not None and isinstance(node, dict) and node.get('loc'):
            d['line'] = node['loc'].get('line')
            d['column'] = node['loc'].get('col')
        self._diagnostics.append(d)

    @staticmethod
    def _extract_identifier_name(node):
        if node is None or not isinstance(node, dict):
            return None
        t = node.get('type')
        if t == K.Ident:
            return node['name']
        if t == K.Member:
            return ".".join(node['path'])
        if t == K.Call:
            return node['name']
        if t == K.Func and node.get('src') is not None:
            s = node['src']
            return "{" + s[:30] + ("..." if len(s) > 30 else "") + "}"
        return "[" + str(t) + "]"

    # --- vars / symbols (reference/02 §3) -------------------------------

    def _process_vars(self, vars_):
        if not vars_:
            return
        for v in vars_:
            expr = self._substitute(copy.deepcopy(v['expr']))
            if expr is not None and self._is_starter_chain(expr):
                head = self._first_chain_call(expr)
                if head is not None:
                    self._push_diag("S006", head)
            if expr is None or (expr.get('type') == K.Ident and expr['name'] in ('null', 'undefined')):
                self._push_diag("S004", v)
                continue
            if (expr.get('type') == K.Ident and expr['name'] not in self._symbols
                    and expr['name'] not in _STATE_VALUES
                    and self._reg.get_op(expr['name']) is None
                    and not self._can_resolve_op_name(expr['name'])):
                self._push_diag("S003", expr)
                continue
            if expr.get('type') == K.Chain and len(expr['chain']) == 1:
                self._symbols[v['name']] = expr['chain'][0]
            elif expr.get('type') == K.Member:
                resolved = self._resolve_enum_number(expr['path'])
                if resolved is not None:
                    self._symbols[v['name']] = enums.leaf(resolved)  # {type:'Number',value}
                else:
                    self._symbols[v['name']] = expr
            else:
                self._symbols[v['name']] = expr

    # --- enum resolution (reference/02 §2.5) ----------------------------

    def _resolve_enum_number(self, path):
        """Numeric value of a path, or None. Precedence: symbols > project > std (H3)."""
        if not path:
            return None
        head = path[0]
        if head in self._symbols:
            sym = self._symbols[head]
            if len(path) == 1:
                if sym.get('type') == K.Number:
                    return sym['value']
                if sym.get('type') == K.Boolean:
                    return 1 if sym['value'] else 0
                return None
            return None
        node = enums.try_get_head(head)
        if node is None:
            return None
        for i in range(1, len(path)):
            if node is None or enums.is_leaf(node):
                return None
            node = node.get(path[i])
            if node is None:
                return None
        return node['value'] if (node is not None and enums.is_leaf(node)) else None

    def _can_resolve_op_name(self, name):
        for ns in self._search_order:
            if self._reg.get_op(ns + "." + name) is not None:
                return True
        return False

    # --- substitute (reference/02 §2.10) --------------------------------

    def _substitute(self, node):
        if node is None:
            return None
        t = node.get('type')
        if t == K.Ident and node['name'] in self._symbols:
            result = self._substitute(copy.deepcopy(self._symbols[node['name']]))
            if result is not None:
                self._set_var_ref(result, node['name'])
            return result
        if t == K.Chain:
            new_chain = []
            for e in node['chain']:
                if e.get('type') == K.Call:
                    mapped = {'type': K.Call, 'name': e['name'],
                              'args': [self._substitute(a) for a in e['args']]}
                    if e.get('kwargs') is not None:
                        mapped['kwargs'] = {k: self._substitute(val) for k, val in e['kwargs'].items()}
                    new_chain.append(self._resolve_call(mapped))
                else:
                    new_chain.append(e)
            return {'type': K.Chain, 'chain': new_chain}
        if t == K.Call:
            mapped = {'type': K.Call, 'name': node['name'],
                      'args': [self._substitute(a) for a in node['args']]}
            if node.get('namespace') is not None:
                mapped['namespace'] = node['namespace']
            if node.get('kwargs') is not None:
                mapped['kwargs'] = {k: self._substitute(val) for k, val in node['kwargs'].items()}
            return self._resolve_call(mapped)
        return node

    @staticmethod
    def _set_var_ref(n, name):
        if n.get('type') in (K.Number, K.Ident, K.Member, K.Oscillator, K.Midi, K.Audio):
            n['varRef'] = name

    def _resolve_call(self, call):
        name = call['name']
        if name in self._symbols:
            val = self._symbols[name]
            vt = val.get('type')
            if vt == K.Ident:
                out = {'type': K.Call, 'name': val['name'], 'args': call['args']}
                if call.get('kwargs') is not None:
                    out['kwargs'] = call['kwargs']
                if call.get('namespace') is not None:
                    out['namespace'] = call['namespace']
                return out
            if vt == K.Call:
                merged_args = list(val.get('args') or [])
                if call.get('args'):
                    merged_args.extend(call['args'])  # APPEND (H5)
                merged_kw = None
                if val.get('kwargs') is not None:
                    merged_kw = dict(val['kwargs'])
                if call.get('kwargs') is not None:
                    if merged_kw is None:
                        merged_kw = {}
                    merged_kw.update(call['kwargs'])  # call-site wins
                merged = {'type': K.Call, 'name': val['name'], 'args': merged_args}
                if merged_kw is not None:
                    merged['kwargs'] = merged_kw
                nsv = call.get('namespace') or val.get('namespace')
                if nsv is not None:
                    merged['namespace'] = nsv
                return merged
        return call

    # --- starter helpers (reference/02 §2.9) ----------------------------

    @staticmethod
    def _first_chain_call(node):
        if node.get('type') == K.Call:
            return node
        if node.get('type') == K.Chain and node['chain'] and node['chain'][0].get('type') == K.Call:
            return node['chain'][0]
        return None

    def _is_starter_chain(self, node):
        if node.get('type') != K.Chain:
            return False
        info = self._get_starter_info(node)
        return info is not None and info[1] == 0

    def _get_starter_info(self, node):
        """(call, index) of the first starter op in the chain, or None."""
        t = node.get('type')
        if t == K.Call:
            name = node['name']
            ns = node.get('namespace')
            if ns is not None and ns.get('resolved') is not None:
                name = ns['resolved'] + "." + node['name']
            return (node, 0) if self._reg.is_starter_op(name) else None
        if t == K.Chain:
            for i, entry in enumerate(node['chain']):
                if entry.get('type') == K.Call:
                    name = entry['name']
                    ns = entry.get('namespace')
                    if ns is not None and ns.get('resolved') is not None:
                        name = ns['resolved'] + "." + entry['name']
                    if self._reg.is_starter_op(name):
                        return (entry, i)
        return None

    # --- statement compilation (reference/02 §4) ------------------------

    def _compile_stmt(self, stmt):
        t = stmt.get('type')
        if t == K.IfStmt:
            raise UnsupportedDsl("if/elif/else branches are not implemented in the first-cut DSL "
                                 "frontend (reference/02 §4.1).")
        if t in (K.Break, K.Continue, K.Return):
            raise UnsupportedDsl("break/continue/return are not implemented in the first-cut DSL "
                                 "frontend (reference/02 §4).")
        if t is None and 'chain' in stmt:  # chain-statement wrapper (no `type`)
            return self._compile_chain_statement(stmt)
        return None

    def _compile_chain_statement(self, stmt):
        chain = []
        chain_node = {'type': K.Chain, 'chain': stmt['chain']}
        has_write = stmt.get('write') is not None or stmt.get('write3d') is not None

        if not has_write and self._is_starter_chain(chain_node):
            self._push_diag("S006", stmt['chain'][0] if stmt['chain'] else stmt)
        if not has_write:
            self._push_diag("S001", stmt['chain'][0] if stmt['chain'] else stmt,
                            "Chain must have explicit write() or write3d() target")
            return None

        write3d_tex3d = None
        write3d_geo = None
        if stmt.get('write3d') is not None:
            write3d_tex3d = {'kind': 'vol', 'name': self._surface_name(stmt['write3d']['tex3d'])}
            write3d_geo = {'kind': 'geo', 'name': self._surface_name(stmt['write3d']['geo'])}

        w = stmt.get('write')
        write_name = w['name'] if w is not None else None

        final_index = self._process_chain(chain, stmt['chain'], None, False, write_name)

        write_surf = None
        if w is not None:
            write_surf = {'kind': 'output', 'name': w['name']}

        return {'chain': chain, 'write': write_surf,
                'write3d': ({'tex3d': write3d_tex3d, 'geo': write3d_geo}
                            if stmt.get('write3d') is not None else None),
                'final': final_index, 'states': []}

    # --- chain flattening (reference/02 §5) -----------------------------

    def _process_chain(self, chain, calls, input_, allow_starterless, write_name):
        current = input_
        for original in calls:
            t = original.get('type')

            # read() builtin (reference/02 §5.1)
            if t == K.Read:
                if current is not None:
                    self._push_diag("S001", original, "read() is a starter node and cannot be chained "
                                    "inline. Use standalone read() to start a new chain.")
                    continue
                surface = self._to_surface(original.get('surface'))
                if surface is None:
                    self._push_diag("S001", original, "read() requires a valid surface reference")
                    continue
                rd_idx = self._temp_index
                self._temp_index += 1
                rd_args = {'tex': surface}
                if original.get('_skip'):
                    rd_args['_skip'] = True
                chain.append(self._step('_read', rd_args, None, rd_idx, builtin=True,
                                        comments=original.get('leadingComments')))
                current = rd_idx
                continue

            # read3d two-arg starter (reference/02 §5.1)
            if t == K.Read3D and original.get('geo') is not None:
                if current is not None:
                    self._push_diag("S001", original, "read3d() is a starter node and cannot be chained "
                                    "inline. Use standalone read3d() to start a new chain.")
                    continue
                tex3d = self._make_3d_ref(original.get('tex3d'), 'vol', K.VolRef)
                geo = self._make_3d_ref(original.get('geo'), 'geo', K.GeoRef)
                if tex3d is None or geo is None:
                    self._push_diag("S001", original, "read3d() as starter requires tex3d and geo references")
                    continue
                rd3_idx = self._temp_index
                self._temp_index += 1
                rd3_args = {'tex3d': tex3d, 'geo': geo}
                if original.get('_skip'):
                    rd3_args['_skip'] = True
                chain.append(self._step('_read3d', rd3_args, None, rd3_idx, builtin=True,
                                        comments=original.get('leadingComments')))
                current = rd3_idx
                continue

            # write() builtin (reference/02 §5.1)
            if t == K.Write:
                surface = self._to_surface(original['surface'])
                if surface is None:
                    self._push_diag("S001", original, "write() requires a valid surface reference")
                    continue
                if current is None:
                    self._push_diag("S005", original, "write() requires an input - cannot be first in chain")
                    continue
                wr_idx = self._temp_index
                self._temp_index += 1
                chain.append(self._step('_write', {'tex': surface}, current, wr_idx, builtin=True,
                                        comments=original.get('leadingComments')))
                current = wr_idx
                continue

            # write3d() chain node (reference/02 §5.1)
            if t == K.Write3D:
                tex3d = self._make_3d_ref(original['tex3d'], 'vol', K.VolRef)
                geo = self._make_3d_ref(original['geo'], 'geo', K.GeoRef)
                if tex3d is None or geo is None:
                    self._push_diag("S001", original, "write3d() requires tex3d and geo references")
                    continue
                if current is None:
                    self._push_diag("S005", original, "write3d() requires an input - cannot be first in chain")
                    continue
                wr3_idx = self._temp_index
                self._temp_index += 1
                chain.append(self._step('_write3d', {'tex3d': tex3d, 'geo': geo}, current, wr3_idx,
                                        builtin=True, comments=original.get('leadingComments')))
                current = wr3_idx
                continue

            # subchain / DSL loop bracket (reference/02 §5.1)
            if t == K.Subchain:
                if current is None:
                    self._push_diag("S005", original, "subchain() requires an input - cannot be first in chain")
                    continue
                iters = original.get('iterations') or 1

                begin_idx = self._temp_index
                self._temp_index += 1
                begin_args = {}
                if original.get('name') is not None:
                    begin_args['name'] = original['name']
                if original.get('id') is not None:
                    begin_args['id'] = original['id']
                if iters > 1:
                    begin_args['iterations'] = float(iters)
                chain.append(self._step('_subchain_begin', begin_args, current, begin_idx,
                                        builtin=True, comments=original.get('leadingComments')))
                current = begin_idx

                current = self._process_chain(chain, original['body'], current, False, write_name)

                end_idx = self._temp_index
                self._temp_index += 1
                end_args = {}
                if original.get('name') is not None:
                    end_args['name'] = original['name']
                if original.get('id') is not None:
                    end_args['id'] = original['id']
                if iters > 1:
                    end_args['iterations'] = float(iters)
                chain.append(self._step('_subchain_end', end_args, current, end_idx, builtin=True))
                current = end_idx
                continue

            # effect call (reference/02 §5.2)
            call = self._resolve_call(copy.deepcopy(original))

            ns = call.get('namespace')
            search_order = ns['searchOrder'] if (ns is not None and ns.get('searchOrder')) else self._search_order
            candidates = []
            if ns is not None and ns.get('resolved') is not None:
                candidates.append(ns['resolved'] + "." + call['name'])
            for nsx in search_order:
                candidates.append(nsx + "." + call['name'])
            op_name = None
            spec = None
            for cand in candidates:
                s = self._reg.get_op(cand)
                if s is not None:
                    op_name = cand
                    spec = s
                    break
            if spec is None:
                self._push_diag("S001", original, "Unknown effect: '" + call['name'] + "'")
                continue

            alias_warning = self._reg.check_effect_alias(op_name)
            if alias_warning is not None:
                self._push_diag("S008", original, alias_warning)

            if op_name == "prev":
                idxp = self._temp_index
                self._temp_index += 1
                argsp = {'tex': {'kind': 'output', 'name': write_name}}
                chain.append(self._step(op_name, argsp, current, idxp,
                                        comments=original.get('leadingComments')))
                current = idxp
                continue

            is_starter = self._reg.is_starter_op(op_name)
            starterless_root = current is None
            allow_passthrough_root = allow_starterless and op_name in _SURFACE_PASSTHROUGH_CALLS
            if starterless_root and not is_starter and not allow_passthrough_root:
                self._push_diag("S005", original)
                continue
            starter_has_input = is_starter and current is not None
            from_input = None if starter_has_input else current
            if starter_has_input:
                self._push_diag("S005", original)

            args = {}
            self._resolve_args(chain, spec, call, op_name, original, args, write_name)

            idx = self._temp_index
            self._temp_index += 1
            chain.append(self._step(op_name, args, from_input, idx,
                                    comments=original.get('leadingComments')))
            current = idx
        return current

    @staticmethod
    def _step(op, args, from_, temp, builtin=False, comments=None):
        s = {'op': op, 'args': args, 'from': from_, 'temp': temp}
        if builtin:
            s['builtin'] = True
        return s

    # --- argument resolution (reference/02 §6) --------------------------

    def _resolve_args(self, chain, spec, call, op_name, original, args, write_name):
        kw = call.get('kwargs')
        if kw is not None:
            warnings = self._reg.resolve_param_aliases(op_name, kw)
            for w in warnings:
                self._push_diag("S007", call, w)
        seen = set()
        spec_args = spec.args

        i = 0
        while i < len(spec_args):
            d = spec_args[i]
            if kw is not None and d.name in kw:
                node = kw[d.name]
            elif i < len(call['args']):
                node = call['args'][i]
            else:
                node = None
            node = self._substitute(node)
            arg_key = d.name

            # color-splat special case (reference/02 §6)
            if (kw is None and node is not None and node.get('type') == K.Color and d.type != "color"
                    and d.name == "r" and i + 2 < len(spec_args)
                    and spec_args[i + 1].name == "g" and spec_args[i + 2].name == "b"):
                args["r"] = node['value'][0]
                args[spec_args[i + 1].name] = node['value'][1]
                args[spec_args[i + 2].name] = node['value'][2]
                i += 3
                continue
            if kw is not None and d.name in kw:
                seen.add(d.name)

            # array literal (reference/02 §6)
            if node is not None and node.get('type') == K.ArrayLiteral:
                value = []
                for el in node['elements']:
                    if el.get('type') == K.Number:
                        value.append(el['value'])
                    else:
                        self._push_diag("S002", el, "Array element must be a number for '" + d.name
                                        + "' in " + call['name'] + "()")
                        value.append(0)
                args[arg_key] = value
                i += 1
                continue

            ty = d.type
            if ty == "surface":
                self._resolve_surface_arg(chain, d, node, call, args, arg_key, write_name)
            elif ty == "color":
                self._resolve_color_arg(d, node, call, args, arg_key)
            elif ty == "vec3":
                self._resolve_vec_arg(d, node, call, args, arg_key, 3)
            elif ty == "vec4":
                self._resolve_vec_arg(d, node, call, args, arg_key, 4)
            elif ty == "boolean":
                self._resolve_boolean_arg(d, node, call, args, arg_key)
            elif ty == "member":
                self._resolve_member_arg(d, node, call, args, arg_key)
            elif ty == "volume":
                self._resolve_volume_arg(d, node, call, args, arg_key, "vol", "vol")
            elif ty == "geometry":
                self._resolve_volume_arg(d, node, call, args, arg_key, "geo", "geo")
            elif ty == "string":
                self._resolve_string_arg(d, node, op_name, original, call, args, arg_key)
            else:
                self._resolve_numeric_arg(d, node, call, args, arg_key)
            i += 1

        # _skip meta-arg (reference/02 §6.14)
        if kw is not None and "_skip" in kw:
            skip_node = kw["_skip"]
            args["_skip"] = (skip_node.get('type') == K.Boolean and skip_node.get('value') is True)
            seen.add("_skip")
        # unknown-kwarg sweep (reference/02 §6.14)
        if kw is not None:
            for key in kw:
                if key not in seen:
                    self._push_diag("S001", kw[key], "Unknown argument '" + key + "' for " + call['name'] + "()")

    # 6.1 surface
    def _resolve_surface_arg(self, chain, d, node, call, args, arg_key, write_name):
        if node is not None and node.get('type') == K.String:
            self._push_diag("S001", node, "String literal not allowed for surface parameter '" + d.name + "'")
            dflt = self._to_surface({'type': K.Ident, 'name': d.default}) if isinstance(d.default, str) else None
            args[arg_key] = dflt
            return
        surf = None
        invalid_starter_chain = False
        starter = self._get_starter_info(node) if node is not None else None

        if node is not None and node.get('type') == K.Read and node.get('surface') is not None:
            surf = self._to_surface(node['surface'])
        inline = surf if surf is not None else self._call_to_surface(node)
        if inline is not None:
            surf = inline
        elif node is not None and node.get('type') == K.Chain:
            idx = self._process_chain(chain, node['chain'], None, True, write_name)
            if idx is not None:
                surf = {'kind': 'temp', 'index': idx}
        elif node is not None and node.get('type') == K.Call:
            idx = self._process_chain(chain, [node], None, True, write_name)
            if idx is not None:
                surf = {'kind': 'temp', 'index': idx}
        elif starter is not None:
            self._push_diag("S005", starter[0])
            invalid_starter_chain = True
        else:
            surf = self._to_surface(node)

        if surf is None:
            if invalid_starter_chain:
                args[arg_key] = None
                return
            has_default = isinstance(d.default, str)
            if not has_default:
                if node is None:
                    self._push_diag("S001", call, "Missing required surface argument '" + d.name
                                    + "' for " + call['name'] + "()")
                elif node.get('type') == K.Ident and node['name'] not in self._symbols:
                    self._push_diag("S003", node, "Undefined variable '" + node['name'] + "' for '"
                                    + d.name + "' in " + call['name'] + "()")
                else:
                    self._push_diag("S001", node, "Invalid surface reference for '" + d.name + "' in "
                                    + call['name'] + "()")
            else:
                surf = (self._to_surface({'type': K.Ident, 'name': d.default})
                        or {'kind': 'pipeline', 'name': d.default})
        args[arg_key] = surf

    # 6.2 color
    def _resolve_color_arg(self, d, node, call, args, arg_key):
        if node is not None and node.get('type') == K.String:
            self._push_diag("S001", node, "String literal not allowed for color parameter '" + d.name + "'")
            args[arg_key] = self._default_arg(d)
            return
        if node is not None and node.get('type') == K.Color:
            args[arg_key] = list(node['value'])
            return
        if node is not None and node.get('type') != K.Ident:
            self._push_diag("S002", node, "Argument out of range for '" + d.name + "' in " + call['name'] + "()")
        args[arg_key] = self._default_arg(d)

    # 6.3 / 6.4 vec3 / vec4
    def _resolve_vec_arg(self, d, node, call, args, arg_key, n):
        vec_name = "vec3" if n == 3 else "vec4"
        fallback = [0, 0, 0] if n == 3 else [0, 0, 0, 1]
        if node is not None and node.get('type') == K.String:
            self._push_diag("S001", node, "String literal not allowed for " + vec_name + " parameter '" + d.name + "'")
            args[arg_key] = self._default_arg(d, fallback)
            return
        if node is not None and node.get('type') == K.Call and node['name'] == vec_name and len(node['args']) == n:
            value = []
            for a in node['args']:
                if a.get('type') == K.Number:
                    value.append(a['value'])
                else:
                    self._push_diag("S002", a, "Argument out of range for '" + d.name + "' in " + call['name'] + "()")
                    value.append(0)
            args[arg_key] = value
            return
        if node is not None and node.get('type') == K.Color:
            args[arg_key] = [node['value'][k] for k in range(n)]
            return
        if node is not None and node.get('type') != K.Ident:
            self._push_diag("S002", node, "Argument out of range for '" + d.name + "' in " + call['name'] + "()")
        args[arg_key] = self._default_arg(d, fallback)

    # 6.5 boolean
    def _resolve_boolean_arg(self, d, node, call, args, arg_key):
        if node is None:
            args[arg_key] = self._default_bool(d)
            return
        t = node.get('type')
        if t == K.String:
            self._push_diag("S001", node, "String literal not allowed for boolean parameter '" + d.name + "'")
            args[arg_key] = self._default_bool(d)
            return
        if t == K.Boolean:
            args[arg_key] = node['value']
            return
        if t == K.Number:
            args[arg_key] = node['value'] != 0
            return
        if t == K.Func:
            raise UnsupportedDsl("Func boolean params ((state)=>...) are not implemented in the first-cut "
                                 "DSL frontend (reference/02 §6.5).")
        if t == K.Ident and node['name'] in _STATE_VALUES:
            raise UnsupportedDsl("state-value boolean params are not implemented in the first-cut DSL "
                                 "frontend (reference/02 §6.5).")
        if t == K.Ident and node['name'] not in _STATE_VALUES:
            self._push_diag("S003", node)
        elif t != K.Ident:
            self._push_diag("S002", node, "Argument out of range for '" + d.name + "' in " + call['name'] + "()")
        args[arg_key] = self._default_bool(d)

    # 6.6 member (enum-typed) -> NUMBER; falls back to 0 (H14)
    def _resolve_member_arg(self, d, node, call, args, arg_key):
        if node is not None and node.get('type') == K.String:
            self._push_diag("S001", node, "String literal not allowed for member/enum parameter '" + d.name + "'")
            args[arg_key] = self._default_arg(d)
            return
        prefix = enum_paths.normalize_member_path(d.enum_path or d.enum)
        path = None
        if node is not None:
            t = node.get('type')
            if t == K.Member:
                path = enum_paths.normalize_member_path(node['path'])
            elif t == K.Number:
                args[arg_key] = node['value']
                return
            elif t == K.Boolean:
                args[arg_key] = 1 if node['value'] else 0
                return
            elif t == K.Ident and node['name'] in _STATE_VALUES:
                raise UnsupportedDsl("state-value member params are not implemented in the first-cut DSL "
                                     "frontend (reference/02 §6.6).")
            elif t == K.Ident:
                path = [node['name']]

        if path is None:
            path = enum_paths.normalize_member_path(self._default_string(d))

        resolved = self._resolve_enum_number(path) if path is not None else None
        if resolved is None:
            path = enum_paths.apply_enum_prefix(path or [], prefix)
            if prefix is not None and path is not None and not enum_paths.path_starts_with(path, prefix):
                self._push_diag("S001", node or call, "Invalid enum value for '" + d.name
                                + "': expected path starting with '" + ".".join(prefix) + "'")
                path = list(prefix)
            resolved = self._resolve_enum_number(path) if path is not None else None
        if resolved is None:
            fb = enum_paths.normalize_member_path(self._default_string(d))
            fbv = self._resolve_enum_number(fb) if fb is not None else None
            resolved = fbv if fbv is not None else 0
        args[arg_key] = resolved

    # 6.7 / 6.8 volume / geometry
    def _resolve_volume_arg(self, d, node, call, args, arg_key, kind, pat):
        ref_kind = K.VolRef if kind == "vol" else K.GeoRef
        if node is not None and node.get('type') == K.String:
            self._push_diag("S001", node, "String literal not allowed for " + kind + " parameter '" + d.name + "'")
            args[arg_key] = ({'kind': kind, 'name': d.default} if isinstance(d.default, str) else None)
            return
        value = None
        if node is not None and node.get('type') == K.Read3D and node.get('tex3d') is not None and node.get('geo') is None:
            nm = self._surface_name(node['tex3d'])
            if nm is not None and self._matches_pattern(nm, pat):
                value = {'kind': kind, 'name': nm}
            else:
                self._push_diag("S001", node, "Invalid " + kind + " reference in read3d() for '" + d.name + "'")
                value = self._default_surface(d, kind)
        elif node is not None and node.get('type') == ref_kind:
            value = {'kind': kind, 'name': node['name']}
        elif node is not None and node.get('type') == K.Ident:
            nm = node['name']
            if nm == "none":
                value = {'kind': kind, 'name': "none"}
            elif self._matches_pattern(nm, pat):
                value = {'kind': kind, 'name': nm}
            else:
                self._push_diag("S001", node, "Invalid " + kind + " reference '" + nm + "' for '" + d.name + "'")
                value = self._default_surface(d, kind)
        elif node is None and isinstance(d.default, str):
            value = {'kind': kind, 'name': d.default}
        args[arg_key] = value

    # 6.9 string (STRICT allowlist)
    def _resolve_string_arg(self, d, node, op_name, original, call, args, arg_key):
        func_name = op_name[op_name.rfind('.') + 1:] if '.' in op_name else op_name
        allowlist_key = func_name + "." + d.name
        if allowlist_key not in _ALLOWED_STRING_PARAMS:
            self._push_diag("S001", node or original, "String parameter '" + d.name + "' on effect '"
                            + func_name + "' is NOT in the allowed string params list. String params are "
                            "strictly controlled - use enums or choices instead.")
            args[arg_key] = self._default_arg(d)
            return
        if node is not None and node.get('type') == K.String:
            args[arg_key] = node['value']
            return
        if node is not None and node.get('type') == K.Ident and d.choices is not None:
            if node['name'] in d.choices:
                args[arg_key] = d.choices[node['name']]
            else:
                self._push_diag("S001", node, "Invalid choice '" + node['name'] + "' for string parameter '" + d.name + "'")
                args[arg_key] = self._default_arg(d)
            return
        if node is not None:
            self._push_diag("S001", node, "String parameter '" + d.name + "' requires a quoted string literal, got "
                            + str(node.get('type')))
            args[arg_key] = self._default_arg(d)
            return
        args[arg_key] = self._default_arg(d)

    # 6.10 numeric
    def _resolve_numeric_arg(self, d, node, call, args, arg_key):
        if node is None:
            self._numeric_default(d, args, arg_key)
            return
        t = node.get('type')
        if t == K.String:
            self._push_diag("S001", node, "String literal not allowed for numeric parameter '" + d.name
                            + "' - strings are only valid for type: \"string\" parameters")
            args[arg_key] = self._default_arg(d)
            return
        if t == K.Number or t == K.Boolean:
            value = (1 if node['value'] else 0) if t == K.Boolean else node['value']
            clamped = self._clamp(value, d)
            if clamped != value:
                self._push_diag("S002", node, "Argument out of range for '" + d.name + "' in " + call['name']
                                + "() (got " + _jsnum(value) + ", clamped to " + _jsnum(clamped) + ")")
            args[arg_key] = clamped
            return
        if t == K.Func:
            raise UnsupportedDsl("Func numeric params ((state)=>...) are not implemented in the first-cut "
                                 "DSL frontend (reference/02 §6.10).")
        if t == K.Oscillator:
            args[arg_key] = self._resolve_oscillator(node)
            return
        if t == K.Midi:
            raise UnsupportedDsl("midi() automation args are not implemented in the first-cut DSL frontend "
                                 "(reference/02 §6.12).")
        if t == K.Audio:
            raise UnsupportedDsl("audio() automation args are not implemented in the first-cut DSL frontend "
                                 "(reference/02 §6.13).")
        if t == K.Member:
            cur = self._resolve_enum_number(node['path'])
            if cur is not None:
                v = self._clamp(cur, d)
                if v != cur:
                    self._push_diag("S002", node, "Argument out of range for '" + d.name + "' in " + call['name']
                                    + "() (got " + _jsnum(cur) + ", clamped to " + _jsnum(v) + ")")
                args[arg_key] = v
            else:
                self._push_diag("S001", node, "Cannot resolve enum value for '" + d.name + "': '"
                                + ".".join(node['path']) + "'")
                args[arg_key] = self._default_arg(d)
            return
        if t == K.Ident and node['name'] in _STATE_VALUES:
            raise UnsupportedDsl("state-value numeric params (time/frame/...) are not implemented in the "
                                 "first-cut DSL frontend (reference/02 §6.10).")
        if t == K.Ident and d.enum is not None:
            prefix = enum_paths.normalize_member_path(d.enum)
            path = (list(prefix) + [node['name']]) if prefix is not None else [node['name']]
            resolved = self._resolve_enum_number(path)
            if resolved is not None:
                args[arg_key] = self._clamp(resolved, d)
            else:
                self._push_diag("S003", node)
                args[arg_key] = self._default_arg(d)
            return
        if t == K.Ident and d.choices is not None:
            if node['name'] in d.choices:
                args[arg_key] = self._clamp(d.choices[node['name']], d)
            else:
                self._push_diag("S003", node)
                args[arg_key] = self._default_arg(d)
            return
        # else: defaultFrom or default
        if t == K.Ident and node['name'] not in _STATE_VALUES:
            self._push_diag("S003", node)
        elif t != K.Ident:
            self._push_diag("S002", node, "Argument out of range for '" + d.name + "' in " + call['name'] + "()")
        self._numeric_default(d, args, arg_key)

    def _numeric_default(self, d, args, arg_key):
        if d.default_from is not None and d.default_from in args:
            args[arg_key] = args[d.default_from]
        else:
            args[arg_key] = self._default_arg(d)

    # 6.11 osc() value oscillator -> resolved config object (reference/02 §6.11)
    def _resolve_oscillator(self, node):
        osc_type = 0
        ot = node['oscType']
        if ot.get('type') == K.Member:
            r = self._resolve_enum_number(ot['path'])
            if r is not None:
                osc_type = r
        elif ot.get('type') == K.Ident:
            r = self._resolve_enum_number(["oscKind", ot['name']])
            if r is not None:
                osc_type = r
        return {
            'type': 'Oscillator',
            'oscType': osc_type,
            'min': _clamp01(self._resolve_osc_param(node['min']) if self._resolve_osc_param(node['min']) is not None else 0),
            'max': _clamp01(self._resolve_osc_param(node['max']) if self._resolve_osc_param(node['max']) is not None else 1),
            'speed': self._resolve_osc_param(node['speed']) if self._resolve_osc_param(node['speed']) is not None else 1,
            'offset': self._resolve_osc_param(node['offset']) if self._resolve_osc_param(node['offset']) is not None else 0,
            'seed': self._resolve_osc_param(node['seed']) if self._resolve_osc_param(node['seed']) is not None else 1,
        }

    def _resolve_osc_param(self, param):
        if param is None:
            return None
        t = param.get('type')
        if t == K.Number:
            return param['value']
        if t == K.Boolean:
            return 1 if param['value'] else 0
        if t == K.Member:
            return self._resolve_enum_number(param['path'])
        return None

    # --- helpers --------------------------------------------------------

    @staticmethod
    def _clamp(value, d):
        if d.has_min and value < d.min:
            return d.min
        if d.has_max and value > d.max:
            return d.max
        return value

    @staticmethod
    def _default_arg(d, fallback_array=None):
        dv = d.default
        if dv is None:
            return list(fallback_array) if fallback_array is not None else None
        if isinstance(dv, bool):
            return dv
        if isinstance(dv, (int, float)):
            return dv
        if isinstance(dv, str):
            return dv
        if isinstance(dv, list):
            return [e if (isinstance(e, (int, float)) and not isinstance(e, bool)) else 0 for e in dv]
        return None

    @staticmethod
    def _default_bool(d):
        dv = d.default
        if isinstance(dv, bool):
            return dv
        if isinstance(dv, (int, float)):
            return dv != 0
        return False

    @staticmethod
    def _default_string(d):
        return d.default if isinstance(d.default, str) else None

    @staticmethod
    def _default_surface(d, kind):
        return {'kind': kind, 'name': d.default} if isinstance(d.default, str) else None

    @staticmethod
    def _to_surface(node):
        if node is None or not isinstance(node, dict):
            return None
        t = node.get('type')
        if t == K.OutputRef:
            return {'kind': 'output', 'name': node['name']}
        if t == K.SourceRef:
            return {'kind': 'source', 'name': node['name']}
        if t == K.XyzRef:
            return {'kind': 'xyz', 'name': node['name']}
        if t == K.VelRef:
            return {'kind': 'vel', 'name': node['name']}
        if t == K.RgbaRef:
            return {'kind': 'rgba', 'name': node['name']}
        if t == K.MeshRef:
            return {'kind': 'mesh', 'name': node['name']}
        if t == K.Ident and node['name'] == "none":
            return {'kind': 'output', 'name': 'none'}
        if t == K.Ident and node['name'] in _STATE_SURFACES:
            return {'kind': 'state', 'name': node['name']}
        return None

    def _call_to_surface(self, node):
        if node is None:
            return None
        if node.get('type') == K.Chain and len(node['chain']) == 1:
            return self._call_to_surface(node['chain'][0])
        if node.get('type') != K.Call or node['name'] not in _SURFACE_PASSTHROUGH_CALLS:
            return None
        target = node['args'][0] if node['args'] else None
        if target is None and node.get('kwargs') is not None:
            target = node['kwargs'].get('tex')
        return self._to_surface(target) if target is not None else None

    @staticmethod
    def _surface_name(n):
        if n is None:
            return None
        t = n.get('type')
        if t in (K.SourceRef, K.VolRef, K.GeoRef, K.XyzRef, K.VelRef, K.RgbaRef, K.MeshRef, K.OutputRef):
            return n['name']
        if t == K.Ident:
            return n['name']
        return None

    @staticmethod
    def _make_3d_ref(n, default_kind, ref_kind):
        name = _Validator._surface_name(n)
        if name is None:
            return None
        if default_kind == "vol":
            kind = "vol" if (n.get('type') == ref_kind) else "tex3d"
        else:
            kind = "geo"
        return {'kind': kind, 'name': name}

    @staticmethod
    def _matches_pattern(name, prefix):
        if name is None or len(name) != len(prefix) + 1:
            return False
        if not name.startswith(prefix):
            return False
        dd = name[len(prefix)]
        return '0' <= dd <= '7'


def _clamp01(x):
    return max(0, min(1, x))


def _jsnum(v):
    """Format a number like JS String(n) for diagnostic messages (12.0 -> '12')."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
