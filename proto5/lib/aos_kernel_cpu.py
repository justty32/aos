"""kernel 的 `cpu add／rm／ls`（kernel-cli.md 的 cpu 三段）；按池摘要與一顆一行的排版在 aos_kernel_rows。

cpu add／rm 只改 `K/info.json` 的池表：拿 `K/.info.lock` 獨占鎖（等 10 秒）→ 讀 → 改 → 驗 → 唯一 .tmp → rename。
不放任何單、不用 boot；kernel 在跑的話下一格就照新數字做（kernel-pools）。
cpu ls 讀帳本＋daemon 的 summary.json（O(池數)）；`--pool P` 再逐顆讀 kids 檔（O(池大小)）。
"""
import copy
import fcntl
import json
import os
from pathlib import Path
import time

import aos_daemon
import aos_daemon_ticks
import aos_home
import aos_kernel_store
from aos_kernel_info import (
    KERNEL_POOL, CLIUsage, KernelError, _parse_info, load_info, members, pool_name_ok, split_key,
)
from aos_kernel_rows import cpu_line, cpu_rows, pool_lines, pool_rows

LOCK_WAIT_S = 10.0


class UsageError(CLIUsage):
    """用法錯（退 2），但代號不是 Usage（例：PoolExists）。"""
    def __init__(self, code, msg):
        KernelError.__init__(self, code, msg)


# ---- 寫 info（kernel-cli「cpu add／rm 怎麼寫 info」） ----

