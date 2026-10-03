"""multid 的 kernel 任務：一個 kernel 看好幾個 daemon（S-21 路二、S-18）。

讀自己 node 的 kern/kernel.json：
    {"daemons": {"<名>": {"space": "空間路徑/.aosd"} 或 {"abs": "/絕對/.aosd"}, "restart": spawn 項目（可選）},
     "poll": 秒, "stale_s": 秒}
每 poll 秒：
- 每個 daemon：找 .aosd（space 走掛載點，沒掛到就寫加掛請求；abs 直接用），讀 status.json，
  判斷死活（status.at 停了？pid 還在？daemon.lock 鎖得到？），訊號一變就記事件；
  判定死了且有 restart 設定 → 寫自己 node 的 .aos/spawn/（請下個 tick 起 daemon），等它回來。
- 執行 kern/cmd/*.json：{"op": "ctl", "daemon": 名, "body": 控制檔內容} → 寫進那個 daemon 的 ctl/，等回條記延遲。
事件寫 kern/events.jsonl（t＝time.time()），最新看法寫 kern/view.json。
"""
import datetime
import fcntl
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_mount  # noqa: E402
from aos7_fs import append_jsonl, read_json, task_env, write_json  # noqa: E402

E = task_env()
NODE, TASK, TID = E["node"], E["task"], E["tid"]
KDIR = os.path.join(NODE, "kern")


def ev(**kw):
    append_jsonl(os.path.join(KDIR, "events.jsonl"), dict(t=time.time(), tid=TID, **kw))


def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def lock_free(aosd):
    """daemon.lock 鎖得到＝沒有 daemon 握著它（只在懷疑死掉時才試，免得擋到剛要起的 daemon）。"""
    p = os.path.join(aosd, "daemon.lock")
    if not os.path.exists(p):
        return None
    fd = os.open(p, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def age_of(at):
    try:
        return round(time.time() - datetime.datetime.fromisoformat(at).timestamp(), 3)
    except (TypeError, ValueError):
        return None


def main():
    cfg = read_json(os.path.join(KDIR, "kernel.json"), {})
    poll, stale_s = cfg.get("poll", 0.05), cfg.get("stale_s", 0.5)
    resolve = aos7_mount.resolver(TASK)
    state = {n: {"sig": {}, "restarting": None, "last_pid": None} for n in cfg.get("daemons", {})}
    pending = {}        # ctl 檔名 → (daemon, 送出時間)
    asked = set()
    restarts = 0
    ev(ev="start", mounts=read_json(os.path.join(TASK, "birth.json"), {}).get("mounts"))
    while True:
        view = {"t": time.time(), "round": (read_json(os.path.join(TASK, "tock.json"), {}) or {}).get("round"),
                "daemons": {}}
        resolve = aos7_mount.resolver(TASK)   # 加掛後 birth.json 會變
        dirs = {}
        for name, d in cfg.get("daemons", {}).items():
            if "abs" in d:
                aosd = d["abs"]
            else:
                aosd = resolve(d["space"])
                if aosd is None:
                    r = aos7_mount.request(TASK, d["space"], why="kernel 要看 daemon %s" % name)
                    if (name, r) not in asked:
                        asked.add((name, r))
                        ev(ev="mount", daemon=name, path=d["space"], result=r)
                    view["daemons"][name] = {"reach": r}
                    continue
            dirs[name] = aosd
            st = read_json(os.path.join(aosd, "status.json"), {}) or {}
            s = state[name]
            age = age_of(st.get("at"))
            pid = st.get("pid")
            sig = {"stale": age is None or age > stale_s, "pid_dead": not pid_alive(pid)}
            if sig["stale"] or sig["pid_dead"]:
                if not s["restarting"]:
                    sig["lock_free"] = lock_free(aosd)
            for k, v in sig.items():
                if s["sig"].get(k) != v:
                    ev(ev="signal", daemon=name, sig=k, value=v, age=age, pid=pid)
            s["sig"].update(sig)
            dead = sig["stale"] and sig["pid_dead"]
            if dead and d.get("restart") and not s["restarting"]:
                restarts += 1
                fname = "kern-restart-%s-%d" % (name, restarts)
                write_json(os.path.join(NODE, ".aos", "spawn", fname + ".json"), d["restart"])
                s["restarting"] = {"t": time.time(), "old_pid": pid}
                ev(ev="restart_spawned", daemon=name, spawn=fname, old_pid=pid)
            if s["restarting"] and not sig["stale"] and not sig["pid_dead"] and pid != s["restarting"]["old_pid"]:
                ev(ev="back", daemon=name, pid=pid, root=st.get("root"),
                   took=round(time.time() - s["restarting"]["t"], 3))
                s["restarting"] = None
            view["daemons"][name] = {"aosd": aosd, "pid": pid, "age": age, "sig": dict(s["sig"]),
                                     "root": st.get("root"),
                                     "nodes": {k: {"round": v.get("round"), "paused": v.get("paused")}
                                               for k, v in (st.get("nodes") or {}).items()}}
        # 指令
        cdir = os.path.join(KDIR, "cmd")
        for fn in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
            cmd = read_json(os.path.join(cdir, fn)) or {}
            os.replace(os.path.join(cdir, fn), os.path.join(KDIR, "cmd-done-" + fn))
            name = cmd.get("daemon")
            if cmd.get("op") == "ctl":
                if name not in dirs:
                    ev(ev="ctl_fail", daemon=name, why="碰不到這個 daemon 的 .aosd", cmd=fn)
                    continue
                body = dict(cmd.get("body") or {}, by="%s:%s" % (E["node_id"], TID))
                cname = "k-%d.json" % time.time_ns()
                write_json(os.path.join(dirs[name], "ctl", cname), body)
                pending[cname] = (name, time.time(), fn)
                ev(ev="ctl_sent", daemon=name, file=cname, cmd=fn, body=body)
        for cname, (name, t0, fn) in list(pending.items()):
            if name not in dirs:
                continue
            done = read_json(os.path.join(dirs[name], "ctl-done", cname))
            if done:
                ev(ev="receipt", daemon=name, file=cname, cmd=fn, result=done.get("result"),
                   latency=round(time.time() - t0, 3))
                del pending[cname]
        view["pending"] = {k: v[0] for k, v in pending.items()}
        write_json(os.path.join(KDIR, "view.json"), view)
        time.sleep(poll)


if __name__ == "__main__":
    main()
