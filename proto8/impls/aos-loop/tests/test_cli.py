#!/usr/bin/env python3
"""test_cli.py：aos-loop 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-loop

每個案例一個空的暫存資料夾（tempfile，結束就清掉）、環境先清掉 AOS_*；自己造小程式（不靠 demo）。
直接叫 aos-loop（不經 aos-exec），所以要 AOS_STACK 的案例自己給。
A 段從 proto8/tests/test_exec.py 裡 aos-loop 的案例移植（那邊經 aos-exec 叫；行為應一致，錯誤一行多了代號）；
B 段是 run／max 的細節、字串 run 走 aos-exec 的規則、不寫 stdout；C 段是訊號（轉給那次、收完以 128＋N 結束）；
D 段是窗（interval_ms、ctl、state）；E 段是 10-21 傍晚的命令列（旗標、設定檔 檔#/指標、run 陣列；ideas § 9）；
F 段是 10-23 壓測後的修正；G 段是設定檔與 ctl 的指示詞（10-23 晚）。
10-21 起 run 不收內嵌單子，A～D 段寫內嵌單子的案例由 loop() 換成 `loop.json#/body`（見 loop）。
"""
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "bin",
                                                                          "aos-loop"))
failures = 0
cases = []


def case(fn):
    cases.append(fn)
    return fn


def env_of(env):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e.update(env or {})
    return e


def run(*args, env=None, cwd=None, input=None):
    """跑 aos-loop，回 (退出碼, stdout, 錯誤代號或 None, stderr)。"""
    r = subprocess.run([BIN, *args], capture_output=True, text=True, env=env_of(env), cwd=cwd, input=input,
                       timeout=60)
    err = None
    if r.returncode == 1 and r.stderr.startswith("aos-loop: ") and len(r.stderr.splitlines()) == 1:
        err = r.stderr[len("aos-loop: "):].split(" ", 1)[0]   # 自己的錯：一行「aos-loop: 代號 原因」
    return r.returncode, r.stdout, err, r.stderr


def put(path, text, mode=0o644):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if isinstance(text, str) else json.dumps(text))
    p.chmod(mode)
    return str(p)


def prog(parent, name, body, entry="_entry"):
    """parent/name/entry：可執行的 sh 小程式。回資料夾路徑。"""
    put(Path(parent) / name / entry, "#!/bin/sh\n" + body, 0o755)
    return str(Path(parent) / name)


def loop(t, cfg):
    """寫 t/loop.json。10-21 起 run 只收 aos-exec 的目標（10-21 plan L11）：cfg 的 run 是物件（內嵌單子）時，
    照新寫法搬到 body、run 改成 "loop.json#/body"（相對 cwd；案例都在 t 裡跑）。要原樣寫進去就用 put。"""
    if isinstance(cfg, dict) and isinstance(cfg.get("run"), dict):
        cfg = dict(cfg, run="loop.json#/body", body=cfg["run"])
    return put(Path(t, "loop.json"), cfg)


def stack(t):
    s = Path(t, "stack")
    s.mkdir(exist_ok=True)
    return s


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


# ───────── A. 從 proto8/tests/test_exec.py 移植 ─────────

@case
def failure_code(t):
    prog(t, "bad", "exit 7\n")
    loop(t, {"run": "bad", "max": 3})
    rc, out, _, stderr = run("loop.json", cwd=t)
    check("子資料夾失敗：以原碼結束", (rc, stderr), (7, "aos-loop: 第 1 次 bad 失敗，結束碼 7\n"))


