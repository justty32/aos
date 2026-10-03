#!/usr/bin/env python3
"""示範場景一鍵跑：把 demo/scene 複製到暫存根，起 aos7-daemon 跑幾秒，停掉後印出每條時間線每回合發生什麼。

    python3 proto7-1/demo/play.py [--root DIR] [--seconds 8] [--quiet]

場景（仿 proto7 核心 spec 的四層）：team（kernel＋路二的 poke＋路一的子 daemon subd）、team/agents/carol（臨時找 bob 說話，靠執行中加掛）、
team/agents/amy 與 team/agents/bob（agent 互傳 ping；bob 另有一個會卡住的 worker）、
team/sub 是子 daemon 的空間根，裡面有一條時間線 w。
最後一段「檢查」逐項列出該發生的事有沒有發生；全部發生回 0。
"""
import argparse
import glob
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P71 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(P71, "lib"))
import aos7_audit  # noqa: E402
import aos7_fs as fs  # noqa: E402

DAEMON = os.path.join(P71, "bin", "aos7-daemon")


def our_procs(root):
    """找還活著、環境變數 AOS7_ROOT 落在 root 底下的程序（孤兒檢查）。"""
    found = []
    for env_path in glob.glob("/proc/[0-9]*/environ"):
        try:
            with open(env_path, "rb") as f:
                env = f.read().split(b"\0")
        except OSError:
            continue
        for kv in env:
            if kv.startswith(b"AOS7_ROOT=") and kv[10:].decode(errors="replace").startswith(root):
                found.append(int(env_path.split("/")[2]))
                break
    return [p for p in found if p != os.getpid()]


def run(root, seconds, quiet):
    """起 daemon、跑 seconds 秒、寫 stop 控制檔、等它結束；回殘留程序清單。"""
    out = open(os.path.join(root, "daemon.out"), "w")
    env = fs.env_with_bin()
    env["AOS7_AUDIT"] = "1"   # 任務的寫入記到各自的 writes.jsonl，最後檢查有沒有寫出自己的 node 與掛載點
    d = subprocess.Popen([sys.executable, DAEMON, root], stdout=out, stderr=subprocess.STDOUT,
                         env=env, start_new_session=True)
    t0 = time.monotonic()
    end = t0 + seconds
    added = False
    while time.monotonic() < end and d.poll() is None:
        time.sleep(0.2)
        if not added and time.monotonic() - t0 > seconds * 0.3:
            # 中途改 kernel.json 加成員 carol：kernel 自己寫加掛請求，不用改 tasks.json（M-6）
            kpath = os.path.join(root, "team", "kernel.json")
            cfg = fs.read_json(kpath, {})
            cfg["members"] = cfg.get("members", []) + ["agents/carol"]
            fs.write_json(kpath, cfg)
            added = True
            if not quiet:
                print("\r  （%.1f 秒：kernel.json 加成員 agents/carol）" % (time.monotonic() - t0))
        if not quiet:
            st = fs.read_json(os.path.join(root, ".aosd", "status.json"), {})
            rs = " ".join("%s:%s" % (k, v.get("round")) for k, v in sorted(st.get("nodes", {}).items()))
            print("\r  跑著… " + rs + " " * 10, end="", flush=True)
    if not quiet:
        print()
    fs.write_json(os.path.join(root, ".aosd", "ctl", "zz-play-stop.json"),
                  {"op": "stop", "kill": True, "by": "play.py"})
    try:
        d.wait(timeout=10)
    except subprocess.TimeoutExpired:
        d.terminate()
        d.wait(timeout=5)
    time.sleep(0.3)
    left = our_procs(root)
    for p in left:  # 收尾：不留孤兒（留下來的照樣報出來）
        try:
            os.kill(p, signal.SIGKILL)
        except OSError:
            pass
    return left


