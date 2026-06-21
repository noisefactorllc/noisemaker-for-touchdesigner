"""dsl_syntax_error.py — 1:1 port of hlsl Compiler/Lang/DslSyntaxError.cs.

Mirrors the JS `SyntaxError` text shape `"<message> at line L col C"`. The error
formatter (reference/01 §9) parses the trailing `at line L col C` back out to draw the
caret, so the text format is parity-critical — do not change it.
"""


class DslSyntaxError(Exception):
    """A lexer/parser error. `message` carries the full `"... at line L col C"` text."""

    def __init__(self, message, line=None, col=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    @staticmethod
    def at(core, line, col):
        """Build `"<core> at line L col C"` (mirrors C# DslSyntaxError.At)."""
        return DslSyntaxError("%s at line %d col %d" % (core, line, col), line, col)
