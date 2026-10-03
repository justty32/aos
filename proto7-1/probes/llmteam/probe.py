"""llmteam：路一＋路二混合的 LLM 團隊。

- **A**（node `lab` 裡 tick 起的任務，跑 a_task.py）：在自己 node 開子 daemon（路一：tasks.json 加 aos7-daemon 任務＋subroot），
  子根 `lab/sub` 下建 w1、w2 兩個 worker node，就緒寫 `lab/READY.json`；之後要讓「外面 stop 掉的子 daemon 保持停住」。
- **B**（探針程序裡的外部維運員）：只准寫 `lab/sub/.aosd/` 與 `ops/`，用子 daemon 的控制檔（路二）：pause w1、讓 w2 只再跑
  3 回合、stop 整個子 daemon，結果寫 `ops/report.json`。

兩個同時跑、只靠檔案協調。旁邊一個 thread 每 50 ms 取樣子 daemon（pid、gen、stopped、w1／w2 回合），量「B stop 之後父的 keep
有沒有把子 daemon 起回來」。

    python3 probe.py                                   # 離線：A、B 都是照稿腦（run_all 用）
    python3 probe.py --real deepseek-chat,claude-haiku-4.5   # A 用第一個、B 用第二個模型
    python3 probe.py --real ... --cap 30,30                  # 每個 LLM 的呼叫上限（預設 30,30）
"""
import glob
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
import llmop  # noqa: E402
import aos7_audit  # noqa: E402
from aos7_fs import read_json, read_jsonl  # noqa: E402

T = pl.aos7_task
PY = pl.PY
A_TASK = os.path.join(HERE, "a_task.py")

B_ROLE = """你是外部維運員（不在任何 node 裡），只有 read_file、write_file 兩個工具，路徑都相對空間根。
你只准寫 `lab/sub/.aosd/` 與 `ops/` 底下的檔。沒有 sleep 工具：要等什麼，就再讀一次相關的檔（每讀一次大約過一兩秒）。"""

B_GOAL = """lab 裡有個 agent 開了一個子 daemon，子空間根是 `lab/sub`（就緒時它會寫 `lab/READY.json`，現在應該已經有了）。
只用這個子 daemon 的控制檔做下面三件事，每一步都要確認真的生效：
(1) 暫停 w1，確認它真的停住；
(2) 讓 w2 從現在起只再跑 3 回合就停，確認它停住，並記下它停在第幾回合；
(3) 停掉整個子 daemon（連它的任務），確認它真的停了，而且沒有又被起來。
最後把每一步的結果寫成 `ops/report.json`（至少含 w1 是否停住、w2 停在第幾回合、子 daemon 是否保持停止）。"""


class OpsTools(llmop.FileTools):
    def write_file(self, path, content):
        r = self.rel(self._resolve(path))
        if not (r.startswith("lab/sub/.aosd/") or r.startswith("ops/")):
            raise OSError("你只准寫 lab/sub/.aosd/ 與 ops/ 底下：%s" % r)
        return super().write_file(path, content)


def _j(base, rel):
    return read_json(os.path.join(base, rel))


