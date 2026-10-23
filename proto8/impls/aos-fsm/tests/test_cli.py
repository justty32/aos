#!/usr/bin/env python3
"""test_cli.py：aos-fsm 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-fsm

每個案例一個空的暫存資料夾（tempfile，結束就清掉）、環境先清掉 AOS_*、cwd＝那個資料夾、AOS_STACK＝裡面的 stack/。
A 段從 proto8/tests/test_fsm.py 移植（行為應一致，錯誤一行多了代號）；B 段是條文與 bin 版推得出、那邊沒測的細節；
C 段是訊號（轉給那格、trace 與 state 照常寫完，再以 128＋N 結束）；D 段是 10-21 傍晚的命令列（ideas § 9）；
E 段是 fsm.json 的指示詞（10-23 晚）。
10-21 起 val 不收內嵌單子、trace 沒有 timed_out：寫內嵌單子的案例由 table() 換成 `fsm.json#/states/<名>/body`（見 table）；
格被逾時收掉＝那格的 aos-exec 以 128＋N 結束（fsm 看不到格裡有沒有逾時，C-52）。
巢狀逾時那案要 aos-exec 在 PATH 上：用兄弟專案 ../aos-exec/bin/aos-exec（沒建就那案算失敗）。
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
                                                                          "aos-fsm"))
IMPLS = Path(__file__).resolve().parent.parent.parent
EXEC_BIN = IMPLS / "aos-exec" / "bin"
failures = 0
cases = []


def case(fn):
    cases.append(fn)
    return fn


def env_of(t, env, stack=True):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = str(EXEC_BIN) + os.pathsep + e.get("PATH", "")
    if stack:
        e["AOS_STACK"] = str(Path(t, "stack"))
    e.update(env or {})
    return e


def run(t, fsm="fsm.json", env=None, stack=True):
    """跑一次，回 (退出碼, stdout, 錯誤代號或 None, stderr)。"""
    args = [BIN] if fsm is None else [BIN, fsm]
    r = subprocess.run(args, capture_output=True, text=True, env=env_of(t, env, stack), cwd=t, timeout=60)
    err = None
    if r.returncode == 1 and r.stderr.startswith("aos-fsm: ") and len(r.stderr.splitlines()) == 1:
        err = r.stderr[len("aos-fsm: "):].split(" ", 1)[0]   # 自己的錯：一行「aos-fsm: 代號 原因」
    return r.returncode, r.stdout, err, r.stderr


def put(path, text, mode=0o644):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if isinstance(text, str) else json.dumps(text))
    p.chmod(mode)
    return str(p)


def cell(t, name, body):
    put(Path(t, name, "_entry"), "#!/bin/sh\n" + body, 0o755)


def table(t, states, start="a"):
    """寫 t/fsm.json。10-21 起 val 只收 aos-exec 的目標（10-21 plan F2）：val 是物件（內嵌單子）的格，照新寫法把單子搬到
    同一格的 body、val 改成 "fsm.json#/states/<名>/body"（相對 cwd＝t）。要原樣寫進去就用 put。"""
    out = {}
    for name, c in states.items():
        if isinstance(c, dict) and isinstance(c.get("val"), dict):
            c = dict(c, val="fsm.json#/states/%s/body" % name, body=c["val"])
        out[name] = c
    return put(Path(t, "fsm.json"), {"start": start, "states": out})


def st(t):
    return Path(t, "stack")


def state(t):
    return (st(t) / "state.txt").read_text()


def trace(t):
    return [json.loads(l) for l in (st(t) / "trace.jsonl").read_text().splitlines()]


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


AB = {"a": {"val": "a", "next": "b"}, "b": {"val": "b", "next": "a"}}


# ───────── A. 從 proto8/tests/test_fsm.py 移植 ─────────

@case
def state_in_stack_and_advances(t):
    cell(t, "a", "exit 0\n"); cell(t, "b", "exit 0\n")
    table(t, AB)
    rc = run(t)[0]
    check("第一次 0、state＝b", (rc, state(t)), (0, "b\n"))   # 純文字一行狀態名，跟 shell 版同格式
    run(t)
    check("第二次 state＝a", state(t), "a\n")
    check("cwd 不留 state", list(Path(t).glob("state.txt")), [])


@case
def state_written_by_rename_not_in_place(t):
    # N-05：先寫 .state.txt 再改名蓋過去——蓋完 inode 換了、不留暫存檔
    cell(t, "a", "exit 0\n"); cell(t, "b", "exit 0\n")
    table(t, AB)
    put(st(t) / "state.txt", "a\n")
    before = os.stat(st(t) / "state.txt").st_ino
    rc = run(t)[0]
    check("改名寫入", (rc, state(t), os.stat(st(t) / "state.txt").st_ino != before, (st(t) / ".state.txt").exists()),
          (0, "b\n", True, False))


@case
def cell_10_passes_up_and_state_unchanged(t):
    cell(t, "a", "exit 10\n"); cell(t, "b", "exit 0\n")
    table(t, AB)
    put(st(t) / "state.txt", "a\n")
    check("格退 10：原樣往上、state 不動", (run(t)[0], state(t)), (10, "a\n"))


@case
def cell_failure_code_state_unchanged(t):
    cell(t, "a", "exit 3\n")
    table(t, {"a": {"val": "a", "next": "a"}, "b": {"val": "a", "next": "a"}})
    put(st(t) / "state.txt", "b\n")
    rc, out, _, stderr = run(t)
    check("格失敗：原碼、state 不動、fsm 不說話", (rc, state(t), stderr), (3, "b\n", ""))


@case
def string_cell_goes_through_aos_exec(t):
    cell(t, "a", 'echo "$AOS_STACK" > "$AOS_STACK/seen"\n')
    table(t, {"a": {"val": "a", "next": "a"}})
    st(t).mkdir()
    rc = run(t)[0]
    check("字串格＝aos-exec 它", (rc, (st(t) / "seen").read_text().strip()), (0, str(st(t)) + "/"))


@case
def object_cell_in_process_with_timeout(t):
    st(t).mkdir()
    table(t, {"a": {"val": {"argv": ["sleep", "30"], "timeout_ms": 200, "grace_ms": 300}, "next": "a"}})
    rc = run(t)[0]
    tr = trace(t)[0]
    check("單子逾時", (rc, tr["code"], tr["elapsed_ms"] < 5000, (st(t) / "state.txt").exists()), (143, 143, True, False))


@case
def object_cell_exit_code_and_env_resolved(t):
    st(t).mkdir()
    table(t, {"a": {"val": {"argv": ["sh", "-c", "echo hi; exit 4"],
                            "stdout": {"$env": "AOS_STACK", "$path": "out.txt"}}, "next": "a"}})
    rc = run(t)[0]
    check("單子的碼、$env 解開", (rc, (st(t) / "out.txt").read_text(), (st(t) / "state.txt").exists()), (4, "hi\n", False))


@case
def trace_jsonl_one_line_per_beat(t):
    cell(t, "a", "exit 0\n"); cell(t, "b", "exit 5\n")
    table(t, AB)
    for _ in range(3):
        run(t)
    tr = trace(t)
    check("每次一行", [(x["state"], x["code"]) for x in tr], [("a", 0), ("b", 5), ("b", 5)])
    check("欄位（沒有 timed_out）", list(tr[0]), ["at", "state", "code", "signal", "elapsed_ms"])
    for x in tr:
        datetime.datetime.fromisoformat(x["at"])


@case
def requires_stack(t):
    table(t, {"a": {"val": {"argv": ["true"]}, "next": "a"}})
    rc, _, err, stderr = run(t, stack=False)
    check("沒設 AOS_STACK", (rc, err, "沒設定 AOS_STACK" in stderr), (1, "StackMissing", True))


@case
def own_errors_exit_1_one_line(t):
    table(t, {"a": {"val": {"argv": ["true"]}, "next": "a"}})
    put(st(t) / "state.txt", "zzz\n")
    put(Path(t, "bad.json"), "{nope")
    put(Path(t, "objval.json"), {"start": "a", "states": {"a": {"val": {"argv": ["no-such-cmd-xyz"]}, "next": "a"}}})
    want = {"fsm.json": "StateUnknown", "bad.json": "CfgBad", "absent.json": "CfgMissing", "objval.json": "CfgBad"}
    for f, code in want.items():
        if f == "objval.json":
            put(st(t) / "state.txt", "a\n")
        rc, _, err, stderr = run(t, f)
        check("自己的錯 %s" % f, (rc, err, len(stderr.splitlines())), (1, code, 1))


@case
def outer_timeout_kills_nested_tree(t):
    cell(t, "slow/inner", 'echo $$ > "$AOS_STACK/pid"\nexec sleep 30\n')
    cell(t, "slow", "aos-exec inner\n")
    table(t, {"a": {"val": {"argv": ["aos-exec", "slow"], "timeout_ms": 300, "grace_ms": 200}, "next": "a"}})
    st(t).mkdir()
    t0 = time.monotonic()
    rc = run(t)[0]
    fast = time.monotonic() - t0 < 10   # 孤兒 sleep 會握著 pipe 拖滿 30 秒
    pid = int((st(t) / "pid").read_text())
    gone = False
    for _ in range(20):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            gone = True
            break
        time.sleep(0.05)
    check("外層逾時整棵收掉", (fast, rc != 0, trace(t)[0]["code"] != 0, (st(t) / "state.txt").exists(), gone),
          (True, True, True, False, True))


# ───────── B. 細節 ─────────

@case
def usage(t):
    check("沒給 FSM.json", run(t, None)[:3:2], (1, "ArgumentsBad"))


@case
def bad_tables(t):
    for doc in ({"states": {}}, {"start": 1, "states": {}}, {"start": "a"}, {"start": "a", "states": []}, ["a"]):
        put(Path(t, "fsm.json"), doc)
        check("表壞 %r" % (doc,), run(t)[:3:2], (1, "CfgBad"))


@case
def bad_cells(t):
    # 10-22 起開跑時查整張表：格的形狀不對也算表壞（CfgBad；原本這次查到那格才擋、StateUnknown）
    for c, code in (({"val": "a"}, "CfgBad"), ({"next": "a"}, "CfgBad"), ({"val": "a", "next": 3}, "CfgBad"),
                    ("a", "CfgBad"), ({"val": 3, "next": "a"}, "CfgBad"), ({"val": [], "next": "a"}, "CfgBad"),
                    ({"val": ["a", 1], "next": "a"}, "CfgBad"), ({"val": {"argv": ["true"]}, "next": "a"}, "CfgBad")):
        put(Path(t, "fsm.json"), {"start": "a", "states": {"a": c}})
        check("格壞 %r" % (c,), run(t)[:3:2], (1, code))
    check("格壞不留 trace", (st(t) / "trace.jsonl").exists(), False)


@case
def empty_state_file_means_start(t):
    cell(t, "a", "exit 0\n"); cell(t, "b", "exit 0\n")
    table(t, AB)
    put(st(t) / "state.txt", "  \n")
    run(t)
    put(st(t) / "state.txt", "  b \n")   # 前後空白去掉
    run(t)
    check("空的 state＝start；去空白", [x["state"] for x in trace(t)], ["a", "b"])


@case
def trace_line_format(t):
    # 排版同 Python json.dumps：", "、": "、key 順序固定、signal null、at 是秒為單位的 UTC +00:00
    cell(t, "a", "exit 0\n")
    table(t, {"a": {"val": "a", "next": "a"}})
    run(t)
    line = (st(t) / "trace.jsonl").read_text()
    ok = re.fullmatch(r'\{"at": "\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+00:00", "state": "a", "code": 0, "signal": null, '
                      r'"elapsed_ms": \d+\}\n', line)   # at＝ISO 8601 UTC 到毫秒（10-23 命名統合）
    check("trace 一行的排版", (ok is not None, line), (True, line))


@case
def string_cell_killed_signal_in_trace(t):
    cell(t, "a", "kill -9 $$\n")
    table(t, {"a": {"val": "a", "next": "a"}})
    rc = run(t)[0]
    x = trace(t)[0]
    check("字串格被訊號停掉", (rc, x["code"], x["signal"], "timed_out" in x), (137, 137, 9, False))


@case
def string_cell_entry_missing(t):
    # 等同 `aos-exec nope` 退 1：那層 aos-exec 說自己的錯，fsm 不說話、以 1 結束、trace 有一行
    table(t, {"a": {"val": "nope", "next": "a"}})
    st(t).mkdir()   # aos-exec 在找入口時就失敗、還沒建 AOS_STACK
    rc, _, _, stderr = run(t)
    check("格的入口不在", (rc, stderr.startswith("aos-exec: EntryMissing "), len(stderr.splitlines()), trace(t)[0]["code"]),
          (1, True, 1, 1))


@case
def cell_stdout_not_read(t):
    # 不讀格的 stdout：原樣接呼叫者的；next 只在表上
    cell(t, "a", 'echo \'{"next": "zzz"}\'\n')
    table(t, {"a": {"val": "a", "next": "b"}, "b": {"val": "a", "next": "a"}})
    rc, out, _, _ = run(t)
    check("格的 stdout 原樣過、不影響 next", (rc, out, state(t)), (0, '{"next": "zzz"}\n', "b\n"))


@case
def cell_relative_paths_from_cwd(t):
    # 字串 val 與單子的相對路徑都從 cwd 算
    Path(t, "sub").mkdir()
    cell(t, "sub/c", "pwd > \"$AOS_STACK/pwd\"\n")
    st(t).mkdir()
    table(t, {"a": {"val": "sub/c", "next": "b"},
              "b": {"val": {"argv": ["pwd"], "cwd": "sub", "stdout": {"$env": "AOS_STACK", "$path": "pwd2"}}, "next": "a"}})
    run(t); run(t)
    real = os.path.realpath(t)
    check("相對路徑", ((st(t) / "pwd").read_text().strip(), (st(t) / "pwd2").read_text().strip()),
          (real + "/sub/c", real + "/sub"))


@case
def string_cell_path_as_is(t):
    # ideas § 24：aos 的程式都不動 PATH，字串格看到的 PATH 跟 fsm 收到的一樣（不加任何 bin）
    cell(t, "a", 'echo "$PATH" > "$AOS_STACK/path"\n')
    table(t, {"a": {"val": "a", "next": "a"}})
    st(t).mkdir()
    rc = run(t, env={"PATH": "/usr/bin:/bin"})[0]
    check("字串格 PATH 原樣", (rc, (st(t) / "path").read_text().strip()), (0, "/usr/bin:/bin"))


# ───────── C. 訊號 ─────────

def wait_file(path, secs=10):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if Path(path).exists():
            return True
        time.sleep(0.02)
    return False


@case
def sigterm_cell_finishes_then_143(t):
    # 格收到轉來的 SIGTERM 收好、退 0：trace 有一行、state 照樣換，fsm 再以 143 結束（P-36）
    cell(t, "a", 'trap \'exit 0\' TERM\ntouch "$AOS_STACK/up"\nwhile :; do sleep 0.05; done\n')
    table(t, {"a": {"val": "a", "next": "b"}, "b": {"val": "a", "next": "a"}})
    st(t).mkdir()
    p = subprocess.Popen([BIN, "fsm.json"], cwd=t, env=env_of(t, None), stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    ok = wait_file(st(t) / "up")
    p.send_signal(signal.SIGTERM)
    out, err = p.communicate(timeout=20)
    check("SIGTERM：收完 143、trace 與 state 寫完", (ok, p.returncode, err, state(t), trace(t)[0]["code"]),
          (True, 143, "", "b\n", 0))


@case
def sigint_inst_cell(t):
    st(t).mkdir()
    table(t, {"a": {"val": {"argv": ["sh", "-c", 'touch "$AOS_STACK/up"; exec sleep 30']}, "next": "a"}})
    p = subprocess.Popen([BIN, "fsm.json"], cwd=t, env=env_of(t, None), stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    ok = wait_file(st(t) / "up")
    p.send_signal(signal.SIGINT)
    out, err = p.communicate(timeout=20)
    x = trace(t)[0]
    # 單子由那格的 aos-exec 跑、它當監工：子程式被 SIGINT 停掉，aos-exec 以 130 結束（signal 不是 fsm 看到的，null）
    check("單子格被轉來的 SIGINT 停掉", (ok, p.returncode, x["code"], x["signal"], (st(t) / "state.txt").exists()),
          (True, 130, 130, None, False))


@case
def inst_ref_and_argv0(t):
    # 10-20 ideas D1、D3：單子裡 $ref 從 fsm.json 所在的資料夾算（cwd 在別處）；argv[0] 帶 / 又 exec 不了＝交給 PATH 上的 aos-exec
    q = Path(t, "q")
    put(q / "sub" / "data.json", {"a": {"b": ["echo", "deep"]}, "msg": "hi"})
    put(q / "tools" / "cfg.json", {"t": {"u": ["echo", "ptr"]}})
    st(t).mkdir()
    fj = str(q / "fsm.json")   # val 的相對路徑照 cwd、fsm 不轉，所以寫絕對路徑
    put(q / "fsm.json", {"start": "a", "states": {
        "a": {"val": fj + "#/states/a/body", "next": "b",
              "body": {"argv": [{"$ref": "sub/data.json#/a/b/0"}, {"$ref": "sub/data.json#/msg"}],
                       "stdout": {"$env": "AOS_STACK", "$path": "fout"}}},
        "b": {"val": fj + "#/states/b/body", "next": "a",
              "body": {"argv": ["tools/cfg.json#/t/u"], "cwd": str(q), "stdout": {"$env": "AOS_STACK", "$path": "fout2"}}}}})
    rc1 = run(t, str(q / "fsm.json"))[0]
    rc2 = run(t, str(q / "fsm.json"))[0]
    check("$ref 從 fsm.json 的資料夾、argv[0] 交給 aos-exec",
          (rc1, (st(t) / "fout").read_text(), rc2, (st(t) / "fout2").read_text()), (0, "hi\n", 0, "ptr\n"))


# ───────── D. 10-21 傍晚的命令列：`aos-fsm [旗標] 設定檔`、檔#/指標、val 陣列（ideas § 9；對照 proto8/tests/test_fsm.py）─────────

@case
def cli_usage(t):
    table(t, {"a": {"val": "a", "next": "a"}})
    for args, code in ((("fsm.json", "more"), "ArgumentsBad"), (("--cfg", "fsm.json"), "FlagUnknown"),
                       (("--x=1", "fsm.json"), "FlagUnknown")):
        r = subprocess.run([BIN, *args], capture_output=True, text=True, env=env_of(t, None), cwd=t, timeout=60)
        check("usage %r" % (args,), (r.returncode, r.stderr.startswith("aos-fsm: %s usage: aos-fsm [旗標] 設定檔.json（" % code)),
              (1, True))
    cell(t, "a", "exit 0\n")
    r = subprocess.run([BIN, "--", "fsm.json"], capture_output=True, text=True, env=env_of(t, None), cwd=t, timeout=60)
    check("-- 結束旗標", (r.returncode, state(t)), (0, "a\n"))


@case
def cli_config_pointer(t):
    cell(t, "a", "exit 0\n")
    put(Path(t, "agent.json"), {"_entry": ["aos-fsm", {"$env": "AOS_CF", "$path": "#/fsm"}],
                                "fsm": {"start": "a", "states": {"a": {"val": "a", "next": "z"}, "z": {"val": "a", "next": "a"}}}})
    rc = run(t, "agent.json#/fsm")[0]
    check("設定檔 檔#/指標", (rc, state(t)), (0, "z\n"))
    for spec, code in (("agent.json#/nope", "CfgMissing"), ("agent.json#fsm", "CfgBad")):
        check("設定檔 %s" % spec, run(t, spec)[:3:2], (1, code))


@case
def cell_val_array(t):
    cell(t, "a", 'echo "$*" > "$AOS_STACK/args"\n')
    table(t, {"a": {"val": ["a", "x y", "--z"], "next": "a"}})
    rc = run(t)[0]
    check("val 陣列＝[目標, 參數...]", (rc, (st(t) / "args").read_text()), (0, "x y --z\n"))


# ───────── E. 10-22：state 在但讀不了退 1、開跑時查整張表（ideas 10-22 § 7；對照 proto8/tests/test_fsm.py）─────────

def own_error_no_beat(t, name, r):
    rc, _, err, stderr = r
    check(name, (rc, err, len(stderr.splitlines()), (st(t) / "ran").exists(), (st(t) / "trace.jsonl").exists()),
          (1, err if err in ("StateBad", "CfgBad", "StateUnknown", "DirectiveBad") else "?", 1, False, False))
    return err


@case
def state_exists_but_unreadable(t):
    cell(t, "a", 'touch "$AOS_STACK/ran"\n')
    table(t, {"a": {"val": "a", "next": "b"}, "b": {"val": "a", "next": "a"}})
    sf = st(t) / "state.txt"
    sf.mkdir(parents=True)
    check("state 是資料夾", own_error_no_beat(t, "state 是資料夾：不跑", run(t)), "StateBad")
    sf.rmdir()
    sf.write_bytes(b"\xff\xfe\n")
    check("state 不是 UTF-8", own_error_no_beat(t, "state 不是 UTF-8：不跑", run(t)), "StateBad")
    check("state 不動", sf.read_bytes(), b"\xff\xfe\n")
    if os.geteuid() != 0:   # root 讀得到沒權限的檔
        sf.write_text("b\n")
        sf.chmod(0)
        try:
            check("state 沒權限", own_error_no_beat(t, "state 沒權限：不跑", run(t)), "StateBad")
        finally:
            sf.chmod(0o644)
    sf.write_text("zz\n")
    check("state 不在表上", own_error_no_beat(t, "state 不在表上：不跑", run(t)), "StateUnknown")
    sf.write_text("\u3000b\u3000\n")   # 去頭尾空白認 Unicode 空白（同 bin 的 str.strip()）
    rc = run(t)[0]
    check("state 去全形空白", (rc, state(t)), (0, "a\n"))
    sf.unlink()
    rc, _, _, stderr = run(t)
    check("沒有檔＝start", (rc, stderr, state(t)), (0, "", "b\n"))


@case
def whole_table_checked_before_beat(t):
    cell(t, "a", 'touch "$AOS_STACK/ran"\n')
    good = {"val": "a", "next": "a"}
    for what, start, states in (
            ("start 不在表上", "zz", {"a": good}),
            ("next 不在表上", "a", {"a": {"val": "a", "next": "nope"}}),
            ("別格 next 不在表上", "a", {"a": good, "b": {"val": "a", "next": "nope"}}),
            ("next 空字串", "a", {"a": {"val": "a", "next": ""}}),
            ("別格 next 空字串", "a", {"a": good, "b": {"val": "a", "next": ""}}),
            ("next 頭尾空白", "a", {"a": {"val": "a", "next": " a"}, " a": good}),
            ("next 頭尾全形空白", "a", {"a": {"val": "a", "next": "a\u3000"}, "a\u3000": good}),
            ("next 有換行", "a", {"a": {"val": "a", "next": "x\ny"}, "x\ny": good}),
            ("next 不是字串", "a", {"a": good, "b": {"val": "a", "next": 3}}),
            ("別格沒 next", "a", {"a": good, "b": {"val": "a"}}),
            ("別格不是物件", "a", {"a": good, "b": "a"}),
            ("別格 val 是物件", "a", {"a": good, "b": {"val": {"argv": ["true"]}, "next": "a"}}),
            ("別格 val 空陣列", "a", {"a": good, "b": {"val": [], "next": "a"}})):
        put(Path(t, "fsm.json"), {"start": start, "states": states})
        check("表壞 %s" % what, own_error_no_beat(t, "表壞 %s：不跑" % what, run(t)), "CfgBad")
    put(Path(t, "fsm.json"), {"start": "a", "states": {"a": good, "b": {"val": "a", "next": "a"}}})
    check("表好照跑", (run(t)[0], (st(t) / "ran").exists()), (0, True))


# ───────── E. fsm.json 的指示詞（10-23 晚，使用者「aos 讀的 JSON 全部支援」；N-45）─────────

@case
def table_directives(t):
    # fsm 讀的格（start、states、每一格、val、next）都解；相對 $ref 從 fsm.json 的資料夾算（cwd 在別處）
    cell(t, "a", 'echo a >> "$AOS_STACK/log"\n'); cell(t, "b", 'echo b >> "$AOS_STACK/log"\n')
    put(Path(t, "cfg", "states.json"), {"a": {"val": {"$env": "CELL_A"}, "next": {"$ref": "names.json#/1"}},
                                        "b": {"$ref": "b.json"}})
    put(Path(t, "cfg", "names.json"), ["a", "b"])
    put(Path(t, "cfg", "b.json"), {"val": "b", "next": "a"})
    put(Path(t, "cfg", "fsm.json"), {"start": {"$ref": "names.json#/0"}, "states": {"$ref": "states.json"}})
    r1 = run(t, "cfg/fsm.json", env={"CELL_A": "a"})
    r2 = run(t, "cfg/fsm.json", env={"CELL_A": "a"})
    check("start／states／格／val／next 的指示詞", (r1[0], r1[3], r2[0], (st(t) / "log").read_text(), state(t)),
          (0, "", 0, "a\nb\n", "a\n"))


@case
def table_directive_bad_is_own_error(t):
    cell(t, "a", 'touch "$AOS_STACK/ran"\n')
    put(Path(t, "fsm.json"), {"start": "a", "states": {"a": {"val": {"$env": "NOPE_XYZ"}, "next": "a"}}})
    check("val 的指示詞解不開＝自己的錯、不跑", own_error_no_beat(t, "解不開不跑", run(t)), "DirectiveBad")
    put(Path(t, "fsm.json"), {"start": "a", "states": {"$ref": "nope.json"}})
    check("states 的 $ref 讀不到", run(t)[2], "DirectiveBad")


@case
def table_body_not_resolved(t):
    # fsm 不讀格的 body：body 裡的 $env 沒設不擋開跑，是跑那格的 aos-exec 的錯（C-52）
    put(Path(t, "fsm.json"), {"start": "a", "states": {"a": {"val": "fsm.json#/states/a/body", "next": "a",
                                                               "body": {"argv": ["true"], "stdout": {"$env": "NOPE_XYZ"}}}}})
    rc, _, err, stderr = run(t)
    check("body 的指示詞留給那格", (rc, err, stderr.startswith("aos-exec: DirectiveBad ")), (1, None, True))


for fn in cases:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            fn(tmp)
        except Exception as e:   # 一組炸掉不擋後面的組
            failures += 1
            print("失敗 %s：例外 %r" % (fn.__name__, e))

print("%d 組、%d 個失敗" % (len(cases), failures))
sys.exit(1 if failures else 0)
