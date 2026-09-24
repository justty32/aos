"""kernel 的 boot 交接（handoff §1 六步）、狀態快照與 halt 等待（kernel-cli halt、handoff §3）。"""
import hashlib
import os
from pathlib import Path
import time

import aos_client
import aos_daemon
import aos_home
from aos_kernel_engine import Kernel
from aos_kernel_info import (
    CLI, KCPU, KERNEL_POOL, KernelError, _put, chain_epoch, error_code, load_info, members,
    new_pool, new_state, pool_location,
)
from aos_kernel_pools import pool_summary, pool_summary_state, scale_request


def _ledger_version_check(state):
    if "cpus" in state and "pools" not in state:
        raise KernelError("LedgerVersion", "K/state.json 是 proto5 的帳本（cpus 表）；請先用 proto5 halt、"
                          "把 state.json 移走再 boot（proto5-2 不接手舊帳本）")


def _call(daemon, name, body, wait_ms):
    """放一張 scale 單、等回音；回（回音, 錯誤碼或 None）。ack 由呼叫者記進帳本。"""
    if not (Path(daemon) / "responses" / name).exists():
        _put(daemon, name, body)
    response = aos_client.wait_response(daemon, name, timeout_ms=wait_ms, poll_ms=5)
    return response, (error_code(response) if "error" in response else None)


def _gone_or_idle(daemon, dpool):
    """boot 與 halt 共用：那池 summary 確定不在（gone），或 count 0、running 0、killing 0、draining 0。
    summary 在但讀不到（unknown）一律當還在（astra P6）。draining 也要 0：handoff §1.2 字面只列
    running／killing，但同段要「沒有任何一格在跑」，縮 0 後還在收的孩子算 draining（astra P2、D-5）。"""
    state, summary = pool_summary_state(daemon, dpool)
    if state == "gone":
        return True
    if state != "ok":
        return False
    return all(summary.get(k, 0) == 0 for k in ("count", "running", "killing", "draining"))


def _why_busy(targets):
    """等不到時給人看的原因。"""
    out = []
    for daemon, dpool in targets:
        state, summary = pool_summary_state(daemon, dpool)
        if state == "unknown":
            out.append("%s %s 的 summary.json 在但讀不到" % (daemon, dpool))
        elif state == "ok" and not _gone_or_idle(daemon, dpool):
            out.append("%s %s：%s" % (daemon, dpool, "、".join(
                "%s %s" % (k, summary.get(k, 0)) for k in ("count", "running", "killing", "draining"))))
    return "；".join(out)


