"""Deterministic recursive oscillator, MIDI, and audio uniform automation.

The host owns MIDI/audio capture and resets. MPE state supplies get_zone_voice
(or getZoneVoice), returning the selected held note and its channel. MIDI
expression arrays accept integer or string-keyed dictionaries. Default audio
channels come from get_device_channel_state (or getDeviceChannelState), or a
snapshot's defaultChannels dictionary/one-based-channel list. Unavailable
selected inputs return the descriptor minimum rather than aggregate state.
"""

import json
import math
import os
import time as clock


_TAU = math.pi * 2
_MAX_AUTOMATION_DEPTH = 8
_AUTOMATION_FIELD_RANGES = {
    'unit': {'min': 0, 'max': 1},
    'oscillatorSpeed': {'min': -20, 'max': 20},
    'oscillatorOffset': {'min': -1, 'max': 1},
    'oscillatorSeed': {'min': 1, 'max': 9999},
    'midiSensitivity': {'min': 0, 'max': 10},
}
_INTEGRATION_RULES = (
    (
        (-0.9894009349916499, -0.9445750230732326, -0.8656312023878318,
         -0.755404408355003, -0.6178762444026438, -0.4580167776572274,
         -0.2816035507792589, -0.0950125098376374, 0.0950125098376374,
         0.2816035507792589, 0.4580167776572274, 0.6178762444026438,
         0.755404408355003, 0.8656312023878318, 0.9445750230732326,
         0.9894009349916499),
        (0.0271524594117541, 0.0622535239386479, 0.0951585116824928,
         0.1246289712555339, 0.1495959888165767, 0.1691565193950025,
         0.1826034150449236, 0.1894506104550685, 0.1894506104550685,
         0.1826034150449236, 0.1691565193950025, 0.1495959888165767,
         0.1246289712555339, 0.0951585116824928, 0.0622535239386479,
         0.0271524594117541),
    ),
    (
        (-0.9602898564975363, -0.7966664774136267, -0.525532409916329,
         -0.1834346424956498, 0.1834346424956498, 0.525532409916329,
         0.7966664774136267, 0.9602898564975363),
        (0.1012285362903763, 0.2223810344533745, 0.3137066458778873,
         0.362683783378362, 0.362683783378362, 0.3137066458778873,
         0.2223810344533745, 0.1012285362903763),
    ),
    (
        (-0.8611363115940526, -0.3399810435848563, 0.3399810435848563,
         0.8611363115940526),
        (0.3478548451374538, 0.6521451548625461, 0.6521451548625461,
         0.3478548451374538),
    ),
    ((-0.5773502691896257, 0.5773502691896257), (1, 1)),
)


def _finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _member(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _method(value, *names):
    for name in names:
        candidate = _member(value, name)
        if callable(candidate):
            return candidate
    return None


def automation_type(value):
    if not isinstance(value, dict):
        return None
    direct = value.get('type')
    if direct in ('Oscillator', 'Midi', 'Audio'):
        return direct
    ast = value.get('_ast')
    nested = ast.get('type') if isinstance(ast, dict) else None
    return nested if nested in ('Oscillator', 'Midi', 'Audio') else None


def _scale(value, value_range):
    if not isinstance(value_range, dict):
        return value
    minimum = value_range.get('min')
    maximum = value_range.get('max')
    if not _finite_number(minimum) or not _finite_number(maximum):
        return value
    return minimum + value * (maximum - minimum)


def _resolve_field(value, normalized_time, value_range, external_state, depth,
                   stack, fallback, wall_time_ms):
    if automation_type(value):
        return _evaluate(value, normalized_time, value_range, external_state,
                         depth + 1, stack, wall_time_ms)
    return value if _finite_number(value) else fallback


def _osc_sine(value):
    return (1 - math.cos(value * _TAU)) * 0.5


def _osc_tri(value):
    fraction = value - math.floor(value)
    return 1 - abs(fraction * 2 - 1)


def _osc_saw(value):
    return value - math.floor(value)


def _osc_saw_inv(value):
    return 1 - _osc_saw(value)


def _osc_square(value):
    return 1 if _osc_saw(value) >= 0.5 else 0


def _hash21(px, py, seed):
    x = math.fmod(px * 234.34 + seed, 1)
    y = math.fmod(py * 435.345 + seed, 1)
    if x < 0:
        x += 1
    if y < 0:
        y += 1
    return math.fmod(x * y * (x + y + (x + y) * 34.23), 1)


def _noise2d(px, py, seed):
    ix, iy = math.floor(px), math.floor(py)
    fx, fy = px - ix, py - iy
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = _hash21(ix, iy, seed)
    b = _hash21(ix + 1, iy, seed)
    c = _hash21(ix, iy + 1, seed)
    d = _hash21(ix + 1, iy + 1, seed)
    return (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy)
            + c * (1 - fx) * fy + d * fx * fy)


