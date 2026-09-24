"""kernel 的啟動交接、狀態查詢與停機等待。"""
import os
from pathlib import Path
import time

import aos_client
import aos_daemon
import aos_home
from aos_kernel_engine import Kernel
from aos_kernel_info import CLI, KernelError, _put, load_info, new_state

def boot(home, daemon=None, wait_ms=30000):
    home = Path(home).absolute()
    info = load_info(home)
    cli = CLI.resolve()
    if not cli.is_file() or not os.access(cli, os.X_OK):
        raise KernelError("ReadFailed", "kernel CLI 必須有執行位：%s" % cli)
    daemon = aos_daemon.daemon_home(daemon)
    aos_home.load_info(daemon, "daemon")
    if not aos_daemon.is_alive(daemon):
        raise KernelError("NotRunning", "daemon 沒在跑：%s" % daemon)
    c = next(c for c, config in info["cpus"].items() if config["pool"] == "kernel")
    old_state = aos_home.read_state(home)
    old_c = old_state.get("kcpu", c)
    handoff = list(dict.fromkeys([old_c, c]))
    children = aos_daemon.read_state(daemon)["children"]
    # 換 kernel 池時仍先收帳本釘死的舊主人；兩個名字都驗完才送任何 kill。
    for name in handoff:
        child = children.get(name)
        if child is not None and child["target"] != str(home / "cpus" / name / "inst.json"):
            raise KernelError("NameTaken", "kernel cpu 名字已由另一個目標使用：%s" % name)
    chain = "%d-%d" % (time.time_ns(), os.getpid())
    # 交接完成前不碰舊帳本；kill 的 ack 暫存，取得帳本後一併記入出貨箱。
    kill_acks = []
    for name in handoff:
        if name not in children:
            continue
        request = ("k-%s-boot-kill.json" % chain if len(handoff) == 1 else
                   "k-%s-boot-kill-%s.json" % (chain, name))
        response = aos_client.call(daemon, "kill", {"name": name}, name=request,
                                   timeout_ms=5000, poll_ms=5, acknowledge=False)
        error = response.get("error")
        if error and error.get("data", {}).get("code") != "NotFound":
            raise KernelError(error.get("data", {}).get("code", str(error["code"])), error["message"])
        kill_acks.append({"home": daemon, "name": request})
        deadline = time.monotonic() + wait_ms / 1000
        while name in aos_daemon.read_state(daemon)["children"]:
            if time.monotonic() >= deadline:
                raise KernelError("AlreadyRunning", "舊 kernel cpu 尚未退出；kill 已送出")
            time.sleep(.005)
    raw = aos_home.read_json(home / "info.json")
    raw["daemon"] = daemon
    aos_home.write_json(home / "info.json", raw)
    info["daemon"] = daemon
    state = aos_home.read_state(home, new_state(info, chain, c, cli))
    state.update(chain=chain, kcpu=c, cli=str(cli), last_seq=0, phase="running", stops=[])
    state["acks"].extend(kill_acks)
    kernel = Kernel(home, info, state, 0)
    kernel.save()
    for name, config in info["cpus"].items():
        kernel._create_cpu(name, config)
        kernel._daemon_call("spawn", {"name": name, "target": str(kernel.cpu_home(name) / "inst.json"), "restart": True},
                            "k-%s-0-spawn-%s.json" % (chain, name))
    name, request = kernel.tick_request(1)
    _put(kernel.cpu_home(c), name, request)
    return 0


def status(home):
    info, state = load_info(home), aos_home.read_state(home)
    daemon = info.get("daemon", aos_daemon.daemon_home())
    child_state = aos_daemon.read_state(daemon)
    c = state.get("kcpu")
    cpu_home = Path(home) / "cpus" / c if c else None
    cpu_state = aos_home.read_state(cpu_home) if cpu_home and cpu_home.exists() else {}
    return {k: state.get(k) for k in ("chain", "phase", "last_seq", "cpus", "queue", "procs")} | {
        "daemon": {"alive": aos_daemon.is_alive(daemon), "children": child_state["children"]},
        "kernel_cpu": {"name": c, "current": cpu_state.get("current"),
                       "requests": len(list((cpu_home / "requests").glob("*.json"))) if cpu_home else 0}}


def stop(home, wait_ms=30000, no_wait=False):
    home = Path(home).absolute()
    def post():
        _put(home, "stop-" + aos_client.new_name("cli"), {"jsonrpc": "2.0", "method": "stop"})
    if no_wait:
        post()
        return 0
    state = aos_home.read_state(home, {})
    if not state:
        print("stopped")
        return 0
    info = load_info(home)
    daemon = info.get("daemon", aos_daemon.daemon_home())
    def children(ledger):
        names = {*ledger.get("cpus", {}), *info["cpus"], ledger.get("kcpu")}
        # 與 boot 一樣比對絕對 target；同名但屬於別家的孩子不算。
        base = str(home / "cpus") + os.sep
        return {name: child for name, child in aos_daemon.read_state(daemon)["children"].items()
                if name in names and child["target"].startswith(base)
                and os.path.abspath(child["target"]).startswith(base)}
    owned = children(state)
    if state.get("phase") == "stopped" and not owned:
        print("stopped")
        return 0
    if not aos_daemon.is_alive(daemon) or state.get("kcpu") not in owned:
        print("not running")
        return 0
    post()
    deadline = time.monotonic() + wait_ms / 1000
    while True:
        state = aos_home.read_state(home)
        if state.get("phase") == "stopped" and not children(state):
            print("stopped")
            return 0
        if time.monotonic() >= deadline:
            raise KernelError("Timeout", "等了 %d ms 還沒停好（stop 已放、不撤回），用 aos-kernel ls --target %s 看" % (wait_ms, home))
        time.sleep(.005)

