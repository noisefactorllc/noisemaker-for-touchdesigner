"""effect_validator.py — validate an effect definition against the definition
grammar consumed by the port's runtime/registry. Faithful Python port of
noisefactorllc/noisemaker `shaders/src/runtime/effect-validator.js` @
9d3474dfdc6cb737ebb7b2f3598b16d940af1544 (upstream GAP-003).

Contract (identical to the reference): deterministic and side-effect-free.
`validate_effect_definition(def)` returns a list of error strings — [] for
valid input. Never throws for malformed/null/array/non-object containers,
never mutates the input, never invokes lifecycle hooks, and never sorts
globals. Declaration/schema validation is distinct from shader compilation,
GPU capability, and runtime behavior.

Port adaptations (documented deviations, everything else message-identical):
- The reference validates plain definition objects AND `Effect` class
  instances/subclass constructors (JavaScript prototype merging). This port's
  definitions are plain JSON dicts loaded by `EffectRegistry`, so only the
  plain-object path exists; the `Effect`-instance branches are structurally
  N/A. Non-dict inputs get the reference's "must be a plain object or Effect
  instance" diagnosis (with the JS `typeof` name in the message).
- `TOP_LEVEL_KEYS` additionally accepts `starter`: this port's codegen
  (`tools/convert-definitions.mjs`) stamps the manifest-derived starter flag
  onto every converted definition (the C#/Python loader keys on it). The
  reference validator never sees that field because the reference reads
  `definition.js` modules, not converted JSON.
- `resolveStdEnum` walks this port's std enum tree (`enums.std()`), which is a
  verified 1:1 port of `shaders/src/lang/std_enums.js` (same tables, same
  `{type:'Number', value:n}` leaves, same oscKind noise/noise1d alias).
"""

import math
import re

from ..compiler.lang.enums import std as _std_enums

GLOBAL_TYPES = [
    'float', 'int', 'boolean', 'vec2', 'vec3', 'vec4', 'mat3',
    'color', 'surface', 'volume', 'geometry', 'member', 'palette', 'button',
    'string',
]

UI_CONTROLS = ['slider', 'checkbox', 'dropdown', 'color', 'button', 'vector3', 'vec3']

UI_KEYS = ['label', 'control', 'category', 'hidden', 'hint', 'format',
           'buttonLabel', 'enabledBy', 'multiline']

ENABLED_BY_OPS = ['eq', 'neq', 'lt', 'gt', 'gte', 'lte', 'in', 'notIn']

GLOBAL_SPEC_KEYS = [
    'type', 'default', 'uniform', 'define', 'choices', 'enum',
    'min', 'max', 'step', 'zero', 'randMin', 'randMax', 'randChance', 'randChoices',
    'colorModeUniform', 'ui',
]

PASS_KEYS = [
    'name', 'program', 'type', 'entryPoint', 'drawMode', 'drawBuffers',
    'count', 'countUniform', 'repeat', 'blend', 'workgroups',
    'storageBuffers', 'storageTextures', 'viewport', 'conditions',
    'defines', 'uniforms', 'inputs', 'outputs',
]

TEXTURE_SPEC_KEYS = ['width', 'height', 'depth', 'format', 'is3D']

CONDITION_CONTAINER_KEYS = ['runIf', 'skipIf']

DIM_KEYWORDS = ['screen', 'auto', 'input', 'resolution']

FORMATS = ['rgba16f', 'rgba16float', 'rgba8', 'rgba8unorm', 'rgba32f', 'rgba32float']

DRAW_MODES = ['points', 'triangles', 'billboards']

PASS_TYPES = ['render', 'compute']

LAYOUT_ENTRY_KEYS = {'name', 'slot', 'components'}

BYTE_LAYOUT_KEYS = {'name', 'offset', 'size', 'type'}

DIM_SPEC_KEYS = {'param', 'power', 'multiply', 'default', 'paramDefault',
                 'screenDivide', 'scale', 'clamp', 'inputOverride'}

TOP_LEVEL_KEYS = {
    'name', 'namespace', 'func', 'description', 'tags', 'globals', 'passes',
    'textures', 'textures3d', 'shaders', 'uniformLayout', 'uniformLayouts',
    'paramAliases', 'openCategories', 'defaultProgram', 'hidden', 'deprecatedBy',
    'externalTexture', 'externalMesh', 'builtinMeshes', 'outputTex3d', 'outputGeo',
    'state', 'uniforms', 'onInit', 'onUpdate', 'onDestroy', 'asyncInit',
    # Port deviation: see module docstring (converter-stamped starter flag).
    'starter',
}

PIPELINE_INPUTS = {
    'inputTex', 'inputTex3d', 'inputGeo', 'inputXyz', 'inputVel', 'inputRgba',
    'noise', 'midiNoteGrid', 'feedback', 'selfTex', 'outputTex', 'none',
}

PIPELINE_OUTPUTS = {'outputTex', 'outputTex3d', 'outputXyz', 'outputVel', 'outputRgba'}

PERCENT_PATTERN = re.compile(r'^[\d.]+$')

HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')

COMPONENTS_PATTERN = re.compile(r'^[xyzw]{1,4}$')

OUTPUT_SURFACE_PATTERN = re.compile(r'^o[0-7]$')

