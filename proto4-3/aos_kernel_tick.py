#!/usr/bin/env python3
"""aos-kernel-tick：kernel 的心跳，獨立指令（不吃參數，cwd 就是家）。

    aos-kernel-tick

kernel 每隔一段時間自己跑一次的就是這支（`aos-kernel-init` 寫出的 `inst.json` 指到這裡）
——跟很久一次的 `aos-kernel-init` 不是同一種壽命，所以也拆成自己的指令
（[proto4 筆記 §19.7](../proto4/notes/2026-09-08-ideas.md)）。核心是 `tick()`：六步，
順序固定，做完一律退出 0。

1. **讀自己的表**（`state.json`，沒有＝空表）。
2. **點 cpu**：讀 daemon 的 `state.json`（直接讀檔，不開 ctl 進程），看 `cpus/<n>.json`
   這 N 個 key 哪些在 daemon 表上。不在表上的：檔案不見了就先寫一份 idle 指令，再
   `aos-daemon-ctl add`（**不開 `--stop-on-error`**）。add 失敗（daemon 沒跑之類）記一行
   log、那顆 cpu 這回合不排程，退出仍 0。
3. **處理 syscall**：依序讀 `syscalls/*.json`，目前只認 rm。
4. **檢查佇列**：`procs/*.json`（不含 `bad/`）逐個讀，基本欄位或 aos-exec 完整驗證不過
   → 搬到 `procs/bad/` 同名（§17.1：cwd 這道檢查只在 kernel 做）。
5. **排程**：idle 的 cpu 有人等就上人；有人在跑但「daemon 的 runs － 上去時記的 runs」
   滿 quantum 而且還有人等，就換人——**換檔不留空窗**（§17.2 第 3 條）：先
   `os.link(cpus/n.json, procs/<舊>.json)` 讓舊的先在 `procs/` 有名字，再
   `os.rename(procs/<新>.json, cpus/n.json)` 原子蓋過去，`cpus/n.json` 任何時刻都在。
   佇列是 FIFO：新出現的排尾巴、被換下來的也排尾巴、檔案不見的從佇列拿掉。
6. **寫表寫 log**（`state.json` 先 `.tmp` 再 rename、`kernel.log` append 一行），退出 0。
"""
import json
import os
import subprocess
import sys
import time

import aos_home
import aos_inst
from aos_kernel import CTL_BIN, IDLE_INST, here_or_die
from aos_kernel_syscall import handle_syscalls


def tick(h, cfg, now=None):
    now = time.time() if now is None else now
    st = h.state()
    for n in range(cfg["ncpu"]):
        st["cpus"].setdefault(str(n), None)
    notes = []
    ready = poll_cpus(h, cfg, st, notes)
    handle_syscalls(h, cfg, st, notes)
    check_queue(h, notes)
    schedule(h, cfg, st, ready, notes, now)
    h.save(st)
    h.log("%s q=[%s] | %s" % (
        " ".join("cpu%d=%s" % (n, (st["cpus"].get(str(n)) or {}).get("pid", "idle"))
                 for n in range(cfg["ncpu"])),
        " ".join(st["queue"]), "；".join(notes) if notes else "沒事"))
    return 0


def daemon_runs():
    """daemon 的表：key（那份 .json 的 realpath）→ 那一筆。讀不到＝空的。"""
    state = aos_home.Home(aos_home.resolve_home()).state() or {}
    runs = state.get("runs")
    return runs if isinstance(runs, dict) else {}