@case
def embedded_inst_runs_each_lap(t):
    s = stack(t)
    loop(t, {"run": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/n"']}, "max": 3})
    rc, _, _, stderr = run("loop.json", cwd=t, env={"AOS_STACK": str(s)})
    check("內嵌單子一次次跑", (rc, stderr, (s / "n").read_text().split()), (0, "", ["x", "x", "x"]))


@case
def reaching_max_exits_0_with_empty_stderr(t):
    loop(t, {"run": {"argv": ["true"]}, "max": 2})
    rc, out, _, stderr = run("loop.json", cwd=t)
    check("跑滿 max：0、stderr 空", (rc, out, stderr), (0, "", ""))


@case
def embedded_inst_stop_and_failure_codes(t):
    for code, want in ((10, 0), (7, 7)):
        loop(t, {"run": {"argv": ["sh", "-c", "exit %d" % code]}, "max": 3})
        check("單子退 %d" % code, run("loop.json", cwd=t)[0], want)
    rc, _, _, stderr = run("loop.json", cwd=t)
    check("單子失敗那行的「誰」＝run 的目標", stderr, "aos-loop: 第 1 次 loop.json#/body 失敗，結束碼 7\n")


@case
def own_errors_exit_1_one_line(t):
    want = {None: "CfgMissing", "{nope": "CfgBad", '{"max": 2}': "CfgBad",
            '{"run": {"argv": ["no-such-cmd-xyz"]}}': "CfgBad"}   # 10-21 起 run 是物件＝自己的錯
    for text, code in want.items():
        if text is not None:
            put(Path(t, "loop.json"), text)
        rc, _, err, stderr = run("loop.json", cwd=t)
        check("自己的錯 %r" % text, (rc, err, len(stderr.splitlines())), (1, code, 1))


# ───────── B. run／max 的細節、字串 run＝aos-exec 它 ─────────

@case
def usage(t):
    check("沒給 LOOP.json", run()[:3:2], (1, "ArgumentsBad"))


@case
def max_default_unlimited(t):
    # 10-21 plan L8：max 沒寫＝不限（原 10）；第 15 次退 10 停
    s = stack(t)
    loop(t, {"run": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/n"; [ $(wc -l < "$AOS_STACK/n") -ge 15 ] && exit 10; exit 0']}})
    rc = run("loop.json", cwd=t, env={"AOS_STACK": str(s)})[0]
    check("max 沒寫＝不限", (rc, len((s / "n").read_text().split())), (0, 15))


@case
def max_zero_and_negative(t):
    loop(t, {"run": {"argv": ["sh", "-c", "touch ran"]}, "max": 0})
    rc, out, _, stderr = run("loop.json", cwd=t)
    check("max 0：一次都不跑", (rc, stderr, Path(t, "ran").exists()), (0, "", False))
    # 10-20 起照 bin 版：max 要是非負整數（負的＝自己的錯）
    loop(t, {"run": {"argv": ["sh", "-c", "touch ran"]}, "max": -3})
    check("max -3：CfgBad", (run("loop.json", cwd=t)[:3:2], Path(t, "ran").exists()), ((1, "CfgBad"), False))


@case
def bad_fields(t):
    for cfg in ({"run": "x", "max": "3"}, {"run": "x", "max": 2.5}, {"run": "x", "max": True},
                {"run": "x", "max": None}, {"run": 3}, {"run": []}, {"run": ["x", 1]}, {"run": [None]},
                {"run": {"argv": ["true"]}}, {"run": None}, ["run"]):
        put(Path(t, "loop.json"), cfg)
        check("欄位不對 %r" % (cfg,), run("loop.json", cwd=t)[:3:2], (1, "CfgBad"))


@case
def other_keys_ignored(t):
    loop(t, {"run": {"argv": ["true"]}, "max": 1, "foo": 5, "loops": {}})
    check("其他 key 忽略", run("loop.json", cwd=t)[:2], (0, ""))


@case
def string_run_goes_through_aos_exec(t):
    # 沒設 AOS_WS＝cwd、AOS_STACK＝$AOS_WS/.stack/、AOS_CF／AOS_CD、cd 進入口所在的資料夾
    prog(t, "cell", 'echo "$AOS_WS|$AOS_STACK|$AOS_CF|$AOS_CD|$(pwd)" >> "$AOS_STACK/seen"\n')
    loop(t, {"run": "cell", "max": 2})
    rc, _, _, stderr = run("loop.json", cwd=t)
    real = os.path.realpath(t)
    line = "%s|%s/.stack/|%s/cell/_entry|%s/cell|%s/cell" % (real, real, real, real, real)
    check("字串 run＝aos-exec 它", (rc, stderr, Path(t, ".stack", "seen").read_text().splitlines()),
          (0, "", [line, line]))


@case
def string_run_keeps_given_ws_and_stack(t):
    ws = Path(t, "ws"); ws.mkdir()
    s = stack(t)
    prog(t, "cell", 'echo "$AOS_WS|$AOS_STACK" > "$AOS_STACK/seen"\n')
    loop(t, {"run": "cell", "max": 1})
    run("loop.json", cwd=t, env={"AOS_WS": str(ws), "AOS_STACK": str(s)})
    check("沿用 AOS_WS／AOS_STACK", (s / "seen").read_text().strip(), "%s|%s/" % (ws, s))


@case
def string_run_stop_code(t):
    prog(t, "idle", "exit 10\n")
    loop(t, {"run": "idle", "max": 5})
    check("字串 run 退 10＝正常停", run("loop.json", cwd=t)[:4:3], (0, ""))


@case
def string_run_entry_missing_is_that_laps_failure(t):
    # 等同 `aos-exec nope` 退 1：那一層 aos-exec 說自己的錯，loop 說「第幾次、誰、碼幾」
    loop(t, {"run": "nope", "max": 3})
    rc, _, _, stderr = run("loop.json", cwd=t)
    lines = stderr.splitlines()
    check("入口不在：碼 1、兩行", (rc, len(lines), lines[0].startswith("aos-exec: EntryMissing "), lines[1]),
          (1, 2, True, "aos-loop: 第 1 次 nope 失敗，結束碼 1"))


@case
def string_run_json_entries(t):
    # 子資料夾的入口是 argv 陣列、inst 單子（子行程裡 run_inst）都行
    put(Path(t, "a", "_entry.json"), ["sh", "-c", 'echo a >> "$AOS_STACK/n"'])
    put(Path(t, "b", "_entry.json"), {"argv": ["sh", "-c", 'echo b >> "$AOS_STACK/n"; exit 10']})
    for name in ("a", "b"):
        loop(t, {"run": name, "max": 2})
        check("JSON 入口 %s" % name, run("loop.json", cwd=t)[0], 0)
    check("跑了幾次", Path(t, ".stack", "n").read_text().split(), ["a", "a", "b"])


@case
def entry_reread_each_lap(t):
    # 每次重找入口（同每次都叫一次 aos-exec）：第一次把入口換掉，第二次跑新的
    put(Path(t, "c", "next"), "#!/bin/sh\nexit 10\n", 0o755)
    prog(t, "c", 'echo 1 >> "$AOS_STACK/n"; mv "$AOS_CD/next" "$AOS_CD/_entry"\n')
    loop(t, {"run": "c", "max": 5})
    check("每次重找入口", (run("loop.json", cwd=t)[0], Path(t, ".stack", "n").read_text().split()), (0, ["1"]))


@case
def does_not_write_stdout(t):
    # loop 自己不寫 stdout；那次的 stdout 接呼叫者的（loop 不讀）
    prog(t, "cell", "echo hi\n")
    loop(t, {"run": "cell", "max": 2})
    check("字串 run 的 stdout 原樣過", run("loop.json", cwd=t)[:2], (0, "hi\nhi\n"))
    loop(t, {"run": {"argv": ["echo", "yo"]}, "max": 2})
    check("單子的 stdout 原樣過", run("loop.json", cwd=t)[:2], (0, "yo\nyo\n"))


@case
def inst_env_directive_and_relative_cwd(t):
    # 單子的指示詞由 aos-exec（run_inst）解；相對路徑從入口檔（loop.json）所在的資料夾算
    s = stack(t)
    Path(t, "sub").mkdir()
    loop(t, {"run": {"argv": ["pwd"], "cwd": "sub", "stdout": {"$env": "AOS_STACK", "$path": "out"}}, "max": 1})
    rc = run("loop.json", cwd=t, env={"AOS_STACK": str(s)})[0]
    check("$env＋path、相對 cwd", (rc, (s / "out").read_text().strip()), (0, os.path.realpath(Path(t, "sub"))))
    loop(t, {"run": {"argv": ["true"], "stdout": {"$env": "NOPE_XYZ"}}, "max": 1})
    rc, _, _, stderr = run("loop.json", cwd=t)
    lines = stderr.splitlines()
    check("$env 沒設＝那次 aos-exec 的錯（碼 1）", (rc, len(lines), lines[0].startswith("aos-exec: DirectiveBad ")),
          (1, 2, True))


@case
def inst_timeout_is_failure(t):
    loop(t, {"run": {"argv": ["sleep", "30"], "timeout_ms": 200, "grace_ms": 200}, "max": 3})
    t0 = time.monotonic()
    rc, _, _, stderr = run("loop.json", cwd=t)
    check("逾時那次＝失敗（143）", (rc, stderr, time.monotonic() - t0 < 10),
          (143, "aos-loop: 第 1 次 loop.json#/body 失敗，結束碼 143\n", True))


@case
def killed_by_signal_code(t):
    prog(t, "k", "kill -9 $$\n")
    loop(t, {"run": "k", "max": 3})
    check("字串 run 被訊號停掉＝128＋N", run("loop.json", cwd=t)[0], 137)


@case
def string_run_path_as_is(t):
    # ideas § 24：aos 的程式都不動 PATH，字串 run 那次看到的 PATH 跟 loop 收到的一樣（不加任何 bin）
    prog(t, "cell", 'echo "$PATH" > "$AOS_STACK/path"\n')
    loop(t, {"run": "cell", "max": 1})
    rc = run("loop.json", cwd=t, env={"PATH": "/usr/bin:/bin"})[0]
    check("字串 run PATH 原樣", (rc, Path(t, ".stack", "path").read_text().strip()), (0, "/usr/bin:/bin"))


# ───────── C. 訊號：轉給那次、收完以 128＋N 結束 ─────────

def start(t, env=None):
    p = subprocess.Popen([BIN, "loop.json"], cwd=t, env=env_of(env), stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    return p


def wait_file(path, secs=10):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if Path(path).exists():
            return True
        time.sleep(0.02)
    return False


@case
def sigterm_forwarded_to_string_lap(t):
    # 那次收到 SIGTERM 收好自己、退 0；loop 不起下一次，以 143 結束
    prog(t, "c", 'trap \'echo got >> "$AOS_STACK/log"; exit 0\' TERM\n'
                 'echo ran >> "$AOS_STACK/log"; touch "$AOS_STACK/up"\nwhile :; do sleep 0.05; done\n')
    loop(t, {"run": "c", "max": 5})
    p = start(t)
    ok = wait_file(Path(t, ".stack", "up"))
    p.send_signal(signal.SIGTERM)
    out, err = p.communicate(timeout=20)
    check("字串 run：轉 SIGTERM、收完 143", (ok, p.returncode, out, err, Path(t, ".stack", "log").read_text().split()),
          (True, 143, "", "", ["ran", "got"]))


@case
def sigint_forwarded_to_inst_lap(t):
    s = stack(t)
    loop(t, {"run": {"argv": ["sh", "-c", 'trap \'echo got > "$AOS_STACK/got"; exit 0\' INT; '
                              'touch "$AOS_STACK/up"; while :; do sleep 0.05; done']}, "max": 5})
    p = start(t, {"AOS_STACK": str(s)})
    ok = wait_file(s / "up")
    p.send_signal(signal.SIGINT)
    out, err = p.communicate(timeout=20)
    check("單子：轉 SIGINT 給整群、收完 130", (ok, p.returncode, err, (s / "got").exists()), (True, 130, "", True))


@case
def sighup_lap_dies(t):
    # 那次不接、被 SIGHUP 停掉：loop 還是以 128＋1 結束（不另說「第幾次失敗」）
    prog(t, "c", 'touch "$AOS_STACK/up"\nexec sleep 30\n')
    loop(t, {"run": "c", "max": 5})
    p = start(t)
    ok = wait_file(Path(t, ".stack", "up"))
    p.send_signal(signal.SIGHUP)
    out, err = p.communicate(timeout=20)
    check("SIGHUP：129", (ok, p.returncode, err), (True, 129, ""))


# ───────── D. 選填 key：interval_ms、ctl、state（10-20，對照 proto8/tests/test_loop.py 的 Windows）─────────

def count():
    return {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/laps"']}


def run_loop(t, cfg, env=None):
    loop(t, cfg)
    return subprocess.run([BIN, "loop.json"], cwd=t, env=env_of(env), capture_output=True, text=True, timeout=30)


@case
def state_written_with_heartbeat(t):
    s = stack(t)
    r = run_loop(t, {"run": count(), "max": 3, "state": "state.json"}, {"AOS_STACK": str(s)})
    st = json.loads((s / "state.json").read_text())
    check("state 寫好、結束碼", (r.returncode, r.stderr, st["kind"], st["phase"], st["runs"], st["code"], st["max"],
                             st["ctl_seq"]), (0, "", "state", "done", 3, 0, 3, None))
    check("state 欄位順序（同 bin 版）", list(st), ["kind", "phase", "runs", "max", "interval_ms", "paused", "ctl_seq",
                                             "ctl_warning", "code", "pid", "started_at_ticks", "boot_id", "at"])
    check("心跳欄位", (isinstance(st["pid"], int), isinstance(st["started_at_ticks"], int), isinstance(st["at"], str),
                     (s / ".state.json").exists()), (True, True, True, False))
    # at＝ISO 8601 UTC 到毫秒，同 Python datetime.now(timezone.utc).isoformat(timespec="milliseconds")（10-23 命名統合）
    at = datetime.datetime.fromisoformat(st["at"])
    check("心跳 at 的寫法", (re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+00:00", st["at"]) is not None,
                         abs((datetime.datetime.now(datetime.timezone.utc) - at).total_seconds()) < 60), (True, True))


@case
def no_windows_no_files(t):
    s = stack(t)
    r = run_loop(t, {"run": count(), "max": 2}, {"AOS_STACK": str(s)})
    check("沒開窗就不寫檔", (r.returncode, sorted(p.name for p in s.iterdir())), (0, ["laps"]))


@case
def window_without_stack(t):
    r = run_loop(t, {"run": count(), "max": 1, "ctl": "ctl.json"})
    check("寫了窗卻沒 AOS_STACK", (r.returncode, r.stderr.startswith("aos-loop: StackMissing ")), (1, True))
    r = run_loop(t, {"run": count(), "max": 1, "state": ""})
    check("窗名空字串", (r.returncode, r.stderr.startswith("aos-loop: CfgBad ")), (1, True))


@case
def bad_interval(t):
    for v in (-1, "5", 1.5, None):
        r = run_loop(t, {"run": count(), "interval_ms": v})
        check("interval_ms %r" % (v,), (r.returncode, r.stderr.startswith("aos-loop: CfgBad ")), (1, True))


@case
def interval_spaces_laps(t):
    s = stack(t)
    t0 = time.monotonic()
    r = run_loop(t, {"run": count(), "max": 3, "interval_ms": 300}, {"AOS_STACK": str(s)})
    check("interval_ms 隔開兩次", (r.returncode, time.monotonic() - t0 >= 0.6, len((s / "laps").read_text().split())),
          (0, True, 3))


@case
def ctl_stopped_and_seq(t):
    s = stack(t)
    (s / "ctl.json").write_text(json.dumps({"stopped": True, "seq": 7}))
    r = run_loop(t, {"run": count(), "max": 3, "ctl": "ctl.json", "state": "state.json"}, {"AOS_STACK": str(s)})
    st = json.loads((s / "state.json").read_text())
    check("ctl stopped＋seq", (r.returncode, r.stderr, st["phase"], st["runs"], st["ctl_seq"], (s / "laps").exists()),
          (0, "", "stopped", 0, 7, False))


@case
def ctl_max_overrides(t):
    s = stack(t)
    (s / "ctl.json").write_text(json.dumps({"max": 1}))
    r = run_loop(t, {"run": count(), "max": 5, "ctl": "ctl.json"}, {"AOS_STACK": str(s)})
    check("ctl 的 max 蓋過設定", (r.returncode, len((s / "laps").read_text().split())), (0, 1))


@case
def bad_ctl_kept_last_good(t):
    s = stack(t)
    (s / "ctl.json").write_text(json.dumps({"max": "two"}))
    r = run_loop(t, {"run": count(), "max": 2, "ctl": "ctl.json", "state": "state.json"}, {"AOS_STACK": str(s)})
    st = json.loads((s / "state.json").read_text())
    check("壞 ctl 不採用、記 ctl_warning", (r.returncode, r.stderr, len((s / "laps").read_text().split()),
                                       "max" in (st["ctl_warning"] or "")), (0, "", 2, True))
    (s / "ctl.json").write_text("{nope")
    r = run_loop(t, {"run": count(), "max": 1, "ctl": "ctl.json", "state": "state.json"}, {"AOS_STACK": str(s)})
    st = json.loads((s / "state.json").read_text())
    check("ctl 不是 JSON", (r.returncode, "JSON" in (st["ctl_warning"] or "")), (0, True))


@case
def ctl_pause_then_resume(t):
    s = stack(t)
    (s / "ctl.json").write_text(json.dumps({"paused": True}))
    loop(t, {"run": count(), "max": 2, "ctl": "ctl.json", "state": "state.json"})
    p = start(t, {"AOS_STACK": str(s)})
    ok = wait_file(s / "state.json")
    time.sleep(0.5)
    paused = json.loads((s / "state.json").read_text())["phase"]
    ran = (s / "laps").exists()
    (s / "ctl.json").write_text(json.dumps({"paused": False}))
    out, err = p.communicate(timeout=20)
    check("ctl paused 再放開", (ok, paused, ran, p.returncode, err, len((s / "laps").read_text().split())),
          (True, "paused", False, 0, "", 2))


@case
def signal_while_waiting(t):
    s = stack(t)
    loop(t, {"run": count(), "max": 5, "interval_ms": 5000, "state": "state.json"})
    p = start(t, {"AOS_STACK": str(s)})
    ok = wait_file(s / "laps")
    time.sleep(0.2)
    p.send_signal(signal.SIGTERM)
    out, err = p.communicate(timeout=20)
    st = json.loads((s / "state.json").read_text())
    check("睡 interval 時收到 SIGTERM", (ok, p.returncode, err, st["phase"], st["code"],
                                       len((s / "laps").read_text().split())), (True, 143, "", "stopped", 143, 1))


@case
def ref_from_config_dir(t):
    # 單子裡 $ref 的相對檔名從 loop.json 所在的資料夾算（cwd 在別處）。10-21 起由 aos-exec 跑 `cfg/loop.json#/body`：
    # 寫著單子的檔＝loop.json；run 的相對路徑照 cwd，loop 不轉
    s = stack(t)
    put(Path(t, "cfg", "data.json"), {"msg": "hi"})
    put(Path(t, "cfg", "loop.json"), {"run": "cfg/loop.json#/body", "max": 1,
                                      "body": {"argv": ["echo", {"$ref": "data.json#/msg"}],
                                               "stdout": {"$env": "AOS_STACK", "$path": "out"}}})
    r = subprocess.run([BIN, "cfg/loop.json"], cwd=t, env=env_of({"AOS_STACK": str(s)}), capture_output=True, text=True)
    check("$ref 從設定檔的資料夾算", (r.returncode, (s / "out").read_text()), (0, "hi\n"))


# ───────── E. 10-21 傍晚的命令列：`aos-loop [旗標] 設定檔`、檔#/指標、run 陣列（ideas § 9；對照 proto8/tests/test_loop.py 的 Cli）─────────

@case
def cli_usage(t):
    loop(t, {"run": "x", "max": 0})
    for args in ((), ("loop.json", "more"), ("--max",)):
        rc, _, err, stderr = run(*args, cwd=t)
        check("usage %r" % (args,), (rc, err, "usage: aos-loop [--max N]" in stderr), (1, "ArgumentsBad", True))
    for args in (("--nope", "1", "loop.json"), ("--cfg", "loop.json")):   # 不認得的旗標（10-23 命名統合）
        rc, _, err, stderr = run(*args, cwd=t)
        check("usage %r" % (args,), (rc, err, "usage: aos-loop [--max N]" in stderr), (1, "FlagUnknown", True))
    rc, _, err, _ = run("--max", "x", "loop.json", cwd=t)
    check("--max 不是數字", (rc, err), (1, "CfgBad"))
    rc, _, err, _ = run("--interval-ms=-1", "loop.json", cwd=t)
    check("--interval-ms 負的", (rc, err), (1, "CfgBad"))


@case
def cli_flags_beat_config(t):
    s = stack(t)
    loop(t, {"run": count(), "max": 5})
    r = subprocess.run([BIN, "--max", "2", "loop.json"], cwd=t, env=env_of({"AOS_STACK": str(s)}), capture_output=True,
                       text=True, timeout=30)
    check("--max 蓋過 loop.json", (r.returncode, len((s / "laps").read_text().split())), (0, 2))
    (s / "laps").unlink()
    r = subprocess.run([BIN, "--max=1", "--state", "st.json", "--interval-ms", "0", "loop.json"], cwd=t,
                       env=env_of({"AOS_STACK": str(s)}), capture_output=True, text=True, timeout=30)
    st = json.loads((s / "st.json").read_text())
    check("--state、--max=", (r.returncode, st["runs"], st["max"], len((s / "laps").read_text().split())), (0, 1, 1, 1))
    r = subprocess.run([BIN, "--ctl", "c.json", "loop.json"], cwd=t, env=env_of(None), capture_output=True, text=True)
    check("--ctl 卻沒 AOS_STACK", (r.returncode, r.stderr.startswith("aos-loop: StackMissing ")), (1, True))


@case
def cli_config_pointer(t):
    s = stack(t)
    put(Path(t, "big.json"), {"loops": {"a": {"run": "big.json#/bodies/a", "max": 2}},
                              "bodies": {"a": {"argv": ["sh", "-c", 'echo a >> "$AOS_STACK/laps"']}}})
    r = subprocess.run([BIN, "big.json#/loops/a"], cwd=t, env=env_of({"AOS_STACK": str(s)}), capture_output=True,
                       text=True, timeout=30)
    check("設定檔 檔#/指標", (r.returncode, r.stderr, (s / "laps").read_text().split()), (0, "", ["a", "a"]))
    for spec, code in (("big.json#/nope", "CfgMissing"), ("big.json#loops", "CfgBad"), ("big.json#/loops", "CfgBad"),
                       ("nope.json", "CfgMissing")):
        rc, _, err, _ = run(spec, cwd=t)
        check("設定檔 %s" % spec, (rc, err), (1, code))


@case
def cli_run_array(t):
    prog(t, "c", 'echo "$*" >> "$AOS_STACK/args"\n')
    loop(t, {"run": ["c", "a b", "--x"], "max": 2})
    rc, _, _, stderr = run("loop.json", cwd=t)
    check("run 陣列＝[目標, 參數...]", (rc, stderr, Path(t, ".stack", "args").read_text().splitlines()),
          (0, "", ["a b --x", "a b --x"]))
    prog(t, "-dash", 'echo d >> "$AOS_STACK/args"\n')
    loop(t, {"run": "-dash", "max": 1})
    check("- 開頭的目標（aos-exec -- 目標）", run("loop.json", cwd=t)[0], 0)
    prog(t, "f", "exit 3\n")
    loop(t, {"run": ["f", "x"], "max": 1})
    check("陣列失敗那行的「誰」＝目標", run("loop.json", cwd=t)[3], "aos-loop: 第 1 次 f 失敗，結束碼 3\n")


@case
def loop_json_as_entry(t):
    # loop.json 帶 "_entry": ["aos-loop", {"$env": "AOS_CF"}]，`aos-exec loop.json` 就把它跑起來（PATH 上要有兩支）
    exe = os.path.join(os.path.dirname(BIN), "..", "..", "aos-exec", "bin")
    prog(t, "c", 'echo x >> "$AOS_STACK/n"\n')
    loop(t, {"run": "c", "max": 2, "_entry": ["aos-loop", {"$env": "AOS_CF"}]})
    path = os.pathsep.join([os.path.dirname(BIN), os.path.abspath(exe), "/usr/bin", "/bin"])
    r = subprocess.run([os.path.join(exe, "aos-exec"), "loop.json"], cwd=t, env=env_of({"PATH": path}),
                       capture_output=True, text=True, timeout=30)
    check("aos-exec loop.json", (r.returncode, r.stderr, Path(t, ".stack", "n").read_text().split()), (0, "", ["x", "x"]))


# ───────── F. 10-23 壓測後（使用者「都修都處理」）─────────

@case
def stack_missing_not_created(t):
    # 第 6 點：直接跑 aos-loop、開了 state 窗、$AOS_STACK 不在＝state 寫不了＝WriteFailed 一行、退 1，不自己建
    # （建 stack 只在 aos-exec 做，N-59 第 1 件；資料夾不見照 N-28 開頭 ③ 是使用者自己承擔）。第一次之前就寫 state，所以那次沒跑。
    mark = Path(t, "ran")
    prog(t, "c", 'echo x >> "%s"\n' % mark)
    gone = Path(t, "no", "stack")
    loop(t, {"run": "c", "max": 1, "state": "state.json"})
    rc, _, err, stderr = run("loop.json", cwd=t, env={"AOS_STACK": str(gone) + "/"})
    check("stack 不在：WriteFailed、退 1、不建、那次沒跑", (rc, err, gone.exists(), mark.exists()), (1, "WriteFailed", False, False))
    loop(t, {"run": "c", "max": 1})
    rc, _, _, stderr = run("loop.json", cwd=t, env={"AOS_STACK": str(gone) + "/"})
    check("沒開窗就用不到 stack：照跑", (rc, stderr, mark.exists()), (0, "", True))


# ───────── G. 設定檔與 ctl 的指示詞（10-23 晚，使用者「aos 讀的 JSON 全部支援」；N-45）─────────

@case
def cfg_directives(t):
    # loop 讀的五格（run、max、interval_ms、ctl、state）整個解；相對 $ref 從設定檔的資料夾算（cwd 在別處）
    s = stack(t)
    prog(t, "c", 'echo x >> "$AOS_STACK/n"\n')
    put(Path(t, "cfg", "n.json"), {"max": 2})
    (s / "w").mkdir()
    put(Path(t, "cfg", "loop.json"), {"run": {"$env": "RUN_ME"}, "max": {"$ref": "n.json#/max"},
                                      "state": {"$env": "ST", "$path": "state.json"}})
    r = subprocess.run([BIN, "cfg/loop.json"], cwd=t, env=env_of({"AOS_STACK": str(s), "RUN_ME": "c", "ST": "w"}),
                       capture_output=True, text=True, timeout=30)
    st = json.loads((s / "w" / "state.json").read_text()) if (s / "w" / "state.json").exists() else {}
    check("run／max／state 的指示詞", (r.returncode, r.stderr, len((s / "n").read_text().split()), st.get("max")),
          (0, "", 2, 2))
    # 整份是 $ref：換成那份檔，裡面的 $ref 從那份檔的資料夾算
    put(Path(t, "real", "loop.json"), {"run": "c", "max": {"$ref": "m.json"}})
    put(Path(t, "real", "m.json"), 1)
    put(Path(t, "top.json"), {"$ref": "real/loop.json"})
    (s / "n").unlink()
    r = subprocess.run([BIN, "top.json"], cwd=t, env=env_of({"AOS_STACK": str(s)}), capture_output=True, text=True)
    check("整份 $ref", (r.returncode, r.stderr, len((s / "n").read_text().split())), (0, "", 1))
    # run 陣列的元素也解
    loop(t, {"run": ["c", {"$env": "ARG"}], "max": 1})
    check("run 陣列元素的 $env", run("loop.json", cwd=t, env={"AOS_STACK": str(s), "ARG": "z"})[0], 0)


@case
def cfg_directive_bad_is_own_error(t):
    loop(t, {"run": "c", "max": {"$env": "NOPE_XYZ"}})
    rc, _, err, stderr = run("loop.json", cwd=t)
    check("設定檔的指示詞解不開＝自己的錯", (rc, err), (1, "DirectiveBad"))
    loop(t, {"run": "c", "max": {"$ref": "nope.json"}})
    check("$ref 讀不到", run("loop.json", cwd=t)[2], "DirectiveBad")
    loop(t, {"run": "c", "max": {"$ref": "loop.json#/max"}})
    check("$ref 繞圈", run("loop.json", cwd=t)[2], "DirectiveBad")
    # 寫法不合＝原封不動留著，照 key 的規則算（max 是物件＝CfgBad）
    loop(t, {"run": "c", "max": {"$ref": ""}})
    check("寫法不合原封不動", run("loop.json", cwd=t)[2], "CfgBad")


@case
def cfg_unread_keys_not_resolved(t):
    # loop 不讀的 key（body、_entry…）不解：body 裡 $env 沒設，起來不算 loop 的錯，是那次 aos-exec 的錯（C-52）
    put(Path(t, "loop.json"), {"run": "loop.json#/body", "max": 1, "other": {"$env": "NOPE_XYZ"},
                               "body": {"argv": ["true"], "stdout": {"$env": "NOPE_XYZ"}}})
    rc, _, err, stderr = run("loop.json", cwd=t)
    check("body 的指示詞留給那次", (rc, err, stderr.startswith("aos-exec: DirectiveBad ")), (1, None, True))


@case
def ctl_directives(t):
    # ctl 讀的五格整個解；相對 $ref 從 ctl 的資料夾（$AOS_STACK）算
    s = stack(t)
    put(s / "parts" / "stop.json", {"yes": True, "seq": 4})
    (s / "ctl.json").write_text(json.dumps({"stopped": {"$ref": "parts/stop.json#/yes"},
                                            "seq": {"$ref": "parts/stop.json", "$at": "/seq"}}))
    r = run_loop(t, {"run": count(), "max": 3, "ctl": "ctl.json", "state": "state.json"}, {"AOS_STACK": str(s)})
    st = json.loads((s / "state.json").read_text())
    check("ctl 的 $ref", (r.returncode, st["phase"], st["runs"], st["ctl_seq"], st["ctl_warning"]),
          (0, "stopped", 0, 4, None))
    # ctl 整份是 $ref
    (s / "ctl.json").write_text(json.dumps({"$ref": "parts/max.json"}))
    put(s / "parts" / "max.json", {"max": 1})
    r = run_loop(t, {"run": count(), "max": 3, "ctl": "ctl.json"}, {"AOS_STACK": str(s)})
    check("ctl 整份 $ref", (r.returncode, len((s / "laps").read_text().split())), (0, 1))


@case
def ctl_directive_bad_not_adopted(t):
    # 解不開＝整份不採用、維持上一份好的、原因進 ctl_warning（N-08），不退出
    s = stack(t)
    (s / "ctl.json").write_text(json.dumps({"stopped": True, "max": {"$env": "NOPE_XYZ"}}))
    r = run_loop(t, {"run": count(), "max": 2, "ctl": "ctl.json", "state": "state.json"}, {"AOS_STACK": str(s)})
    st = json.loads((s / "state.json").read_text())
    check("ctl 指示詞解不開不採用", (r.returncode, r.stderr, st["phase"], st["runs"], "NOPE_XYZ" in (st["ctl_warning"] or "")),
          (0, "", "done", 2, True))


for fn in cases:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            fn(tmp)
        except Exception as e:   # 一組炸掉不擋後面的組
            failures += 1
            print("失敗 %s：例外 %r" % (fn.__name__, e))

print("%d 組、%d 個失敗" % (len(cases), failures))
sys.exit(1 if failures else 0)