def boot(home, wait_ms=30000):
    home = Path(home).absolute()
    # 1. 驗（不改任何東西）
    info = load_info(home)
    cli = CLI.resolve()
    if not cli.is_file() or not os.access(cli, os.X_OK):
        raise KernelError("ReadFailed", "kernel CLI 必須有執行位：%s" % cli)
    locations = {p: pool_location(info, p) for p in info["pools"]}
    missing = [p for p, loc in locations.items() if loc[0] is None]
    if missing:
        raise KernelError("NoDaemon", "這些池解不出 daemon 家：%s（在 info.json 寫 daemon，或 init --daemon）" % "、".join(missing))
    for daemon in dict.fromkeys(loc[0] for loc in locations.values()):
        if not aos_daemon.is_alive(daemon):
            raise KernelError("NotRunning", "daemon 沒在跑：%s（先 aos-daemon boot --target %s）" % (daemon, daemon))
    old = aos_home.read_state(home, {})
    _ledger_version_check(old)
    # 納入後文件組實測：手建的家缺 requests/、responses/ 時 boot 會成功、之後 add／halt 才 WriteFailed；boot 先補上。
    aos_home.ensure_queue(home)
    chain = "%d-%d" % (time.time_ns(), os.getpid())
    decl = [chain_epoch(chain), 0]
    # 2. 交接 kernel 池：帳本的與 info 的各縮到 0、等回音、等 daemon 那池收乾淨。
    acks = []
    old_kernel = (old.get("pools") or {}).get(KERNEL_POOL)
    targets = [(old_kernel["daemon"], old_kernel["dpool"])] if old_kernel else []
    targets = list(dict.fromkeys([*targets, tuple(locations[KERNEL_POOL])]))
    if old_kernel and old_kernel.get("pending"):
        name = old_kernel["pending"]["name"]
        if (Path(old_kernel["daemon"]) / "responses" / name).exists():
            acks.append({"home": old_kernel["daemon"], "name": name})
    for n, (daemon, dpool) in enumerate(targets):
        name = "k-%s-boot-scale-%s-down%s.json" % (chain, KERNEL_POOL, "" if n == 0 else "-%d" % (n + 1))
        body = scale_request(name, home, KERNEL_POOL, {"dpool": dpool}, 0, [], decl)
        _, code = _call(daemon, name, body, wait_ms)
        acks.append({"home": daemon, "name": name})
        if code is not None:
            _ack_now(acks, chain)
            raise KernelError(code, "kernel 池 %s（daemon %s）縮到 0 失敗：%s" % (dpool, daemon, code))
    deadline = time.monotonic() + wait_ms / 1000
    while not all(_gone_or_idle(d, p) for d, p in targets):
        if time.monotonic() >= deadline:
            _ack_now(acks, chain)
            raise KernelError("AlreadyRunning", "舊 kernel cpu 還沒收乾淨（縮到 0 的單已送、不撤回；%s）；等一下再 boot"
                              % _why_busy(targets))
        time.sleep(.005)
    # 3. 寫帳本：舊主人確認退出後重讀（astra P1）；交接前的 old 只拿來找舊 kernel 池，
    #    等待期間舊 tick 可能又提交過（新登記的行程、結清的工作），不能拿舊快照蓋掉。
    state = aos_home.read_state(home, {})
    _ledger_version_check(state)
    state = state if state else new_state(chain, cli)
    state.update(chain=chain, kcpu=KCPU, cli=str(cli), last_seq=0, phase="running", halting=False)
    for key, default in (("busy", {}), ("on", {}), ("ready", {}), ("delayed", []), ("stale", {}), ("procs", {}),
                         ("acks", []), ("replies", []), ("deletes", []), ("sends", []), ("pools", {})):
        state.setdefault(key, default)
    state["sends"] = [s for s in state["sends"] if (s.get("body") or {}).get("method") != "scale"]
    state["acks"].extend(acks)
    for pool, entry in list(state["pools"].items()):
        if pool == KERNEL_POOL:
            continue
        entry.update(dirty=True, redeclare=True, boot_redeclare=True, retry_at=None)  # 整份重送（astra P3）
    kernel_daemon, kernel_dpool = locations[KERNEL_POOL]
    state["pools"][KERNEL_POOL] = {"daemon": kernel_daemon, "dpool": kernel_dpool,
                                   "sent": {"count": 0, "skip": []}, "pending": None}
    state["recent"] = list(state["busy"])
    kernel = Kernel(home, info, state, 0)
    kernel.save()
    # 4. 建家與模板：每池 envs.json、inst.json；W 裡每一號缺的補齊。
    for pool, config in info["pools"].items():
        entry = state["pools"].get(pool)
        if pool != KERNEL_POOL and entry is None:
            entry = state["pools"][pool] = new_pool(*locations[pool])
        digest = kernel.write_pool_files(pool, config["envs"])
        if pool != KERNEL_POOL:
            entry["envs_digest"] = digest
        for i in members(config["count"], config["skip"]):
            kernel.ensure_cpu_home(pool, i)
    kernel.save()
    # 5. 拉 kernel 池
    name = "k-%s-boot-scale-%s.json" % (chain, KERNEL_POOL)
    body = scale_request(name, home, KERNEL_POOL, {"dpool": kernel_dpool}, 1, [], decl)
    _, code = _call(kernel_daemon, name, body, wait_ms)
    state["acks"].append({"home": kernel_daemon, "name": name})
    if code is None:
        state["pools"][KERNEL_POOL]["sent"] = {"count": 1, "skip": []}
    kernel.save()
    if code is not None:
        raise KernelError(code, "kernel 池 %s（daemon %s）拉起失敗：%s" % (kernel_dpool, kernel_daemon, code))
    # 6. 放第 1 格
    name, request = kernel.tick_request(1)
    _put(kernel.cpu_home(KCPU), name, request)
    return 0