# Semantic component order consumed by the backends' uniform packing
# ({x: 0, y: 1, z: 2, w: 3}); ASCII codes do not follow xyzw order.
COMPONENT_ORDER = {'x': 0, 'y': 1, 'z': 2, 'w': 3}

# Verbatim from shaders/src/runtime/tags.js TAG_DEFINITIONS keys (VALID_TAGS).
VALID_TAGS = [
    'color', 'distort', 'edges', 'geometric', 'lens', 'noise', 'transform',
    'util', 'sim', '3d', 'audio', 'agents', 'antialiasing', 'artist', 'blend',
    'blur', 'fractal', 'geometry', 'glitch', 'image', 'mesh', 'midi',
    'palette', 'pattern', 'pixel', 'text', 'tiling', 'video',
]


def _is_obj(value):
    return isinstance(value, dict)


def _is_finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _js_typeof(value):
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)):
        return 'number'
    if isinstance(value, str):
        return 'string'
    return 'object'


def resolve_std_enum(path_str):
    """Resolve a std enum path. Returns ('leaf', value) / ('table', node) or None."""
    if not isinstance(path_str, str) or len(path_str) == 0:
        return None
    node = _std_enums()
    for part in path_str.split('.'):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    if isinstance(node, dict) and 'value' in node:
        return ('leaf', node['value'])
    if isinstance(node, dict):
        return ('table', node)
    return None


def _validate_dim_spec(spec, errors, label):
    if isinstance(spec, bool):
        errors.append(f"{label}: dimension must be a positive finite number, keyword, percentage, or dimension expression")
        return
    if isinstance(spec, (int, float)):
        if not _is_finite_number(spec) or spec <= 0:
            errors.append(f"{label}: dimension must be a positive finite number, keyword, percentage, or dimension expression")
        return
    if isinstance(spec, str):
        if spec in DIM_KEYWORDS:
            return
        if spec.endswith('%') and PERCENT_PATTERN.match(spec[:-1]):
            try:
                percent = float(spec[:-1])
            except ValueError:
                percent = float('nan')
            if not _is_finite_number(percent) or percent <= 0:
                errors.append(f"{label}: invalid percentage '{spec}'")
            return
        errors.append(f"{label}: invalid dimension '{spec}'")
        return
    if _is_obj(spec):
        for key in spec:
            if key not in DIM_SPEC_KEYS:
                errors.append(f"{label}: unknown dimension field '{key}'")
        if 'param' in spec:
            if not isinstance(spec['param'], str) or not spec['param']:
                errors.append(f"{label}: \"param\" must be a non-empty string")
            if 'power' in spec and not _is_finite_number(spec['power']):
                errors.append(f"{label}: \"power\" must be a finite number")
            if 'multiply' in spec and not _is_finite_number(spec['multiply']):
                errors.append(f"{label}: \"multiply\" must be a finite number")
            if 'default' in spec and not _is_finite_number(spec['default']):
                errors.append(f"{label}: \"default\" must be a finite number")
            if 'paramDefault' in spec and not _is_finite_number(spec['paramDefault']):
                errors.append(f"{label}: \"paramDefault\" must be a finite number")
            if 'inputOverride' in spec and \
                    (not isinstance(spec['inputOverride'], str) or not spec['inputOverride']):
                errors.append(f"{label}: \"inputOverride\" must be a non-empty string")
            return
        if 'screenDivide' in spec:
            if not isinstance(spec['screenDivide'], str) or not spec['screenDivide']:
                errors.append(f"{label}: \"screenDivide\" must be a non-empty string")
            if 'default' in spec and not _is_finite_number(spec['default']):
                errors.append(f"{label}: \"default\" must be a finite number")
            return
        if 'scale' in spec:
            if not _is_finite_number(spec['scale']):
                errors.append(f"{label}: \"scale\" must be a finite number")
            if 'clamp' in spec:
                clamp = spec['clamp']
                if not _is_obj(clamp):
                    errors.append(f"{label}: \"clamp\" must be an object")
                else:
                    if 'min' in clamp and not _is_finite_number(clamp['min']):
                        errors.append(f"{label}: \"clamp.min\" must be a finite number")
                    if 'max' in clamp and not _is_finite_number(clamp['max']):
                        errors.append(f"{label}: \"clamp.max\" must be a finite number")
                    for key in clamp:
                        if key not in ('min', 'max'):
                            errors.append(f"{label}: unknown clamp field '{key}'")
            return
        errors.append(f"{label}: dimension object must reference \"param\", \"screenDivide\", or \"scale\"")
        return
    errors.append(f"{label}: invalid dimension specification")


