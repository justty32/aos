"""kernel 的 boot（kernel/boot.md）、狀態快照與 halt 等待。

2026-09-24 one-boot：沒有 kernel cpu、沒有 tick 鏈；boot＝寫 sqlite 帳本＋向 daemon 登記「請替我開 tick」。
"""
import hashlib
import os
from pathlib import Path
import time

import aos_client
import aos_daemon
import aos_daemon_ticks
import aos_home
import aos_kernel_store
from aos_kernel_engine import Kernel, take_lock
from aos_kernel_info import (
    CLI, KERNEL_POOL, KernelError, _put, chain_epoch, error_code, load_info, members,
    new_pool, new_state, pool_location, ticker_daemon, work_pools,
)
from aos_kernel_pools import pool_summary, pool_summary_state, scale_request


def _ledger_version_check(state):
    if "cpus" in state and "pools" not in state:
        raise KernelError("LedgerVersion", "K/state.json 是 proto5 第 1 版的帳本（cpus 表）；請先用舊版 halt、"
                          "把 state.json 移走再 boot（只接手第 2 版的 state.json）")


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
    """one-boot（kernel/boot.md）：驗 → 拿 tick 鎖 → （舊帳本）匯入、舊 kernel 池縮到 0 → 寫帳本 → 建家 → 向 daemon 登記開 tick。"""
    home = Path(home).absolute()
    # 1. 驗（不改任何東西）
    info = load_info(home)
    cli = CLI.resolve()
    if not cli.is_file() or not os.access(cli, os.X_OK):
        raise KernelError("ReadFailed", "kernel CLI 必須有執行位：%s" % cli)
    ticker = ticker_daemon(info)
    if ticker is None:
        raise KernelError("NoDaemon", "解不出替 kernel 開 tick 的 daemon 家（在 info.json 寫 daemon，或 init --daemon）")
    locations = {p: pool_location(info, p) for p in work_pools(info)}
    missing = [p for p, loc in locations.items() if loc[0] is None]
    if missing:
        raise KernelError("NoDaemon", "這些池解不出 daemon 家：%s（在 info.json 寫 daemon，或 init --daemon）" % "、".join(missing))
    for daemon in dict.fromkeys([ticker, *(loc[0] for loc in locations.values())]):
        if not aos_daemon.is_alive(daemon):
            raise KernelError("NotRunning", "daemon 沒在跑：%s（先 aos-daemon boot --target %s，或直接 aos up）" % (daemon, daemon))
    legacy = aos_kernel_store.legacy(home)
    if legacy:
        _ledger_version_check(aos_home.read_state(home, {}))
    # 納入後文件組實測：手建的家缺 requests/、responses/ 時 boot 會成功、之後 add／halt 才 WriteFailed；boot 先補上。
    aos_home.ensure_queue(home)
    (home / "pools").mkdir(exist_ok=True)
    # 2. 拿 tick 鎖：boot 寫帳本時不能有一格正在跑（tick 被 kill -9 鎖自己消失）。
    lock = take_lock(home, wait_ms)
    if lock is None:
        raise KernelError("AlreadyRunning", "有一格 tick 跑了超過 %d ms 還沒完（K/.tick.lock 被佔）；等一下再 boot" % wait_ms)
    try:
        return _boot_locked(home, info, cli, ticker, locations, legacy, wait_ms)
    finally:
        os.close(lock)