def poll_cpus(h, cfg, st, notes):
    """回 `{n: daemon 那一筆}`——只有在 daemon 表上的 cpu 這回合才排程。"""
    runs = daemon_runs()
    ready = {}
    for n in range(cfg["ncpu"]):
        path = h.cpu(n)
        if not os.path.exists(path):            # 檔被人刪了：補一份 idle，上面那位就沒了
            aos_home.write_json(path, IDLE_INST)
            if st["cpus"].get(str(n)):
                notes.append("cpu%d 的檔不見了（原本是 %s），補 idle"
                             % (n, st["cpus"][str(n)].get("pid")))
                st["cpus"][str(n)] = None
        ent = runs.get(os.path.realpath(path))
        if ent is not None:
            ready[n] = ent
            continue
        ok, msg = ctl_add(path, cfg)
        notes.append("cpu%d 插上 daemon %s%s" % (n, "成功" if ok else "失敗",
                                                 "" if ok else "：" + msg))
    return ready


def ctl_add(path, cfg):
    """`aos-daemon-ctl add <絕對路徑> --interval-ms X [--timeout-ms Y]`，回 (成功嗎, 說了什麼)。"""
    args = [sys.executable, CTL_BIN, "add", os.path.abspath(path),
            "--interval-ms", str(cfg["interval_ms"])]
    if cfg["timeout_ms"]:
        args += ["--timeout-ms", str(cfg["timeout_ms"])]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e).replace("\n", " ")
    return r.returncode == 0, (r.stdout + r.stderr).strip().replace("\n", " ")


def bad_reason(path):
    """這份 procs/*.json 有沒有問題？沒有＝回 None。"""
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except OSError as e:
        return "讀不到：%s" % e
    except ValueError:
        return "不是 JSON"
    if not isinstance(obj, dict):
        return "不是 JSON 物件"
    if "argv" not in obj:
        return "沒有 argv"
    if "cwd" not in obj:
        return "沒寫 cwd"
    if not isinstance(obj["cwd"], str):
        return "cwd 不是字串"
    try:
        aos_inst.load(path, os.path.dirname(path))
    except aos_inst.InstError as e:
        return str(e)
    return None


def check_queue(h, notes):
    """壞的搬去 `procs/bad/` 同名——搬走就不會被排上 cpu。"""
    for pid in h.pids():
        path = h.proc(pid)
        why = bad_reason(path)
        if why is None:
            continue
        os.makedirs(h.bad, exist_ok=True)
        os.replace(path, os.path.join(h.bad, "%s.json" % pid))
        notes.append("退件 %s.json（%s）" % (pid, why))


def schedule(h, cfg, st, ready, notes, now):
    present = h.pids()
    on_cpu = {c["pid"] for c in st["cpus"].values() if c}
    queue = [p for p in st["queue"] if p in present and p not in on_cpu]
    for p in present:                          # 新出現的排尾巴（同一回合的照 pid 順序）
        if p not in queue and p not in on_cpu:
            queue.append(p)
    for n in range(cfg["ncpu"]):
        if n in ready:
            _one_cpu(h, cfg, st, queue, notes, now, n, ready)
    st["queue"] = queue


def _one_cpu(h, cfg, st, queue, notes, now, n, ready):
    key = str(n)
    cur = st["cpus"].get(key)
    ent = ready[n]
    runs_now = ent.get("runs", 0)
    if cur and runs_now < cur.get("runs_at", 0):    # cpu 換過一支 aos-run，runs 從頭數
        cur["runs_at"] = runs_now
    if cur is None:
        if queue:
            _take(h, st, queue, notes, now, n, runs_now)
        return
    if (cfg["done_exit"] != 0 and ent.get("last_kind") == "child"
            and ent.get("last_exit") == cfg["done_exit"]
            and runs_now - cur.get("runs_at", 0) >= 2):
        _finish(h, st, notes, now, n, cur["pid"])
        return
    if ent.get("last_kind") == "aos" and runs_now - cur.get("runs_at", 0) >= 2:
        cur["aos_ticks"] = cur.get("aos_ticks", 0) + 1
    else:
        cur["aos_ticks"] = 0
    if cur["aos_ticks"] >= 2:
        _reject_running(h, st, notes, n, cur["pid"])
        return
    if runs_now - cur.get("runs_at", 0) >= cfg["quantum"] and queue:
        _swap(h, st, queue, notes, now, n, runs_now, cur["pid"])


