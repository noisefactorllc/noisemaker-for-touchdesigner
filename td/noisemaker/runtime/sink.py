"""Output-sink coordination for completed Noisemaker render TOPs."""

from collections.abc import MutableMapping
from types import MappingProxyType


_EMPTY_DESCRIPTOR = MappingProxyType({})


class _IdentityMap(MutableMapping):
    """Map arbitrary objects by identity without requiring hashability."""

    def __init__(self):
        self._entries = {}

    def __getitem__(self, key):
        entry = self._entries.get(id(key))
        if entry is None or entry[0] is not key:
            raise KeyError(key)
        return entry[1]

    def __setitem__(self, key, value):
        self._entries[id(key)] = (key, value)

    def __delitem__(self, key):
        entry = self._entries.get(id(key))
        if entry is None or entry[0] is not key:
            raise KeyError(key)
        del self._entries[id(key)]

    def __iter__(self):
        return (entry[0] for entry in self._entries.values())

    def __len__(self):
        return len(self._entries)

    def clear(self):
        self._entries.clear()


def _validate_sink(sink):
    if sink is None or not all(callable(getattr(sink, method, None))
                               for method in ("configure", "submit", "close")):
        raise TypeError("Sink must implement configure, submit, and close")


class SinkManager:
    """Configure and submit to independent sinks without coupling their failures."""

    def __init__(self, on_error=None):
        self._on_error = on_error
        self._registrations = []
        self._registrations_by_sink = _IdentityMap()
        self._stats = _IdentityMap()
        self._descriptor = _EMPTY_DESCRIPTOR
        self._configured = False
        self._closed = False
        self._iteration_depth = 0
        self._has_tombstones = False

    @property
    def stats(self):
        return self._stats

    def add(self, sink):
        if self._closed:
            raise RuntimeError("SinkManager is closed")
        _validate_sink(sink)
        if sink in self._registrations_by_sink:
            raise ValueError("Sink is already registered")
        if self._configured:
            sink.configure(self._descriptor)

        registration = {
            "sink": sink,
            "stats": {"accepted": 0, "dropped": 0, "failed": 0},
            "active": True,
        }
        self._registrations.append(registration)
        self._registrations_by_sink[sink] = registration
        self._stats[sink] = registration["stats"]

        removed = False

        def remove():
            nonlocal removed
            if removed:
                return
            removed = True
            self._remove_registration(registration)

        return remove

    def remove(self, sink):
        self._remove_registration(self._registrations_by_sink.get(sink))

    def _remove_registration(self, registration):
        if not registration or not registration["active"]:
            return
        sink = registration["sink"]
        registration["active"] = False
        registration["sink"] = None
        self._has_tombstones = True
        if self._registrations_by_sink.get(sink) is registration:
            del self._registrations_by_sink[sink]
            del self._stats[sink]
        try:
            sink.close()
        finally:
            if self._iteration_depth == 0:
                self._compact_registrations()

    def _compact_registrations(self):
        if not self._has_tombstones:
            return
        self._registrations = [registration for registration in self._registrations
                               if registration["active"]]
        self._has_tombstones = False

    def _report(self, error, sink):
        if not callable(self._on_error):
            return
        try:
            self._on_error(error, sink)
        except Exception:
            pass

    def configure(self, descriptor=None):
        if self._closed:
            return
        self._descriptor = _EMPTY_DESCRIPTOR if descriptor is None else descriptor
        self._configured = True
        self._iteration_depth += 1
        try:
            for registration in self._registrations:
                if not registration["active"]:
                    continue
                sink = registration["sink"]
                try:
                    sink.configure(self._descriptor)
                except Exception as error:
                    registration["stats"]["failed"] += 1
                    self._report(error, sink)
        finally:
            self._iteration_depth -= 1
            if self._iteration_depth == 0:
                self._compact_registrations()

    def submit(self, texture, timestamp):
        if self._closed:
            return
        self._iteration_depth += 1
        try:
            for registration in self._registrations:
                if not registration["active"]:
                    continue
                sink = registration["sink"]
                try:
                    result = sink.submit(texture, timestamp)
                except Exception as error:
                    registration["stats"]["failed"] += 1
                    self._report(error, sink)
                    continue
                if result is True:
                    registration["stats"]["accepted"] += 1
                elif result is False:
                    registration["stats"]["dropped"] += 1
        finally:
            self._iteration_depth -= 1
            if self._iteration_depth == 0:
                self._compact_registrations()

    def close(self, options=None):
        if self._closed:
            return
        self._closed = True
        first_error = None
        for registration in self._registrations:
            if not registration["active"]:
                continue
            sink = registration["sink"]
            registration["active"] = False
            registration["sink"] = None
            try:
                sink.close(options)
            except Exception as error:
                if first_error is None:
                    first_error = error
        self._registrations.clear()
        self._registrations_by_sink.clear()
        self._stats.clear()
        self._has_tombstones = False
        if first_error is not None:
            raise first_error
