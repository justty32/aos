#!/usr/bin/env python3
"""可預測性的兩把尺 —— 第一版量尺。

兩把尺（構想集 01 章 A-04）：
  ① 自報 vs 實際：串在原稿 `resources` 裡自報「幾格、幾筆指令、幾次 LLM」，
     跟實際跑出來的差多少。
  ② 分布寬度：同一支串跑 N 次（預設 5），格數／牆鐘秒／指令數／token 的分布多寬。

怎麼跑：
    python3 proto/bench/run.py            # 三支串各跑五次
    python3 proto/bench/run.py --runs 3 --series a-inst,c-llm
    python3 proto/bench/run.py --keep     # 留下暫存家好事後翻現場

輸出：proto/bench/results/<時間>/raw.jsonl 與 summary.md。

規矩：純標準庫；一律用 `python3 proto/aos.py …` 呼叫原型，不 import aosp；
每次跑都開一個全新的暫存家（各自 AOS_HOME），不碰使用者的 ~，也不碰 proto/ 底下的檔。
"""
import argparse
import glob
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
REPO = os.path.dirname(PROTO)
AOS = os.path.join(PROTO, "aos.py")
BIN = os.path.join(PROTO, "bin")
SERIES_DIR = os.path.join(HERE, "series")
RESULTS_DIR = os.path.join(HERE, "results")

# ---------------------------------------------------------------- 三支固定的串
# lands：這支串會用到的地，相對於串資料夾；第一個是入口地（run 跑的就是它）。
# llm ：要不要起 LLM 世界。
SERIES = [
    {
        "name": "a-inst",
        "title": "(a) 純指令串：10 步 inst、全確定",
        "lands": ["."],
        "llm": False,
    },
    {
        "name": "b-call",
        "title": "(b) 有同步子地的串：父 call sync、子 5 步",
        "lands": [".", "child"],
        "llm": False,
    },
    {
        "name": "c-llm",
        "title": "(c) 有 LLM 世界的串：投 3 筆請求給假後端再 await",
        "lands": ["."],
        "llm": True,
    },
]

# LLM 世界的假後端。原型支援 `echo:`／`fail:`／`slow:<ms>`（見 aosp/llm.py）。
# 這裡用 slow:，讓 LLM 呼叫真的有等待時間；fast／smart 兩級不同毫秒，
# 一支串裡三筆請求就有粗細不一的等待，算是原型給得起的「抖動」。
FAKE_ENDPOINTS = {"fast": "slow:40", "smart": "slow:180"}

# 一趟 run 的保險絲：格數上限（避免 bug 讓 bench 永遠跑不完）
BUDGET = 500
# LLM 世界 serve 的格數與間隔
SERVE_STEPS = 600
SERVE_EVERY_MS = 50


# ---------------------------------------------------------------- 小工具
def sh(argv, env=None, cwd=None, timeout=300):
    """跑一支子行程，回 (exit code, stdout, stderr)。"""
    p = subprocess.run(argv, env=env, cwd=cwd, timeout=timeout,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def aos(args, env, timeout=300):
    return sh([sys.executable, AOS] + list(args), env=env, timeout=timeout)


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def count_insts(land_root):
    """實際跑了幾筆指令＝`.aos/ticks/<N>/insts/*.json` 的檔數。

    原型沒有指令計數器（見 README「原型缺什麼」），只能自己數檔。
    """
    pat = os.path.join(land_root, ".aos", "ticks", "*", "insts", "*.json")
    return len(glob.glob(pat))


def count_tick_dirs(land_root):
    """`.aos/ticks/<N>/` 的目錄數。注意：只有「這一格真的跑了指令」才會有目錄，
    所以它不等於格數，是「有動作的格數」。"""
    d = os.path.join(land_root, ".aos", "ticks")
    if not os.path.isdir(d):
        return 0
    return len([x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x))])


