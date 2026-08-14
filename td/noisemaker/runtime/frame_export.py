"""Bounded adapter-driven queue for non-blocking GPU frame export."""


def _validate_adapter(adapter):
    if adapter is None or not all(callable(getattr(adapter, method, None)) for method in (
            "create_slot", "begin", "poll", "read", "destroy_slot")):
        raise TypeError(
            "Frame export adapter must implement create_slot, begin, poll, read, and destroy_slot"
        )


class FrameExportQueue:
    """Coordinate a fixed ring of backend-owned asynchronous readback slots."""

    def __init__(self, adapter, slots=3, on_error=None):
        _validate_adapter(adapter)
        if isinstance(slots, bool) or not isinstance(slots, int) or not 2 <= slots <= 8:
            raise ValueError("Frame export slots must be an integer from 2 through 8")
        self.adapter = adapter
        self._on_error = on_error
        self._slots = [self._new_record() for _ in range(slots)]
        self._configured = False
        self._closed = False
        self.stats = {"accepted": 0, "dropped": 0, "completed": 0, "failed": 0}

    @staticmethod
    def _new_record():
        return {
            "adapter_slot": None,
            "created": False,
            "pending": False,
            "texture": None,
            "timestamp": None,
            "on_frame": None,
            "context": None,
        }

    @property
    def available(self):
        return (self._configured and not self._closed and
                any(not record["pending"] for record in self._slots))

    def configure(self, descriptor):
        if self._closed:
            return
        destroy_error = self._destroy_slots()
        self._configured = False
        if destroy_error is not None:
            raise destroy_error
        try:
            for index, record in enumerate(self._slots):
                record["adapter_slot"] = self.adapter.create_slot(index, descriptor)
                record["created"] = True
        except Exception:
            cleanup_error = self._destroy_slots()
            if cleanup_error is not None:
                self._report(cleanup_error)
            raise
        self._configured = True

    def enqueue(self, texture, timestamp, on_frame, context=None):
        if not callable(on_frame):
            raise TypeError("Frame export callback must be callable")
        if not self._configured or self._closed:
            self.stats["dropped"] += 1
            return False
        record = next((candidate for candidate in self._slots if not candidate["pending"]), None)
        if record is None:
            self.stats["dropped"] += 1
            return False

        record.update({
            "pending": True,
            "texture": texture,
            "timestamp": timestamp,
            "on_frame": on_frame,
            "context": context,
        })
        try:
            self.adapter.begin(record["adapter_slot"], texture, timestamp)
        except Exception as error:
            self._release(record)
            self.stats["failed"] += 1
            self._report(error)
            return False
        self.stats["accepted"] += 1
        return True

    def poll(self):
        if not self._configured or self._closed:
            return
        for record in self._slots:
            if not record["pending"]:
                continue
            try:
                ready = self.adapter.poll(record["adapter_slot"])
                if ready is False:
                    continue
                if ready is not True:
                    raise TypeError("Frame export adapter poll must return a boolean")
                frame = self.adapter.read(record["adapter_slot"])
                timestamp = record["timestamp"]
                on_frame = record["on_frame"]
                context = record["context"]
            except Exception as error:
                self._release(record)
                self.stats["failed"] += 1
                self._report(error)
                continue

            self._release(record)
            try:
                on_frame(frame, timestamp, context)
                self.stats["completed"] += 1
            except Exception as error:
                self.stats["failed"] += 1
                self._report(error)

    def close(self, options=None):
        if self._closed:
            return
        self._closed = True
        self._configured = False
        backend_lost = bool(options and (
            options.get("backend_lost") is True or options.get("backendLost") is True
        ))
        destroy_error = None
        if backend_lost:
            self._abandon_slots()
        else:
            destroy_error = self._destroy_slots()
        self.adapter = None
        if destroy_error is not None:
            raise destroy_error

    @staticmethod
    def _release(record):
        record.update({
            "pending": False,
            "texture": None,
            "timestamp": None,
            "on_frame": None,
            "context": None,
        })

    def _destroy_slots(self):
        first_error = None
        for record in self._slots:
            if not record["created"]:
                continue
            adapter_slot = record["adapter_slot"]
            record["created"] = False
            record["adapter_slot"] = None
            self._release(record)
            try:
                self.adapter.destroy_slot(adapter_slot)
            except Exception as error:
                if first_error is None:
                    first_error = error
        return first_error

    def _abandon_slots(self):
        for record in self._slots:
            record["created"] = False
            record["adapter_slot"] = None
            self._release(record)

    def _report(self, error):
        if not callable(self._on_error):
            return
        try:
            self._on_error(error)
        except Exception:
            pass