def _validate_uniform_layout(layout, errors, label):
    if isinstance(layout, list):
        entries = []
        for i, item in enumerate(layout):
            if _is_obj(item):
                entries.append(item)
            _validate_layout_entry(item, errors, f"{label}[{i}]")
        _check_layout_conflicts(entries, errors, label)
        return
    if not _is_obj(layout):
        errors.append(f"{label}: must be an object or array layout")
        return
    if layout.get('type') == 'byte':
        if not isinstance(layout.get('layout'), list):
            errors.append(f"{label}: byte layout requires a \"layout\" array")
            return
        for key in layout:
            if key not in ('type', 'layout'):
                errors.append(f"{label}: unknown byte-layout field '{key}'")
        byte_entries = []
        for i, entry in enumerate(layout['layout']):
            entry_label = f"{label}.layout[{i}]"
            if not _is_obj(entry):
                errors.append(f"{entry_label}: entry must be an object")
                continue
            for key in entry:
                if key not in BYTE_LAYOUT_KEYS and key != 'components':
                    errors.append(f"{entry_label}: unknown field '{key}'")
            if not isinstance(entry.get('name'), str) or not entry['name']:
                errors.append(f"{entry_label}: missing \"name\" string")
            if not _is_integer(entry.get('offset')) or entry['offset'] < 0:
                errors.append(f"{entry_label}: \"offset\" must be a non-negative integer")
            if not _is_integer(entry.get('size')) or entry['size'] <= 0:
                errors.append(f"{entry_label}: \"size\" must be a positive integer")
            if not isinstance(entry.get('type'), str) or not entry['type']:
                errors.append(f"{entry_label}: missing \"type\" string")
            if isinstance(entry.get('name'), str) and entry['name'] and \
                    _is_integer(entry.get('offset')) and entry['offset'] >= 0 and \
                    _is_integer(entry.get('size')) and entry['size'] > 0:
                byte_entries.append(entry)
        _check_byte_layout_conflicts(byte_entries, errors, label)
        return
    entries = []
    for name, spec in layout.items():
        entry_label = f"{label}['{name}']"
        if not _is_obj(spec):
            errors.append(f"{entry_label}: layout entry must be an object")
            continue
        merged = dict(spec)
        merged['name'] = name
        _validate_layout_entry(merged, errors, entry_label)
        if _is_integer(spec.get('slot')):
            entries.append({'name': name, 'slot': spec['slot'],
                            'components': spec.get('components')})
    _check_layout_conflicts(entries, errors, label)


def _validate_layout_entry(entry, errors, label):
    if not _is_obj(entry):
        errors.append(f"{label}: layout entry must be an object")
        return
    for key in entry:
        if key not in LAYOUT_ENTRY_KEYS:
            errors.append(f"{label}: unknown field '{key}'")
    if not isinstance(entry.get('name'), str) or not entry['name']:
        errors.append(f"{label}: missing \"name\" string")
    if not _is_integer(entry.get('slot')) or entry['slot'] < 0:
        errors.append(f"{label}: \"slot\" must be a non-negative integer")
    components = entry.get('components')
    if not isinstance(components, str) or not COMPONENTS_PATTERN.match(components):
        errors.append(f"{label}: \"components\" must be 1-4 characters from xyzw")
        return
    for i in range(1, len(components)):
        if COMPONENT_ORDER[components[i]] <= COMPONENT_ORDER[components[i - 1]]:
            errors.append(f"{label}: \"components\" '{components}' must be in ascending xyzw order")
            break


def _check_byte_layout_conflicts(entries, errors, label):
    for i in range(len(entries)):
        a = entries[i]
        for j in range(i + 1, len(entries)):
            b = entries[j]
            if a['name'] == b['name']:
                errors.append(f"{label}: duplicate byte-layout entries '{a['name']}' (offsets {a['offset']} and {b['offset']})")
                continue
            a_start = a['offset']
            a_end = a['offset'] + a['size']
            b_start = b['offset']
            b_end = b['offset'] + b['size']
            if a_start < b_end and b_start < a_end:
                errors.append(f"{label}: byte layout conflict: '{a['name']}' (offset {a['offset']}, size {a['size']}) overlaps '{b['name']}' (offset {b['offset']}, size {b['size']})")


def _check_layout_conflicts(entries, errors, label):
    for i in range(len(entries)):
        a = entries[i]
        if not _is_obj(a) or not _is_integer(a.get('slot')) or not isinstance(a.get('components'), str):
            continue
        for j in range(i + 1, len(entries)):
            b = entries[j]
            if not _is_obj(b) or not _is_integer(b.get('slot')) or not isinstance(b.get('components'), str):
                continue
            if a['slot'] != b['slot']:
                continue
            overlap = any(c in b['components'] for c in a['components'])
            if a['components'] == b['components']:
                errors.append(f"{label}: duplicate layout entries '{a['name']}' and '{b['name']}' claim slot {a['slot']} components '{a['components']}'")
            elif overlap:
                errors.append(f"{label}: layout conflict at slot {a['slot']}: '{a['name']}' ({a['components']}) overlaps '{b['name']}' ({b['components']})")