def _osc_noise(value, seed):
    angle = math.fmod(value, 1) * _TAU
    loop_x, loop_y = math.cos(angle) * 2, math.sin(angle) * 2
    return (_noise2d(loop_x + seed, loop_y + seed, seed)
            + _noise2d(loop_x + seed * 2, loop_y + seed * 2, seed)) * 0.5


def _osc_primitive(osc_type, value):
    whole = math.floor(value)
    fraction = value - whole
    if osc_type == 0:
        return value * 0.5 - math.sin(value * _TAU) / (2 * _TAU)
    if osc_type == 1:
        partial = (fraction * fraction if fraction < 0.5
                   else 2 * fraction - fraction * fraction - 0.5)
        return whole * 0.5 + partial
    if osc_type == 2:
        return whole * 0.5 + fraction * fraction * 0.5
    if osc_type == 3:
        return value - (whole * 0.5 + fraction * fraction * 0.5)
    if osc_type == 4:
        return whole * 0.5 + max(0, fraction - 0.5)
    return None


def _can_integrate_exactly(config):
    return (config.get('oscType') in range(5)
            and all(_finite_number(config.get(field))
                    for field in ('min', 'max', 'speed', 'offset', 'seed')))


def _integrate_simple(config, normalized_time):
    speed = config['speed']
    if speed == 0:
        return _evaluate_oscillator(config, 0, {}, 0, set(), None) * normalized_time
    start = _osc_primitive(config['oscType'], config['offset'])
    end = _osc_primitive(config['oscType'], config['offset'] + speed * normalized_time)
    return (config['min'] * normalized_time
            + (config['max'] - config['min']) * (end - start) / speed)


def _has_dynamic_fields(config):
    fields = ('min', 'max', 'sensitivity') if automation_type(config) == 'Midi' else ('min', 'max')
    return any(automation_type(config.get(field)) for field in fields)


def _integrate(config, normalized_time, value_range, external_state, depth,
               stack, wall_time_ms):
    config_type = automation_type(config)
    if config_type == 'Oscillator' and _can_integrate_exactly(config):
        integral = _integrate_simple(config, normalized_time)
    elif config_type in ('Midi', 'Audio') and not _has_dynamic_fields(config):
        integral = (_evaluate(config, normalized_time, None, external_state,
                              depth + 1, stack, wall_time_ms) * normalized_time)
    else:
        nodes, weights = _INTEGRATION_RULES[min(depth, len(_INTEGRATION_RULES) - 1)]
        midpoint = normalized_time * 0.5
        half_width = normalized_time * 0.5
        integral = half_width * sum(
            weight * _evaluate(config, midpoint + half_width * node, None,
                               external_state, depth + 1, stack, wall_time_ms)
            for node, weight in zip(nodes, weights)
        )
    if not isinstance(value_range, dict):
        return integral
    minimum, maximum = value_range.get('min'), value_range.get('max')
    if not _finite_number(minimum) or not _finite_number(maximum):
        return integral
    return minimum * normalized_time + integral * (maximum - minimum)


