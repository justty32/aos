"""hook_handle - the handle aos.hook_point.open returns: fire a program's hook points through the engine, with errors going to the program's own fail().

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120/04 (the small library; A12 how fail works, A13 checks inside the
engine, A16 names()). Programs call aos.hook_point.open, not this module; the API is written there.
Kept apart from hook_point.py only for the file size. Standard library plus aos.hook_run and aos.hook_lists.
"""
from aos import hook_lists, hook_run


class FailReturned(RuntimeError):
    """The fail() given to open() returned instead of leaving; raised so a bad result never goes on."""

    def __init__(self, code, sentence):
        super().__init__("%s %s" % (code, sentence))
        self.code = code


def call_fail(fail, code, sentence):
    """Call fail(code, sentence); what it raises goes out as it is; if it returns, raise FailReturned."""
    fail(code, sentence)
    raise FailReturned(code, sentence)


class Handle:
    """Fire hook points: built by aos.hook_point.open."""

    def __init__(self, points, table, lists, entries, stack, fail, warn, check, entry_check):
        self.points, self.table = points, table
        self._lists, self._entries, self._entry_check = lists, entries, entry_check
        self._stack, self._fail, self._warn = stack, fail, warn
        self._owners = hook_lists.owners(points)
        types = hook_lists.type_check(points) if points else None
        if types and check:
            self._check = lambda event, key, value: (types(event, key, value), check(event, key, value))
        else:
            self._check = types or check

    def load(self):
        """{name: entry} of who listens now; HooksBad goes to fail."""
        try:
            if self._lists is not None:
                return hook_lists.load(self._lists, self.table, self._owners, self._entry_check)
            if callable(self._entries):
                return self._entries()
            return self._entries if self._entries is not None else {}
        except hook_run.HooksBad as e:
            call_fail(self._fail, "HooksBad", str(e))

    def _known(self, event):
        if event not in self.table:
            call_fail(self._fail, "EventUnknown", "no hook point %s (points: %s)"
                      % (event, ", ".join(self.table) or "none"))

    def has(self, event):
        """Whether some hook is on event (no condition compared)."""
        self._known(event)
        return any(e["event"] == event for e in self.load().values())

    def names(self, event, data, entries=None):
        """The hook names that would run for data, sorted (condition compared, as the engine does)."""
        self._known(event)
        entries = self.load() if entries is None else entries
        return sorted(n for n, e in entries.items() if e["event"] == event and hook_run.matches(e, self.table, data))

    def fire(self, event, data, only=None, entries=None):
        """Run the hooks of event through the engine; HooksBad / HookFailed / EventUnknown go to fail.
        only = exactly these names (those on event), no condition compared again; entries = load()'s result."""
        self._known(event)
        entries = self.load() if entries is None else entries
        if only is not None:
            entries = {n: {k: v for k, v in e.items() if k != "condition"}
                       for n, e in entries.items() if n in only and e["event"] == event}
        try:
            return hook_run.fire(event, data, entries, self._stack, self.table, warn=self._warn, check=self._check)
        except hook_run.HooksBad as e:
            call_fail(self._fail, "HooksBad", str(e))
        except hook_run.HookFailed as e:
            call_fail(self._fail, "HookFailed", str(e))