def _validate_enabled_by(cond, errors, label, context):
    if isinstance(cond, str):
        if cond not in context['globalKeys']:
            errors.append(f"{label}: enabledBy references unknown global '{cond}'")
        return
    if not _is_obj(cond):
        errors.append(f"{label}: \"enabledBy\" must be a global name or condition object")
        return
    if 'and' in cond or 'or' in cond:
        for key in cond:
            if key not in ('and', 'or'):
                errors.append(f"{label}: unknown enabledBy field '{key}'")
        for branch in ('and', 'or'):
            if branch in cond:
                if not isinstance(cond[branch], list):
                    errors.append(f"{label}: \"enabledBy.{branch}\" must be an array")
                else:
                    for sub in cond[branch]:
                        _validate_enabled_by(sub, errors, label, context)
        return
    for key in cond:
        if key != 'param' and key not in ENABLED_BY_OPS:
            errors.append(f"{label}: unknown enabledBy field '{key}'")
    if not isinstance(cond.get('param'), str) or not cond['param']:
        errors.append(f"{label}: \"enabledBy\" requires a \"param\" string")
        return
    if cond['param'] not in context['globalKeys']:
        errors.append(f"{label}: enabledBy references unknown global '{cond['param']}'")
    if not any(op in cond for op in ENABLED_BY_OPS):
        errors.append(f"{label}: \"enabledBy\" requires one of eq/neq/lt/gt/in/notIn")
    if 'in' in cond and not isinstance(cond['in'], list):
        errors.append(f"{label}: \"enabledBy.in\" must be an array")
    if 'notIn' in cond and not isinstance(cond['notIn'], list):
        errors.append(f"{label}: \"enabledBy.notIn\" must be an array")


def _validate_ui(ui, errors, label, context):
    if not _is_obj(ui):
        errors.append(f"{label}: must be an object")
        return
    for key in ui:
        if key not in UI_KEYS:
            errors.append(f"{label}: unknown field '{key}'")
    if 'label' in ui and (not isinstance(ui['label'], str) or not ui['label']):
        errors.append(f"{label}: \"label\" must be a non-empty string")
    if 'control' in ui and ui['control'] is not False and ui['control'] not in UI_CONTROLS:
        errors.append(f"{label}: unknown control '{ui['control']}'")
    if 'category' in ui and (not isinstance(ui['category'], str) or not ui['category']):
        errors.append(f"{label}: \"category\" must be a non-empty string")
    if 'hidden' in ui and not isinstance(ui['hidden'], bool):
        errors.append(f"{label}: \"hidden\" must be a boolean")
    if 'multiline' in ui and not isinstance(ui['multiline'], bool):
        errors.append(f"{label}: \"multiline\" must be a boolean")
    for key in ('hint', 'format', 'buttonLabel'):
        if key in ui and (not isinstance(ui[key], str) or not ui[key]):
            errors.append(f"{label}: \"{key}\" must be a non-empty string")
    if 'enabledBy' in ui:
        _validate_enabled_by(ui['enabledBy'], errors, label, context)


def _validate_default(spec, errors, label):
    spec_type = spec['type'] if isinstance(spec.get('type'), str) else None
    value = spec.get('default')

    if spec_type in ('float', 'palette', 'button'):
        if not _is_finite_number(value):
            errors.append(f"{label}: \"default\" must be a finite number")
    elif spec_type == 'int':
        if not _is_finite_number(value) or not _is_integer(value):
            errors.append(f"{label}: \"default\" must be a finite integer")
    elif spec_type == 'boolean':
        if not isinstance(value, bool):
            errors.append(f"{label}: \"default\" must be a boolean")
    elif spec_type in ('vec2', 'vec3', 'vec4', 'mat3'):
        dims = 2 if spec_type == 'vec2' else 3 if spec_type == 'vec3' else 4 if spec_type == 'vec4' else 9
        if not isinstance(value, list) or len(value) != dims or not all(_is_finite_number(v) for v in value):
            errors.append(f"{label}: \"default\" must be an array of {dims} finite numbers")
    elif spec_type == 'color':
        if isinstance(value, list):
            if len(value) != 3 or not all(_is_finite_number(v) for v in value):
                errors.append(f"{label}: \"default\" must be a 3-component color array")
        elif not isinstance(value, str) or not HEX_COLOR.match(value):
            errors.append(f"{label}: \"default\" must be a 3-component color array or '#rrggbb' string")
    elif spec_type == 'string':
        if not isinstance(value, str):
            errors.append(f"{label}: \"default\" must be a string")
    elif spec_type in ('surface', 'volume', 'geometry', 'member'):
        if not isinstance(value, str):
            errors.append(f"{label}: \"default\" must be a string")
        elif spec_type == 'member':
            resolved = resolve_std_enum(value)
            if resolved is None or resolved[0] != 'leaf':
                errors.append(f"{label}: \"default\" '{value}' does not resolve to a std enum value")
    # Unknown type already reported separately.


def _range_dims(spec_type):
    if spec_type == 'vec2':
        return 2
    if spec_type in ('vec3', 'color'):
        return 3
    if spec_type == 'vec4':
        return 4
    if spec_type == 'mat3':
        return 9
    return 1