def _take(h, st, queue, notes, now, n, runs_now):
    """空的 cpu 上人：直接 rename 過去。"""
    nxt = queue[0]
    try:
        os.replace(h.proc(nxt), h.cpu(n))
    except OSError as e:
        notes.append("cpu%d 上 %s 失敗：%s" % (n, nxt, e))
        return
    queue.pop(0)
    st["cpus"][str(n)] = {"pid": nxt, "since": now, "runs_at": runs_now}
    notes.append("cpu%d 上 %s" % (n, nxt))


def _swap(h, st, queue, notes, now, n, runs_now, old):
    """跑滿 quantum：換人。先硬連結讓舊的在 procs/ 有名字，再 rename 蓋過去。"""
    nxt = queue[0]
    try:
        os.link(h.cpu(n), h.proc(old))          # 舊的先回佇列，cpus/n.json 還在
    except OSError as e:
        notes.append("cpu%d 換不了（舊的搬不回去）：%s" % (n, e))
        return
    try:
        os.replace(h.proc(nxt), h.cpu(n))       # 原子蓋過去，中間沒有空窗
    except OSError as e:
        os.unlink(h.proc(old))                  # 收回硬連結，維持原狀
        notes.append("cpu%d 換不了（新的搬不上去）：%s" % (n, e))
        return
    queue.pop(0)
    queue.append(old)                           # 換下來的排隊尾
    st["cpus"][str(n)] = {"pid": nxt, "since": now, "runs_at": runs_now}
    notes.append("cpu%d 換人 %s→%s" % (n, old, nxt))


def _finish(h, st, notes, now, n, pid):
    """保留退出碼表示做完：先留 done 名字，再用 idle 原子蓋過 cpu。"""
    tmp = h.cpu(n) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(IDLE_INST, f, ensure_ascii=False, indent=1)
        os.makedirs(h.done, exist_ok=True)
        done = h.proc_done(pid)
        if os.path.exists(done):
            os.unlink(done)
        os.link(h.cpu(n), done)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        notes.append("cpu%d 收不了 %s：%s" % (n, pid, e))
        return
    try:
        os.replace(tmp, h.cpu(n))
    except OSError as e:
        os.unlink(done)
        notes.append("cpu%d 收不了 %s（idle 換不上去）：%s" % (n, pid, e))
        return
    st["cpus"][str(n)] = None
    notes.append("cpu%d 上 %s 做完了，收進 procs/done/" % (n, pid))


def _reject_running(h, st, notes, n, pid):
    """aos-exec 連續失敗：先留 bad 名字，再用 idle 原子蓋過 cpu。"""
    tmp = h.cpu(n) + ".tmp"
    bad = os.path.join(h.bad, "%s.json" % pid)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(IDLE_INST, f, ensure_ascii=False, indent=1)
        os.makedirs(h.bad, exist_ok=True)
        if os.path.exists(bad):
            os.unlink(bad)
        os.link(h.cpu(n), bad)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        notes.append("cpu%d 退不了 %s：%s" % (n, pid, e))
        return
    try:
        os.replace(tmp, h.cpu(n))
    except OSError as e:
        os.unlink(bad)
        notes.append("cpu%d 退不了 %s（idle 換不上去）：%s" % (n, pid, e))
        return
    st["cpus"][str(n)] = None
    notes.append("退件 %s（cpu%d 上連續回 125：aos-exec 自己失敗；原因跑 "
                 "aos-exec K/procs/bad/%s.json --stderr - 看）" % (pid, n, pid))


def cmd_tick(argv):
    if argv:
        sys.stderr.write("aos-kernel-tick: 不吃參數（cwd 就是家）\n")
        return 2
    h, cfg = here_or_die("aos-kernel-tick")
    if h is None:
        return 1
    return tick(h, cfg)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    return cmd_tick(argv)


if __name__ == "__main__":
    sys.exit(main())