def _evaluate_oscillator(config, normalized_time, external_state, depth,
                         stack, wall_time_ms):
    minimum = _resolve_field(config.get('min'), normalized_time,
                             _AUTOMATION_FIELD_RANGES['unit'], external_state,
                             depth, stack, 0, wall_time_ms)
    maximum = _resolve_field(config.get('max'), normalized_time,
                             _AUTOMATION_FIELD_RANGES['unit'], external_state,
                             depth, stack, 1, wall_time_ms)
    offset = _resolve_field(config.get('offset'), normalized_time,
                            _AUTOMATION_FIELD_RANGES['oscillatorOffset'], external_state,
                            depth, stack, 0, wall_time_ms)
    seed = _resolve_field(config.get('seed'), normalized_time,
                          _AUTOMATION_FIELD_RANGES['oscillatorSeed'], external_state,
                          depth, stack, 1, wall_time_ms)
    speed = config.get('speed')
    phase = (_integrate(speed, normalized_time,
                        _AUTOMATION_FIELD_RANGES['oscillatorSpeed'], external_state,
                        depth, stack, wall_time_ms)
             if automation_type(speed)
             else normalized_time * (speed if _finite_number(speed) else 1))
    raw_by_type = {
        0: _osc_sine, 1: _osc_tri, 2: _osc_saw,
        3: _osc_saw_inv, 4: _osc_square,
    }
    osc_type = config.get('oscType')
    raw = (_osc_noise(phase + offset, seed) if osc_type == 5
           else raw_by_type.get(osc_type, lambda _value: 0)(phase + offset))
    return minimum + raw * (maximum - minimum)


def _selected_entry(state, config, collection_name):
    identity = config.get('id')
    name = config.get('name')
    if not identity and not name:
        return state
    collection = _member(state, collection_name, {})
    if not isinstance(collection, dict):
        return None
    if identity:
        entry = collection.get(identity)
        if entry is None or _member(entry, 'connected', True) is not True:
            return None
        return _member(entry, 'state', entry)
    matches = [entry for entry in collection.values()
               if _member(entry, 'connected', True) is True
               and _member(entry, 'name') == name]
    if len(matches) != 1:
        return None
    return _member(matches[0], 'state', matches[0])


def _selected_midi_state(config, midi_state):
    get_port = _method(midi_state, 'get_port_state', 'getPortState')
    return get_port(config) if get_port else _selected_entry(midi_state, config, 'ports')


def _midi_channel(state, channel_number):
    get_channel = _method(state, 'get_channel', 'getChannel')
    if get_channel:
        return get_channel(channel_number)
    channels = _member(state, 'channels')
    if _finite_number(channel_number) and float(channel_number).is_integer():
        channel_number = int(channel_number)
    if isinstance(channels, dict):
        return channels.get(str(channel_number), channels.get(channel_number,
                            channels.get('1', channels.get(1))))
    if isinstance(channels, (list, tuple)):
        index = channel_number - 1 if isinstance(channel_number, int) else 0
        if 0 <= index < len(channels):
            return channels[index]
        return channels[0] if channels else None
    return None


def _evaluate_midi(config, midi_state, wall_time_ms, minimum, maximum, sensitivity):
    if config.get("_invalid") or midi_state is None:
        return minimum

    def integer_in(value, low, high):
        return _finite_number(value) and float(value).is_integer() and low <= value <= high

    def indexed(values, key, default=0):
        if _finite_number(key) and float(key).is_integer():
            key = int(key)
        if isinstance(values, dict):
            return values.get(key, values.get(str(key), default))
        if isinstance(values, (list, tuple)) and integer_in(key, 0, len(values) - 1):
            return values[int(key)]
        return default

    mode = config.get("mode", 4)
    has_zone = "zone" in config
    if has_zone and ("channel" in config or not integer_in(config["zone"], 0, 1)):
        return minimum
    if "members" in config and (not has_zone or not integer_in(config["members"], 1, 15)):
        return minimum
    if not has_zone and mode >= 5 and not integer_in(config.get("channel"), 1, 16):
        return minimum
    voice = None
    if has_zone:
        get_voice = _method(midi_state, "get_zone_voice", "getZoneVoice")
        voice = get_voice(config) if get_voice else None
        if voice is None:
            return minimum
        channel = _member(voice, "channel")
    else:
        channel = _midi_channel(midi_state, config.get("channel"))
    if channel is None:
        return minimum
    note = voice if voice is not None else channel
    gate = 1 if voice is not None else _member(note, "gate", 0)
    key = _member(note, "key", 0)
    velocity = _member(note, "velocity", 0)
    if mode in (5, 6):
        cc = config.get("cc", 1)
        if not integer_in(cc, 0, 31 if mode == 6 else 127):
            return minimum
        raw = indexed(_member(channel, "cc14" if mode == 6 else "cc"), cc)
        return minimum + raw / (16383 if mode == 6 else 127) * (maximum - minimum)
    if mode == 7:
        parameter = config.get("nrpn")
        if not integer_in(parameter, 0, 16382):
            return minimum
        raw = indexed(_member(channel, "nrpn"), parameter)
        return minimum + raw / 16383 * (maximum - minimum)
    if mode == 8:
        return minimum + _member(channel, "pitchBend", 8192) / 16383 * (maximum - minimum)
    if mode == 9:
        return minimum + _member(channel, "pressure", 0) / 127 * (maximum - minimum)
    if mode == 10:
        return minimum + indexed(_member(channel, "polyPressure"), key) / 127 * (maximum - minimum)
    raw = 0
    if mode == 0:
        raw = key
    elif mode == 1 and gate == 1:
        raw = key
    elif mode == 2 and gate == 1:
        raw = velocity
    elif mode in (3, 4) and gate == 1:
        raw = key if mode == 3 else velocity
        elapsed = wall_time_ms - _member(note, "time", wall_time_ms)
        decay = min(1, elapsed * sensitivity * 0.001)
        raw *= 1 - decay
    return minimum + (raw / 127) * (maximum - minimum)


