#!/usr/bin/env python3
class FileCountTracker:
    """Per-task, per-stage file counter shared by every multi-file processor.

    A processor announces its stage once (`set_stage`) and reports each file it
    finishes (`advance`). The status renderer reads it back through
    `current()`; nothing here does I/O, so a status tick never scans the disk.
    Counters are plain int reads/writes: safe from both the event loop and the
    worker threads (`sync_to_async`) the processors run in.
    """

    __slots__ = ('stage', 'done', 'total', 'base', 'current_file', 'failed')

    def __init__(self):
        self.stage = None
        self.done = 0
        self.total = 0
        self.base = 0
        self.current_file = None
        self.failed = 0

    def set_stage(self, stage, total=0, base=0):
        self.stage = stage
        self.total = max(0, int(total or 0))
        self.base = max(0, int(base or 0))
        self.done = 0
        self.current_file = None
        self.failed = 0

    def advance(self, name=None, failed=False):
        self.done += 1
        if failed:
            self.failed += 1
        if name is not None:
            self.current_file = name

    def finish(self):
        if self.total and self.done > self.total:
            self.done = self.total

    def clear(self):
        self.stage = None
        self.done = 0
        self.total = 0
        self.base = 0
        self.current_file = None
        self.failed = 0

    def current(self):
        """(done, total, failed, current_file) or None when nothing is displayable.

        Hidden for single-file stages and for stages that could not count, so
        single-file tasks keep their existing status untouched.
        """
        if not self.stage or self.total <= 1 or self.done < 1:
            return None
        return self.done, self.total, self.failed, self.current_file


def stage_counts(listener):
    """What a status object should report: its task's current stage counts."""
    tracker = getattr(listener, 'file_count', None)
    return tracker.current() if tracker is not None else None
