"""daemon：看管者。裁決 G-01 —— daemon 只當看管者，替每塊登記的地起一支 `aos run`。

daemon 掛了各地時鐘照走（子行程是 detach 的）；代價是沒人能一次全停，
所以 `aos daemon stop` 在 daemon 不在時也要能做：先對帳再全停。
"""
import errno
import json
import os
import signal
import subprocess
import sys
import time

from . import execute, exits, fsutil, layout, loader, registry

DEFAULT_EVERY_MS = 500
_SLEEP_SLICE = 0.05
RUN_LOG = "daemon-run.log"       # 每塊地的 .aos/daemon-run.log
DAEMON_LOG = "daemon.log"        # 家的 .aos/daemon.log


def _aos_py():
    """proto/aos.py 的絕對路徑。"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aos.py")


def _child_env():
    """子行程一定要繼承同一個 $AOS_HOME，不然它會去找 ~ 的登記表。"""
    env = dict(os.environ)
    env["AOS_HOME"] = layout.home()
    return env


def _die(msg, code, hint=None):
    sys.stderr.write("錯誤：%s\n" % msg)
    if hint:
        sys.stderr.write("下一步：%s\n" % hint)
    return code


# ---------- 登記表那筆 -> aos run 的旗標 ----------
def run_argv(entry):
    """依登記表那筆的 `clock` 組 `aos run` 的 argv（WRITER-BRIEF 4.6）。"""
    argv = [sys.executable, _aos_py(), "run", entry["path"], "--register"]
    clock = entry.get("clock") or {}
    kind = clock.get("kind")
    if kind == "steps":
        argv += ["--steps", str(int(clock.get("steps", 1)))]
    elif kind == "every":
        argv += ["--every", str(int(clock.get("every_ms", DEFAULT_EVERY_MS))), "--until", "idle"]
    elif kind == "once":
        argv += ["--steps", "1"]
    else:                       # until idle（也是沒寫時的預設）
        argv += ["--until", "idle"]
    if entry.get("budget") is not None:
        argv += ["--budget", str(int(entry["budget"]))]
    return argv


def _spawn_run(entry, home=None):
    """替一塊登記的地起一支 detach 的 `aos run`。回傳 (pid, 說明)。"""
    land = layout.Land(entry["path"])
    argv = run_argv(entry)
    fsutil.ensure_dir(land.aos)
    logpath = os.path.join(land.aos, RUN_LOG)
    log = open(logpath, "ab")
    try:
        p = subprocess.Popen(argv, env=_child_env(), stdin=subprocess.DEVNULL,
                             stdout=log, stderr=log, start_new_session=True, close_fds=True)
    except OSError as e:
        log.close()
        return None, "起不了 aos run：%s（看 %s）" % (e, logpath)
    finally:
        try:
            log.close()
        except OSError:
            pass
    registry.update(land.root, home=home, pid=p.pid, state=registry.RUNNING)
    return p.pid, "起了 aos run %s（pid %d，紀錄在 %s）" % (land.root, p.pid, logpath)


# ---------- 迴圈 ----------
def _loop(every_ms, home=None, printer=None):
    """前景迴圈。每 every_ms 掃一次登記表。"""
    say = printer or (lambda s: None)
    h = home or layout.Home()
    stop = {"hit": None}

    def _on(signum, frame):
        stop["hit"] = signum

    for s in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(s, _on)
        except (ValueError, OSError):
            pass
    try:
        # 子行程我們不 wait，交給系統自動收屍，免得留一地殭屍
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    except (ValueError, OSError, AttributeError):
        pass

    registry.set_daemon_pid(os.getpid(), h)
    try:
        fsutil.atomic_write_text(h.daemon_pid, "%d\n" % os.getpid())
    except OSError:
        pass
    say("daemon 起來了，pid %d，每 %d 毫秒掃一次登記表（%s）" % (os.getpid(), every_ms, h.registry))

    try:
        while not stop["hit"]:
            registry.reconcile(h)
            reg = registry.load(h)
            for e in reg["entries"]:
                if e.get("state") != registry.PENDING:
                    continue
                pid, note = _spawn_run(e, h)
                say("  " + note)
            deadline = time.time() + float(every_ms) / 1000.0
            while not stop["hit"] and time.time() < deadline:
                time.sleep(min(_SLEEP_SLICE, max(0.0, deadline - time.time())))
    finally:
        say("daemon 收工（訊號 %s）" % stop["hit"])
        _clear_daemon_pid(h)
    return exits.OK


def _clear_daemon_pid(home=None):
    h = home or layout.Home()
    try:
        registry.set_daemon_pid(None, h)
    except Exception:
        pass
    try:
        os.unlink(h.daemon_pid)
    except OSError:
        pass


# ---------- 子命令 ----------
def op_start(args, home=None):
    h = home or layout.Home()
    fsutil.ensure_dir(h.aos)
    registry.reconcile(h)
    reg = registry.load(h)
    live = reg.get("daemon_pid")
    if registry.alive(live) and live != os.getpid():
        print("已經在跑，pid %d。想換設定就先 `aos daemon stop`。" % live)
        return exits.OK

    every = int(getattr(args, "every", None) or DEFAULT_EVERY_MS)
    if getattr(args, "foreground", False):
        return _loop(every, h, printer=(lambda s: (print(s), sys.stdout.flush())[0]))

    argv = [sys.executable, _aos_py(), "daemon", "start", "--foreground",
            "--every", str(every)]
    logpath = os.path.join(h.aos, DAEMON_LOG)
    log = open(logpath, "ab")
    try:
        p = subprocess.Popen(argv, env=_child_env(), stdin=subprocess.DEVNULL,
                             stdout=log, stderr=log, start_new_session=True, close_fds=True)
    except OSError as e:
        log.close()
        return _die("起不了 daemon：%s" % e, exits.USAGE,
                    "先確認 %s 跑得動：python3 %s daemon status" % (_aos_py(), _aos_py()))
    finally:
        try:
            log.close()
        except OSError:
            pass
    registry.set_daemon_pid(p.pid, h)
    try:
        fsutil.atomic_write_text(h.daemon_pid, "%d\n" % p.pid)
    except OSError:
        pass
    # 等它真的活起來（最多 2 秒），不然使用者馬上敲 ls 會看到空的
    for _ in range(40):
        if not registry.alive(p.pid):
            break
        if registry.load(h).get("daemon_pid") == p.pid:
            break
        time.sleep(0.05)
    if not registry.alive(p.pid):
        return _die("daemon 起來就死了", exits.USAGE, "看 %s" % logpath)
    print("daemon 起來了，pid %d（紀錄在 %s）" % (p.pid, logpath))
    print("  登記表：%s；停：aos daemon stop" % h.registry)
    return exits.OK


def op_add(args, home=None):
    """`aos daemon add <地>`：只登記時鐘，不當場開跑，交給 daemon 去起那支 `aos run`。

    原型自己加的子命令（FINDINGS「一塊地要跑起來要敲兩次」那條）。裁決 S-02 之後
    agent 要自己登記時鐘、由 daemon 起它，指令面本來沒有一條路能登出 `pending`
    那一態（`aos run --register` 會當場開跑），所以補這個。
    """
    if not getattr(args, "land", None):
        return _die("`aos daemon add` 少了地", exits.USAGE,
                    "aos daemon add <地> [--every 毫秒｜--steps N｜--until idle] [--budget N]")
    land = layout.Land(args.land)
    if not land.is_land():
        return _die("%s 不是一塊地（沒有 %s）" % (land.root, land.layout), exits.NOT_A_LAND,
                    "python3 proto/aos.py init %s" % land.root)
    h = home or layout.Home()
    if getattr(args, "steps", None) is not None:
        clock = {"kind": "steps", "steps": int(args.steps)}
    elif getattr(args, "until", None) == "idle":
        clock = {"kind": "until", "until": "idle"}
    else:
        clock = {"kind": "every", "every_ms": int(getattr(args, "every", None)
                                                  or DEFAULT_EVERY_MS)}
    e = registry.register(land.root, clock, budget=getattr(args, "budget", None),
                          state=registry.PENDING, home=h)
    if getattr(args, "json", False):
        print(json.dumps(e, ensure_ascii=False, indent=2))
        return exits.OK
    print("登記了 %s，鐘 %s，狀態 %s"
          % (e["path"], json.dumps(e["clock"], ensure_ascii=False), e["state"]))
    if registry.daemon_alive(h):
        print("  daemon 在跑，下一輪掃登記表就會替它起 `aos run %s --register`。" % land.root)
    else:
        print("  daemon 不在，這筆會一直卡在 pending。下一步：`aos daemon start`。")
    return exits.OK


def op_stop(args, home=None):
    """G-01 的代價：daemon 不在時也要能全停 —— 先對帳再全停。"""
    h = home or layout.Home()
    registry.reconcile(h)
    reg = registry.load(h)
    n = 0
    for e in reg["entries"]:
        pid = e.get("pid")
        if e.get("state") == registry.RUNNING and registry.alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                n += 1
                print("請 %s 的 run 停下來（pid %d，SIGTERM）" % (e["path"], pid))
            except OSError as err:
                print("殺不掉 %s 的 pid %d：%s" % (e["path"], pid, err))
    dpid = reg.get("daemon_pid")
    if registry.alive(dpid):
        try:
            os.kill(dpid, signal.SIGTERM)
            print("請 daemon 停下來（pid %d，SIGTERM）" % dpid)
        except OSError as err:
            print("殺不掉 daemon pid %d：%s" % (dpid, err))
    else:
        print("daemon 本來就不在（登記表 daemon_pid=%s）；已經先對帳再把各地的 run 全停。" % dpid)
    # 給它們一點時間走乾淨，再對帳一次讓登記表不留幽靈
    for _ in range(30):
        time.sleep(0.05)
        if not any(registry.alive(e.get("pid")) for e in registry.load(h)["entries"]):
            break
    registry.reconcile(h)
    _clear_daemon_pid(h)
    print("停了 %d 塊地的 run。`aos daemon ls` 看現況。" % n)
    return exits.OK


def op_ls(args, home=None):
    h = home or layout.Home()
    registry.reconcile(h)
    reg = registry.load(h)
    if getattr(args, "json", False):
        print(json.dumps(reg, ensure_ascii=False, indent=2))
        return exits.OK
    if not reg["entries"]:
        print("登記表是空的（%s）。" % h.registry)
        print("下一步：`aos run <地> --register` 或讓父地的 call async 去登記。")
        return exits.OK
    print("登記表 %s（daemon_pid=%s%s）"
          % (h.registry, reg.get("daemon_pid"),
             "，活著" if registry.alive(reg.get("daemon_pid")) else "，不在"))
    for e in reg["entries"]:
        pid = e.get("pid")
        pidtxt = "-" if pid is None else ("%d 活著" % pid if registry.alive(pid) else "%d 死了" % pid)
        print("  %-8s pid %-12s 鐘 %-28s 預算 %-6s %s"
              % (e.get("state"), pidtxt, json.dumps(e.get("clock"), ensure_ascii=False),
                 e.get("budget"), e.get("path")))
    return exits.OK


def op_exec(args, home=None):
    """給人手動催一格用。"""
    if not getattr(args, "land", None):
        return _die("`aos daemon exec` 少了地", exits.USAGE,
                    "aos daemon exec <地>")
    land = layout.Land(args.land)
    try:
        rep = execute.exec_once(land)
    except execute.NotALand as e:
        return _die(str(e), exits.NOT_A_LAND, "python3 proto/aos.py init %s" % land.root)
    except loader.ParseError as e:
        return _die(str(e), exits.PARSE, "改好 %s 再跑一次" % land.source("main"))
    except fsutil.LockBusy as e:
        return _die(str(e), exits.LOCK_BUSY,
                    "那塊地已經有 run 在跑；先 `aos stop %s` 或等它停" % land.root)
    if getattr(args, "json", False):
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
        return exits.OK
    print("第 %d 格 @ %s" % (rep["tick"], rep["land"]))
    for n in rep["notes"]:
        print("  " + n)
    print("  %s" % ("閒著了" if rep["idle"] else "還有串在跑"))
    return exits.OK


def op_status(args, home=None):
    h = home or layout.Home()
    registry.reconcile(h)
    reg = registry.load(h)
    dpid = reg.get("daemon_pid")
    live = registry.alive(dpid)
    counts = {}
    for e in reg["entries"]:
        counts[e.get("state")] = counts.get(e.get("state"), 0) + 1
    if getattr(args, "json", False):
        print(json.dumps({
            "home": h.root, "registry": h.registry, "daemon_pid": dpid,
            "daemon_alive": live, "entries": len(reg["entries"]), "states": counts,
        }, ensure_ascii=False, indent=2))
        return exits.OK
    print("家：%s" % h.root)
    print("daemon：%s" % ("在跑，pid %d" % dpid if live else "不在"))
    if not live and dpid:
        print("  登記表寫著 pid %s 但那支已經死了；`aos daemon start` 會順手對帳。" % dpid)
    print("登記 %d 筆：%s" % (len(reg["entries"]),
                             "、".join("%s %d" % kv for kv in sorted(counts.items())) or "（空）"))
    if not live and counts.get(registry.PENDING):
        print("  有 %d 筆 pending 沒人去起；下一步：aos daemon start" % counts[registry.PENDING])
    return exits.OK


_OPS = {"start": op_start, "stop": op_stop, "ls": op_ls, "exec": op_exec,
        "status": op_status, "add": op_add}


def cli_daemon(args):
    fn = _OPS.get(getattr(args, "op", None))
    if fn is None:
        return _die("不認得 `aos daemon %s`" % getattr(args, "op", None), exits.USAGE,
                    "只認得：%s" % "、".join(sorted(_OPS)))
    try:
        return fn(args)
    except KeyboardInterrupt:
        return exits.CANCELLED


# ---------- aos stop <地> ----------
def who_runs(land, home=None):
    """誰在跑這塊地？回傳 (pid, 從哪知道的) 或 (None, None)。

    登記表是第一手；沒登記的 run 還有 .aos/lock 裡的 pid 可查（不然
    `aos run` 不加 --register 就變成殺不掉，錯誤還不指路）。
    """
    reg = registry.load(home)
    e = registry.find(reg, land.root)
    if e and e.get("state") == registry.RUNNING and registry.alive(e.get("pid")):
        return e["pid"], "登記表"
    info = fsutil.read_json(land.lock) or {}
    pid = info.get("pid")
    if isinstance(pid, int) and registry.alive(pid):
        return pid, "鎖檔 %s" % land.lock
    return None, None


def make_control(op, from_path=None):
    """控制信（WRITER-BRIEF 4.6）：{"format_version":1,"id":…,"op":…,"from":…,"at":…}"""
    return {
        "format_version": 1,
        "id": fsutil.new_id(),
        "op": op,
        "from": os.path.abspath(from_path or os.getcwd()),
        "at": fsutil.now_iso(),
    }


def cli_stop(args):
    land = layout.Land(args.land)
    if not land.is_land():
        return _die("%s 不是一塊地（沒有 %s）" % (land.root, land.layout), exits.NOT_A_LAND,
                    "python3 proto/aos.py init %s" % land.root)
    pid, src = who_runs(land)

    if getattr(args, "kill", False):
        if pid is None:
            print("這塊地現在沒人在跑，什麼都沒做。")
            print("  查過：登記表 %s、鎖檔 %s" % (layout.Home().registry, land.lock))
            print("  下一步：`aos daemon ls` 看誰在跑，或 `aos status %s` 看它停在哪。" % land.root)
            return exits.OK
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError as e:
            if e.errno == errno.ESRCH:
                print("pid %d 剛好已經走了，什麼都沒做。" % pid)
                return exits.OK
            return _die("殺不掉 pid %d：%s" % (pid, e), exits.USAGE,
                        "換個有權限的使用者，或 `aos daemon stop` 全停")
        registry.update(land.root, pid=None, state=registry.STOPPED)
        print("已經 SIGKILL pid %d（從%s查到的）。" % (pid, src))
        print("  注意：直接殺不寫停止原因檔，那塊地的 .aos/stopped.json 會停在上一輪的內容；"
              "想留紀錄就用不帶 --kill 的 `aos stop`。")
        return exits.OK

    if pid is None:
        print("這塊地現在沒人在跑，什麼都沒做。")
        print("  查過：登記表 %s、鎖檔 %s" % (layout.Home().registry, land.lock))
        print("  控制信只有 run 在跑時才有人收，先投進去只會變成下一趟 run 的舊帳，所以這次不投。")
        print("  下一步：`aos daemon ls` 看誰在跑；要跑就 `aos run %s`。" % land.root)
        return exits.OK

    msg = make_control("stop")
    fsutil.ensure_dir(land.control)
    path = os.path.join(land.control, "%s.json" % msg["id"])
    fsutil.write_json(path, msg)
    print("停止信投進 %s" % path)
    print("  那塊地的 run（pid %d，從%s查到的）會在這一格跑完後停下來，"
          "原因寫進 %s。" % (pid, src, land.stopped))
    return exits.OK
