"""parser.py — recursive-descent parser. 1:1 port of hlsl Compiler/Lang/Parser.cs (itself a
1:1 port of shaders/src/lang/parser.js). reference/01 §2-§7. Produces a Program AST dict.

PARITY-CRITICAL behaviors replicated:
  - Numeric +-*/ are CONSTANT-FOLDED at parse time in double, left-to-right within a
    precedence level; operands MUST be Number literals (else "Expected number")
    (reference/01 §4.4). Math.PI = 3.141592653589793.
  - HEX color: int(pair,16)/255 in double; 3-digit char duplication; alpha default 1.0;
    8-digit alpha A/255 (reference/01 §5).
  - Special-form transforms in order: from, osc (4-way heuristic), midi, audio, read, read3d
    (reference/01 §4.2).
  - memberTokens / exprStart / namespaceTokens membership (reference/01 §2.1).
  - `search` mandatory + position-restricted; `render` terminates the program; duplicate
    render throws (reference/01 §3.1). Inline namespace `a.b()` forbidden (§4.2.2/§4.3).

AST nodes are plain dicts (ast.NodeKind type strings). Kwargs are plain dicts — Python dicts
preserve insertion order, matching the reference's order-significant JS kwarg objects.
"""

from . import ast
from .ast import NodeKind as K
from .token import TokenType as T
from .dsl_syntax_error import DslSyntaxError

_EXPR_START = frozenset([
    T.PLUS, T.MINUS, T.NUMBER, T.HEX, T.FUNC, T.STRING, T.IDENT, T.OUTPUT_REF, T.SOURCE_REF,
    T.VOL_REF, T.GEO_REF, T.MESH_REF, T.XYZ_REF, T.VEL_REF, T.RGBA_REF, T.LPAREN, T.LBRACKET,
    T.TRUE, T.FALSE,
])

_MEMBER_TOKENS = frozenset([
    T.IDENT, T.SOURCE_REF, T.OUTPUT_REF, T.VOL_REF, T.GEO_REF, T.MESH_REF, T.XYZ_REF, T.VEL_REF,
    T.RGBA_REF, T.LET, T.RENDER, T.TRUE, T.FALSE, T.IF, T.ELIF, T.ELSE, T.BREAK, T.CONTINUE,
    T.RETURN, T.WRITE, T.WRITE3D, T.SUBCHAIN,
])

_NAMESPACE_TOKENS = frozenset([
    T.IDENT, T.RENDER, T.WRITE, T.WRITE3D, T.TRUE, T.FALSE, T.IF, T.ELIF, T.ELSE, T.BREAK,
    T.CONTINUE, T.RETURN,
])

_OSC_KWARG_KEYS = frozenset(['type', 'min', 'max', 'speed', 'offset', 'seed'])


def parse(tokens, registry=None):
    """Entry point — parse a token list into a Program AST dict (reference/01 §3.1)."""
    return _Parser(tokens, registry)._parse_program()


