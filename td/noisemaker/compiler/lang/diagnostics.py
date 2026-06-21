"""diagnostics.py — diagnostic codes + the collected-diagnostic record. Port of hlsl
Compiler/Lang/Diagnostics.cs (reference/02 §7).

The validator COLLECTS diagnostics (it does not throw, except missing-search). Codes +
severities are the contract (severity strings 'error'/'warning' match the reference output).
"""

SEVERITY_ERROR = 'error'
SEVERITY_WARNING = 'warning'

# code -> (default message, severity). reference/02 §7 / reference/01 §8.7.
_TABLE = {
    'S001': ("Unknown identifier", SEVERITY_ERROR),
    'S002': ("Argument out of range", SEVERITY_WARNING),
    'S003': ("Variable used before assignment", SEVERITY_ERROR),
    'S004': ("Cannot assign null or undefined", SEVERITY_ERROR),
    'S005': ("Illegal chain structure", SEVERITY_ERROR),
    'S006': ("Starter chain missing write() call", SEVERITY_ERROR),
    'S007': ("Deprecated parameter alias", SEVERITY_WARNING),
    'S008': ("Deprecated effect", SEVERITY_WARNING),
}


def default_message(code):
    return _TABLE[code][0]


def severity(code):
    return _TABLE[code][1]


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
    if identifier is not None:
        d['identifier'] = identifier
    return d