def ledger_tokens(home):
    """帳簿 $AOS_HOME/.aos/ledger.jsonl：LLM 呼叫次數與 token 總數。"""
    path = os.path.join(home, ".aos", "ledger.jsonl")
    calls, tin, tout, ms = 0, 0, 0, 0
    if not os.path.isfile(path):
        return {"llm_calls": 0, "tokens_in": 0, "tokens_out": 0, "tokens": 0, "llm_ms": 0}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            calls += 1
            tin += int(obj.get("tokens_in") or 0)
            tout += int(obj.get("tokens_out") or 0)
            ms += int(obj.get("ms") or 0)
    return {"llm_calls": calls, "tokens_in": tin, "tokens_out": tout,
            "tokens": tin + tout, "llm_ms": ms}


def declared(series_dir):
    """自報值：讀入口地原稿 main.aos.json 的頂層 `resources`。

    原型的載入器只做嚴格檢查＋抄過去，多出來的頂層欄位會原樣進 .aos/program/，
    所以 `resources` 放在原稿裡跑得動——但**沒有任何程式讀它**（見 README）。
    """
    src = read_json(os.path.join(series_dir, "main.aos.json"), {}) or {}
    res = src.get("resources") or {}
    return {
        "ticks": res.get("ticks"),
        "insts": res.get("insts"),
        "llm_calls": res.get("llm_calls"),
        "note": res.get("note", ""),
    }


# ---------------------------------------------------------------- 一次跑
def setup(spec, workdir):
    """開一個暫存家＋把串複製進去，回 (env, land_root, lands)。"""
    land_root = os.path.join(workdir, "land")
    home = os.path.join(workdir, "home")
    shutil.copytree(os.path.join(SERIES_DIR, spec["name"]), land_root)
    os.makedirs(home)

    env = dict(os.environ)
    env["AOS_HOME"] = home
    # 地上的指令會直接叫 `aos`（proto/bin/aos 是那支殼）
    env["PATH"] = BIN + os.pathsep + env.get("PATH", "/usr/bin:/bin")
    env.pop("AOS_RESULT", None)
    env.pop("AOS_CALLER", None)

    lands = [os.path.normpath(os.path.join(land_root, p)) for p in spec["lands"]]
    for p in lands:
        code, out, err = aos(["init", p], env)
        if code != 0:
            raise RuntimeError("init %s 失敗（%d）：%s%s" % (p, code, out, err))
    return env, land_root, lands, home


