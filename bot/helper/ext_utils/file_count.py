#!/usr/bin/env python3
class FileCountTracker:

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
        if not self.stage or self.total <= 1:
            return None
        current_num = min(self.done + 1, self.total)
        return current_num, self.total, self.failed, self.current_file


def stage_counts(listener):
    tracker = getattr(listener, 'file_count', None)
    return tracker.current() if tracker is not None else None
