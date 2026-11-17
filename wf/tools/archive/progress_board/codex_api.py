"""Inspect active codex exec processes and safely read their bounded logs and output."""

import datetime as dt
import os
from pathlib import Path
import time

from safe_files import ApiError, safe_read


def _after(argv, flag):
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def _processes():
    found = {}
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            argv = [os.fsdecode(arg) for arg in (entry / "cmdline").read_bytes().split(b"\0") if arg]
            name = os.path.basename(argv[0])
            if name.startswith("node") and len(argv) > 1:
                name = os.path.basename(argv[1])
            if name != "codex" or "app-server" in argv or "exec" not in argv:
                continue
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if fields[0] == "Z":
                continue
            found[int(entry.name)] = {"parent": int(fields[1]), "ticks": int(fields[19]),
                                      "argv": argv, "entry": entry}
        except (OSError, ValueError, IndexError):
            continue
    return found


def codex_processes(cfg):
    try:
        boot = next(int(row.split()[1]) for row in Path("/proc/stat").read_text().splitlines()
                    if row.startswith("btime "))
        clock_ticks = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, StopIteration):
        return []
    candidates, result = _processes(), []
    for pid, candidate in candidates.items():
        if candidate["parent"] in candidates:
            continue
        argv, entry = candidate["argv"], candidate["entry"]
        started = boot + candidate["ticks"] / clock_ticks
        value = {"pid": pid, "started": dt.datetime.fromtimestamp(started).astimezone().isoformat(),
                 "elapsed_sec": max(0, int(time.time() - started)), "argv": argv,
                 "goal": next((arg[6:] for arg in argv if arg.startswith("/goal ")), None),
                 "cwd": _after(argv, "-C"), "model": _after(argv, "-m"),
                 "out_file": None, "out_text": None, "log_file": None,
                 "log_tail": None, "log_refused": None}
        output = _after(argv, "-o")
        if output:
            try:
                path = Path(output).expanduser()
                if not path.is_absolute():
                    path = Path(os.readlink(entry / "cwd")) / path
                value["out_file"] = os.path.realpath(path)
                if path.exists():
                    value["out_text"] = safe_read(cfg, path, 100 * 1024)["text"]
            except (OSError, ApiError):
                pass
        try:
            log = os.readlink(entry / "fd/1")
            if os.path.isabs(log) and Path(log).is_file():
                value["log_file"] = log
                try:
                    text = safe_read(cfg, log, 256 * 1024, tail=True)["text"]
                    value["log_tail"] = "\n".join(text.splitlines()[-60:])
                except ApiError as exc:
                    value["log_refused"] = str(exc)
        except OSError:
            pass
        result.append(value)
    return sorted(result, key=lambda value: (value["started"], value["pid"]))
