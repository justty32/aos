"""hook_flags - keep the two flag files of the aos-loop points (STACK/hook_before_run.flag, hook_after_run.flag) in step with a hooks list: there while a hook listens to that point, gone otherwise.

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120/06 "沒人掛時怎麼做到零成本" with 12 (A1, B1): a loop.json wired to
aos-hook runs on_before_run / on_after_run only while on_before_run_if / on_after_run_if exists, so a loop nobody hooks
pays one access() a run, not one aos-hook process (the user 11-20, open question 11: "用旗標檔"). Hook 5th cut, second half
(line top-1121-hook5).
Only the commands that change a hooks list and the start of a loop call sync(): aos-agent hook add / rm / reset (and
self_hook and aos.gdb through it), aos-hook fire ... after_start, aos-hook check with a stack. Reading a list and firing
an event never touch the flags (A1: a reader that deletes a flag can race a writer that just made it).
Standard library only; prints nothing; a flag that cannot be written or removed raises OSError (the caller says its line).

API:
    FLAGS                      {point: flag file name in the stack}
    sync(stack, points, entries) -> {point: True (flag there) | False (flag gone)} for the loop points that `points`
                               declares (a point not declared is left alone); entries = {name: entry} in effect
"""
import os

FLAGS = {"before_run": "hook_before_run.flag", "after_run": "hook_after_run.flag"}
TEXT = "aos-loop runs on_%s of this loop while this file exists: a hook listens to %s (kept by aos-agent hook and aos-hook)\n"


def sync(stack, points, entries):
    """Make each loop point's flag match the list: there when an entry listens to it, gone when none does."""
    out = {}
    for point, name in FLAGS.items():
        if point not in points:
            continue
        path = os.path.join(stack, name)
        want = any(entry.get("event") == point for entry in entries.values())
        if want and not os.path.exists(path):
            tmp = os.path.join(stack, ".%s.%d.tmp" % (name, os.getpid()))   # N-05: write a temp file, then rename
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(TEXT % (point, point))
            os.replace(tmp, path)
        elif not want:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
        out[point] = want
    return out