def b_script():
    """離線照稿 B：pause w1 → resume w2 rounds 3 → stop kill，每步讀 status 確認。"""
    ST = "lab/sub/.aosd/status.json"

    def until_node(tools, nid, cond):
        def f(t):
            n = ((_j(t.base, ST) or {}).get("nodes") or {}).get(nid) or {}
            return None if cond(n) else "wait"
        return f

    gen0 = {}

    def wait_stopped(t):
        st = _j(t.base, ST) or {}
        gen0.setdefault("g", st.get("gen"))
        rc = (_j(t.base, "lab/sub/.aosd/ctl-done/b-3-stop.json") or {}).get("result") or {}
        if rc.get("ok") is False:
            return None   # Q5：擁有者 lab 沒允許，stop 被拒
        return None if st.get("stopped") or st.get("gen") != gen0["g"] else "wait"   # 被 keep 起回來就換 gen

    def report(t):
        st = _j(t.base, ST) or {}
        w2 = ((st.get("nodes") or {}).get("w2") or {}).get("round")
        return ("write_file", {"path": "ops/report.json", "content": json.dumps(
            {"w1_paused": True, "w2_round": w2, "sub_stopped": bool(st.get("stopped")), "gen": st.get("gen")})})

    return [
        ("read_file", {"path": "lab/READY.json"}),
        ("read_file", {"path": ST}),
        ("write_file", {"path": "lab/sub/.aosd/ctl/b-1-pause-w1.json",
                        "content": json.dumps({"op": "pause", "node": "w1", "by": "B"})}),
        until_node(None, "w1", lambda n: n.get("phase") == "paused"),
        ("write_file", {"path": "lab/sub/.aosd/ctl/b-2-w2-3.json",
                        "content": json.dumps({"op": "resume", "node": "w2", "rounds": 3, "by": "B"})}),
        until_node(None, "w2", lambda n: n.get("phase") == "paused"),
        ("read_file", {"path": ST}),
        lambda t: (wait_stopped(t), None)[1],     # 記下 stop 前的 gen
        ("write_file", {"path": "lab/sub/.aosd/ctl/b-3-stop.json",
                        "content": json.dumps({"op": "stop", "kill": True, "by": "B"})}),
        wait_stopped,
        report,
        "做完了。",
    ]


def sub_daemon_pids(lab):
    """cwd 是 lab 的 aos7-daemon（子 daemon 用相對路徑 `sub` 起，命令列裡看不到空間根）。"""
    out = []
    for cmd in glob.glob("/proc/[0-9]*/cmdline"):
        pid = int(cmd.split("/")[2])
        try:
            with open(cmd, "rb") as f:
                argv = f.read().split(b"\0")
            cwd = os.readlink("/proc/%d/cwd" % pid)
        except OSError:
            continue
        if any(a.endswith(b"aos7-daemon") for a in argv) and os.path.realpath(cwd).startswith(lab):
            out.append(pid)
    return sorted(out)


class Sampler(threading.Thread):
    def __init__(self, lab):
        super().__init__(daemon=True)
        self.lab = lab
        self.sub = os.path.join(lab, "sub")
        self.halt = threading.Event()
        self.samples = []

    def run(self):
        while not self.halt.wait(0.05):
            st = read_json(os.path.join(self.sub, ".aosd", "status.json"), {}) or {}
            self.samples.append({"t": time.time(), "pid": st.get("pid"), "gen": st.get("gen"),
                                 "stopped": st.get("stopped"), "alive": sub_daemon_pids(self.lab),
                                 "w2": ((st.get("nodes") or {}).get("w2") or {}).get("round")})