def start_llm(env, workdir):
    """起 LLM 世界：init、把單元換成假後端 slow:、背景開一支 serve。"""
    code, out, err = aos(["llm", "init"], env)
    if code != 0:
        raise RuntimeError("llm init 失敗（%d）：%s%s" % (code, out, err))
    cfg_path = os.path.join(env["AOS_HOME"], ".aos", "config.json")
    cfg = read_json(cfg_path, {}) or {}
    for u in cfg.get("units", []):
        u["endpoint"] = FAKE_ENDPOINTS.get(u.get("tier"), "echo:")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    world = os.path.join(env["AOS_HOME"], ".aos", "llm")
    log = open(os.path.join(workdir, "llm-serve.log"), "wb")
    proc = subprocess.Popen(
        [sys.executable, AOS, "llm", "serve", "--land", world,
         "--steps", str(SERVE_STEPS), "--every", str(SERVE_EVERY_MS)],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    return proc, log


def stop_llm(proc, log):
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    finally:
        try:
            log.close()
        except Exception:
            pass


def one_run(spec, index, keep_dir=None):
    """跑一次，回一筆量測記錄。"""
    workdir = tempfile.mkdtemp(prefix="aos-bench-%s-%d-" % (spec["name"], index))
    proc = log = None
    rec = {
        "series": spec["name"],
        "title": spec["title"],
        "run": index,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "workdir": workdir,
    }
    try:
        env, land_root, lands, home = setup(spec, workdir)
        if spec["llm"]:
            proc, log = start_llm(env, workdir)
            time.sleep(0.3)   # 讓 serve 先站起來

        t0 = time.perf_counter()
        code, out, err = aos(
            ["run", land_root, "--until", "idle", "--budget", str(BUDGET), "--json"], env)
        wall = time.perf_counter() - t0

        report = read_json_str(out)
        stop_llm(proc, log)
        proc = None

        # ---- 收數字 ----
        insts = sum(count_insts(p) for p in lands)
        tickdirs = sum(count_tick_dirs(p) for p in lands)
        led = ledger_tokens(home)
        baton = read_json(os.path.join(land_root, ".aos", "series.json"), {}) or {}
        baton_res = [s.get("resources") for s in baton.get("series", [])]

        rec.update({
            "exit_code": code,
            "wall_s": round(wall, 4),
            "ticks": (report or {}).get("ticks"),
            "reason": (report or {}).get("reason"),
            "idle": (report or {}).get("idle"),
            "insts": insts,
            "tick_dirs": tickdirs,
            "llm_calls": led["llm_calls"],
            "tokens": led["tokens"] if spec["llm"] else None,
            "tokens_in": led["tokens_in"] if spec["llm"] else None,
            "tokens_out": led["tokens_out"] if spec["llm"] else None,
            "llm_ms": led["llm_ms"] if spec["llm"] else None,
            "baton_resources": baton_res,
            "series_status": [s.get("status") for s in baton.get("series", [])],
            "stderr_tail": err.strip()[-500:],
        })
        rec["ok"] = bool(code == 0 and rec["reason"] == "idle"
                         and all(s == "done" for s in rec["series_status"]))
        if not rec["ok"]:
            rec["message"] = (report or {}).get("message", "")
        return rec
    except Exception as e:                       # noqa: BLE001 — bench 不該因一次失敗全掛
        rec.update({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})
        return rec
    finally:
        stop_llm(proc, log)
        if keep_dir:
            dst = os.path.join(keep_dir, "%s-%d" % (spec["name"], index))
            try:
                shutil.move(workdir, dst)
                rec["workdir"] = dst
            except OSError:
                pass
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def read_json_str(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


# ---------------------------------------------------------------- 兩把尺
def spread(values):
    """分布寬度。回 dict：n／min／max／中位數／最大最小差／相對寬度。"""
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    med = statistics.median(vals)
    rel = None if med == 0 else (hi - lo) / float(med)
    return {"n": len(vals), "min": lo, "max": hi, "median": med,
            "range": hi - lo, "rel_range": rel}


def fmt(v, unit=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        return ("%.3f%s" % (v, unit)) if abs(v) < 100 else ("%.1f%s" % (v, unit))
    return "%s%s" % (v, unit)


def fmt_list(values, unit=""):
    return "、".join(fmt(v, unit) for v in values)


# 表格每一列＝(尺, 指標名, 從記錄取值的 key, 自報值的 key 或 None, 單位)
ROWS = [
    ("① 自報vs實際", "格數", "ticks", "ticks", ""),
    ("① 自報vs實際", "指令數", "insts", "insts", ""),
    ("① 自報vs實際", "LLM 次數", "llm_calls", "llm_calls", ""),
    ("② 分布寬度", "格數", "ticks", None, ""),
    ("② 分布寬度", "牆鐘秒", "wall_s", None, "s"),
    ("② 分布寬度", "指令數", "insts", None, ""),
    ("② 分布寬度", "token", "tokens", None, ""),
]


def verdict(ruler, metric, dec, sp, n):
    """一句話結論。n＝跑了幾次。"""
    if sp is None:
        return "這支串沒有這個數字（不打 LLM）。"
    if ruler.startswith("①"):
        if dec is None:
            return "原稿沒自報這一項。"
        if sp["min"] == sp["max"]:
            d = sp["min"] - dec
            if d == 0:
                return "自報準，%d 次都一樣。" % n
            return "%d 次都是 %s，比自報多 %+d（固定偏差，可以在自報公式裡補掉）。" % (
                n, sp["min"], d)
        return "實際在 %s~%s 之間跳，自報 %s 本身就不是一個數字說得完的。" % (
            sp["min"], sp["max"], dec)
    # ② 分布寬度
    if sp["range"] == 0:
        return "%d 次一模一樣，完全可預測。" % n
    if sp["rel_range"] is not None and sp["rel_range"] < 0.05:
        return "抖 %s（中位數的 %.1f%%），可以當常數看。" % (fmt(sp["range"]), sp["rel_range"] * 100)
    if sp["rel_range"] is not None and sp["rel_range"] < 0.25:
        return "抖 %s（中位數的 %.0f%%），會晃但還在一個量級。" % (
            fmt(sp["range"]), sp["rel_range"] * 100)
    return "抖 %s（中位數的 %.0f%%），這條不穩，別拿它當保證。" % (
        fmt(sp["range"]), sp["rel_range"] * 100)


def summarize(all_recs, outdir, runs):
    lines = []
    lines.append("# 可預測性的兩把尺 — 第一版量測")
    lines.append("")
    lines.append("跑的時間：%s　每支串跑 %d 次　機器：%s"
                 % (time.strftime("%Y-%m-%d %H:%M:%S"), runs, os.uname().sysname))
    lines.append("")
    lines.append("兩把尺照 [構想集 01 章](../../../wf/workflows/ideas/01-what-and-goals.md) A-04：")
    lines.append("**① 自報 vs 實際**（原稿 `resources` 自報 vs 跑出來的）、"
                 "**② 分布寬度**（同一支串跑 %d 次，數字散多開）。" % runs)
    lines.append("")

    # ---- 主表 ----
    lines.append("## 表")
    lines.append("")
    lines.append("| 串 | 尺 | 自報 | 實際 %d 次 | 最大最小差 | 結論 |" % runs)
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for spec in all_recs["order"]:
        recs = all_recs["by_series"][spec]
        dec = all_recs["declared"][spec]
        ok = [r for r in recs if r.get("ok")]
        use = ok or recs
        for ruler, metric, key, deckey, unit in ROWS:
            vals = [r.get(key) for r in use]
            sp = spread(vals)
            d = dec.get(deckey) if deckey else None
            if sp is None and d is None:
                continue
            lines.append("| %s | %s %s | %s | %s | %s | %s |" % (
                spec, ruler, metric,
                fmt(d) if deckey else "—",
                fmt_list(vals, unit),
                fmt(sp["range"], unit) if sp else "—",
                verdict(ruler, metric, d, sp, len(use)),
            ))
    lines.append("")

    # ---- 成功／失敗 ----
    lines.append("## 跑成功了沒")
    lines.append("")
    lines.append("| 串 | 成功 / 總數 | 停止原因 | 備註 |")
    lines.append("| --- | --- | --- | --- |")
    for spec in all_recs["order"]:
        recs = all_recs["by_series"][spec]
        ok = [r for r in recs if r.get("ok")]
        reasons = sorted(set(str(r.get("reason") or r.get("error")) for r in recs))
        bad = [r for r in recs if not r.get("ok")]
        note = "—" if not bad else (bad[0].get("message") or bad[0].get("error") or "")[:80]
        lines.append("| %s | %d / %d | %s | %s |"
                     % (spec, len(ok), len(recs), "、".join(reasons), note))
    lines.append("")

    # ---- 哪支最不穩 ----
    lines.append("## 哪支最不穩")
    lines.append("")
    lines.append("拿牆鐘秒的相對寬度（最大最小差 ÷ 中位數）排：")
    lines.append("")
    lines.append("| 串 | 牆鐘中位數 | 牆鐘最大最小差 | 相對寬度 | 格數寬度 |")
    lines.append("| --- | --- | --- | --- | --- |")
    rank = []
    for spec in all_recs["order"]:
        use = [r for r in all_recs["by_series"][spec] if r.get("ok")] \
            or all_recs["by_series"][spec]
        w = spread([r.get("wall_s") for r in use])
        t = spread([r.get("ticks") for r in use])
        if w:
            rank.append((w["rel_range"] if w["rel_range"] is not None else 0, spec, w, t))
    for rel, spec, w, t in sorted(rank, reverse=True):
        lines.append("| %s | %s | %s | %.1f%% | %s |" % (
            spec, fmt(w["median"], "s"), fmt(w["range"], "s"), rel * 100,
            fmt(t["range"]) if t else "—"))
    lines.append("")
    if rank:
        worst = sorted(rank, reverse=True)[0]
        lines.append("**最不穩的是 `%s`**（牆鐘相對寬度 %.1f%%）。" % (worst[1], worst[0] * 100))
        lines.append("")

    # ---- 自報這件事本身 ----
    lines.append("## 自報值今天躺在哪")
    lines.append("")
    lines.append("原稿頂層寫的 `resources` 只是被載入器原樣抄進 `.aos/program/main.json`，"
                 "**沒有任何程式讀它**；接力棒 `.aos/series.json` 每條串都有一個 `resources` 欄，"
                 "跑完仍然是：")
    lines.append("")
    for spec in all_recs["order"]:
        recs = all_recs["by_series"][spec]
        vals = sorted(set(json.dumps(r.get("baton_resources"), ensure_ascii=False)
                          for r in recs))
        lines.append("- `%s`：%s" % (spec, "、".join(vals)))
    lines.append("")
    lines.append("所以尺①今天是 bench 自己把原稿的自報值跟檔案系統數出來的實際值兜起來的，"
                 "不是系統自己記的帳。要它變成系統的帳，見 README「原型缺什麼」。")
    lines.append("")

    text = "\n".join(lines) + "\n"
    with open(os.path.join(outdir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------- 主流程
def main(argv=None):
    ap = argparse.ArgumentParser(description="可預測性的兩把尺")
    ap.add_argument("--runs", type=int, default=5, help="每支串跑幾次（預設 5）")
    ap.add_argument("--series", default="", help="只跑這幾支，逗號分隔（預設全部）")
    ap.add_argument("--keep", action="store_true", help="留下每次的暫存家，好事後翻現場")
    ap.add_argument("--out", default=None, help="輸出目錄（預設 proto/bench/results/<時間>）")
    args = ap.parse_args(argv)

    want = [s.strip() for s in args.series.split(",") if s.strip()]
    specs = [s for s in SERIES if not want or s["name"] in want]
    if not specs:
        sys.stderr.write("錯誤：--series 沒有對到任何一支；有的是 %s\n"
                         % "、".join(s["name"] for s in SERIES))
        return 2

    outdir = args.out or os.path.join(RESULTS_DIR, time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(outdir, exist_ok=True)
    keep_dir = os.path.join(outdir, "workdirs") if args.keep else None
    if keep_dir:
        os.makedirs(keep_dir, exist_ok=True)

    raw_path = os.path.join(outdir, "raw.jsonl")
    all_recs = {"order": [], "by_series": {}, "declared": {}}
    with open(raw_path, "w", encoding="utf-8") as raw:
        for spec in specs:
            print("== %s ==" % spec["title"])
            all_recs["order"].append(spec["name"])
            all_recs["by_series"][spec["name"]] = []
            all_recs["declared"][spec["name"]] = declared(
                os.path.join(SERIES_DIR, spec["name"]))
            for i in range(1, args.runs + 1):
                rec = one_run(spec, i, keep_dir)
                rec["declared"] = all_recs["declared"][spec["name"]]
                raw.write(json.dumps(rec, ensure_ascii=False) + "\n")
                raw.flush()
                all_recs["by_series"][spec["name"]].append(rec)
                print("  第 %d 次：%s 格數 %s 指令 %s 牆鐘 %s 秒 token %s"
                      % (i, "OK " if rec.get("ok") else "壞了",
                         rec.get("ticks"), rec.get("insts"),
                         fmt(rec.get("wall_s")), rec.get("tokens")))

    text = summarize(all_recs, outdir, args.runs)
    print()
    print(text)
    print("原始資料：%s" % raw_path)
    print("表：%s" % os.path.join(outdir, "summary.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
