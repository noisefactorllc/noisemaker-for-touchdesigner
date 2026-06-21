"""enums.py — stdEnums tree + dynamic enum registry. Port of hlsl Compiler/Lang/Enums.cs
(shaders/src/lang/std_enums.js + enums.js, reference/01 §8.1-§8.2).

The enum tree maps dotted member paths (e.g. ["oscKind","sine"]) to integer leaves. The
representation mirrors the reference exactly: a SUBTREE is a plain dict of {name: node}; a LEAF
is `{'type':'Number','value':int}` (so `'type' in node` distinguishes them — reference deepMerge
treats any object with a `type` key as a leaf). Effect `choices` layer on via register_choice;
project (effect) enums take precedence over std (reference/02 §2.5).

PARITY HAZARDS replicated:
  - palette enum values are POSITIONAL indices into share/palettes.json key order, 0-based,
    INCLUDING "none" at index 0 (reference/01 §8.1). The key list is verbatim (56 entries).
  - oscKind.noise == oscKind.noise1d == 5 (reference/01 §8.1).
"""

# share/palettes.json key order (verbatim, 0-based positional enum; "none" IS index 0).
PALETTE_KEYS = [
    "none", "seventiesShirt", "fiveG", "afterimage", "barstow", "bloob",
    "blueSkies", "brushedMetal", "burningSky", "california", "columbia",
    "cottonCandy", "darkSatin", "dealerHat", "dreamy", "eventHorizon",
    "ghostly", "grayscale", "hazySunset", "heatmap", "hypercolor", "jester",
    "justBlue", "justCyan", "justGreen", "justPurple", "justRed", "justYellow",
    "mars", "modesto", "moss", "neptune", "netOfGems", "organic", "papaya",
    "radioactive", "royal", "santaCruz", "sherbet", "sherbetDouble", "silvermane",
    "skykissed", "solaris", "spooky", "springtime", "sproingtime", "sulphur",
    "summoning", "superhero", "toxic", "tropicalia", "tungsten", "vaporwave",
    "vibrant", "vintage", "vintagePhoto",
]


def leaf(value):
    return {'type': 'Number', 'value': value}


def is_leaf(node):
    return isinstance(node, dict) and node.get('type') == 'Number'


def _build_std():
    root = {}
    root['channel'] = {'r': leaf(0), 'g': leaf(1), 'b': leaf(2), 'a': leaf(3)}
    root['color'] = {'mono': leaf(0), 'rgb': leaf(1), 'hsv': leaf(2)}
    root['oscType'] = {
        'sine': leaf(0), 'linear': leaf(1), 'sawtooth': leaf(2), 'sawtoothInv': leaf(3),
        'square': leaf(4), 'noise1d': leaf(5), 'noise2d': leaf(6),
    }
    root['oscKind'] = {
        'sine': leaf(0), 'tri': leaf(1), 'saw': leaf(2), 'sawInv': leaf(3), 'square': leaf(4),
        'noise': leaf(5), 'noise1d': leaf(5), 'noise2d': leaf(6),  # noise == noise1d == 5
    }
    root['midiMode'] = {
        'noteChange': leaf(0), 'gateNote': leaf(1), 'gateVelocity': leaf(2),
        'triggerNote': leaf(3), 'velocity': leaf(4),
    }
    root['audioBand'] = {'low': leaf(0), 'mid': leaf(1), 'high': leaf(2), 'vol': leaf(3)}
    root['palette'] = {key: leaf(idx) for idx, key in enumerate(PALETTE_KEYS)}
    return root


# The std enum tree (built once) and the effect-contributed (project) tree. Module-level,
# mirroring the reference's module-state enum registries (std_enums.js / enums.js).
_STD = _build_std()
_PROJECT = {}


def std():
    return _STD


def project():
    return _PROJECT


def try_get_head(head):
    """Top-level enum head, project before std (reference/02 §2.5 resolveEnum precedence)."""
    if head in _PROJECT:
        return _PROJECT[head]
    if head in _STD:
        return _STD[head]
    return None


def register_choice(path, value):
    """Install a nested enum leaf, e.g. register_choice(["filter","blur","mode","gaussian"], 0).
    Creates intermediate subtrees. Used by EffectRegistry to register effect `choices`."""
    if not path:
        return
    head = _PROJECT.get(path[0])
    if head is None or is_leaf(head):
        head = {}
        _PROJECT[path[0]] = head
    cur = head
    for i in range(1, len(path) - 1):
        nxt = cur.get(path[i])
        if nxt is None or is_leaf(nxt):
            nxt = {}
            cur[path[i]] = nxt
        cur = nxt
    cur[path[-1]] = leaf(value)
