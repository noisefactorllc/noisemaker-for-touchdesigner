"""enum_paths.py — member-path utilities. 1:1 port of hlsl Compiler/Lang/EnumPaths.cs
(shaders/src/lang/enumPaths.js, reference/01 §8.3). Used by the validator's member /
numeric-enum resolution.
"""


def normalize_member_path(value):
    """List -> non-empty string segments; string -> split on '.', trim, drop empties; else None.
    (Mirrors the two C# overloads in one Python function.)"""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        parts = [seg for seg in value if seg]
        return parts if parts else None
    if isinstance(value, str):
        if not value:
            return None
        parts = [seg.strip() for seg in value.split('.')]
        parts = [p for p in parts if p]
        return parts if parts else None
    return None


def path_starts_with(path, prefix):
    if not prefix:
        return True
    if path is None or len(path) < len(prefix):
        return False
    for i in range(len(prefix)):
        if path[i] != prefix[i]:
            return False
    return True


def apply_enum_prefix(path, prefix):
    """Qualify a short member with its enum name: if `path` already starts with `prefix`
    return a copy; else try each proper suffix of `prefix`; else prepend the whole prefix."""
    if not path:
        return path
    if not prefix:
        return list(path)
    if path_starts_with(path, prefix):
        return list(path)
    for i in range(1, len(prefix)):
        suffix = prefix[i:]
        if path_starts_with(path, suffix):
            result = prefix[0:i]
            result = list(result)
            result.extend(path)
            return result
    concat = list(prefix)
    concat.extend(path)
    return concat