def scene(r, a_model, b_model, caps, tag):
    real = not a_model.startswith("script")
    res = {"tag": tag, "A": a_model, "B": b_model}
    with pl.Space("llmteam") as sp:
        lab = sp.node("lab", [], interval_ms=300, files={
            ".aos/spawn/llm-a.json": {"name": "llm-a", "argv": [PY, A_TASK, a_model, str(caps[0])]}})
        os.makedirs(os.path.join(sp.root, "ops"))
        sub = os.path.join(lab, "sub")
        smp = Sampler(lab)
        smp.start()
        t0 = time.monotonic()
        p0 = sp.start(env={"AOS7_AUDIT": "1"})
        try:
            sp.wait_for(lambda: os.path.exists(os.path.join(lab, "READY.json")), timeout=300 if real else 20,
                        poll=0.2, msg="A 沒寫 READY.json")
            res["t_ready"] = round(time.monotonic() - t0, 1)
            ready = True
        except pl.ProbeTimeout:
            ready = False
        res["ready"] = ready
        st_sub = read_json(os.path.join(sub, ".aosd", "status.json"), {}) or {}
        res["sub_nodes_at_ready"] = sorted((st_sub.get("nodes") or {}))
        res["parent_nodes_at_ready"] = sorted((sp.status().get("nodes") or {}))

        # ---- B ----
        btools = OpsTools(sp.root, name="B")
        bout = None
        if ready:
            bbrain = llmop.RealBrain(b_model) if real else llmop.ScriptBrain(b_script())
            bout = llmop.run_agent(bbrain, btools, llmop.system_prompt(B_ROLE), B_GOAL, max_calls=caps[1],
                                   min_turn_s=1.0 if real else 0.05, timeout_s=420 if real else 20,
                                   transcript=os.path.join(sp.base, "B.jsonl"))
            res["B"] = {k: bout[k] for k in ("calls", "tokens", "turns", "stop")}
            res["B_final"] = (bout.get("final") or "")[:600]
        # ---- 等 A 結束 ----
        a_dir = None
        try:
            sp.wait_for(lambda: glob.glob(os.path.join(lab, ".aos", "tasks*", "llm-a-*", "result.json")),
                        timeout=480 if real else 20, poll=0.3, msg="A 沒結束")
        except pl.ProbeTimeout:
            res["A_timeout"] = True
        found = glob.glob(os.path.join(lab, ".aos", "tasks*", "llm-a-*"))
        a_dir = found[0] if found else None
        aout = read_json(os.path.join(a_dir, "result.json"), {}) if a_dir else {}
        res["A"] = {k: aout.get(k) for k in ("calls", "tokens", "turns", "stop")}
        res["A_final"] = (aout.get("final") or "")[:600]
        time.sleep(1.5)                           # 讓 keep 有機會再起一次
        smp.halt.set()
        smp.join()

        # ---- 量 ----
        sub_log = read_jsonl(os.path.join(sub, ".aosd", "log.jsonl"))
        ctl_done = [read_json(p, {}) for p in sorted(glob.glob(os.path.join(sub, ".aosd", "ctl-done", "*.json")))]
        res["B_ctl"] = [(c.get("op"), c.get("node"), c.get("rounds"), (c.get("result") or {}).get("ok"),
                         (c.get("result") or {}).get("msg")) for c in ctl_done]
        res["B_ctl_misplaced"] = sorted(os.path.relpath(p, sp.root) for p in
                                        glob.glob(os.path.join(sub, ".aosd", "*.json"))
                                        if os.path.basename(p) not in ("status.json", "paused.json", "gen.json", "owner.json",
                                                                         "stopped.json"))
        res["ctl_pending"] = sorted(os.listdir(os.path.join(sub, ".aosd", "ctl"))) if os.path.isdir(
            os.path.join(sub, ".aosd", "ctl")) else []
        res["paused_final"] = (read_json(os.path.join(sub, ".aosd", "paused.json"), {}) or {}).get("paused")
        starts = [e for e in sub_log if e.get("ev") == "start"]
        stops = [e for e in sub_log if e.get("ev") == "stop"]
        res["sub_starts"] = len(starts)
        res["sub_stops"] = len(stops)
        # w2：resume rounds 之後實際又收了幾回合
        rs = [c for c in ctl_done if c.get("op") == "resume" and c.get("node") == "w2" and c.get("rounds")]
        w2_rounds = read_jsonl(os.path.join(sub, "w2", ".aos", "rounds.jsonl"))
        if rs:
            at = rs[-1]["result"]["at"]
            after = [x["round"] for x in w2_rounds if x.get("tock_at", "") > at]
            res["w2_after_resume_rounds"] = after
            res["w2_rounds_after_resume"] = len(after)
            res["w2_steps_done"] = any(e.get("ev") == "steps-done" and e.get("node") == "w2" for e in sub_log)
        res["w2_round_final"] = (read_json(os.path.join(sub, "w2", ".aos", "round.json"), {}) or {}).get("round")
        rep = read_json(os.path.join(sp.root, "ops", "report.json"))
        res["B_report"] = rep
        # stop 之後被重起：第一次 stop 之後還有 start
        if stops:
            t_stop = stops[0]["at"]
            res["restarted_after_stop"] = sum(1 for e in starts if e["at"] > t_stop)
        alive_ever = sorted({p for s in smp.samples for p in s["alive"]})
        res["sub_daemon_pids_seen"] = len(alive_ever)
        res["sub_daemon_alive_end"] = sub_daemon_pids(lab)
        # lab 的任務表與任務
        res["lab_tasks_json_final"] = read_json(os.path.join(lab, ".aos", "tasks.json"))
        res["lab_tasks"] = sorted(os.path.basename(d) for d in glob.glob(os.path.join(lab, ".aos", "tasks", "*")))
        births = {os.path.basename(d): b for d in glob.glob(os.path.join(lab, ".aos", "tasks", "*"))
                  for b in [read_json(os.path.join(d, "birth.json"), {}) or {}] if "aos7-daemon" in str(b.get("argv"))}
        res["subd_births"] = {k: {"argv": v.get("argv"), "subroot": v.get("subroot"),
                                  "subroot_error": v.get("subroot_error")} for k, v in births.items()}
        exits = {k: (read_json(os.path.join(lab, ".aos", "tasks", k, "exit.json"), {}) or {}).get("code") for k in births}
        res["subd_exit_codes"] = exits
        res["subd_exit_summary"] = {str(c): sum(1 for v in exits.values() if v == c) for c in set(exits.values())}
        r_lab_a = sp.round_of("lab")
        time.sleep(0.7)
        res["lab_advancing"] = sp.round_of("lab") > r_lab_a
        res["parent_nodes_end"] = sorted((sp.status().get("nodes") or {}))
        res["parent_live_end"] = sp.status().get("nodes", {}).get("lab", {}).get("live")
        # 寫入紀錄：A 寫進子 daemon 根算不算越界
        aud = aos7_audit.scan(sp.root)
        res["audit_bad"] = sorted({os.path.relpath(b.get("path", ""), sp.root) for _, b in aud["bad"]})[:20]
        by = {}
        for d, b in aud["bad"]:
            k = os.path.relpath(d, sp.root)
            by.setdefault(k, set()).add(os.path.relpath(b.get("path", ""), sp.root).split("/.")[0])
        res["audit_bad_by_task"] = {k: sorted(v)[:6] for k, v in by.items()}
        res["A_tool_errors"] = [(x["tool"], x.get("path"), x.get("err")) for x in aout.get("tool_log", []) if not x.get("ok")]
        res["B_tool_errors"] = [(x["tool"], x.get("path"), x.get("err")) for x in btools.errors()]
        res["A_writes"] = [x.get("path") for x in aout.get("tool_log", []) if x["tool"] == "write_file"]
        res["B_writes"] = [x.get("path") for x in btools.writes()]
        # 子 daemon 的 node 有沒有先被父搶走（P-11）
        res["parent_grabbed"] = sorted({e.get("node") for e in sp.log() if e.get("ev") == "node+" and e.get("node") != "lab"})
        # 收：stop 父
        rcs = sp.stop_all()
        res["parent_rc"] = list(rcs.values())[0]
        time.sleep(0.3)
        res["leftover_after_parent_stop"] = sorted(set(pl.our_procs(sp.base)) | set(sub_daemon_pids(lab)))
        if real:
            keep_runs(sp, a_dir, tag)
    return res


