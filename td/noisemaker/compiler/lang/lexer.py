"""lexer.py — DSL tokenizer. 1:1 port of hlsl Compiler/Lang/Lexer.cs (itself a 1:1 port
of shaders/src/lang/lexer.js). reference/01 §1.

PARITY-CRITICAL details replicated exactly:
  - 1-based line/col; col counts code units (Python str index == JS UTF-16 unit for the
    BMP; the DSL is ASCII-only for identifiers). Tabs = 1. '\\n' resets col=1, line++.
  - Rule order is load-bearing (reference/01 §1.4): comments, surface-prefix refs
    (o/s, then vol BEFORE vel — disambiguated by the 3rd char — geo, xyz; rgba/mesh need
    4 prefix chars + digit), hex {3,6,8} only, arrow FUNC, leading-dot number, single-char
    punctuation, triple-quote string, single/double string (escapes NOT decoded), number,
    identifier/keyword, else throw.
  - HEX gated to total length 4/7/9 (i.e. 3/6/8 hex digits); otherwise '#' falls through
    to the final throw.
  - String escapes are NOT decoded: lexeme is the raw inter-delimiter text.
"""

from .token import Token, TokenType as T
from .dsl_syntax_error import DslSyntaxError

# RESERVED_KEYWORDS (reference/01 §1.3 / lexer.js, frozen).
_KEYWORDS = {
    'let': T.LET,
    'render': T.RENDER,
    'write': T.WRITE,
    'write3d': T.WRITE3D,
    'true': T.TRUE,
    'false': T.FALSE,
    'if': T.IF,
    'elif': T.ELIF,
    'else': T.ELSE,
    'break': T.BREAK,
    'continue': T.CONTINUE,
    'return': T.RETURN,
    'search': T.SEARCH,
    'subchain': T.SUBCHAIN,
}

_SINGLE = {
    '.': T.DOT,
    '(': T.LPAREN,
    ')': T.RPAREN,
    '{': T.LBRACE,
    '}': T.RBRACE,
    '[': T.LBRACKET,
    ']': T.RBRACKET,
    ',': T.COMMA,
    ':': T.COLON,
    '=': T.EQUAL,
    ';': T.SEMICOLON,
    '+': T.PLUS,
    '-': T.MINUS,
    '*': T.STAR,
    '/': T.SLASH,
}


def _is_digit(c):
    return '0' <= c <= '9'


def _is_letter(c):
    return ('a' <= c <= 'z') or ('A' <= c <= 'Z')


def _is_hex(c):
    return ('0' <= c <= '9') or ('a' <= c <= 'f') or ('A' <= c <= 'F')


