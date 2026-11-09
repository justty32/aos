"""daemon_ctl 門鈴：核對公開窗與 Linux 行程身分後，用 pidfd 送出宣告的 poke 訊號。"""
import json
import os
import signal

from .base import Fail
from .entry import read_loop

MODES = ("ctl", "mail", "all")


def poke(d, mode="ctl"):
    """只在公開窗宣告訊號且行程身分吻合時送門鈴；成功不輸出。"""
    if mode not in MODES:
        raise Fail("ArgumentsBad", "unknown poke mode: %s" % mode)
    try:
        name = read_loop(os.path.join(d, "daemon.json")).get("state", "state.json")
    except Fail:
        name = "state.json"
    if not isinstance(name, str) or not name:
        raise Fail("StateMissing", "the daemon's state window is off; cannot find its pid")
    missing = "no aos-daemon running at %s" % d
    path = os.path.join(d, name)
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except FileNotFoundError:
        raise Fail("DaemonMissing", missing + " (no state.json)") from None
    except (OSError, ValueError) as e:
        raise Fail("StateBad", "cannot read the state window at %s: %s" % (path, e)) from None
    if not isinstance(state, dict):
        raise Fail("StateBad", "the state window at %s must be a JSON object" % path)
    signals = state.get("poke")
    number = signals.get(mode) if isinstance(signals, dict) else None
    if type(number) is not int or number <= 0:
        raise Fail("PokeFailed", "the state window at %s declares no poke signals (not an aos-daemon, or one too old to poke)" % d)
    pid = state.get("pid")
    ticks = state.get("started_at_ticks")
    boot = state.get("boot_id")
    if type(pid) is not int or pid <= 0 or type(ticks) is not int or ticks < 0 or not isinstance(boot, str):
        raise Fail("DaemonMissing", missing + "; its state.json has no pid, started_at_ticks and boot_id")
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            current_boot = fh.read().strip()
    except (OSError, ValueError) as e:
        raise Fail("DaemonMissing", missing + " (cannot read boot_id: %s)" % e) from None
    if boot != current_boot:
        raise Fail("DaemonMissing", missing + " (state.json is from an earlier boot)")
    fd = None
    try:
        fd = os.pidfd_open(pid)
        try:
            with open("/proc/%d/stat" % pid, encoding="utf-8") as fh:
                stat = fh.read()
            current_ticks = int(stat[stat.rindex(")") + 1:].split()[19])
        except (OSError, ValueError, IndexError):
            raise Fail("DaemonMissing", missing + " (cannot read pid %d starttime)" % pid) from None
        if current_ticks != ticks:
            raise Fail("DaemonMissing", missing + " (pid %d is now another process)" % pid)
        signal.pidfd_send_signal(fd, number)
    except ProcessLookupError:
        raise Fail("DaemonMissing", missing + " (pid %d is gone)" % pid) from None
    except PermissionError:
        raise Fail("PokeFailed", "cannot signal the daemon (pid %d): permission denied" % pid) from None
    except OSError as e:
        raise Fail("PokeFailed", "cannot signal the daemon (pid %d): %s" % (pid, e.strerror or e)) from None
    finally:
        if fd is not None:
            os.close(fd)