def _ack_now(acks, chain):
    """boot 半途失敗、還沒碰帳本：已收的回音當場 ack，免得留在 daemon 家。"""
    for item in acks:
        digest = hashlib.sha256(item["name"].encode()).hexdigest()[:16]
        _put(item["home"], "ack-%s-0-%s-%s.json" % (chain, Path(item["home"]).name, digest),
             {"jsonrpc": "2.0", "method": "ack", "params": {"name": item["name"]}})


def status(home):
    """ls 用的快照：帳本＋每池 daemon 摘要（O(池數)）。"""
    home = Path(home).absolute()
    info, state = load_info(home), aos_home.read_state(home, {})
    pools = {}
    for pool, entry in (state.get("pools") or {}).items():
        summary = None
        try:
            summary = pool_summary(entry["daemon"], entry["dpool"])
        except (AttributeError, aos_home.HomeError, OSError):
            pass
        pools[pool] = {**entry, "summary": summary}
    kernel = (state.get("pools") or {}).get(KERNEL_POOL) or {}
    daemon = kernel.get("daemon") or (pool_location(info, KERNEL_POOL) or (None,))[0]
    cpu_home = home / "pools" / KERNEL_POOL / "cpus" / "0"
    cpu_state = aos_home.read_state(cpu_home) if cpu_home.exists() else {}
    return {k: state.get(k) for k in ("chain", "phase", "last_seq", "halting", "busy", "procs")} | {
        "pools": pools,
        "queued": sum(len(q) for q in (state.get("ready") or {}).values()) + len(state.get("delayed") or []),
        "daemon": {"home": daemon, "alive": bool(daemon) and aos_daemon.is_alive(daemon)},
        "kernel_cpu": {"name": KCPU, "current": cpu_state.get("current"),
                       "requests": len(list((cpu_home / "requests").glob("*.json"))) if cpu_home.exists() else 0}}


def _halted(state):
    """phase=stopped，且這個 kernel 的每個池在 daemon 那邊都消失或 count 0、running 0、killing 0、draining 0。"""
    if state.get("phase") != "stopped":
        return False
    seen = {(e["daemon"], e["dpool"]) for e in (state.get("pools") or {}).values()}
    return all(_gone_or_idle(d, p) for d, p in seen)


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
    _ledger_version_check(state)
    if _halted(state):
        print("stopped")
        return 0
    if state.get("phase") != "stopped":
        kernel = (state.get("pools") or {}).get(KERNEL_POOL)
        # summary 讀不到（unknown）當還在跑：照放 stop、照等（astra P6）。
        known, summary = pool_summary_state(kernel["daemon"], kernel["dpool"]) if kernel else ("gone", None)
        if (kernel is None or not aos_daemon.is_alive(kernel["daemon"]) or known == "gone"
                or (known == "ok" and summary.get("count", 0) == 0)):
            print("not running")
            return 0
        post()
    deadline = time.monotonic() + wait_ms / 1000
    while True:
        state = aos_home.read_state(home)
        if _halted(state):
            print("stopped")
            return 0
        if time.monotonic() >= deadline:
            why = _why_busy({(e["daemon"], e["dpool"]) for e in (state.get("pools") or {}).values()})
            raise KernelError("Timeout", "等了 %d ms 還沒停好（stop 已放、不撤回）。若卡在縮池，daemon 那邊會留下非 0 的宣告，"
                              "這時停 daemon 的話下次開 daemon 會把那些池拉回來；先用 aos-kernel ls --target %s 看原因%s"
                              % (wait_ms, home, "（%s）" % why if why else ""))
        time.sleep(.005)
