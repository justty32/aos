#!/usr/bin/env python3
"""aos-kernel 的 syscall 收件匣；內建 rm，其餘可交給 module。"""
import json
import os
import sys
import time

import aos_home
from aos_kernel import IDLE_INST, KHome


def _home_error(shown):
    sys.stderr.write("aos-kernel: %s 不是 kernel 的家（還沒灌？先跑："
                     "aos-kernel-init %s --ncpu N）\n" % (shown, shown))
    return 1


def cmd_rm(argv):
    """寫 rm 單，等 kernel 下一回合回覆。"""
    if len(argv) not in (1, 2):
        sys.stderr.write("用法：aos-kernel rm [K] NAME\n")
        return 2
    if len(argv) == 1:
        kernel_dir, pid = os.getcwd(), argv[0]
        shown = kernel_dir
    else:
        kernel_dir, pid = argv
        shown = kernel_dir
    if not pid or "/" in pid:
        sys.stderr.write("aos-kernel rm: NAME 不能是空字串，也不能含 /\n")
        return 2
    h = KHome(kernel_dir)
    cfg = h.config()
    if cfg is None:
        return _home_error(shown)
    os.makedirs(h.syscalls_done, exist_ok=True)
    name = "%d-rm-%s.json" % (time.time_ns(), pid)
    request = os.path.join(h.syscalls, name)
    tmp = request + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"op": "rm", "pid": pid}, f, ensure_ascii=False,
                      separators=(",", ":"))
        os.replace(tmp, request)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        sys.stderr.write("aos-kernel rm: 單子寫不進去：%s\n" % e)
        return 1

    done = os.path.join(h.syscalls_done, name)
    limit = max(3.0, 3 * cfg["interval_ms"] / 1000.0)
    until = time.monotonic() + limit
    while time.monotonic() < until:
        if os.path.exists(done):
            try:
                with open(done, encoding="utf-8") as f:
                    out = json.load(f)
                os.unlink(done)
            except (OSError, ValueError) as e:
                sys.stderr.write("aos-kernel rm: 回音讀不到：%s\n" % e)
                return 1
            print(out.get("msg", ""))
            return 0 if out.get("ok") else 1
        time.sleep(0.05)
    print("kernel 沒回應（daemon 在跑嗎？aos-kernel ls K 看看）")
    return 1


def handle_syscalls(h, cfg, st, notes, modules=None):
    """按檔名處理 syscalls/*.json，回音原子寫進 syscalls/done/。"""
    if modules is None:
        from aos_kernel_module import load_modules
        modules = load_modules(cfg)
        notes.extend(modules.notes)
    os.makedirs(h.syscalls_done, exist_ok=True)
    try:
        names = sorted(n for n in os.listdir(h.syscalls)
                       if n.endswith(".json")
                       and os.path.isfile(os.path.join(h.syscalls, n)))
    except OSError as e:
        notes.append("syscall 收件匣讀不到：%s" % e)
        return
    for name in names:
        request = os.path.join(h.syscalls, name)
        try:
            with open(request, encoding="utf-8") as f:
                call = json.load(f)
        except (OSError, ValueError) as e:
            msg = "看不懂這張單：%s" % e
            notes.append(msg)
            _done(h, name, False, msg, notes)
            _unlink(request, notes)
            continue
        if not isinstance(call, dict):
            msg = "看不懂這張單：不是 JSON 物件"
            notes.append(msg)
            _done(h, name, False, msg, notes)
            _unlink(request, notes)
            continue
        op = call.get("op")
        if op != "rm":
            owner = next((module for module in modules if op in module.OPS), None)
            if owner is not None and getattr(owner, "handle", None) is not None:
                try:
                    ok, msg = owner.handle(h, cfg, st, call)
                    ok, msg = bool(ok), str(msg)
                except BaseException as exc:
                    ok = False
                    msg = "module %s 壞了：%s" % (
                        owner.NAME, str(exc).replace("\n", " ") or type(exc).__name__)
                notes.append(msg)
                _done(h, name, ok, msg, notes)
                _unlink(request, notes)
                continue
            why = "沒有 op" if "op" not in call else "不認得的 op：%s" % op
            msg = "看不懂這張單：%s" % why
            notes.append(msg)
            _done(h, name, False, msg, notes)
            _unlink(request, notes)
            continue
        pid = call.get("pid")
        if not isinstance(pid, str) or not pid:
            msg = "看不懂這張單：rm 沒有 pid"
            notes.append(msg)
            _done(h, name, False, msg, notes)
            _unlink(request, notes)
            continue
        ok, msg = _remove(h, cfg, st, pid, notes)
        _done(h, name, ok, msg, notes)
        _unlink(request, notes)


def _remove(h, cfg, st, pid, notes):
    for n in range(cfg["ncpu"]):
        cur = st["cpus"].get(str(n))
        if cur and cur.get("pid") == pid:
            tmp = h.cpu(n) + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(IDLE_INST, f, ensure_ascii=False, indent=1)
                os.replace(tmp, h.cpu(n))
            except OSError as e:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                msg = "rm %s 失敗：%s" % (pid, e)
                notes.append(msg)
                return False, msg
            st["cpus"][str(n)] = None
            st.setdefault("waiting", {}).pop(pid, None)
            msg = "rm %s（原本在 cpu%d）" % (pid, n)
            notes.append(msg)
            return True, msg
    path = h.proc(pid)
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError as e:
            msg = "rm %s 失敗：%s" % (pid, e)
            notes.append(msg)
            return False, msg
        st.setdefault("waiting", {}).pop(pid, None)
        msg = "rm %s（原本在佇列）" % pid
        notes.append(msg)
        return True, msg
    cleared = []
    for label, folder in (("done", h.done), ("bad", h.bad)):
        old = os.path.join(folder, "%s.json" % pid)
        if not os.path.isfile(old):
            continue
        try:
            os.unlink(old)
        except OSError as e:
            msg = "rm %s 失敗：%s" % (pid, e)
            notes.append(msg)
            return False, msg
        cleared.append(label)
    if cleared:
        msg = "；".join("清掉 %s 裡的舊紀錄：%s" % (label, pid) for label in cleared)
        notes.append(msg)
        return True, msg
    msg = "找不到這個行程：%s（佇列、cpu、done、bad 都沒有）" % pid
    notes.append(msg)
    return False, msg


def _done(h, name, ok, msg, notes):
    path = os.path.join(h.syscalls_done, name)
    try:
        aos_home.write_json(path, {"ok": ok, "msg": msg})
    except OSError as e:
        notes.append("syscall %s 回音寫不下來：%s" % (name, e))


def _unlink(path, notes):
    try:
        os.unlink(path)
    except OSError as e:
        notes.append("syscall 單子刪不掉：%s" % e)