def _lock(home, wait_s=None):
    wait_s = LOCK_WAIT_S if wait_s is None else wait_s
    fd = os.open(home / ".info.lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o644)
    deadline = time.monotonic() + wait_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                raise KernelError("Busy", "別的 aos-kernel cpu add／rm 正拿著 %s，等了 %d 秒；等一下再試" % (
                    home / ".info.lock", wait_s))
            time.sleep(.02)


def _literal_dict(value):
    return isinstance(value, dict) and not any(isinstance(k, str) and k.startswith("$") for k in value)


def _edit(home, change):
    """鎖著做完 讀→改→驗→寫；change(raw, info) 只改 raw 的 pools.P.count／skip／新池那格，回要印的字。"""
    home = Path(home).absolute()
    aos_home.read_json(home / "info.json")  # 家不在就先報讀不到，不在別人的地方建鎖檔
    fd = _lock(home)
    try:
        raw = aos_home.read_json(home / "info.json")
        info = _parse_info(home, copy.deepcopy(raw))
        if not _literal_dict(raw) or not _literal_dict(raw.get("pools")):
            raise KernelError("NotLiteral", "info.json 的 pools 用了指示詞，cpu add／rm 不改；請直接編 %s" % (home / "info.json"))
        message = change(raw, info)
        _parse_info(home, copy.deepcopy(raw))  # 改完一樣要過讀驗；過不了就不寫
        aos_home.write_json(home / "info.json", raw)
        return message
    finally:
        os.close(fd)


def _literal_pool(raw, pool):
    """既有池那格要是字面物件、count／skip 是字面值，CLI 才改；否則請人手改（D-37）。"""
    config = raw["pools"][pool]
    ok = (_literal_dict(config) and type(config.get("count")) is int and
          ("skip" not in config or (isinstance(config["skip"], list) and all(type(s) is int for s in config["skip"]))))
    if not ok:
        raise KernelError("NotLiteral", "池 %s 的 count／skip 用了指示詞，cpu add／rm 不改；請直接編 info.json" % pool)
    return config


def _set_count(config, count, skip):
    """寫回 count 與整理過的 skip：只排序、去重，一律保留、不丟（D-38，隊長裁定見 decisions.md：
    Q4 永久退休優先於 skip 長度，代價是 skip 只增不減，要清得手改 info）。"""
    skip = sorted(set(skip))
    config["count"] = count
    if skip or "skip" in config:
        config["skip"] = skip


def kernel_running(home):
    """kernel 現在會不會照新數字做：帳本 phase running、替它開 tick 的 daemon 活著而且登記著它（one-boot）。"""
    try:
        state = aos_kernel_store.meta(home, "phase", "chain", "ticker")
        if state.get("phase") != "running" or not state.get("chain") or not state.get("ticker"):
            return False
        if not aos_daemon.is_alive(state["ticker"]):
            return False
        return aos_daemon_ticks.peek(state["ticker"], home) is not None
    except (aos_home.HomeError, OSError, KeyError, TypeError, AttributeError):
        return False


def _check_pool_arg(pool):
    if not pool_name_ok(pool):
        raise CLIUsage("池名不合法（1～64 字、只用 A-Z a-z 0-9 _ . -）：%r" % pool)
    if pool == KERNEL_POOL:
        raise CLIUsage("kernel 是保留名（one-boot 起 kernel 沒有自己的池），不能 cpu add／rm")


def _parse_envs(values):
    envs = {}
    for item in values or ():
        key, sep, value = item.partition("=")
        if not sep or not key or key.startswith("$") or "\0" in item:
            raise CLIUsage("--env 要寫成 KEY=VALUE（KEY 不能空、不能用 $ 開頭）：%r" % item)
        if key in envs:
            raise CLIUsage("--env %s 給了兩次" % key)
        envs[key] = value
    return envs


def _report(home, pool, before, after):
    lines = ["pool %s count %d -> %d" % (pool, before, after)]
    if not kernel_running(home):
        lines.append("kernel 沒在跑：下次 boot 生效（aos-kernel boot --target %s）" % home)
    return "\n".join(lines)


def cpu_add(home, pool, count=None, env=None, daemon=None, dpool=None):
    home = Path(home).absolute()
    _check_pool_arg(pool)
    count = 1 if count is None else count
    if type(count) is not int or count < 0:
        raise CLIUsage("--count 必須是非負整數")
    envs = _parse_envs(env)
    if daemon == "" or dpool == "":
        raise CLIUsage("--daemon／--dpool 不可為空")
    if dpool is not None and not pool_name_ok(dpool):
        raise CLIUsage("--dpool 不合法（同池名規則）：%r" % dpool)

    def change(raw, info):
        pools = raw["pools"]
        if pool in pools:
            if env or daemon is not None or dpool is not None:
                raise UsageError("PoolExists", "池 %s 已經在了：cpu add 只加 count；改既有池的 envs／daemon／dpool 請直接編 %s"
                                 "（影響見 kernel-info §4）" % (pool, home / "info.json"))
            config = _literal_pool(raw, pool)
            before = config["count"]
            _set_count(config, before + count, config.get("skip", []))
            return _report(home, pool, before, before + count)
        config = {"count": count}
        if envs:
            config["envs"] = envs
        if daemon is not None:
            config["daemon"] = os.path.abspath(os.path.expanduser(daemon))
        if dpool is not None:
            config["dpool"] = dpool
        pools[pool] = config
        return _report(home, pool, 0, count)
    return _edit(home, change)


def cpu_rm(home, name=None, pool=None, count=None):
    home = Path(home).absolute()
    if (name is None) == (pool is None):
        raise CLIUsage("cpu rm 要給 P/<i>，或 --pool P --count N（二選一）")
    if name is not None:
        if count is not None:
            raise CLIUsage("cpu rm P/<i> 不能再給 --count")
        parsed = split_key(name)
        if parsed is None:
            raise CLIUsage("cpu 全名要寫成 P/<i>（i 是不帶前導 0 的十進位）：%r" % name)
        pool, number = parsed
    else:
        if count is None:
            raise CLIUsage("cpu rm --pool P 要給 --count N")
        if type(count) is not int or count <= 0:
            raise CLIUsage("--count 必須是正整數")
        number = None
    _check_pool_arg(pool)

    def change(raw, info):
        if pool not in raw["pools"]:
            raise KernelError("NotFound", "沒有這個池：%s（看 aos-kernel cpu ls --target %s）" % (pool, home))
        config = _literal_pool(raw, pool)
        before, skip = config["count"], list(config.get("skip", []))
        if number is not None:
            if number not in set(members(before, skip)):
                raise KernelError("NotFound", "%s/%d 不是池 %s 現在的成員（看 aos-kernel cpu ls --target %s --pool %s）" % (
                    pool, number, pool, home, pool))
            _set_count(config, before - 1, skip + [number])
            return _report(home, pool, before, before - 1)
        if count > before:
            raise CLIUsage("池 %s 只有 %d 顆，不能收 %d 顆" % (pool, before, count))
        _set_count(config, before - count, skip)
        return _report(home, pool, before, before - count)
    return _edit(home, change)


def cpu_ls(home, pool=None, as_json=False):
    home = Path(home).absolute()
    info = load_info(home)
    state = aos_home.read_state(home, {}) if aos_kernel_store.legacy(home) else aos_kernel_store.read(home, {})
    rows = pool_rows(home, info, state, only=pool)
    if pool is not None and not rows:
        raise KernelError("NotFound", "沒有這個池：%s（info 與帳本都沒有）" % pool)
    if pool is not None:
        rows[pool]["cpus"] = cpu_rows(info, state, pool, rows[pool])
    if as_json:
        return json.dumps({"pools": rows}, ensure_ascii=False)
    lines = pool_lines(home, info, rows)
    if pool is not None:
        lines.extend(cpu_line(item) for item in rows[pool]["cpus"])
    return "\n".join(lines)