def lex(src):
    """Tokenize `src` into a list[Token] ending in one EOF token (reference/01 §1)."""
    tokens = []
    if src is None:
        src = ''
    i = 0
    line = 1
    col = 1
    n = len(src)

    # Bounds-safe char fetch (JS src[k] past end == undefined; here a NUL sentinel that
    # never matches any real test).
    def at(k):
        return src[k] if 0 <= k < n else '\0'

    while i < n:
        ch = src[i]

        if ch == ' ' or ch == '\t' or ch == '\r':
            i += 1
            col += 1
            continue
        if ch == '\n':
            i += 1
            line += 1
            col = 1
            continue

        start_line = line
        start_col = col

        # 2. line comment //...
        if ch == '/' and at(i + 1) == '/':
            j = i + 2
            while j < n and src[j] != '\n':
                j += 1
            tokens.append(Token(T.COMMENT, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 3. block comment /* ... */
        if ch == '/' and at(i + 1) == '*':
            j = i + 2
            end_line = line
            end_col = col + 2
            while j < n and not (src[j] == '*' and at(j + 1) == '/'):
                if src[j] == '\n':
                    end_line += 1
                    end_col = 1
                else:
                    end_col += 1
                j += 1
            if j >= n:
                raise DslSyntaxError.at("Unterminated comment", start_line, start_col)
            j += 2
            tokens.append(Token(T.COMMENT, src[i:j], start_line, start_col))
            line = end_line
            col = end_col + 2
            i = j
            continue

        # 4. output or source reference (o/s + digit)
        if (ch == 'o' or ch == 's') and _is_digit(at(i + 1)):
            j = i + 1
            while j < n and _is_digit(src[j]):
                j += 1
            t = T.OUTPUT_REF if ch == 'o' else T.SOURCE_REF
            tokens.append(Token(t, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 5. vol reference (vol + digit) — tested BEFORE vel (rule 8)
        if ch == 'v' and at(i + 1) == 'o' and at(i + 2) == 'l' and _is_digit(at(i + 3)):
            j = i + 3
            while j < n and _is_digit(src[j]):
                j += 1
            tokens.append(Token(T.VOL_REF, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 6. geo reference (geo + digit)
        if ch == 'g' and at(i + 1) == 'e' and at(i + 2) == 'o' and _is_digit(at(i + 3)):
            j = i + 3
            while j < n and _is_digit(src[j]):
                j += 1
            tokens.append(Token(T.GEO_REF, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 7. xyz reference (xyz + digit)
        if ch == 'x' and at(i + 1) == 'y' and at(i + 2) == 'z' and _is_digit(at(i + 3)):
            j = i + 3
            while j < n and _is_digit(src[j]):
                j += 1
            tokens.append(Token(T.XYZ_REF, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 8. vel reference (vel + digit) — v disambiguated from vol by 3rd char
        if ch == 'v' and at(i + 1) == 'e' and at(i + 2) == 'l' and _is_digit(at(i + 3)):
            j = i + 3
            while j < n and _is_digit(src[j]):
                j += 1
            tokens.append(Token(T.VEL_REF, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 9. rgba reference (rgba + digit)
        if (ch == 'r' and at(i + 1) == 'g' and at(i + 2) == 'b' and at(i + 3) == 'a'
                and _is_digit(at(i + 4))):
            j = i + 4
            while j < n and _is_digit(src[j]):
                j += 1
            tokens.append(Token(T.RGBA_REF, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 10. mesh reference (mesh + digit)
        if (ch == 'm' and at(i + 1) == 'e' and at(i + 2) == 's' and at(i + 3) == 'h'
                and _is_digit(at(i + 4))):
            j = i + 4
            while j < n and _is_digit(src[j]):
                j += 1
            tokens.append(Token(T.MESH_REF, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 11. hex color literal (#); only emit for total length 4/7/9
        if ch == '#':
            j = i + 1
            while j < n and _is_hex(src[j]):
                j += 1
            length = j - i
            if length == 4 or length == 7 or length == 9:
                tokens.append(Token(T.HEX, src[i:j], start_line, start_col))
                col += length
                i = j
                continue
            # else fall through ('#' matches no later rule -> final throw)

        # 12. arrow function () => expr
        if ch == '(' and at(i + 1) == ')':
            j = i + 2
            while j < n and (src[j] == ' ' or src[j] == '\t'):
                j += 1
            if at(j) == '=' and at(j + 1) == '>':
                j += 2
                while j < n and (src[j] == ' ' or src[j] == '\t'):
                    j += 1
                depth = 0
                expr_start = j
                while j < n:
                    c = src[j]
                    if c == '(':
                        depth += 1
                    elif c == ')':
                        if depth == 0:
                            break
                        depth -= 1
                    elif depth == 0:
                        if c == ',' or c == ';' or c == '\n' or c == '}':
                            break
                    j += 1
                expr = src[expr_start:j].strip()
                tokens.append(Token(T.FUNC, expr, start_line, start_col))
                col += j - i
                i = j
                continue
            # else fall through: '(' handled by single-char punctuation below

        # 13. leading-dot number .D
        if ch == '.' and _is_digit(at(i + 1)):
            j = i + 1
            while j < n and _is_digit(src[j]):
                j += 1
            tokens.append(Token(T.NUMBER, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 14. single-char punctuation
        punct = _SINGLE.get(ch)
        if punct is not None:
            tokens.append(Token(punct, ch, start_line, start_col))
            i += 1
            col += 1
            continue

        # 15. triple-quoted string """ ... """ (checked before single quotes)
        if ch == '"' and at(i + 1) == '"' and at(i + 2) == '"':
            j = i + 3
            while j < n - 2:
                if src[j] == '"' and src[j + 1] == '"' and src[j + 2] == '"':
                    break
                if src[j] == '\n':
                    line += 1
                    col = 0
                j += 1
            if j >= n - 2 or not (at(j) == '"' and at(j + 1) == '"' and at(j + 2) == '"'):
                raise DslSyntaxError.at("Unterminated triple-quoted string", start_line, start_col)
            content = src[i + 3:j]
            tokens.append(Token(T.STRING, content, start_line, start_col))
            # multi-line col fixup (reference/01 §1.4 rule 15)
            lines = content.split('\n')
            if len(lines) > 1:
                col = len(lines[-1]) + 4
            else:
                col += j - i + 3
            i = j + 3
            continue

        # 16. single/double quoted string (escapes consume 2 chars, NOT decoded)
        if ch == '"' or ch == "'":
            quote = ch
            j = i + 1
            while j < n and src[j] != quote and src[j] != '\n':
                if src[j] == '\\' and j + 1 < n:
                    j += 2
                else:
                    j += 1
            if j >= n or src[j] == '\n':
                raise DslSyntaxError.at("Unterminated string literal", line, col)
            content = src[i + 1:j]
            tokens.append(Token(T.STRING, content, start_line, start_col))
            col += j - i + 1
            i = j + 1
            continue

        # 17. number D...
        if _is_digit(ch):
            j = i
            while j < n and _is_digit(src[j]):
                j += 1
            if at(j) == '.' and _is_digit(at(j + 1)):
                j += 1
                while j < n and _is_digit(src[j]):
                    j += 1
            tokens.append(Token(T.NUMBER, src[i:j], start_line, start_col))
            col += j - i
            i = j
            continue

        # 18. identifier / keyword
        if _is_letter(ch) or ch == '_':
            j = i
            while j < n and (_is_letter(src[j]) or _is_digit(src[j]) or src[j] == '_'):
                j += 1
            lexeme = src[i:j]
            kw = _KEYWORDS.get(lexeme)
            tokens.append(Token(kw if kw is not None else T.IDENT, lexeme, start_line, start_col))
            col += j - i
            i = j
            continue

        # 19. anything else
        raise DslSyntaxError.at("Unexpected character '" + ch + "'", line, col)

    tokens.append(Token(T.EOF, "", line, col))
    return tokens