def _boot_locked(home, info, cli, ticker, locations, legacy, wait_ms):
    chain = "%d-%d" % (time.time_ns(), os.getpid())
    decl = [chain_epoch(chain), 0]
    store = aos_kernel_store.Store(home, create=True)
    try:
        if legacy:
            state = aos_home.read_state(home, {})
            store.orig = aos_kernel_store._rows(store.conn)[1]
        else:
            state = store.load()
        # 3. 舊版（kernel cpu 時代）帳本的 kernel 池：縮到 0、等 daemon 收乾淨，才寫新帳本。
        acks = _retire_kernel_pool(home, (state.get("pools") or {}).get(KERNEL_POOL), chain, decl, wait_ms)
        # 4. 寫帳本（一筆交易）
        if not state.get("chain") and not state.get("procs"):
            state = new_state(chain, cli)
        state.update(chain=chain, cli=str(cli), ticker=ticker, last_seq=0, phase="running", halting=False,
                     last_tick_at=time.time())
        state.pop("kcpu", None)
        for key, default in (("busy", {}), ("ready", {}), ("delayed", []), ("stale", {}), ("procs", {}),
                             ("acks", []), ("replies", []), ("deletes", []), ("sends", []), ("pools", {})):
            state.setdefault(key, default)
        state["sends"] = [s for s in state["sends"] if (s.get("body") or {}).get("method") not in ("scale", "tick")]
        state["acks"].extend(acks)
        state["pools"].pop(KERNEL_POOL, None)
        for entry in state["pools"].values():
            entry.update(dirty=True, redeclare=True, boot_redeclare=True, retry_at=None)  # 整份重送（astra P3）
        state["recent"] = list(state["busy"])
        kernel = Kernel(home, info, state, 0, store=store)
        # 5. 建家與模板：每池 envs.json、inst.json；W 裡每一號缺的補齊。
        for pool in work_pools(info):
            config = info["pools"][pool]
            entry = state["pools"].get(pool)
            if entry is None:
                entry = state["pools"][pool] = new_pool(*locations[pool])
            entry["envs_digest"] = kernel.write_pool_files(pool, config["envs"])
            for i in members(config["count"], config["skip"]):
                kernel.ensure_cpu_home(pool, i)
        kernel.save()
        if legacy:
            os.replace(home / aos_kernel_store.LEGACY, home / (aos_kernel_store.LEGACY + ".v2-old"))
    finally:
        store.close()
    # 6. 向 daemon 登記：請它定時（tick_ms）或 K/requests/ 有新檔時開一格。
    name = "k-%s-boot-tick.json" % chain
    body = {"jsonrpc": "2.0", "id": name[:-5], "method": "tick",
            "params": {"home": str(home), "cli": str(cli), "every_ms": info["tick_ms"], "timeout_ms": info["tick_timeout_ms"]}}
    response, code = _call(ticker, name, body, wait_ms)
    _ack_now([{"home": ticker, "name": name}], chain)
    if code is not None:
        raise KernelError(code, "daemon %s 不肯開 tick：%s（%s）" % (ticker, code, response["error"].get("message")))
    return 0


def _retire_kernel_pool(home, old_kernel, chain, decl, wait_ms):
    """舊版帳本才有 kernel 池（那顆 kernel cpu）：送 scale 0、等回音、等 daemon 那池收乾淨；回要 ack 的回音。"""
    if not old_kernel:
        return []
    acks = []
    if old_kernel.get("pending"):
        name = old_kernel["pending"]["name"]
        if (Path(old_kernel["daemon"]) / "responses" / name).exists():
            acks.append({"home": old_kernel["daemon"], "name": name})
    target = (old_kernel["daemon"], old_kernel["dpool"])
    name = "k-%s-boot-scale-%s-down.json" % (chain, KERNEL_POOL)
    body = scale_request(name, home, KERNEL_POOL, {"dpool": target[1]}, 0, [], decl)
    _, code = _call(target[0], name, body, wait_ms)
    acks.append({"home": target[0], "name": name})
    if code is not None:
        _ack_now(acks, chain)
        raise KernelError(code, "舊 kernel 池 %s（daemon %s）縮到 0 失敗：%s" % (target[1], target[0], code))
    deadline = time.monotonic() + wait_ms / 1000
    while not _gone_or_idle(*target):
        if time.monotonic() >= deadline:
            _ack_now(acks, chain)
            raise KernelError("AlreadyRunning", "舊 kernel cpu 還沒收乾淨（縮到 0 的單已送、不撤回；%s）；等一下再 boot"
                              % _why_busy([target]))
        time.sleep(.005)
    return acks