def _validate_range_bounds(spec, errors, label):
    spec_type = spec['type'] if isinstance(spec.get('type'), str) else None
    dims = _range_dims(spec_type)

    bound_values = {}
    for field in ('min', 'max'):
        value = spec.get(field)
        if value is None and field not in spec:
            continue
        if _is_finite_number(value):
            bound_values[field] = [value]
        elif isinstance(value, list) and len(value) == dims and all(_is_finite_number(v) for v in value):
            bound_values[field] = value
        elif isinstance(value, list):
            errors.append(f"{label}: \"{field}\" must be an array of {dims} finite numbers for type '{spec_type if spec_type is not None else 'unknown'}'")
        else:
            errors.append(f"{label}: \"{field}\" must be a finite number or an array of {dims} finite numbers")

    if 'min' in bound_values and 'max' in bound_values:
        same_form = (len(bound_values['min']) == 1) == (len(bound_values['max']) == 1)
        if not same_form:
            errors.append(f"{label}: \"min\" and \"max\" must both be scalars or both be arrays")
        else:
            mn = bound_values['min']
            mx = bound_values['max']
            for i in range(len(mn)):
                if mn[i] > mx[i]:
                    errors.append(f"{label}: \"min\" must not exceed \"max\"")
                    break

    # Default containment: broadcast scalar bounds, compare componentwise.
    dflt = spec.get('default')
    if isinstance(dflt, list) and all(_is_finite_number(v) for v in dflt) and \
            'min' in bound_values and 'max' in bound_values:
        for i in range(len(dflt)):
            mn = bound_values['min'][0] if len(bound_values['min']) == 1 else bound_values['min'][i]
            mx = bound_values['max'][0] if len(bound_values['max']) == 1 else bound_values['max'][i]
            if dflt[i] < mn or dflt[i] > mx:
                errors.append(f"{label}: default [{', '.join(str(v) for v in dflt)}] is outside the declared range")
                break
    elif _is_finite_number(dflt) and 'min' in bound_values and 'max' in bound_values and \
            len(bound_values['min']) == 1 and len(bound_values['max']) == 1:
        if dflt < bound_values['min'][0] or dflt > bound_values['max'][0]:
            errors.append(f"{label}: default {dflt} is outside the declared range [{bound_values['min'][0]}, {bound_values['max'][0]}]")


def _validate_globals(globals_, errors, context):
    if globals_ is None:
        return
    if not _is_obj(globals_):
        errors.append('"globals" must be an object')
        return

    uniform_owners = {}
    for key, spec in globals_.items():
        label = f"Global '{key}'"
        if not _is_obj(spec):
            errors.append(f"{label}: must be an object")
            continue

        for field in spec:
            if field not in GLOBAL_SPEC_KEYS:
                errors.append(f"{label}: unknown field '{field}'")

        if not spec.get('type'):
            errors.append(f"{label}: Missing \"type\"")
        elif not isinstance(spec['type'], str) or spec['type'] not in GLOBAL_TYPES:
            errors.append(f"{label}: Unknown type '{str(spec['type'])}'")

        if 'default' in spec:
            _validate_default(spec, errors, label)

        if 'min' in spec or 'max' in spec:
            _validate_range_bounds(spec, errors, label)

        for field in ('step', 'zero', 'randMin', 'randMax', 'randChance'):
            if field in spec and not _is_finite_number(spec[field]):
                errors.append(f"{label}: \"{field}\" must be a finite number")
        if 'randChoices' in spec:
            if not isinstance(spec['randChoices'], list) or not all(_is_finite_number(v) for v in spec['randChoices']):
                errors.append(f"{label}: \"randChoices\" must be an array of finite numbers")

        if 'uniform' in spec and (not isinstance(spec['uniform'], str) or not spec['uniform']):
            errors.append(f"{label}: \"uniform\" must be a non-empty string")
        elif isinstance(spec.get('uniform'), str) and spec['uniform']:
            owner = uniform_owners.get(spec['uniform'])
            if owner is not None:
                errors.append(f"{label}: uniform '{spec['uniform']}' conflicts with global '{owner}'")
            else:
                uniform_owners[spec['uniform']] = key

        if 'define' in spec and (not isinstance(spec['define'], str) or not spec['define']):
            errors.append(f"{label}: \"define\" must be a non-empty string")

        if 'colorModeUniform' in spec and (not isinstance(spec['colorModeUniform'], str) or not spec['colorModeUniform']):
            errors.append(f"{label}: \"colorModeUniform\" must be a non-empty string")

        if 'choices' in spec:
            choices = spec['choices']
            if not _is_obj(choices):
                errors.append(f"{label}: \"choices\" must be an object mapping names to values")
            else:
                numeric = []
                string_type = spec.get('type') == 'string'
                for choice_name, value in choices.items():
                    if value is None:
                        continue  # Section headers in dropdown menus.
                    if string_type:
                        # String-typed globals carry string-valued choices
                        # (e.g. font families); consumed by the UI control layer.
                        if not isinstance(value, str):
                            errors.append(f"{label}: choices['{choice_name}'] must be a string for type 'string'")
                        continue
                    if not _is_finite_number(value):
                        errors.append(f"{label}: choices['{choice_name}'] must be a number or null")
                    else:
                        numeric.append(value)
                if numeric and _is_finite_number(spec.get('default')) and spec['default'] not in numeric:
                    errors.append(f"{label}: default {spec['default']} is not among the declared choice values")

        if 'enum' in spec:
            if not isinstance(spec['enum'], str) or not spec['enum']:
                errors.append(f"{label}: \"enum\" must be a non-empty string")
            else:
                resolved = resolve_std_enum(spec['enum'])
                if resolved is None or resolved[0] != 'table':
                    errors.append(f"{label}: enum '{spec['enum']}' does not resolve to a std enum table")

        if 'ui' in spec:
            _validate_ui(spec['ui'], errors, f"{label}.ui", context)


