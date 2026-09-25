"""diagnostics.py — diagnostic codes + the collected-diagnostic record. Port of hlsl
Compiler/Lang/Diagnostics.cs (reference/02 §7).

The validator COLLECTS diagnostics (it does not throw, except missing-search). Codes +
severities are the contract (severity strings 'error'/'warning' match the reference output).
"""

SEVERITY_ERROR = 'error'
SEVERITY_WARNING = 'warning'

STAGE_LEXER = 'lexer'
STAGE_PARSER = 'parser'
STAGE_SEMANTIC = 'semantic'
STAGE_RUNTIME = 'runtime'

# code -> (default message, severity, stage). reference/02 §7 / reference/01 §8.7 / diagnostics.js
_TABLE = {
    'L001': ("Unexpected character", SEVERITY_ERROR, STAGE_LEXER),
    'L002': ("Unterminated string literal", SEVERITY_ERROR, STAGE_LEXER),
    'L003': ("Unterminated comment", SEVERITY_ERROR, STAGE_LEXER),
    'L004': ("Output surface reference out of range", SEVERITY_ERROR, STAGE_LEXER),
    'P001': ("Unexpected token", SEVERITY_ERROR, STAGE_PARSER),
    'P002': ("Expected closing parenthesis", SEVERITY_ERROR, STAGE_PARSER),
    'P003': ("Invalid automation arguments", SEVERITY_ERROR, STAGE_PARSER),
    'P004': ("Invalid search directive", SEVERITY_ERROR, STAGE_PARSER),
    'P005': ("Invalid output operation", SEVERITY_ERROR, STAGE_PARSER),
    'P006': ("Invalid subchain", SEVERITY_ERROR, STAGE_PARSER),
    'P007': ("Invalid call expression", SEVERITY_ERROR, STAGE_PARSER),
    'S001': ("Unknown identifier", SEVERITY_ERROR, STAGE_SEMANTIC),
    'S002': ("Argument out of range", SEVERITY_WARNING, STAGE_SEMANTIC),
    'S003': ("Variable used before assignment", SEVERITY_ERROR, STAGE_SEMANTIC),
    'S004': ("Cannot assign null or undefined", SEVERITY_ERROR, STAGE_SEMANTIC),
    'S005': ("Illegal chain structure", SEVERITY_ERROR, STAGE_SEMANTIC),
    'S006': ("Starter chain missing write() call", SEVERITY_ERROR, STAGE_SEMANTIC),
    'S007': ("Deprecated parameter alias", SEVERITY_WARNING, STAGE_SEMANTIC),
    'S008': ("Deprecated effect", SEVERITY_WARNING, STAGE_SEMANTIC),
    'R001': ("Runtime error", SEVERITY_ERROR, STAGE_RUNTIME),
}


def default_message(code):
    return _TABLE[code][0]


def severity(code):
    return _TABLE[code][1]


def stage(code):
    return _TABLE[code][2]


def make(code, message=None, line=None, column=None, identifier=None):
    """Build a diagnostic record (the shape the reference `compile()` emits in `diagnostics`)."""
    d = {
        'code': code,
        'message': message if message is not None else default_message(code),
        'severity': severity(code),
    }
    if line is not None:
        d['line'] = line
    if column is not None:
        d['column'] = column
    if line is not None and column is not None:
        d['location'] = {'line': line, 'column': column}
    if identifier is not None:
        d['identifier'] = identifier
    return d