def keep_runs(sp, a_dir, tag):
    """真模型的逐字紀錄留一份精簡的到 runs/（每行截短）。"""
    d = os.path.join(HERE, "runs")
    os.makedirs(d, exist_ok=True)
    for who, src in (("A", os.path.join(a_dir, "transcript.jsonl") if a_dir else None),
                     ("B", os.path.join(sp.base, "B.jsonl"))):
        if not src or not os.path.exists(src):
            continue
        with open(src, encoding="utf-8") as f, open(os.path.join(d, "%s-%s.jsonl" % (tag, who)), "w", encoding="utf-8") as g:
            for line in f:
                g.write(line[:1500].rstrip("\n") + ("\n" if len(line) <= 1500 else "…\n"))


def offline(r):
    res = scene(r, "script", "script", (99, 99), "script")
    r.check("A（照稿）寫出 READY.json", res["ready"])
    r.check("子 daemon 由 lab 的任務起、帶 subroot", any(v["subroot"] == "lab/sub" for v in res["subd_births"].values()),
            res["subd_births"])
    r.check("w1、w2 歸子 daemon 管，父的 status 只有 lab（父沒先搶，P-11 沒發生）",
            res["sub_nodes_at_ready"] == ["w1", "w2"] and res["parent_nodes_at_ready"] == ["lab"]
            and not res["parent_grabbed"], (res["sub_nodes_at_ready"], res["parent_nodes_at_ready"], res["parent_grabbed"]))
    r.check("B 的三個控制檔都被子 daemon 接受", [c[3] for c in res["B_ctl"]] == [True, True, True], res["B_ctl"])
    r.check("w2 在 resume rounds=3 之後剛好又收 3 回合（含當時進行中的那回合）", res.get("w2_rounds_after_resume") == 3,
            res.get("w2_after_resume_rounds"))
    r.check("B 的 stop 讓子 daemon 退出（log 有 stop）", res["sub_stops"] >= 1)
    r.check("最後沒有活著的子 daemon（A 設了 allow_stop，stop 留下 stopped.json）", not res["sub_daemon_alive_end"],
            res["sub_daemon_alive_end"])
    r.check("B stop 之後父的 keep 沒把子 daemon 起回來（Q5：stopped.json 擋住）", not res.get("restarted_after_stop"),
            res.get("restarted_after_stop"))
    r.check("lab 照常前進", res["lab_advancing"])
    r.check("父 daemon 正常退出、沒有殘留", res["parent_rc"] == 0 and not res["leftover_after_parent_stop"],
            (res["parent_rc"], res["leftover_after_parent_stop"]))
    r.measure("A 就緒秒數", res.get("t_ready"))
    r.measure("子 daemon 起了幾次（log start）／stop 幾次", [res["sub_starts"], res["sub_stops"]])
    r.measure("B stop 之後 keep 又把子 daemon 起回來的次數", res.get("restarted_after_stop"))
    r.measure("subd 任務結束碼", res["subd_exit_codes"])
    r.measure("paused.json 最後內容（子 daemon 重起會照讀）", res["paused_final"])
    r.measure("A 寫進子 daemon 根被寫入紀錄判越界的（前幾項）", res["audit_bad"][:4])
    if res["audit_bad"]:
        r.finding("A 在 lab/sub 底下建 w1／w2 的 node 檔，寫入紀錄判成越界（lab/sub 已是別的 daemon 的根）：誰能替子 daemon 播種 node 沒有說法")
    r.measure("寫入紀錄 ok:false（依任務）", res["audit_bad_by_task"])

    # ---- 第二場：A 寫完 READY 就收工（不擋 keep）----
    nv = scene(r, "script-naive", "script", (99, 99), "naive")
    stop_c = [c for c in nv["B_ctl"] if c[0] == "stop"]
    r.check("naive：A 沒設 allow_stop，B 的 stop 被拒、回條說子 daemon 屬於 lab（Q5）",
            stop_c and stop_c[0][3] is False and "屬於 node lab" in (stop_c[0][4] or ""), nv["B_ctl"])
    r.check("naive：子 daemon 沒停、也沒重起（同一份一直活著）",
            nv["sub_stops"] == 0 and nv["sub_starts"] == 1 and nv["sub_daemon_alive_end"],
            (nv["sub_starts"], nv["sub_stops"], nv["sub_daemon_alive_end"]))
    r.check("naive：子 daemon 一直在，w1、w2 都停著", nv["paused_final"] == ["w1", "w2"], nv["paused_final"])
    r.measure("naive：B 的 report", nv["B_report"])
    r.measure("naive：子 daemon 起／停次數", [nv["sub_starts"], nv["sub_stops"]])
    r.measure("naive：subd 任務結束碼", nv["subd_exit_codes"])
    r.check("naive：父 daemon 正常退出、連子 daemon 一起收乾淨", nv["parent_rc"] == 0 and not nv["leftover_after_parent_stop"],
            (nv["parent_rc"], nv["leftover_after_parent_stop"]))
    return res


def main():
    argv = sys.argv[1:]
    models = llmop.model_arg(argv)
    if not models:
        r = pl.Result("llmteam")
        offline(r)
        return r.done()
    caps = (30, 30)
    if "--cap" in argv:
        caps = tuple(int(x) for x in argv[argv.index("--cap") + 1].split(","))
    a_model, b_model = models[0], models[1] if len(models) > 1 else models[0]
    tag = "%s-%s-%s" % (time.strftime("%H%M%S"), a_model, b_model)
    r = pl.Result("llmteam-real")
    res = scene(r, a_model, b_model, caps, tag)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    d = os.path.join(HERE, "runs")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "%s-result.json" % tag), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    pl.run_main(main)