def _validate_texture_map(textures, errors, container_name):
    if textures is None:
        return
    if not _is_obj(textures):
        errors.append(f"\"{container_name}\" must be an object")
        return
    for name, spec in textures.items():
        label = f"Texture '{name}'"
        if not _is_obj(spec):
            errors.append(f"{label}: must be an object")
            continue
        for key in spec:
            if key not in TEXTURE_SPEC_KEYS:
                errors.append(f"{label}: unknown field '{key}'")
        for dim in ('width', 'height'):
            if dim in spec:
                _validate_dim_spec(spec[dim], errors, f"{label}.{dim}")
        if 'depth' in spec and (not _is_finite_number(spec['depth']) or spec['depth'] <= 0):
            errors.append(f"{label}: \"depth\" must be a positive finite number")
        if 'format' in spec:
            if not isinstance(spec['format'], str) or spec['format'] not in FORMATS:
                errors.append(f"{label}: unknown format '{spec['format']}'")
        if 'is3D' in spec and not isinstance(spec['is3D'], bool):
            errors.append(f"{label}: \"is3D\" must be a boolean")


def _references_global(name, context):
    return name in context['globalKeys'] or name in context['globalUniformNames']


def _validate_pass(source, pass_, index, errors, context):
    label = f"Pass {index}"
    if not _is_obj(pass_):
        errors.append(f"{label}: must be an object")
        return

    if not pass_.get('program') or not isinstance(pass_.get('program'), str):
        errors.append(f"{label}: Missing \"program\" string")

    for key in pass_:
        if key not in PASS_KEYS:
            errors.append(f"{label}: unknown field '{key}'")

    if 'name' in pass_ and (not isinstance(pass_['name'], str) or not pass_['name']):
        errors.append(f"{label}: \"name\" must be a non-empty string")
    if 'entryPoint' in pass_ and (not isinstance(pass_['entryPoint'], str) or not pass_['entryPoint']):
        errors.append(f"{label}: \"entryPoint\" must be a non-empty string")
    if 'type' in pass_ and pass_['type'] not in PASS_TYPES:
        errors.append(f"{label}: unknown pass type '{pass_['type']}'")
    if 'drawMode' in pass_ and pass_['drawMode'] not in DRAW_MODES:
        errors.append(f"{label}: unknown drawMode '{pass_['drawMode']}'")
    if 'drawBuffers' in pass_ and \
            (not _is_integer(pass_['drawBuffers']) or pass_['drawBuffers'] < 1):
        errors.append(f"{label}: \"drawBuffers\" must be a positive integer")
    if 'count' in pass_:
        count = pass_['count']
        if isinstance(count, str):
            if count not in ('auto', 'screen', 'input'):
                errors.append(f"{label}: unknown count '{count}'")
        elif not _is_integer(count) or count < 1:
            errors.append(f"{label}: \"count\" must be a positive integer, 'auto', 'screen', or 'input'")
    if 'countUniform' in pass_:
        if not isinstance(pass_['countUniform'], str) or not pass_['countUniform']:
            errors.append(f"{label}: \"countUniform\" must be a non-empty string")
        elif not _references_global(pass_['countUniform'], context):
            errors.append(f"{label}: countUniform '{pass_['countUniform']}' does not reference a declared global")
    if 'repeat' in pass_:
        repeat = pass_['repeat']
        if isinstance(repeat, str):
            if not repeat:
                errors.append(f"{label}: \"repeat\" string must name a uniform")
        elif not _is_integer(repeat) or repeat < 1:
            errors.append(f"{label}: \"repeat\" must be a positive integer or a uniform name string")
    if 'blend' in pass_:
        blend = pass_['blend']
        if not isinstance(blend, bool) and \
                (not isinstance(blend, list) or len(blend) != 2 or
                 not all(isinstance(v, str) and v for v in blend)):
            errors.append(f"{label}: \"blend\" must be a boolean or [src, dst] factor strings")
    if 'workgroups' in pass_:
        workgroups = pass_['workgroups']
        if not isinstance(workgroups, list) or len(workgroups) < 1 or len(workgroups) > 3 or \
                not all(_is_finite_number(v) or (isinstance(v, str) and v) for v in workgroups):
            errors.append(f"{label}: \"workgroups\" must be an array of 1-3 numbers or uniform names")
    if 'storageBuffers' in pass_ and not _is_obj(pass_['storageBuffers']):
        errors.append(f"{label}: \"storageBuffers\" must be an object")
    if 'storageTextures' in pass_ and not _is_obj(pass_['storageTextures']):
        errors.append(f"{label}: \"storageTextures\" must be an object")
    if 'viewport' in pass_:
        viewport = pass_['viewport']
        if not _is_obj(viewport):
            errors.append(f"{label}: \"viewport\" must be an object")
        else:
            for key in viewport:
                if key in ('width', 'height'):
                    _validate_dim_spec(viewport[key], errors, f"{label}.viewport.{key}")
                elif key in ('x', 'y', 'w', 'h'):
                    if not _is_finite_number(viewport[key]):
                        errors.append(f"{label}.viewport.{key} must be a finite number")
                else:
                    errors.append(f"{label}.viewport: unknown field '{key}'")
    if 'conditions' in pass_:
        conditions = pass_['conditions']
        if not _is_obj(conditions):
            errors.append(f"{label}: \"conditions\" must be an object")
        else:
            for key in conditions:
                if key not in CONDITION_CONTAINER_KEYS:
                    errors.append(f"{label}.conditions: unknown field '{key}'")
            for list_key in CONDITION_CONTAINER_KEYS:
                if list_key not in conditions:
                    continue
                conditions_list = conditions[list_key]
                if not isinstance(conditions_list, list):
                    errors.append(f"{label}.conditions.{list_key} must be an array")
                    continue
                for condition in conditions_list:
                    if not _is_obj(condition):
                        errors.append(f"{label}.conditions.{list_key}: condition must be an object")
                        continue
                    for key in condition:
                        if key not in ('uniform', 'equals'):
                            errors.append(f"{label}.conditions.{list_key}: unknown condition field '{key}'")
                    if not isinstance(condition.get('uniform'), str) or not condition['uniform']:
                        errors.append(f"{label}.conditions.{list_key}: \"uniform\" must be a non-empty string")
                    elif not _references_global(condition['uniform'], context):
                        errors.append(f"{label}.conditions.{list_key}: uniform '{condition['uniform']}' does not reference a declared global")
                    if 'equals' not in condition:
                        errors.append(f"{label}.conditions.{list_key}: condition requires an \"equals\" value")

    if 'uniforms' in pass_:
        uniforms = pass_['uniforms']
        if not _is_obj(uniforms):
            errors.append(f"{label}: \"uniforms\" must be an object")
        else:
            for uniform_name, value in uniforms.items():
                # Numeric literals are preserved; strings name runtime uniforms.
                if not _is_finite_number(value) and (not isinstance(value, str) or not value):
                    errors.append(f"{label}: uniforms['{uniform_name}'] must be a finite number or a non-empty string")

    if 'defines' in pass_:
        defines = pass_['defines']
        if not _is_obj(defines):
            errors.append(f"{label}: \"defines\" must be an object")
        else:
            for key, value in defines.items():
                if not isinstance(value, str) and not _is_finite_number(value):
                    errors.append(f"{label}: defines['{key}'] must be a string or finite number")

    declared_textures = set(source.get('textures') or {}) | set(source.get('textures3d') or {})

    if 'inputs' in pass_:
        inputs = pass_['inputs']
        if not _is_obj(inputs):
            errors.append(f"{label}: \"inputs\" must be an object")
        else:
            for uniform_name, tex_ref in inputs.items():
                if not isinstance(tex_ref, str) or not tex_ref:
                    errors.append(f"{label}: inputs['{uniform_name}'] must be a non-empty texture reference string")
                    continue
                if tex_ref in PIPELINE_INPUTS:
                    continue
                if OUTPUT_SURFACE_PATTERN.match(tex_ref):
                    continue
                if tex_ref.startswith('global_'):
                    continue
                if tex_ref in declared_textures:
                    continue
                if tex_ref in context['globalKeys']:
                    continue
                if isinstance(source.get('externalTexture'), str) and tex_ref == source['externalTexture']:
                    continue
                errors.append(f"{label}: inputs['{uniform_name}'] references unsupported texture '{tex_ref}'")

    if 'outputs' in pass_:
        outputs = pass_['outputs']
        if not _is_obj(outputs):
            errors.append(f"{label}: \"outputs\" must be an object")
        else:
            for attachment, tex_ref in outputs.items():
                if not isinstance(tex_ref, str) or not tex_ref:
                    errors.append(f"{label}: outputs['{attachment}'] must be a non-empty texture reference string")
                    continue
                if tex_ref in PIPELINE_OUTPUTS:
                    continue
                if tex_ref.startswith('global_'):
                    continue
                if tex_ref in declared_textures:
                    continue
                errors.append(f"{label}: outputs['{attachment}'] references unsupported output '{tex_ref}'")


