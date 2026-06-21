"""token.py — DSL token kinds + the token record. 1:1 port of hlsl Token.cs.

reference/01 §1.1: every token is `{type, lexeme, line, col}`.
  - type   : the token kind (TokenType constants below; uppercase strings exactly as the
             reference lexer emits, reference/01 §1.4 — kept as strings, not an enum, so a
             dumped token stream diffs directly against the reference's JSON).
  - lexeme : the matched source substring; for STRING/FUNC it is the *content* without
             delimiters / arrow head (the lexer strips those).
  - line   : 1-based line at token start.
  - col    : 1-based column at token start (per-UTF-16-code-unit; tabs = 1).
"""


class TokenType:
    # literals / identifiers
    NUMBER = 'NUMBER'
    STRING = 'STRING'
    HEX = 'HEX'
    FUNC = 'FUNC'
    IDENT = 'IDENT'

    # surface refs
    OUTPUT_REF = 'OUTPUT_REF'
    SOURCE_REF = 'SOURCE_REF'
    VOL_REF = 'VOL_REF'
    GEO_REF = 'GEO_REF'
    XYZ_REF = 'XYZ_REF'
    VEL_REF = 'VEL_REF'
    RGBA_REF = 'RGBA_REF'
    MESH_REF = 'MESH_REF'

    # punctuation
    DOT = 'DOT'
    LPAREN = 'LPAREN'
    RPAREN = 'RPAREN'
    LBRACE = 'LBRACE'
    RBRACE = 'RBRACE'
    LBRACKET = 'LBRACKET'
    RBRACKET = 'RBRACKET'
    COMMA = 'COMMA'
    COLON = 'COLON'
    EQUAL = 'EQUAL'
    SEMICOLON = 'SEMICOLON'
    PLUS = 'PLUS'
    MINUS = 'MINUS'
    STAR = 'STAR'
    SLASH = 'SLASH'

    # keywords (RESERVED_KEYWORDS — reference/01 §1.3)
    LET = 'LET'
    RENDER = 'RENDER'
    WRITE = 'WRITE'
    WRITE3D = 'WRITE3D'
    TRUE = 'TRUE'
    FALSE = 'FALSE'
    IF = 'IF'
    ELIF = 'ELIF'
    ELSE = 'ELSE'
    BREAK = 'BREAK'
    CONTINUE = 'CONTINUE'
    RETURN = 'RETURN'
    SEARCH = 'SEARCH'
    SUBCHAIN = 'SUBCHAIN'

    # trivia / end
    COMMENT = 'COMMENT'
    EOF = 'EOF'


class Token:
    __slots__ = ('type', 'lexeme', 'line', 'col')

    def __init__(self, type, lexeme, line, col):
        self.type = type
        self.lexeme = lexeme
        self.line = line
        self.col = col

    def __repr__(self):
        return "%s('%s' @%d:%d)" % (self.type, self.lexeme, self.line, self.col)
