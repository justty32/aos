"""hook_run - the hook engine, kept minimal: run the handlers hooked on one event (name order), hand each the event JSON, give back each one's exit code and stdout.

Design: the user 11-21 chose the fourth layer (proto8/thinking/2026-11/21/aos-hook-簡化-1121/07: "簡化到第四層", "庫也極簡",
timeout "留著"): blocking, changing fields, conditions, on_error and types are not here; the program that fires the event
decides what an exit code or a stdout means ("發事件的程式自己決定", 11-21 8th). aos-hook fire, the agent family
(aos.agentlib.hooks) and the kernel all run handlers through this file. Line top-1121-hooknew.
Standard library plus aos.directive_value (a handler written as a directive) and aos.hook_lists (HooksBad); prints nothing,
never exits.

How a handler runs: its folder STACK/hookeds/NAME/ gets event.json (the data plus "event", "hook", "stack"), then
aos-exec --stack STACK/hookeds/NAME/ HANDLER with that file on stdin, in a process group of its own; its stderr goes
straight through. timeout_ms (default 60000, 0 = no limit): at the limit the whole group gets TERM, KILL 2 s later.

API:
    TIMEOUT_MS, BLOCK (10: N-43 "no"), CELLS ("hookeds": the folder of the handlers' own folders in the stack)
    HooksBad                  = aos.hook_lists.HooksBad
    target(entry, name)       -> the handler as an aos-exec target (absolute path); a directive is resolved with
                              aos-directive (#/ and #./ from the entry's place NAME/handler in its list); cannot = OSError
    names(entries, event)     -> the names hooked on event, sorted
    run(name, entry, event, data, stack) -> {"hook": name, "code": exit code or None, "stdout": text,
                              "error": None, or why it did not finish (cannot start, timed out; code is then None)}
    fire(event, data, entries, stack, stop_on_nonzero=False) -> [run() results] of names(entries, event), each with the
                              same data; stop_on_nonzero = stop after the first result whose code is not 0 (or None)
"""
import json
import os
import signal
import subprocess
import time

from aos import directive_value, hook_lists

TIMEOUT_MS = 60000
BLOCK = 10                                       # N-43: 10 = "no", not an error
CELLS = "hookeds"                                # STACK/hookeds/NAME/: the handler's own folder (its $AOS_STACK)
HooksBad = hook_lists.HooksBad


def _stop_group(p):
    """TERM the whole group, KILL after 2 s (as agent-fsm act.py)."""
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        p.poll()
        try:
            os.killpg(p.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def target(entry, name):
    """handler -> the aos-exec target (absolute); cannot resolve = OSError with the reason (it counts as cannot start)."""
    t = entry["handler"]
    if isinstance(t, dict):
        try:                                     # aos-directive's own error line is swallowed; the reason is said here
            t = directive_value.resolve(t, entry["base"], entry["from"], stderr=subprocess.DEVNULL,
                                        at=directive_value.pointer(name, "handler"))
        except directive_value.Error as e:
            why = "aos-directive exited %d" % e.returncode if e.returncode is not None else e
            raise OSError("cannot resolve handler directive: %s" % why) from None
        if not isinstance(t, str) or not t:
            raise OSError("handler directive did not resolve to a non-empty path")
    return t if os.path.isabs(t) else os.path.join(entry["base"], t)


def names(entries, event):
    return sorted(n for n, e in entries.items() if e.get("event") == event)


def run(name, entry, event, data, stack):
    """Run one handler and wait for it (see the module doc). Ctrl-C / TERM while waiting: its group is stopped, then re-raised."""
    out = {"hook": name, "code": None, "stdout": "", "error": None}
    cell = os.path.join(os.path.abspath(stack), CELLS, name)
    doc = {"event": event, "hook": name, "stack": os.path.abspath(stack)}
    doc.update({k: v for k, v in data.items() if k not in doc})
    try:
        os.makedirs(cell, exist_ok=True)
        path, tmp = os.path.join(cell, "event.json"), os.path.join(cell, ".event.json.tmp")   # N-05: temp file, then rename
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
        argv = ["aos-exec", "--stack", cell + "/", target(entry, name)]
        with open(path, "rb") as stdin:
            p = subprocess.Popen(argv, stdin=stdin, stdout=subprocess.PIPE, start_new_session=True)
    except OSError as e:
        out["error"] = "cannot start: %s" % e
        return out
    limit_ms = entry.get("timeout_ms", TIMEOUT_MS)
    try:
        try:
            text, _ = p.communicate(timeout=None if limit_ms == 0 else limit_ms / 1000.0)
        except subprocess.TimeoutExpired:
            _stop_group(p)
            try:
                p.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                p.stdout.close()
                p.wait()
            out["error"] = "did not finish in %d ms (its process group was killed)" % limit_ms
            return out
    except BaseException:                        # Ctrl-C / TERM: do not leave the handler's group behind
        _stop_group(p)
        p.wait()
        raise
    out["code"], out["stdout"] = p.returncode, text.decode("utf-8", "replace")
    return out


def fire(event, data, entries, stack, stop_on_nonzero=False):
    results = []
    for name in names(entries, event):
        r = run(name, entries[name], event, data, stack)
        results.append(r)
        if stop_on_nonzero and r["code"] != 0:
            break
    return results