def validate_effect_definition(defn):
    """Validate an effect definition dict; returns a list of error strings ([] = valid).

    Python port of `validateEffectDefinition` (effect-validator.js @9d3474dfdc6c).
    See the module docstring for the documented port deviations (Effect-class
    instances are JS-only; `starter` is a port-side converter field).
    """
    errors = []

    if not defn:
        return ['Effect definition is null or undefined']

    if isinstance(defn, list):
        errors.append('Effect definition must be a plain object or Effect instance, not an array')
        return errors

    if not isinstance(defn, dict):
        errors.append(f"Effect definition must be a plain object or Effect instance, not {_js_typeof(defn)}")
        return errors

    # Effect instances and subclass constructors carry legitimate extra state
    # (runtime caches, counters, prototype methods, loaded shaders), so
    # top-level unknown-field diagnosis runs on plain definition objects only.
    # Nested declarative containers (globals/passes/textures/ui) are fully
    # diagnosed on every input shape. (JS-only distinction — this port only
    # receives plain definition dicts.)
    source = defn
    diagnose_top_level_unknowns = True

    context = {
        'globalKeys': set(source['globals'].keys()) if _is_obj(source.get('globals')) else set(),
        'globalUniformNames': set(),
    }
    if _is_obj(source.get('globals')):
        for spec in source['globals'].values():
            if _is_obj(spec) and isinstance(spec.get('uniform'), str) and spec['uniform']:
                context['globalUniformNames'].add(spec['uniform'])

    # --- name (existing message preserved) ---
    if not isinstance(source.get('name'), str) or not source['name']:
        errors.append('Missing or invalid "name" property')

    # --- simple typed metadata ---
    if 'namespace' in source and (not isinstance(source['namespace'], str) or not source['namespace']):
        errors.append('"namespace" must be a non-empty string')
    if 'func' in source and (not isinstance(source['func'], str) or not source['func']):
        errors.append('"func" must be a non-empty string')
    if 'description' in source and not isinstance(source['description'], str):
        errors.append('"description" must be a string')
    if 'tags' in source:
        tags = source['tags']
        if not isinstance(tags, list):
            errors.append('"tags" must be an array of tag strings')
        else:
            for tag in tags:
                if not isinstance(tag, str) or not tag:
                    errors.append('"tags" must contain non-empty strings')
                elif tag not in VALID_TAGS:
                    errors.append(f"Unknown tag '{tag}'")
    if 'openCategories' in source:
        categories = source['openCategories']
        if not isinstance(categories, list) or not all(isinstance(c, str) for c in categories):
            errors.append('"openCategories" must be an array of strings')
    if 'defaultProgram' in source and not isinstance(source['defaultProgram'], str):
        errors.append('"defaultProgram" must be a string')
    if 'hidden' in source and not isinstance(source['hidden'], bool):
        errors.append('"hidden" must be a boolean')
    if 'deprecatedBy' in source and (not isinstance(source['deprecatedBy'], str) or not source['deprecatedBy']):
        errors.append('"deprecatedBy" must be a non-empty string')
    if 'externalTexture' in source and (not isinstance(source['externalTexture'], str) or not source['externalTexture']):
        errors.append('"externalTexture" must be a non-empty string')
    if 'externalMesh' in source and (not isinstance(source['externalMesh'], str) or not source['externalMesh']):
        errors.append('"externalMesh" must be a non-empty string')
    if 'builtinMeshes' in source:
        builtin_meshes = source['builtinMeshes']
        if not _is_obj(builtin_meshes):
            errors.append('"builtinMeshes" must be an object')
        else:
            for key, value in builtin_meshes.items():
                if not isinstance(value, str) or not value:
                    errors.append(f"builtinMeshes['{key}'] must be a non-empty string")
    if 'outputTex3d' in source and (not isinstance(source['outputTex3d'], str) or not source['outputTex3d']):
        errors.append('"outputTex3d" must be a non-empty string')
    if 'outputGeo' in source and (not isinstance(source['outputGeo'], str) or not source['outputGeo']):
        errors.append('"outputGeo" must be a non-empty string')

    # --- lifecycle hooks must be functions ---
    # (Definitions arriving through this port's registry are JSON dicts; a
    # hook present as anything callable-bearing JSON is invalid. JSON cannot
    # carry functions, so any present hook value is a schema error, matching
    # the reference's "must be a function" diagnosis for non-function values.)
    for hook in ('onInit', 'onUpdate', 'onDestroy', 'asyncInit'):
        value = source.get(hook)
        if value is not None and not callable(value):
            errors.append(f'"{hook}" must be a function')

    # --- globals ---
    _validate_globals(source.get('globals'), errors, context)

    # --- passes ---
    passes = source.get('passes')
    if not passes or not isinstance(passes, list) or len(passes) == 0:
        errors.append('Missing or empty "passes" array')
    else:
        for index, pass_ in enumerate(passes):
            _validate_pass(source, pass_, index, errors, context)

    # --- textures ---
    _validate_texture_map(source.get('textures'), errors, 'textures')
    _validate_texture_map(source.get('textures3d'), errors, 'textures3d')

    # --- shaders ---
    if 'shaders' in source:
        shaders = source['shaders']
        if not _is_obj(shaders):
            errors.append('"shaders" must be an object mapping program names to shader maps')
        else:
            for prog, shader_map in shaders.items():
                if not _is_obj(shader_map):
                    errors.append(f"shaders['{prog}'] must be an object")

    # --- uniform layouts ---
    if 'uniformLayout' in source:
        _validate_uniform_layout(source['uniformLayout'], errors, 'uniformLayout')
    if 'uniformLayouts' in source:
        uniform_layouts = source['uniformLayouts']
        if not _is_obj(uniform_layouts):
            errors.append('"uniformLayouts" must be an object mapping program names to layouts')
        else:
            for prog, layout in uniform_layouts.items():
                _validate_uniform_layout(layout, errors, f"uniformLayouts['{prog}']")

    # --- param aliases ---
    if 'paramAliases' in source:
        param_aliases = source['paramAliases']
        if not _is_obj(param_aliases):
            errors.append('"paramAliases" must be an object mapping aliases to global names')
        else:
            for alias, target in param_aliases.items():
                if not isinstance(target, str) or not target:
                    errors.append(f"paramAliases['{alias}'] must be a non-empty string")
                elif target not in context['globalKeys']:
                    errors.append(f"paramAliases['{alias}'] references unknown global '{target}'")

    # --- top-level unknown-field diagnosis (plain definition objects only) ---
    if diagnose_top_level_unknowns:
        for key in defn:
            if key not in TOP_LEVEL_KEYS:
                errors.append(f"Unknown definition field '{key}'")

    return errors
