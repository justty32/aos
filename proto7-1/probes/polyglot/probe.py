"""polyglot：非 Python 任務（sh／bash）與 inst JSON 任務，只靠讀寫檔能不能操作這一層（S-01）。

- talker.sh（keep）：輪詢 tock.json、寫 progress.json、經過掛載寫信、寫 mount-req 加掛、寫自己的 ctl.json 要求 restart。
- spawner.sh（spawn 起一次）：開三種背景子程序，看任務 kill 收不收得到。
- ix（inst JSON，用 aos-exec）：看環境變數、輸出去哪、kill 收不收得到；bad（壞 inst）：結束碼與錯誤訊息。
- pyw（Python 對照）：開 AOS7_AUDIT 時 Python 有寫入紀錄、sh 沒有（M-3）。
"""
import datetime
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import probelib as pl  # noqa: E402
from aos7_fs import read_json, read_jsonl  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HZ = os.sysconf("SC_CLK_TCK")


def src(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def procs_of(tid):
    """環境變數 AOS7_TID＝tid 的程序：{pid: cmdline 字串}。"""
    out = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open("/proc/%s/environ" % d, "rb") as f:
                env = f.read().split(b"\0")
            with open("/proc/%s/cmdline" % d, "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace").strip()
        except OSError:
            continue
        if ("AOS7_TID=%s" % tid).encode() in env:
            out[int(d)] = cmd
    return out


def cpu_all(pid):
    """utime+stime+cutime+cstime 秒（含已收的子程序：sed、sleep…）。"""
    with open("/proc/%d/stat" % pid) as f:
        rest = f.read().rsplit(")", 1)[1].split()
    return sum(int(x) for x in rest[11:15]) / HZ, int(rest[19]) / HZ   # (CPU, starttime 秒)


def uptime():
    with open("/proc/uptime") as f:
        return float(f.read().split()[0])


def main():
    r = pl.Result("polyglot")
    with pl.Space("polyglot") as sp:
        sp.node("poly", [{"name": "talker", "mode": "keep", "argv": ["sh", "talker.sh"],
                          "mounts": {"peer": "mail/amy"}}],
                interval_ms=100,
                files={"talker.sh": src("talker.sh"), "spawner.sh": src("spawner.sh"),
                       "ix.inst.json": {"argv": ["sh", "-c", "echo inst-ran $AOS7_TID $AOS7_NODE_ID; sleep 304; echo after"],
                                        "stdout": "inst-out.txt"},
                       "bad.inst.json": {"argv": []}})
        node = sp.path("poly")
        sp.start(env={"AOS7_AUDIT": "1"})
        for name, item in (("spawner", {"name": "spawner", "argv": ["bash", "spawner.sh"]}),
                           ("ix", {"name": "ix", "inst": "ix.inst.json"}),
                           ("bad", {"name": "bad", "inst": "bad.inst.json"}),
                           ("pyw", {"name": "pyw", "argv": [pl.PY, "-c", "import os; open(os.path.join("
                                                            "os.environ['AOS7_NODE'], 'py.txt'), 'w').write('x')"]})):
            pl.write(os.path.join(node, ".aos", "spawn", name + ".json"), item)

        def by_name(n):
            return [t for t in sp.tasks("poly") if (sp.task_file("poly", t, "birth.json") or {}).get("name") == n]

        # ---------- talker：tock、progress、信、加掛、自己 restart ----------
        max_live_talker, lat = 0, []

        def talker_done():
            nonlocal max_live_talker
            live = [t for t in sp.live("poly") if t in by_name("talker")]
            max_live_talker = max(max_live_talker, len(live))
            for t in live:
                pg = sp.task_file("poly", t, "progress.json") or {}
                if pg.get("tock_at") and pg.get("seen_ns"):
                    lat.append(pg["seen_ns"] / 1e9 - datetime.datetime.fromisoformat(pg["tock_at"]).timestamp())
            ts = by_name("talker")
            news = [t for t in ts if (sp.task_file("poly", t, "birth.json") or {}).get("restart_of")]
            return news and ((sp.task_file("poly", news[0], "progress.json") or {}).get("n", 0) >= 3) and news[0]

        new = sp.wait_for(talker_done, timeout=20, msg="sh 任務沒完成自己 restart")
        first = sp.task_file("poly", new, "birth.json")["restart_of"]
        r.check("sh 任務輪詢 tock.json、寫出 progress.json", (sp.task_file("poly", first, "progress.json") or {}).get("n", 0) >= 4)
        letters = sorted(os.listdir(sp.path("mail/amy")))
        r.check("sh 任務經過宣告的掛載寫信到 mail/amy", sum(1 for x in letters if x.startswith("sh-")) >= 4, len(letters))
        r.measure("讀收件夾時看到的 sh 暫存檔（寫到一半或被 kill 留下的）", [x for x in letters if ".tmp." in x])
        md = sp.task_file("poly", first, "mount-done/extra.json") or {}
        r.check("sh 寫的 mount-req 被 tick 審過、掛上", (md.get("result") or {}).get("ok") is True, md.get("result"))
        box = os.listdir(sp.path("other/box")) if os.path.isdir(sp.path("other/box")) else []
        r.check("經過執行中加掛的 mnt/extra 寫到 other/box", any(x.startswith("sh-" + first) for x in box), box)
        cd = sp.task_file("poly", first, "ctl-done.json") or {}
        r.check("sh 寫自己的 ctl.json restart 被執行", cd.get("op") == "restart" and cd["result"]["ok"], cd.get("result"))
        r.check("restart 後的新任務帶著加掛的 mnt/extra",
                os.path.islink(os.path.join(sp.path("poly", ".aos", "tasks", new), "mnt", "extra")))
        r.check("新任務也寫到 other/box", sp.wait_for(lambda: any(x.startswith("sh-" + new) for x in os.listdir(sp.path("other/box"))),
                                                    timeout=5, msg="新 talker 沒寫 other/box"))
        r.check("keep 的 sh 任務同時最多一份", max_live_talker <= 1, max_live_talker)
        ex = sp.task_file("poly", first, "exit.json") or {}
        r.measure("被 restart 的 sh 任務結束碼", ex.get("code"))
        lat = sorted(lat)
        r.measure("sh 每 20 ms 輪詢：tock.json 寫出→sh 看到 ms（中位、最大）",
                  [round(lat[len(lat) // 2] * 1000), round(lat[-1] * 1000)] if lat else None)
        pid = (sp.task_file("poly", new, "pid.json") or {}).get("pid")
        try:
            c, st = cpu_all(pid)
            r.measure("sh 輪詢迴圈 CPU 佔一核的比例（含 sed／sleep 子程序）", round(c / max(0.1, uptime() - st), 3))
        except (OSError, TypeError):
            pass

        # ---------- kill：sh 的背景子程序 ----------
        spw = sp.wait_for(lambda: by_name("spawner"), msg="spawner 沒起")[0]
        sp.wait_for(lambda: len([c for c in procs_of(spw).values() if c.startswith("sleep 30")]) >= 3, timeout=5,
                    msg="spawner 的三個 sleep 沒都起來")
        before = procs_of(spw)
        ixt = sp.wait_for(lambda: by_name("ix"), msg="ix 沒起")[0]
        sp.wait_for(lambda: any("sleep 304" in c for c in procs_of(ixt).values()), timeout=5, msg="inst 的 sleep 沒起")
        for t in (spw, ixt):
            pl.write(os.path.join(node, ".aos", "tasks", t, "ctl.json"), {"op": "kill", "by": "probe"})
        sp.wait_for(lambda: all(os.path.exists(os.path.join(node, ".aos", "tasks", t, "ctl-done.json")) for t in (spw, ixt)),
                    timeout=10, msg="kill 沒被執行")
        time.sleep(0.3)
        after = procs_of(spw)
        alive = sorted(c for c in after.values() if c.startswith("sleep"))
        r.check("kill 收掉 sh 的普通背景子程序（sleep 301）", not any(c == "sleep 301" for c in after.values()))
        r.check("kill 收掉 setsid 但仍是後代的子程序（sleep 302）", not any(c == "sleep 302" for c in after.values()))
        r.measure("kill 前 spawner 的程序", sorted(before.values()))
        r.measure("kill 後 spawner 還活著的程序", alive)
        if any(c == "sleep 303" for c in after.values()):
            r.finding("sh 用雙 fork（( setsid cmd & )）開的子程序被 init 收養、換了 session，kill 只追後代與程序群組，收不到；"
                      "它一直活著，但 AOS7_TID 環境變數還在身上，只有用環境變數找得到")
        for p in after:
            try:
                os.kill(p, signal.SIGKILL)
            except OSError:
                pass
        r.check("kill 收掉 inst 任務（aos-exec 開在另一個 session）的子程序",
                not any("sleep 304" in c for c in procs_of(ixt).values()))
        r.measure("inst 任務被 kill 的結束碼（exit.json）", (sp.task_file("poly", ixt, "exit.json") or {}).get("code"))
        io = open(os.path.join(node, "inst-out.txt")).read().strip() if os.path.exists(os.path.join(node, "inst-out.txt")) else ""
        r.check("inst 任務拿得到 AOS7_* 環境變數（輸出寫到 inst 指定的檔）", ixt in io, io)
        olog = os.path.join(node, ".aos", "tasks", ixt, "out.log")
        r.measure("inst 任務的 out.log 大小（aos-exec 不轉輸出）", os.path.getsize(olog) if os.path.exists(olog) else None)

        bad = by_name("bad")[0]
        sp.wait_for(lambda: sp.task_file("poly", bad, "exit.json"), msg="bad 沒結束")
        r.check("壞 inst 的結束碼是 125（aos-exec 自己失敗）", sp.task_file("poly", bad, "exit.json").get("code") == 125)
        blog = open(os.path.join(node, ".aos", "tasks", bad, "out.log")).read().strip()
        r.measure("壞 inst 的 out.log", blog[-200:])

        # ---------- 寫入紀錄 ----------
        pyw = by_name("pyw")[0]
        sp.wait_for(lambda: sp.task_file("poly", pyw, "exit.json"), msg="pyw 沒結束")
        pw = read_jsonl(os.path.join(node, ".aos", "tasks", pyw, "writes.jsonl"))
        r.check("Python 對照任務有寫入紀錄", any(w.get("path", "").endswith("py.txt") for w in pw), len(pw))
        tw = read_jsonl(os.path.join(node, ".aos", "tasks", first, "writes.jsonl"))
        r.measure("sh 任務的 writes.jsonl 記到的路徑", sorted({os.path.basename(w.get("path", "")) for w in tw}))
        runner = (sp.task_file("poly", first, "pid.json") or {}).get("runner_pid")
        by_runner = [w for w in tw if w.get("pid") == runner]
        r.measure("其中 aos7-run 包裝程式自己寫的筆數（pid＝runner_pid）／ok:false 筆數",
                  [len(by_runner), sum(1 for w in tw if w.get("ok") is False)])
        if by_runner:
            r.finding("aos7-run 也是 Python、也吃到 audit 的 PYTHONPATH，它寫 pid.json／exit.json／out.log 都記進任務的 "
                      "writes.jsonl，跟任務自己的寫入混在一起（用 pid 才分得出來）")
        r.check("sh 任務自己的寫入（progress、信、ctl）一筆都沒記到",
                not any(os.path.basename(w.get("path", "")).startswith(("progress", "sh-", "ctl")) for w in tw))
        r.finding("寫入紀錄只看得到 sh 裡叫的 python3 那一段（viapy.txt），sh 自己寫的 progress、信、ctl.json、"
                  "mount-req 全都看不到（M-3）；非 Python 任務完全不受「只碰給的資料夾」檢查")
        r.finding("sh 沒有等 tock 的辦法，只能每 20 ms 起 sed＋sleep 輪詢；也沒有 JSON 解析，靠 sed 抓 write_json 的排版"
                  "（indent=1、一鍵一行），排版一改就壞；寫信要自己跳脫 body 字串")
        r.finding("原子寫在 sh 裡要自己 printf > tmp && mv；暫存檔落在對方收件夾裡，讀信的一方得自己略過 *.tmp.*")
        r.finding("inst 任務的 stdout／stderr 預設丟 /dev/null（aos-exec 不收輸出），out.log 是空的；"
                  "壞 inst 的錯誤訊息才會進 out.log（aos-exec 自己的 stderr）")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