class _Parser:
    def __init__(self, tokens, registry):
        self._tokens = tokens
        self._registry = registry
        self._current = 0
        self._program_search_order = None         # None until `search` parsed
        self._program_namespace = {'imports': [], 'default': None}

    # --- cursor helpers -------------------------------------------------

    def _peek(self):
        return self._tokens[self._current]

    def _token_at(self, idx):
        return self._tokens[idx] if 0 <= idx < len(self._tokens) else None

    def _advance(self):
        t = self._tokens[self._current]
        self._current += 1
        return t

    def _expect(self, type_, msg):
        t = self._peek()
        if t.type == type_:
            return self._advance()
        raise DslSyntaxError.at(msg, t.line, t.col)

    def _collect_comments(self):
        comments = []
        while self._peek() is not None and self._peek().type == T.COMMENT:
            comments.append(self._advance().lexeme)
        return comments

    # --- program (reference/01 §3.1) ------------------------------------

    def _parse_program(self):
        plans = []
        vars_ = []
        render = None
        trailing_comments = []

        while self._peek().type != T.EOF:
            if self._peek().type == T.SEMICOLON:
                self._advance()
                continue
            leading_comments = self._collect_comments()
            if self._peek().type == T.EOF:
                if leading_comments:
                    trailing_comments.extend(leading_comments)
                break
            if self._peek().type == T.SEARCH:
                if plans or vars_ or render is not None:
                    t = self._peek()
                    raise DslSyntaxError.at("'search' directive must appear before other statements", t.line, t.col)
                self._parse_search_directive()
                continue
            if self._peek().type == T.RENDER:
                if render is not None:
                    t = self._peek()
                    raise DslSyntaxError.at("Duplicate render() directive", t.line, t.col)
                render = self._parse_render_directive()
                while self._peek().type == T.SEMICOLON:
                    self._advance()
                if leading_comments and render is not None:
                    render['leadingComments'] = leading_comments
                trailing = self._collect_comments()
                if trailing:
                    trailing_comments.extend(trailing)
                break  # render TERMINATES program parse (reference/01 §3.1d)
            stmt = self._parse_statement()
            if leading_comments and stmt is not None:
                stmt['leadingComments'] = leading_comments
            if stmt is not None and stmt.get('type') == K.VarAssign:
                vars_.append(stmt)
            elif stmt is not None:
                plans.append(stmt)
            while self._peek().type == T.SEMICOLON:
                self._advance()

        self._expect(T.EOF, "Expected end of input")
        if not self._program_search_order:
            raise DslSyntaxError("Missing required 'search' directive. Every program must start "
                                 "with 'search <namespace>, ...' to specify namespace search order.")

        # namespace meta (deep copy, reference/01 §6.1).
        meta = {
            'imports': [{'name': imp['name'], 'source': imp['source'], 'explicit': imp['explicit']}
                        for imp in self._program_namespace['imports']],
            'default': None,
            'searchOrder': list(self._program_search_order),
        }
        d = self._program_namespace['default']
        if d is not None:
            meta['default'] = {'name': d['name'], 'source': d['source'], 'explicit': d['explicit']}

        program = {'type': K.Program, 'plans': plans, 'render': render, 'namespace': meta}
        if vars_:
            program['vars'] = vars_
        if trailing_comments:
            program['trailingComments'] = trailing_comments
        return program

    def _parse_search_directive(self):
        if self._program_search_order is not None:
            t = self._peek()
            raise DslSyntaxError.at("Only one search directive is allowed per program", t.line, t.col)
        self._advance()  # consume 'search'
        namespaces = []

        first = self._peek()
        if first.type not in _NAMESPACE_TOKENS:
            raise DslSyntaxError.at("Expected namespace identifier after search", first.line, first.col)
        self._advance()
        self._validate_namespace(first)
        namespaces.append(first.lexeme)

        while self._peek().type == T.COMMA:
            self._advance()
            ns_tok = self._peek()
            if ns_tok.type not in _NAMESPACE_TOKENS:
                raise DslSyntaxError.at("Expected namespace identifier after comma", ns_tok.line, ns_tok.col)
            self._advance()
            self._validate_namespace(ns_tok)
            namespaces.append(ns_tok.lexeme)

        self._program_search_order = namespaces
        self._program_namespace['imports'] = [
            {'name': nm, 'source': 'search', 'explicit': True} for nm in namespaces]
        self._program_namespace['default'] = {'name': namespaces[0], 'source': 'search', 'explicit': True}

        while self._peek().type == T.SEMICOLON:
            self._advance()

    def _validate_namespace(self, token):
        ns = token.lexeme
        if self._registry is None or not self._registry.is_valid_namespace(ns):
            valid = ''
            if self._registry is not None:
                valid = ', '.join(self._registry.namespaces)
            raise DslSyntaxError.at("Invalid namespace '" + ns + "'. Valid namespaces: " + valid,
                                    token.line, token.col)

    def _parse_render_directive(self):
        self._advance()  # consume 'render'
        self._expect(T.LPAREN, "Expect '('")
        if self._peek().type != T.OUTPUT_REF:
            raise DslSyntaxError("Expected output reference in render()")
        out_ref = {'type': K.OutputRef, 'name': self._advance().lexeme}
        self._expect(T.RPAREN, "Expect ')'")
        return out_ref

    # --- statements (reference/01 §3.3) ---------------------------------

    def _parse_block(self):
        self._expect(T.LBRACE, "Expect '{'")
        body = []
        while self._peek().type != T.RBRACE:
            body.append(self._parse_statement())
            while self._peek().type == T.SEMICOLON:
                self._advance()
        self._expect(T.RBRACE, "Expect '}'")
        return body

    def _parse_statement(self):
        if self._peek().type == T.SEARCH:
            t = self._peek()
            raise DslSyntaxError.at("'search' directive is only allowed at the start of the program", t.line, t.col)
        if self._peek().type == T.LET:
            self._advance()
            name = self._expect(T.IDENT, "Expected identifier").lexeme
            self._expect(T.EQUAL, "Expect '='")
            if self._peek().type not in _EXPR_START:
                t = self._peek()
                raise DslSyntaxError.at("Expected expression after '='", t.line, t.col)
            expr = self._parse_additive()
            return {'type': K.VarAssign, 'name': name, 'expr': expr}

        tt = self._peek().type
        if tt == T.IF:
            self._advance()
            self._expect(T.LPAREN, "Expect '('")
            condition = self._parse_additive()
            self._expect(T.RPAREN, "Expect ')'")
            then = self._parse_block()
            elif_ = []
            while self._peek().type == T.ELIF:
                self._advance()
                self._expect(T.LPAREN, "Expect '('")
                ec = self._parse_additive()
                self._expect(T.RPAREN, "Expect ')'")
                body = self._parse_block()
                elif_.append({'condition': ec, 'then': body})
            else_branch = None
            if self._peek().type == T.ELSE:
                self._advance()
                else_branch = self._parse_block()
            return {'type': K.IfStmt, 'condition': condition, 'then': then,
                    'elif': elif_, 'else': else_branch}
        if tt == T.BREAK:
            self._advance()
            return {'type': K.Break}
        if tt == T.CONTINUE:
            self._advance()
            return {'type': K.Continue}
        if tt == T.RETURN:
            self._advance()
            if self._peek().type in _EXPR_START:
                return {'type': K.Return, 'value': self._parse_additive()}
            return {'type': K.Return}

        chain = self._parse_chain("statement")
        write = None
        write3d = None
        if chain:
            last = chain[-1]
            if last.get('type') == K.Write:
                write = last['surface']
            elif last.get('type') == K.Write3D:
                write3d = {'tex3d': last['tex3d'], 'geo': last['geo']}
        return {'chain': chain, 'write': write, 'write3d': write3d}

    # --- chains (reference/01 §4.1) -------------------------------------

    def _parse_chain(self, context):
        first_call = self._parse_call()
        calls = [first_call]
        while True:
            saved_pos = self._current
            leading_comments = self._collect_comments()
            if self._peek().type != T.DOT:
                self._current = saved_pos  # comments belong to next statement
                break
            self._advance()  # consume '.'
            post_dot = self._collect_comments()
            all_comments = list(leading_comments)
            all_comments.extend(post_dot)

            next_type = self._peek().type
            if next_type == T.WRITE or next_type == T.WRITE3D:
                if context == "expression":
                    t = self._peek()
                    raise DslSyntaxError.at("'.write()' is only allowed in statement context", t.line, t.col)
                write_node = self._parse_write_call()
                if all_comments:
                    write_node['leadingComments'] = all_comments
                calls.append(write_node)
                continue
            if next_type == T.SUBCHAIN:
                subchain_node = self._parse_subchain_call()
                if all_comments:
                    subchain_node['leadingComments'] = all_comments
                calls.append(subchain_node)
                continue
            call = self._parse_call()
            if all_comments:
                call['leadingComments'] = all_comments
            calls.append(call)
        return calls

    def _parse_write_call(self):
        tok = self._peek()
        token_type = tok.type
        token_line = tok.line
        token_col = tok.col

        if token_type == T.WRITE:
            self._advance()
            self._expect(T.LPAREN, "Expect '('")
            pt = self._peek().type
            if pt == T.OUTPUT_REF:
                surface = {'type': K.OutputRef, 'name': self._advance().lexeme}
            elif pt == T.XYZ_REF:
                surface = {'type': K.XyzRef, 'name': self._advance().lexeme}
            elif pt == T.VEL_REF:
                surface = {'type': K.VelRef, 'name': self._advance().lexeme}
            elif pt == T.RGBA_REF:
                surface = {'type': K.RgbaRef, 'name': self._advance().lexeme}
            elif pt == T.MESH_REF:
                surface = {'type': K.MeshRef, 'name': self._advance().lexeme}
            elif pt == T.IDENT and self._peek().lexeme == "none":
                surface = {'type': K.OutputRef, 'name': self._advance().lexeme}
            else:
                p = self._peek()
                raise DslSyntaxError.at(
                    "write() requires an explicit surface reference (e.g., o0, o1, xyz0, vel0, rgba0, mesh0, none)",
                    p.line, p.col)
            self._expect(T.RPAREN, "Expect ')'")
            return {'type': K.Write, 'surface': surface, 'loc': ast.loc(token_line, token_col)}

        # WRITE3D
        self._advance()
        self._expect(T.LPAREN, "Expect '('")
        pt = self._peek().type
        if pt == T.OUTPUT_REF:
            tex3d = {'type': K.OutputRef, 'name': self._advance().lexeme}
        elif pt == T.VOL_REF:
            tex3d = {'type': K.VolRef, 'name': self._advance().lexeme}
        elif pt == T.IDENT:
            tex3d = {'type': K.Ident, 'name': self._advance().lexeme}
        else:
            p = self._peek()
            raise DslSyntaxError.at("Expected tex3d reference in write3d()", p.line, p.col)
        self._expect(T.COMMA, "Expect ',' between tex3d and geo in write3d()")
        pt = self._peek().type
        if pt == T.OUTPUT_REF:
            geo = {'type': K.OutputRef, 'name': self._advance().lexeme}
        elif pt == T.GEO_REF:
            geo = {'type': K.GeoRef, 'name': self._advance().lexeme}
        elif pt == T.IDENT:
            geo = {'type': K.Ident, 'name': self._advance().lexeme}
        else:
            p = self._peek()
            raise DslSyntaxError.at("Expected geo reference in write3d()", p.line, p.col)
        self._expect(T.RPAREN, "Expect ')'")
        return {'type': K.Write3D, 'tex3d': tex3d, 'geo': geo, 'loc': ast.loc(token_line, token_col)}

    def _parse_subchain_call(self):
        tok = self._peek()
        token_line = tok.line
        token_col = tok.col
        self._advance()  # consume 'subchain'
        self._expect(T.LPAREN, "Expect '(' after subchain")

        name_val = None
        id_val = None
        iterations_val = None
        if self._peek().type != T.RPAREN:
            if self._peek().type == T.STRING:
                name_val = self._advance().lexeme  # positional name
            elif self._peek().type == T.IDENT and self._kw_colon(self._current + 1):
                while self._peek().type == T.IDENT and self._kw_colon(self._current + 1):
                    key = self._advance().lexeme
                    self._advance()  # consume ':'
                    # DSL LOOPS (hlsl additive): `iterations:` takes a NUMBER; name/id stay STRING.
                    if key == "iterations":
                        if self._peek().type != T.NUMBER:
                            p = self._peek()
                            raise DslSyntaxError.at("Expected number value for subchain iterations", p.line, p.col)
                        nval = float(self._advance().lexeme)
                        import math
                        iterations_val = int(math.floor(nval))
                        if iterations_val < 1:
                            iterations_val = 1
                    else:
                        if self._peek().type != T.STRING:
                            p = self._peek()
                            raise DslSyntaxError.at("Expected string value for subchain " + key, p.line, p.col)
                        val = self._advance().lexeme
                        if key == "name":
                            name_val = val
                        elif key == "id":
                            id_val = val
                    if self._peek().type == T.COMMA:
                        self._advance()
        self._expect(T.RPAREN, "Expect ')' after subchain arguments")
        self._expect(T.LBRACE, "Expect '{' to start subchain body")

        body = []
        while self._peek().type != T.RBRACE:
            leading_comments = self._collect_comments()
            if self._peek().type == T.RBRACE:
                break
            if self._peek().type != T.DOT:
                p = self._peek()
                raise DslSyntaxError.at("Expected '.' before chain element in subchain body", p.line, p.col)
            self._advance()  # consume '.'
            post_dot = self._collect_comments()
            all_comments = list(leading_comments)
            all_comments.extend(post_dot)
            call = self._parse_call()
            if all_comments:
                call['leadingComments'] = all_comments
            body.append(call)
        self._expect(T.RBRACE, "Expect '}' to end subchain body")
        if not body:
            raise DslSyntaxError.at("Subchain body cannot be empty", token_line, token_col)

        node = {'type': K.Subchain, 'name': name_val, 'id': id_val, 'body': body,
                'loc': ast.loc(token_line, token_col)}
        if iterations_val is not None:
            node['iterations'] = iterations_val
        return node

    def _kw_colon(self, idx):
        """True if token at idx is the ':' of an `IDENT :` kwarg head."""
        t = self._token_at(idx)
        return t is not None and t.type == T.COLON

    # --- calls (reference/01 §4.2) --------------------------------------

    def _parse_call(self):
        name_token = self._expect(T.IDENT, "Expected identifier")
        # Inline namespace `a.b()` forbidden (reference/01 §4.2.2).
        if self._peek().type == T.DOT:
            nxt = self._token_at(self._current + 1)
            if nxt is not None and nxt.type == T.IDENT:
                after = self._token_at(self._current + 2)
                if after is not None and after.type == T.LPAREN:
                    raise DslSyntaxError.at(
                        "Inline namespace syntax '" + name_token.lexeme + "." + nxt.lexeme +
                        "()' is not allowed. Use 'search " + name_token.lexeme +
                        "' at the start of the program instead,", name_token.line, name_token.col)
        self._expect(T.LPAREN, "Expect '('")
        args = []
        kwargs = None
        keyword = False
        if self._peek().type != T.RPAREN:
            if self._peek().type == T.IDENT and self._kw_colon(self._current + 1):
                keyword = True
                kwargs = {}
                self._parse_kwarg(kwargs)
                while self._peek().type == T.COMMA:
                    self._advance()
                    if self._peek().type == T.RPAREN:
                        break
                    if not (self._peek().type == T.IDENT and self._kw_colon(self._current + 1)):
                        t = self._peek()
                        raise DslSyntaxError.at("Cannot mix positional and keyword arguments", t.line, t.col)
                    self._parse_kwarg(kwargs)
            else:
                args.append(self._parse_arg())
                while self._peek().type == T.COMMA:
                    self._advance()
                    if self._peek().type == T.RPAREN:
                        break
                    if self._peek().type == T.IDENT and self._kw_colon(self._current + 1):
                        t = self._peek()
                        raise DslSyntaxError.at("Cannot mix positional and keyword arguments", t.line, t.col)
                    args.append(self._parse_arg())
        self._expect(T.RPAREN, "Expect ')'")

        call = {'type': K.Call, 'name': name_token.lexeme, 'args': args}
        if keyword:
            call['kwargs'] = kwargs

        # Special-form transforms (reference/01 §4.2, in this order).
        nm = name_token.lexeme
        if nm == "from":
            return self._transform_from(call, name_token)
        if nm == "osc":
            has_type_kwarg = kwargs is not None and 'type' in kwargs
            first_arg_is_osckind = (len(args) > 0 and args[0].get('type') == K.Member
                                    and args[0]['path'] and args[0]['path'][0] == "oscKind")
            is_bare_osc = len(args) == 0 and (kwargs is None or len(kwargs) == 0)
            has_only_osc_kwargs = kwargs is not None and len(kwargs) > 0 and self._all_osc_kwargs(kwargs)
            if has_type_kwarg or first_arg_is_osckind or is_bare_osc or has_only_osc_kwargs:
                return self._transform_osc(call, name_token)
            # else fall through: synth.osc generator effect
        if nm == "midi":
            return self._transform_midi(call, name_token)
        if nm == "audio":
            return self._transform_audio(call, name_token)
        if nm == "read":
            surface = args[0] if args else (
                (kwargs.get('tex') or kwargs.get('surface')) if kwargs is not None else None)
            node = {'type': K.Read, 'surface': surface, 'loc': ast.loc(name_token.line, name_token.col)}
            skip = kwargs.get('_skip') if kwargs is not None else None
            if skip is not None and skip.get('type') == K.Boolean and skip.get('value') is True:
                node['_skip'] = True
            return node
        if nm == "read3d":
            tex3d = args[0] if len(args) > 0 else (kwargs.get('tex3d') if kwargs is not None else None)
            geo = args[1] if len(args) > 1 else (kwargs.get('geo') if kwargs is not None else None)
            node = {'type': K.Read3D, 'tex3d': tex3d, 'geo': geo, 'loc': ast.loc(name_token.line, name_token.col)}
            skip = kwargs.get('_skip') if kwargs is not None else None
            if skip is not None and skip.get('type') == K.Boolean and skip.get('value') is True:
                node['_skip'] = True
            return node
        return call

    @staticmethod
    def _all_osc_kwargs(kwargs):
        for k in kwargs:
            if k not in _OSC_KWARG_KEYS:
                return False
        return True

    def _parse_arg(self):
        return self._parse_additive()

    def _parse_kwarg(self, obj):
        key = self._expect(T.IDENT, "Expected identifier").lexeme
        self._expect(T.COLON, "Expect ':'")
        if self._peek().type not in _EXPR_START:
            t = self._peek()
            raise DslSyntaxError.at("Expected expression after '='", t.line, t.col)
        obj[key] = self._parse_arg()

    # --- special-form transforms (reference/01 §4.6 / §7) ---------------

    def _transform_from(self, call, name_token):
        def fail(message):
            raise DslSyntaxError.at(message, name_token.line, name_token.col)
        if call.get('kwargs') is not None and len(call['kwargs']) > 0:
            fail("'from' does not support named arguments")
        if len(call['args']) != 2:
            fail("'from' requires exactly two arguments (namespace, call)")

        namespace_arg = call['args'][0]
        target_arg = call['args'][1]
        namespace_name = None
        if namespace_arg.get('type') == K.Ident:
            namespace_name = namespace_arg['name']
        elif namespace_arg.get('type') == K.Member:
            namespace_name = ".".join(namespace_arg['path'])
        else:
            fail("'from' namespace argument must be an identifier")
        if not namespace_name:
            fail("'from' namespace argument must be non-empty")

        target_call = None
        if target_arg.get('type') == K.Call:
            target_call = target_arg
        elif (target_arg.get('type') == K.Chain and len(target_arg['chain']) == 1
              and target_arg['chain'][0].get('type') == K.Call):
            target_call = target_arg['chain'][0]
        if target_call is None:
            fail("'from' second argument must be a call expression")

        replacement = {'type': K.Call, 'name': target_call['name'], 'args': list(target_call['args'])}
        if target_call.get('kwargs') is not None:
            replacement['kwargs'] = dict(target_call['kwargs'])
        replacement['namespace'] = {
            'name': namespace_name,
            'path': [namespace_name],
            'explicit': True,
            'source': "from",
            'resolved': namespace_name,
            'searchOrder': [namespace_name],
            'fromOverride': True,
        }
        return replacement

    def _transform_osc(self, call, name_token):
        order = ["type", "min", "max", "speed", "offset", "seed"]
        kwargs = call.get('kwargs')
        if kwargs is not None:
            for key in kwargs:
                if key not in _OSC_KWARG_KEYS:
                    raise DslSyntaxError.at(
                        "osc() unknown parameter '" + key + "'. Valid: type, min, max, speed, offset, seed",
                        name_token.line, name_token.col)
        return {
            'type': K.Oscillator,
            'oscType': self._resolve_param(call, order[0], 0, ast.member_of("oscKind", "sine")),
            'min': self._resolve_param(call, order[1], 1, ast.number(0)),
            'max': self._resolve_param(call, order[2], 2, ast.number(1)),
            'speed': self._resolve_param(call, order[3], 3, ast.number(1)),
            'offset': self._resolve_param(call, order[4], 4, ast.number(0)),
            'seed': self._resolve_param(call, order[5], 5, ast.number(1)),
            'loc': ast.loc(name_token.line, name_token.col),
        }

    def _transform_midi(self, call, name_token):
        order = ["channel", "mode", "min", "max", "sensitivity"]
        channel = self._resolve_param(call, order[0], 0, None)
        if channel is None:
            raise DslSyntaxError.at("midi() requires 'channel' argument", name_token.line, name_token.col)
        return {
            'type': K.Midi,
            'channel': channel,
            'mode': self._resolve_param(call, order[1], 1, ast.member_of("midiMode", "velocity")),
            'min': self._resolve_param(call, order[2], 2, ast.number(0)),
            'max': self._resolve_param(call, order[3], 3, ast.number(1)),
            'sensitivity': self._resolve_param(call, order[4], 4, ast.number(1)),
            'loc': ast.loc(name_token.line, name_token.col),
        }

    def _transform_audio(self, call, name_token):
        order = ["band", "min", "max"]
        band = self._resolve_param(call, order[0], 0, None)
        if band is None:
            raise DslSyntaxError.at("audio() requires 'band' argument", name_token.line, name_token.col)
        return {
            'type': K.Audio,
            'band': band,
            'min': self._resolve_param(call, order[1], 1, ast.number(0)),
            'max': self._resolve_param(call, order[2], 2, ast.number(1)),
            'loc': ast.loc(name_token.line, name_token.col),
        }

    @staticmethod
    def _resolve_param(call, name, index, dflt):
        # kwarg if present, else positional by index, else default (reference/01 §7).
        kwargs = call.get('kwargs')
        if kwargs is not None and name in kwargs:
            return kwargs[name]
        if index < len(call['args']):
            return call['args'][index]
        return dflt

    # --- expressions (reference/01 §4.4/§4.5) ---------------------------

    def _parse_additive(self):
        node = self._parse_multiplicative()
        while self._peek().type == T.PLUS or self._peek().type == T.MINUS:
            op = self._advance().type
            right = self._parse_multiplicative()
            l = self._to_number(node)
            r = self._to_number(right)
            node = ast.number(l + r if op == T.PLUS else l - r)
        return node

    def _parse_multiplicative(self):
        node = self._parse_unary()
        while self._peek().type == T.STAR or self._peek().type == T.SLASH:
            op = self._advance().type
            right = self._parse_unary()
            l = self._to_number(node)
            r = self._to_number(right)
            node = ast.number(l * r if op == T.STAR else l / r)
        return node

    def _parse_unary(self):
        if self._peek().type == T.PLUS:
            self._advance()
            return self._parse_unary()
        if self._peek().type == T.MINUS:
            self._advance()
            val = self._parse_unary()
            return ast.number(-self._to_number(val))
        return self._parse_primary()

    @staticmethod
    def _to_number(node):
        if node.get('type') == K.Number:
            return node['value']
        raise DslSyntaxError("Expected number")

    def _parse_primary(self):
        token = self._peek()
        tt = token.type
        if tt == T.NUMBER:
            self._advance()
            return ast.number(_parse_float_js(token.lexeme))
        if tt == T.STRING:
            self._advance()
            return {'type': K.String, 'value': token.lexeme}
        if tt == T.HEX:
            self._advance()
            return _parse_hex(token.lexeme)
        if tt == T.LBRACKET:
            sl = token.line
            sc = token.col
            self._advance()
            elements = []
            if self._peek().type != T.RBRACKET:
                elements.append(self._parse_arg())
                while self._peek().type == T.COMMA:
                    self._advance()
                    elements.append(self._parse_arg())
            if self._peek().type != T.RBRACKET:
                t = self._peek()
                raise DslSyntaxError.at("Expected ']'", t.line, t.col)
            self._advance()
            return {'type': K.ArrayLiteral, 'elements': elements, 'loc': ast.loc(sl, sc)}
        if tt == T.FUNC:
            self._advance()
            return {'type': K.Func, 'src': token.lexeme}
        if tt == T.TRUE:
            self._advance()
            return {'type': K.Boolean, 'value': True}
        if tt == T.FALSE:
            self._advance()
            return {'type': K.Boolean, 'value': False}
        if tt == T.IDENT:
            # Math.PI
            nxt = self._token_at(self._current + 1)
            nxt2 = self._token_at(self._current + 2)
            if (token.lexeme == "Math" and nxt is not None and nxt.type == T.DOT
                    and nxt2 is not None and nxt2.type == T.IDENT and nxt2.lexeme == "PI"):
                self._advance()
                self._advance()
                self._advance()
                return ast.number(3.141592653589793)
            # member-then-call OR direct call -> parse as chain (expression context)
            if (nxt is not None and nxt.type == T.LPAREN) or self._has_call_after_dot(self._current):
                chain = self._parse_chain("expression")
                return chain[0] if len(chain) == 1 else {'type': K.Chain, 'chain': chain}
            # dotted member path
            self._advance()
            path = [token.lexeme]
            while self._peek().type == T.DOT:
                nxt = self._token_at(self._current + 1)
                if nxt is None:
                    break
                after = self._token_at(self._current + 2)
                if after is not None and after.type == T.LPAREN:
                    break  # dot begins a call
                if nxt.type not in _MEMBER_TOKENS:
                    raise DslSyntaxError.at("Expected identifier after '.'", nxt.line, nxt.col)
                self._advance()  # consume '.'
                self._advance()  # consume segment
                path.append(nxt.lexeme)
            if len(path) > 1:
                return {'type': K.Member, 'path': path}
            return {'type': K.Ident, 'name': path[0]}
        if tt == T.OUTPUT_REF:
            self._advance()
            return {'type': K.OutputRef, 'name': token.lexeme}
        if tt == T.SOURCE_REF:
            self._advance()
            return {'type': K.SourceRef, 'name': token.lexeme}
        if tt == T.VOL_REF:
            self._advance()
            return {'type': K.VolRef, 'name': token.lexeme}
        if tt == T.GEO_REF:
            self._advance()
            return {'type': K.GeoRef, 'name': token.lexeme}
        if tt == T.XYZ_REF:
            self._advance()
            return {'type': K.XyzRef, 'name': token.lexeme}
        if tt == T.VEL_REF:
            self._advance()
            return {'type': K.VelRef, 'name': token.lexeme}
        if tt == T.RGBA_REF:
            self._advance()
            return {'type': K.RgbaRef, 'name': token.lexeme}
        if tt == T.MESH_REF:
            self._advance()
            return {'type': K.MeshRef, 'name': token.lexeme}
        if tt == T.LPAREN:
            self._advance()
            expr = self._parse_additive()
            self._expect(T.RPAREN, "Expect ')'")
            return expr
        raise DslSyntaxError.at("Unexpected token " + token.type, token.line, token.col)

    def _has_call_after_dot(self, index):
        i = index + 1
        t = self._token_at(i)
        if t is None or t.type != T.DOT:
            return False
        while self._token_at(i) is not None and self._token_at(i).type == T.DOT:
            seg_token = self._token_at(i + 1)
            if seg_token is None or seg_token.type not in _MEMBER_TOKENS:
                return False
            i += 2
        t = self._token_at(i)
        return t is not None and t.type == T.LPAREN


# --- module helpers (reference/01 §5, §4.5) -----------------------------

def _parse_hex(lexeme):
    """HEX -> Color (reference/01 §5). int(pair,16)/255 in double."""
    hex_ = lexeme[1:]
    a = 1.0
    if len(hex_) == 3:
        r = _hex_pair(hex_[0] + hex_[0])
        g = _hex_pair(hex_[1] + hex_[1])
        b = _hex_pair(hex_[2] + hex_[2])
    elif len(hex_) == 6:
        r = _hex_pair(hex_[0:2])
        g = _hex_pair(hex_[2:4])
        b = _hex_pair(hex_[4:6])
    else:  # length 8
        r = _hex_pair(hex_[0:2])
        g = _hex_pair(hex_[2:4])
        b = _hex_pair(hex_[4:6])
        a = _hex_pair(hex_[6:8]) / 255.0
    return {'type': 'Color', 'value': [r / 255.0, g / 255.0, b / 255.0, a]}


def _hex_pair(pair):
    return int(pair, 16)


def _parse_float_js(lexeme):
    """JS parseFloat on a lexeme with no sign/exponent — plain float()."""
    return float(lexeme)
