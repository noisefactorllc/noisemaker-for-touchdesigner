"""ast.py — DSL AST node kinds + shape helpers. Port of hlsl Compiler/Lang/Ast.cs.

The reference parser (shaders/src/lang/parser.js) emits plain JS objects discriminated by a
`type` string (reference/01 §6). C# had to model them as a typed class hierarchy; in Python
the faithful equivalent is the same plain-object model — AST nodes are **dicts** with exactly
the reference field set, so a parsed tree diffs directly against the reference `parse()`.

`NodeKind` holds the `type` strings (matching the reference). Helpers build the recurring
shapes; the parser builds the rest inline. PARITY notes (reference/01 §6):
  - Number.value is a DOUBLE carrying the parse-time constant fold (§4.4).
  - Color.value is a 4-double array in 0..1 (§5); no colorspace in the front-end.
  - String.value is RAW (escapes not decoded; §1.4 rules 15/16).
  - The chain-statement wrapper has NO `type` — identified by the `chain` key (§6.2).
  - Member.path has >= 2 segments; a single segment is an Ident (§4.5).
"""


class NodeKind:
    Program = 'Program'
    VarAssign = 'VarAssign'
    IfStmt = 'IfStmt'
    Break = 'Break'
    Continue = 'Continue'
    Return = 'Return'
    Call = 'Call'
    Write = 'Write'
    Write3D = 'Write3D'
    Subchain = 'Subchain'
    Read = 'Read'
    Read3D = 'Read3D'
    Number = 'Number'
    String = 'String'
    Boolean = 'Boolean'
    Color = 'Color'
    ArrayLiteral = 'ArrayLiteral'
    Func = 'Func'
    Ident = 'Ident'
    Member = 'Member'
    Chain = 'Chain'
    OutputRef = 'OutputRef'
    SourceRef = 'SourceRef'
    VolRef = 'VolRef'
    GeoRef = 'GeoRef'
    XyzRef = 'XyzRef'
    VelRef = 'VelRef'
    RgbaRef = 'RgbaRef'
    MeshRef = 'MeshRef'
    Oscillator = 'Oscillator'
    Midi = 'Midi'
    Audio = 'Audio'


def number(value):
    """{type:'Number', value:double} — the parse-time constant-folded literal."""
    return {'type': NodeKind.Number, 'value': value}


def member_of(a, b):
    """A 2-segment Member, used for special-form defaults (oscKind.sine, midiMode.velocity)."""
    return {'type': NodeKind.Member, 'path': [a, b]}


def loc(line, col):
    """The {line,col} source location the reference attaches to Write/Subchain/etc."""
    return {'line': line, 'col': col}