def _has_audio_selector(config):
    source = config.get('_ast')
    if not isinstance(source, dict) or source.get('type') != 'Audio':
        source = config
    return any(field in config or field in source for field in ('name', 'id', 'channel'))


def _valid_audio_selector(config):
    source = config.get('_ast')
    if not isinstance(source, dict) or source.get('type') != 'Audio':
        source = config
    if any(field in source and field not in config for field in ('name', 'id', 'channel')):
        return False
    for field in ('name', 'id'):
        if field in config and (not isinstance(config[field], str) or not config[field]):
            return False
    if 'id' in config and 'name' not in config:
        return False
    channel = config.get('channel')
    return _finite_number(channel) and float(channel).is_integer() and 1 <= channel <= 32


def _selected_audio_state(config, audio_state):
    if not _has_audio_selector(config):
        return audio_state
    if not _valid_audio_selector(config):
        return None
    get_selected = _method(audio_state, 'get_device_channel_state', 'getDeviceChannelState')
    if get_selected:
        return get_selected(config)
    channel_number = int(config['channel'])
    if 'name' not in config:
        channels = _member(audio_state, 'defaultChannels')
    else:
        entry = _selected_entry(audio_state, config, 'devices')
        channels = _member(entry, 'channels')
    if isinstance(channels, dict):
        return channels.get(str(channel_number), channels.get(channel_number))
    if isinstance(channels, (list, tuple)) and channel_number <= len(channels):
        return channels[channel_number - 1]
    return None


def _evaluate_audio(config, state, minimum, maximum):
    if config.get('_invalid') or state is None:
        return minimum
    band = config.get('band')
    if band == 0:
        raw = _member(state, 'low', 0)
    elif band == 1:
        raw = _member(state, 'mid', 0)
    elif band == 2:
        raw = _member(state, 'high', 0)
    elif band == 3:
        raw = _member(state, 'vol', 0)
    elif band == 4:
        if _member(state, 'rawReady', _member(state, 'raw_ready', False)) is not True:
            return minimum
        raw = (max(-1, min(1, _member(state, 'raw', 0) or 0)) + 1) * 0.5
    else:
        raw = 0
    raw = max(0, min(1, raw))
    return minimum + raw * (maximum - minimum)


