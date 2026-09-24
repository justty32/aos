"""`aos up`／`aos down`：一條指令開機、一條指令停機（spec/daemon/up.md；2026-09-24 one-boot）。

程式不合一，只是包起來（I 隊裁決②）：
  up    ＝ 需要的 daemon 沒在跑就開（setsid 放背景、stderr 接 D/daemon.log、PATH 前面補 proto5/cli）
          → aos-kernel boot（寫帳本、向 daemon 登記開 tick）→ 等 daemon 開的第一格跑完。
  down  ＝ aos-kernel halt（等 phase stopped、池都收完；停好那格 kernel 自己撤登記）
          → 這些 daemon 沒別的 kernel、沒別的池了就 aos-daemon halt。
`aos-daemon`／`aos-kernel` 的子命令都還在，給人 debug。
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

import aos_daemon
import aos_daemon_ticks
import aos_home
import aos_kernel_boot
import aos_kernel_store
from aos_kernel_info import CLI, KernelError, load_info, pool_location, ticker_daemon, work_pools

CLI_DIR = CLI.parent
ENV = "AOS_KERNEL_HOME"


class UpError(aos_home.HomeError):
    pass


def _daemons(info):
    """這個 kernel 用到的 daemon 家：開 tick 的那個排第一，再來各池的。"""
    ticker = ticker_daemon(info)
    if ticker is None:
        raise KernelError("NoDaemon", "解不出 daemon 家（在 K/info.json 寫 daemon，或 aos-kernel init --daemon D）")
    homes = [ticker]
    for pool in work_pools(info):
        daemon = pool_location(info, pool)[0]
        if daemon is None:
            raise KernelError("NoDaemon", "池 %s 解不出 daemon 家" % pool)
        homes.append(daemon)
    return list(dict.fromkeys(homes))


def _env():
    env = dict(os.environ)
    parts = env.get("PATH", os.defpath).split(os.pathsep)
    if str(CLI_DIR) not in parts:
        env["PATH"] = os.pathsep.join([str(CLI_DIR), *parts])   # daemon 拉的 cpu、開的 tick 都靠 PATH 找 aos-*
    return env


def start_daemon(home, wait_ms):
    """開一支 daemon（跟終端脫鉤）；等它拿到鎖。回 True＝這次新開的。"""
    home = Path(home)
    if aos_daemon.is_alive(home):
        return False
    home.mkdir(parents=True, exist_ok=True)
    with open(home / "daemon.log", "ab") as log:
        proc = subprocess.Popen([str(CLI_DIR / "aos-daemon"), "boot", "--target", str(home)], env=_env(),
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    deadline = time.monotonic() + wait_ms / 1000
    while not aos_daemon.is_alive(home):
        code = proc.poll()
        if code is not None:
            raise UpError("DaemonFailed", "daemon 開不起來（退出 %d）；看 %s" % (code, home / "daemon.log"))
        if time.monotonic() >= deadline:
            raise UpError("Timeout", "等 daemon 拿到鎖逾時；看 %s" % (home / "daemon.log"))
        time.sleep(.01)
    return True


def up(home, wait_ms=30000):
    home = Path(home).absolute()
    info = load_info(home)
    daemons = _daemons(info)
    started = [d for d in daemons if start_daemon(d, wait_ms)]
    aos_kernel_boot.boot(home, wait_ms)
    # boot 把 last_seq 歸 0；daemon 登記當下就開第一格，等它跑完（能收單了）。
    deadline = time.monotonic() + wait_ms / 1000
    while (aos_kernel_store.meta(home, "last_seq").get("last_seq") or 0) < 1:
        if time.monotonic() >= deadline:
            raise UpError("Timeout", "boot 完了但第一格 tick 沒跑完；看 aos-kernel ls --target %s 與 %s" % (
                home, Path(daemons[0]) / "daemon.log"))
        time.sleep(.005)
    code, message = _settle(home, info, deadline)
    pools = work_pools(info)
    print("up K=%s  daemon %s%s  %d 個池、%d 顆 cpu" % (
        home, daemons[0], "（新開）" if daemons[0] in started else "（本來就在）", len(pools),
        sum(info["pools"][p]["count"] for p in pools)))
    for extra in daemons[1:]:
        print("  另一個 daemon %s%s" % (extra, "（新開）" if extra in started else "（本來就在）"))
    print("health " + message)
    return 1 if code in ("pools", "daemon", "tick", "legacy", "broken", "dirs") else 0


def _settle(home, info, deadline):
    """第一格跑完後，再等各池的第一張宣告有回音（講好了或出錯），最多 5 秒；回 health。
    池名撞了（NameTaken）這類錯要等 daemon 回音後的下一格才看得到，不等就會先印 up 再出事（教程組真跑挖到）。"""
    import aos_kernel_health
    until = min(deadline, time.monotonic() + 5)
    while True:
        state = aos_kernel_store.read(home, {})
        pools = state.get("pools") or {}
        if all(p in pools and (pools[p].get("error") or (pools[p].get("pending") is None and not pools[p].get("redeclare")))
               for p in work_pools(info)) or time.monotonic() >= until:
            return aos_kernel_health.health(home, info=info)
        time.sleep(.02)


def _others(daemon, home):
    """這個 daemon 還在替誰服務（別的 kernel 登記、池）。"""
    kernels = [r["home"] for r in aos_daemon_ticks.registered(daemon) if os.path.abspath(r["home"]) != str(home)]
    pools_dir = Path(daemon) / "pools"
    pools = sorted(p.name for p in pools_dir.iterdir() if p.is_dir()) if pools_dir.is_dir() else []
    return kernels, pools


def down(home, wait_ms=30000, keep_daemon=False):
    home = Path(home).absolute()
    info = load_info(home)
    daemons = _daemons(info)
    code = aos_kernel_boot.stop(home, wait_ms)
    if code:
        return code
    ticker = daemons[0]
    deadline = time.monotonic() + min(wait_ms, 5000) / 1000
    while aos_daemon.is_alive(ticker) and aos_daemon_ticks.peek(ticker, home) is not None:
        if time.monotonic() >= deadline:
            break                                     # 撤登記的單還沒被處理：照樣往下（daemon 停了下次也不會開）
        time.sleep(.01)
    if keep_daemon:
        return 0
    for daemon in daemons:
        if not aos_daemon.is_alive(daemon):
            continue
        kernels, pools = _others(daemon, home)
        if kernels or pools:
            print("daemon %s 沒停：還有 %s（要停就 aos-daemon halt --target %s）" % (
                daemon, "；".join(filter(None, ["別的 kernel：" + "、".join(kernels) if kernels else "",
                                                 "池：" + "、".join(pools) if pools else ""])), daemon))
            continue
        aos_daemon.stop(daemon, wait_ms)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aos", description="一條指令開機、停機（daemon＋kernel）；細節指令用 aos-daemon／aos-kernel")
    subs = parser.add_subparsers(dest="command", required=True)
    for name, text in (("up", "開機：daemon 沒在跑就開，再 boot kernel，等第一格 tick 跑完"),
                       ("down", "停機：kernel halt 等停好，daemon 沒別人要用就一起停")):
        p = subs.add_parser(name, help=text, description=text)
        p.add_argument("--target", metavar="K", help="kernel 家（省略＝AOS_KERNEL_HOME，再沒有就目前資料夾）")
        p.add_argument("--wait-ms", type=int, default=30000, help="每一步等待上限（毫秒，預設 30000）")
        if name == "down":
            p.add_argument("--keep-daemon", action="store_true", help="只停 kernel，daemon 留著")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    note = ""
    try:
        if args.target == "" or args.wait_ms < 0:
            parser.error("--target 不可為空、--wait-ms 不可為負")
        home, source = aos_home.resolve_target(args.target, ENV)
        note = aos_home.target_note("K", home, source, ENV)
        if args.command == "up":
            return up(home, args.wait_ms)
        return down(home, args.wait_ms, args.keep_daemon)
    except aos_home.HomeError as exc:
        sys.stderr.write("aos: %s: %s%s\n" % (exc.code, exc.msg.replace("\n", " "), note))
        return 1
    except OSError as exc:
        sys.stderr.write("aos: IOFailed: %s%s\n" % (exc, note))
        return 1
