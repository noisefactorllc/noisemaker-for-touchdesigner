"""dsl_syntax_error.py — 1:1 port of hlsl Compiler/Lang/DslSyntaxError.cs.

Mirrors the JS `SyntaxError` text shape `"<message> at line L col C"`. The error
formatter (reference/01 §9) parses the trailing `at line L col C` back out to draw the
caret, so the text format is parity-critical — do not change it.
"""


import math


def coord_str(val):
    if val is None:
        return "undefined"
    if isinstance(val, float) and math.isnan(val):
        return "NaN"
    return str(val)


class DslSyntaxError(Exception):
    """A lexer/parser error. `message` carries the full `"... at line L col C"` text."""

    def __init__(self, message, line=None, col=None, diagnostic=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.diagnostic = diagnostic

    coord_str = staticmethod(coord_str)

    @staticmethod
    def at(core, line, col, diagnostic=None):
        """Build `"<core> at line L col C"` (mirrors C# DslSyntaxError.At)."""
        return DslSyntaxError(
            "%s at line %s col %s" % (core, coord_str(line), coord_str(col)),
            line,
            col,
            diagnostic=diagnostic,
        )