def _evaluate(config, normalized_time, value_range, external_state, depth=0,
              stack=None, wall_time_ms=None):
    if stack is None:
        stack = set()
    identity = id(config)
    if (not automation_type(config) or depth > _MAX_AUTOMATION_DEPTH
            or identity in stack):
        return _scale(0, value_range)
    if wall_time_ms is None:
        wall_time_ms = clock.time() * 1000
    stack.add(identity)
    try:
        config_type = automation_type(config)
        if config_type == 'Oscillator':
            value = _evaluate_oscillator(config, normalized_time, external_state,
                                         depth, stack, wall_time_ms)
        elif config_type == 'Midi':
            minimum = _resolve_field(config.get('min'), normalized_time,
                                     _AUTOMATION_FIELD_RANGES['unit'], external_state,
                                     depth, stack, 0, wall_time_ms)
            maximum = _resolve_field(config.get('max'), normalized_time,
                                     _AUTOMATION_FIELD_RANGES['unit'], external_state,
                                     depth, stack, 1, wall_time_ms)
            sensitivity = _resolve_field(
                config.get('sensitivity'), normalized_time,
                _AUTOMATION_FIELD_RANGES['midiSensitivity'], external_state,
                depth, stack, 1, wall_time_ms)
            value = _evaluate_midi(
                config, _selected_midi_state(config, _member(external_state, 'midi')),
                wall_time_ms, minimum, maximum, sensitivity)
        elif config.get('_invalid'):
            value = config.get('min') if _finite_number(config.get('min')) else 0
        else:
            minimum = _resolve_field(config.get('min'), normalized_time,
                                     _AUTOMATION_FIELD_RANGES['unit'], external_state,
                                     depth, stack, 0, wall_time_ms)
            maximum = _resolve_field(config.get('max'), normalized_time,
                                     _AUTOMATION_FIELD_RANGES['unit'], external_state,
                                     depth, stack, 1, wall_time_ms)
            value = _evaluate_audio(
                config, _selected_audio_state(config, _member(external_state, 'audio')),
                minimum, maximum)
    finally:
        stack.remove(identity)
    return _scale(value, value_range)


def resolve_uniform_value(value, normalized_time, param_spec=None, external_state=None):
    """Resolve an automation descriptor at normalized time, scaled to its consumer."""
    if not automation_type(value):
        return value
    return _evaluate(value, normalized_time, param_spec, external_state or {})


def resolve_uniforms(uniforms, uniform_specs, normalized_time, external_state=None):
    return {
        name: resolve_uniform_value(value, normalized_time,
                                    (uniform_specs or {}).get(name), external_state)
        for name, value in (uniforms or {}).items()
    }


def get_audio_input_requirements(graph, effects_root):
    """Return legacy and selected audio captures required by a render graph."""
    result = {'needsLegacy': False, 'needsLegacyRaw': False, 'selected': []}
    selected_keys = {}
    visited = set()

    def visit(value):
        if not isinstance(value, (dict, list, tuple)) or id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value, dict) and automation_type(value) == 'Audio':
            selector_intent = _has_audio_selector(value)
            band = value.get('band')
            valid_band = (value.get('_invalid') is not True and _finite_number(band)
                          and float(band).is_integer() and 0 <= band <= 4)
            if not valid_band:
                return
            visit(value.get('min'))
            visit(value.get('max'))
            name, channel = value.get('name'), value.get('channel')
            if _valid_audio_selector(value):
                requirement = {
                    'id': value.get('id') if isinstance(value.get('id'), str)
                    and value.get('id') else None,
                    'name': name,
                    'channel': channel,
                    'needsRaw': band == 4,
                }
                key = (requirement['id'], name, channel)
                if key in selected_keys:
                    if requirement['needsRaw']:
                        result['selected'][selected_keys[key]]['needsRaw'] = True
                else:
                    selected_keys[key] = len(result['selected'])
                    result['selected'].append(requirement)
            elif not selector_intent:
                result['needsLegacy'] = True
                result['needsLegacyRaw'] = result['needsLegacyRaw'] or band == 4
            return
        values = value if isinstance(value, (list, tuple)) else (
            item for key, item in value.items() if key != '_ast')
        for item in values:
            visit(item)

    for render_pass in getattr(graph, 'passes', []):
        namespace = getattr(render_pass, 'namespace', None)
        func = getattr(render_pass, 'func', None)
        if namespace and func:
            try:
                with open(os.path.join(str(effects_root), namespace, func + '.json')) as handle:
                    if 'audio' in (json.load(handle).get('tags') or []):
                        result['needsLegacy'] = True
            except (OSError, ValueError):
                pass
        visit(getattr(render_pass, 'uniforms', {}))
    return result