def _ack_now(acks, chain):
    """boot 半途失敗、還沒碰帳本：已收的回音當場 ack，免得留在 daemon 家。"""
    for item in acks:
        digest = hashlib.sha256(item["name"].encode()).hexdigest()[:16]
        _put(item["home"], "ack-%s-0-%s-%s.json" % (chain, Path(item["home"]).name, digest),
             {"jsonrpc": "2.0", "method": "ack", "params": {"name": item["name"]}})


def status(home):
    """ls 用的快照：帳本＋每池 daemon 摘要（O(池數)）＋替它開 tick 的 daemon 登記（one-boot）。"""
    home = Path(home).absolute()
    info = load_info(home)
    state = aos_kernel_store.read(home, None)
    legacy = state is None and aos_kernel_store.legacy(home)
    if state is None:
        state = aos_home.read_state(home, {}) if legacy else {}
    pools = {}
    for pool, entry in (state.get("pools") or {}).items():
        if pool == KERNEL_POOL:
            continue
        summary = None
        try:
            summary = pool_summary(entry["daemon"], entry["dpool"])
        except (AttributeError, aos_home.HomeError, OSError):
            pass
        pools[pool] = {**entry, "summary": summary}
    daemon = state.get("ticker") or ticker_daemon(info)
    alive = bool(daemon) and aos_daemon.is_alive(daemon)
    reg = aos_daemon_ticks.peek(daemon, home) if daemon else None
    return {k: state.get(k) for k in ("chain", "phase", "last_seq", "last_tick_at", "halting", "busy", "procs")} | {
        "pools": pools, "legacy": legacy,
        "queued": sum(len(q) for q in (state.get("ready") or {}).values()) + len(state.get("delayed") or []),
        "daemon": {"home": daemon, "alive": alive},
        "ticker": reg}


def _halted(state):
    """phase=stopped，且這個 kernel 的每個池在 daemon 那邊都消失或 count 0、running 0、killing 0、draining 0。"""
    if state.get("phase") != "stopped":
        return False
    seen = {(e["daemon"], e["dpool"]) for p, e in (state.get("pools") or {}).items() if p != KERNEL_POOL}
    return all(_gone_or_idle(d, p) for d, p in seen)


def _read(home):
    if aos_kernel_store.legacy(home):
        raise KernelError("LedgerVersion", "帳本還是舊的 K/state.json；先 aos up（或 aos-kernel boot）換成 sqlite")
    return aos_kernel_store.read(home, {})


def stop(home, wait_ms=30000, no_wait=False):
    home = Path(home).absolute()
    def post():
        _put(home, "stop-" + aos_client.new_name("cli"), {"jsonrpc": "2.0", "method": "stop"})
    if no_wait:
        post()
        return 0
    state = _read(home)
    if not state:
        print("stopped")
        return 0
    if _halted(state):
        print("stopped")
        return 0
    if state.get("phase") != "stopped":
        ticker = state.get("ticker")
        # one-boot：沒有 daemon 替它開 tick（daemon 不在、或沒登記）＝沒在跑，放了 stop 也沒人收。
        if not ticker or not aos_daemon.is_alive(ticker) or aos_daemon_ticks.peek(ticker, home) is None:
            print("not running")
            return 0
        post()
    deadline = time.monotonic() + wait_ms / 1000
    while True:
        state = _read(home)
        if _halted(state):
            print("stopped")
            return 0
        if time.monotonic() >= deadline:
            why = _why_busy({(e["daemon"], e["dpool"]) for p, e in (state.get("pools") or {}).items() if p != KERNEL_POOL})
            raise KernelError("Timeout", "等了 %d ms 還沒停好（stop 已放、不撤回）。若卡在縮池，daemon 那邊會留下非 0 的宣告，"
                              "這時停 daemon 的話下次開 daemon 會把那些池拉回來；先用 aos-kernel ls --target %s 看原因%s"
                              % (wait_ms, home, "（%s）" % why if why else ""))
        time.sleep(.005)