def nodes_with_rounds(root):
    """所有有 rounds.jsonl 的 node 路徑（含子 daemon 底下的），排序。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath) == ".aos" and "rounds.jsonl" in filenames:
            out.append(os.path.dirname(dirpath))
        dirnames[:] = [x for x in dirnames if x not in ("tasks", "tasks-old")]
    return sorted(out)


def short(x):
    return ",".join(x) if x else "-"


def report_rounds(root):
    for node in nodes_with_rounds(root):
        print("\n== 時間線 %s ==" % os.path.relpath(node, root))
        run = []  # 連續「同一種平淡」的回合併成一行：(種類, 回合)

        def flush():
            if run:
                a, b = run[0][1], run[-1][1]
                span = str(a) if a == b else "%s～%s" % (a, b)
                kind = run[0][0]
                text = "沒有任務起落" if not kind else "只有短任務 %s 當回合起落（結束碼 0）" % kind
                print("  第 %s 回合  （%s）" % (span, text))
                run.clear()
        for r in fs.read_jsonl(os.path.join(node, ".aos", "rounds.jsonl")):
            started, ends = r.get("started") or [], r.get("ended") or []
            ended = ["%s(%s)" % (e.get("tid"), e.get("code")) for e in ends]
            ctl = ["%s %s" % (c.get("op"), c.get("tid")) for c in r.get("ctl", [])]
            plain = not ctl and sorted(started) == sorted(e.get("tid") for e in ends) \
                and all(e.get("code") == 0 for e in ends)
            if plain:
                kind = ",".join(sorted({t.rsplit("-r", 1)[0] for t in started}))
                if run and run[0][0] != kind:
                    flush()
                run.append((kind, r.get("round")))
                continue
            flush()
            line = "  第%3s 回合  起:%s  結束:%s" % (r.get("round"), short(started), short(ended))
            if ctl:
                line += "  控制:" + short(ctl)
            print(line)
        flush()


def report_files(root):
    print("\n== kernel 的決定 ==")
    for path in sorted(glob.glob(os.path.join(root, "team", ".aos", "tasks*", "*", "decisions.jsonl"))):
        for d in fs.read_jsonl(path):
            print("  [%s] team 第%s 回合 %-6s %s %s  (%s)" % (os.path.basename(os.path.dirname(path)), d.get("round"),
                  d.get("rule"), d.get("op"), d.get("target"), d.get("why")))
    for label, base in (("daemon", root), ("子 daemon team/sub", os.path.join(root, "team", "sub"))):
        print("\n== %s 執行過的控制檔 ==" % label)
        for path in sorted(glob.glob(os.path.join(base, ".aosd", "ctl-done", "*.json"))):
            c = fs.read_json(path, {})
            res = c.get("result", {})
            print("  %-22s %-7s %-18s by=%s ok=%s %s" % (os.path.basename(path), c.get("op"), c.get("node", ""),
                  c.get("by", ""), res.get("ok"), res.get("msg", "")))
    print("\n== 掛載（S-23：tick 在任務資料夾 mnt/ 下建的連結 → 空間裡的路徑）==")
    seen = set()
    for path in sorted(glob.glob(os.path.join(root, "**", ".aos", "tasks*", "*", "birth.json"), recursive=True)):
        b = fs.read_json(path, {})
        key = (b.get("node"), b.get("name"))
        if b.get("mounts") and key not in seen:
            seen.add(key)
            print("  %s:%s  %s" % (b.get("node"), b.get("tid"),
                  "  ".join("mnt/%s → %s" % (n, m.get("to", m.get("error"))) for n, m in sorted(b["mounts"].items()))))
    print("\n== 執行中加掛的回條（mount-done，M-6）==")
    for path in sorted(glob.glob(os.path.join(root, "**", ".aos", "tasks*", "*", "mount-done", "*.json"), recursive=True)):
        c = fs.read_json(path, {})
        tdir = os.path.dirname(os.path.dirname(path))
        res = c.get("result", {})
        print("  %s  %s  ok=%s %s" % (os.path.relpath(tdir, root).replace("/.aos/tasks-old/", ":").replace("/.aos/tasks/", ":"), c.get("path"),
              res.get("ok"), res.get("msg")))
    au = aos7_audit.scan(root)
    print("\n== 寫入紀錄（%d 個任務、%d 筆寫入，寫出範圍 %d 筆）==" % (au["tasks"], au["writes"], len(au["bad"])))
    for d, r in au["bad"][:20]:
        print("  [越界] %s  %s %s" % (os.path.relpath(d, root), r.get("op"), r.get("path")))
    print("\n== 信件（amy、bob、carol 處理過的）==")
    letters = []
    for who in ("amy", "bob", "carol"):
        for path in glob.glob(os.path.join(root, "team", "agents", who, "inbox", "done", "*.json")):
            m = fs.read_json(path, {})
            letters.append((os.path.basename(path), m))
    for name, m in sorted(letters):
        print("  %s → %s（寄件者第 %s 回合）：%s" % (m.get("from"), m.get("to"), m.get("round"), m.get("body")))


def checks(root, left):
    """該發生的事逐項檢查，回 [(說明, 成立否)]。"""
    def any_file(pattern):
        return bool(glob.glob(os.path.join(root, pattern)))
    decisions = []
    for path in glob.glob(os.path.join(root, "team", ".aos", "tasks*", "*", "decisions.jsonl")):
        decisions += fs.read_jsonl(path)
    ops = {(d.get("rule"), d.get("op")) for d in decisions}
    done_ctl = [fs.read_json(p, {}) for p in glob.glob(os.path.join(root, "team", "sub", ".aosd", "ctl-done", "*.json"))]
    letters = glob.glob(os.path.join(root, "team", "agents", "*", "inbox", "done", "*.json"))
    au = aos7_audit.scan(root)

    def letters_from(to, frm):
        return [m for m in (fs.read_json(p, {}) for p in glob.glob(os.path.join(root, to, "inbox", "done", "*.json")))
                if m.get("from") == frm]

    def granted(task_glob, path):
        return any((fs.read_json(p, {}).get("result") or {}).get("ok") and fs.read_json(p, {}).get("path") == path
                   for p in glob.glob(os.path.join(root, task_glob, "mount-done", "*.json")))
    return [
        ("amy 與 bob 互傳信（>= 4 封）", len(letters) >= 4),
        ("對話到上限，寫出 work/done.txt", any_file("team/agents/*/work/done.txt")),
        ("kernel 把卡住的 worker restart", ("stuck", "restart") in ops),
        ("restart 後 bob 有新的 worker 任務", len(glob.glob(os.path.join(root, "team/agents/bob/.aos/tasks*/worker-*"))) >= 2),
        ("kernel 因預算 pause 某條時間線", ("budget", "pause") in ops),
        ("kernel 之後 resume 它", ("budget", "resume") in ops),
        ("路一：子 daemon subd 有跑出 w 的回合", any_file("team/sub/w/.aos/rounds.jsonl")),
        ("路一：kernel 依壽命 kill subd", ("age", "kill") in ops),
        ("路二：poke 寫子 daemon 控制檔 pause/resume w", {"pause", "resume"} <= {c.get("op") for c in done_ctl}),
        ("加掛：carol 臨時寄給沒掛的 bob，請求加掛後寄到",
         granted("team/agents/carol/.aos/tasks*/*", "team/agents/bob/inbox") and bool(letters_from("team/agents/bob", "team/agents/carol"))),
        ("加掛：bob 回信給 carol 也是先加掛再寄",
         granted("team/agents/bob/.aos/tasks*/*", "team/agents/carol/inbox") and bool(letters_from("team/agents/carol", "team/agents/bob"))),
        ("加掛：kernel.json 中途加成員 carol，kernel 自己加掛它的 .aos",
         granted("team/.aos/tasks*/kernel-*", "team/agents/carol/.aos")),
        ("寄信、寫 ctl、路二都經過掛載點：所有寫入在自己的 node 或掛載點下（%d 筆）" % au["writes"],
         au["writes"] > 0 and not au["bad"]),
        ("停下後沒有殘留程序", not left),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", help="空間根（預設開一個暫存資料夾，全 OK 就刪掉）；會先清空，跑完留著")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--quiet", action="store_true", help="只印檢查結果")
    a = ap.parse_args()
    root = os.path.abspath(a.root) if a.root else tempfile.mkdtemp(prefix="aos7-play-")
    if a.root and os.path.exists(root):
        shutil.rmtree(root)
    shutil.copytree(os.path.join(HERE, "scene"), root, dirs_exist_ok=True)
    print("空間根：%s（跑 %.1f 秒）" % (root, a.seconds))
    left = run(root, a.seconds, a.quiet)
    if not a.quiet:
        report_rounds(root)
        report_files(root)
    print("\n== 檢查 ==")
    res = checks(root, left)
    for text, ok in res:
        print("  [%s] %s" % ("OK" if ok else "--", text))
    if left:
        print("  殘留程序：%s（已 SIGKILL）" % left)
    good = all(ok for _, ok in res)
    if not a.root:   # 自己開的暫存根：全 OK 就清掉；有失敗留著給人看
        if good:
            shutil.rmtree(root, ignore_errors=True)
        else:
            print("  有檢查沒過，空間根留著：%s" % root)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
