#!/usr/bin/env python3
"""test_cli.py：aos-exec 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-exec

每個案例一個空的暫存資料夾、環境先清掉 AOS_*；自己造小程式（不靠 demo）。
A 段從 proto8/tests/test_exec.py（sh 版）移植，行為應一致（錯誤格式也是「aos-exec: …」，多了代號）；B 段是 ideas 10-19 § 14～§ 19 的新規則；
C 段是 inst 單子（§ 20：aos-exec 行程內交給 libaos 跑、留在行程裡當監工）；D 段是 10-20 的指示詞與 argv；
E 段是 10-21 的命令列旗標、.env、入口順序、資料夾與 JSON 物件一路往下、AOS_CO（對照 proto8/tests/test_exec_rules.py、test_exec_env.py）。
A～D 段的 run(XXX, WS, args...) 已換成新命令列 `aos-exec --ws WS XXX args...`（見 run）。
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "bin",
                                                                          "aos-exec"))
BIN_DIR = os.path.dirname(BIN)
failures = 0
cases = []


def case(fn):
    cases.append(fn)
    return fn


def raw(*args, env=None, cwd=None, input=None):
    """跑 `aos-exec args...`，回 (退出碼, stdout, 錯誤代號或 None, stderr)。
    aos-exec 不動 PATH（ideas § 24），入口裡要叫 aos-exec 由呼叫者放：PATH 最前面放 aos-exec 的 bin/（env 可蓋掉）。"""
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = os.pathsep.join([BIN_DIR] + [p for p in e.get("PATH", "").split(os.pathsep) if p != BIN_DIR])
    e.update(env or {})
    r = subprocess.run([BIN, *args], capture_output=True, text=True, env=e, cwd=cwd, input=input)
    err = None
    if r.returncode == 1 and r.stderr.startswith("aos-exec: "):   # 自己的錯：一行「aos-exec: 代號 原因」
        if len(r.stderr.splitlines()) == 1:
            err = r.stderr[len("aos-exec: "):].split(" ", 1)[0]
    return r.returncode, r.stdout, err, r.stderr


def run(xxx, ws=None, *args, **kw):
    """A～D 段沿用的寫法：run(XXX, WS, args...)＝`aos-exec --ws WS XXX args...`（10-21 起命令列 `aos-exec [旗標...] XXX [args...]`，
    原 `aos-exec XXX [WS [args...]]`）；WS 省略（None）＝不給 --ws。"""
    flags = [] if ws is None else ["--ws", ws]
    return raw(*flags, xxx, *args, **kw)


def put(path, text, mode=0o644):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if isinstance(text, str) else json.dumps(text))
    p.chmod(mode)
    return str(p)


def prog(parent, name, body, entry="_exec"):
    """parent/name/entry：可執行的 sh 小程式。回資料夾路徑。"""
    put(Path(parent) / name / entry, "#!/bin/sh\n" + body, 0o755)
    return str(Path(parent) / name)


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


# ───────── A. 從 sh 版 test_exec.py 移植 ─────────

@case
def missing_entry(t):
    Path(t, "p").mkdir()
    rc, out, err, _ = run(str(Path(t, "p")), t)
    check("入口不存在", (rc, err), (1, "EntryMissing"))


@case
def json_only_argv(t):
    # sh 版的 _exec.json 單子案例；inst 單子要等 libaos，這裡用 argv 陣列
    put(Path(t, "p", "_exec.json"), ["sh", "-c", "echo $1:$AOS_WS; exit 5", "sh"])
    ws = Path(t, "ws"); ws.mkdir()
    rc, out, err, _ = run(str(Path(t, "p")), str(ws), "x")
    check("只有 _exec.json", (rc, out.strip()), (5, "x:%s" % ws.resolve()))


@case
def json_custom_entry_name(t):
    put(Path(t, "p", "main.json"), ["echo", "hi"])
    rc, out, _, _ = run(str(Path(t, "p")), t, env={"AOS_ENTRY": "main"})
    check("自訂 AOS_ENTRY 的 .json", (rc, out), (0, "hi\n"))


@case
def small_shell_wrapper(t):
    # 小殼 _exec 是可執行檔，優先於同名 .json；殼裡明指 _exec.json 照樣跑
    d = prog(t, "p", 'exec aos-exec _exec.json "$@"\n')
    put(Path(d, "_exec.json"), ["echo", "a"])
    rc, out, _, _ = run(d, t, "b")
    check("小殼 _exec＋_exec.json", (rc, out), (0, "a b\n"))


@case
def executable_preferred(t):
    d = prog(t, "p", "echo exe\n")
    put(Path(d, "_exec.json"), ["echo", "json"])
    check("可執行檔優先", run(d, t)[1], "exe\n")


@case
def ws_omitted_uses_cwd(t):
    d = prog(t, "p", 'echo "$AOS_WS"\n')
    ws = Path(t, "ws"); ws.mkdir()
    check("WS 省略用 cwd", run(d, cwd=str(ws))[1].strip(), str(ws.resolve()))


@case
def ws_dash_reuses_aos_ws(t):
    d = prog(t, "p", 'echo "$AOS_WS"\n')
    ws = Path(t, "ws"); ws.mkdir()
    other = Path(t, "other"); other.mkdir()
    for extra in ((), ("-",)):
        check("WS %r 沿用 AOS_WS" % (extra,), run(d, *extra, cwd=str(other), env={"AOS_WS": str(ws)})[1].strip(),
              str(ws))


@case
def dash_with_args(t):
    d = prog(t, "p", 'echo "$AOS_WS:$1"\n')
    ws = Path(t, "ws"); ws.mkdir()
    check("- 加 args", run(d, "-", "x", cwd=str(ws))[1].strip(), "%s:x" % ws.resolve())


@case
def ws_given_relative(t):
    d = prog(t, "p", 'echo "$AOS_WS"\n')
    ws = Path(t, "ws"); ws.mkdir()
    check("WS 給絕對路徑", run(d, str(ws), cwd=t)[1].strip(), str(ws.resolve()))
    check("WS 相對於 cwd", run("p", "ws", cwd=t)[1].strip(), str(ws.resolve()))


@case
def ws_missing(t):
    d = prog(t, "p", "echo hi\n")
    check("WS 不存在", run(d, str(Path(t, "nope")))[:3:2], (1, "WorkspaceMissing"))


@case
def args_passthrough(t):
    d = prog(t, "p", 'echo "$#:$1:$2"\n')
    check("args 透傳", run(d, t, "x", "--y")[1].strip(), "2:x:--y")


@case
def args_stdin_cwd_custom_entry(t):
    d = prog(t, "p", 'pwd; echo "$@"; cat\n', entry="main.sh")
    ws = Path(t, "ws"); ws.mkdir()
    out = run(d, str(ws), "a", "b", input="from stdin", env={"AOS_ENTRY": "main.sh"})[1]
    check("args＋stdin＋cwd＋自訂入口", out, "%s\na b\nfrom stdin" % Path(d).resolve())


@case
def nested_same_workspace(t):
    inner = prog(t, "outer/inner", 'echo "$AOS_WS" > "$AOS_WS/seen"\n')
    outer = prog(t, "outer", "aos-exec %s\n" % inner)
    ws = Path(t, "ws"); ws.mkdir()
    rc = run(outer, str(ws))[0]
    check("巢狀同一工作區", (rc, (ws / "seen").read_text().strip()), (0, str(ws)))


@case
def stack_default_and_override(t):
    d = prog(t, "p", 'echo "$AOS_STACK"\n')
    ws = Path(t, "ws"); ws.mkdir()
    check("AOS_STACK 預設", run(d, str(ws))[1].strip(), str(ws) + "/.aos/")
    check("AOS_STACK 預設建好", (ws / ".aos").is_dir(), True)
    mine = Path(t, "mystack")
    check("AOS_STACK 覆寫", run(d, str(ws), env={"AOS_STACK": str(mine)})[1].strip(), str(mine) + "/")
    check("AOS_STACK 覆寫建好", mine.is_dir(), True)
    check("AOS_STACK 相對於呼叫的 cwd", run(d, str(ws), cwd=t, env={"AOS_STACK": "rel"})[1].strip(), t + "/rel/")


@case
def nested_shares_stack(t):
    inner = prog(t, "outer/inner", 'echo "$AOS_STACK" > "$AOS_STACK/seen"\n')
    outer = prog(t, "outer", "aos-exec %s\n" % inner)
    ws = Path(t, "ws"); ws.mkdir()
    rc = run(outer, str(ws))[0]
    check("巢狀共用 stack", (rc, (ws / ".aos" / "seen").read_text().strip()), (0, str(ws) + "/.aos/"))


@case
def usage(t):
    rc, _, err, _ = raw()
    check("沒給 XXX", (rc, err), (1, "Usage"))


# ───────── B. ideas 10-19 § 14～§ 19 ─────────

@case
def json_array_without_x(t):
    put(Path(t, "p", "_exec"), ["sh", "-c", "echo $1", "sh"])     # 沒 +x、內容是 JSON 陣列
    check("沒 +x 的 JSON 陣列", run(str(Path(t, "p")), t, "hi")[:2], (0, "hi\n"))


@case
def shebang_json_array(t):
    put(Path(t, "p", "_exec"), '#!/usr/bin/env aos-exec\n["echo", "sb"]\n')
    check("第一行 #! 跳過", run(str(Path(t, "p")), t)[:2], (0, "sb\n"))


@case
def not_x_not_json(t):
    put(Path(t, "p", "_exec"), "echo hi\n")
    check("沒 +x、不是 JSON", run(str(Path(t, "p")), t)[:3:2], (1, "EntryBad"))


@case
def x_without_shebang(t):
    # § 22：+x 沒 #! 同 execvp 改用 /bin/sh 跑（$0＝那個檔）
    put(Path(t, "p", "_exec"), 'echo "hi:$1:$0"\n', 0o755)
    check("+x 沒 #! 交給 sh", run(str(Path(t, "p")), t, "a")[:2],
          (0, "hi:a:%s\n" % Path(t, "p", "_exec").resolve()))


@case
def argv_command_missing(t):
    check("argv 陣列指令不在", run_with_json(t, ["no-such-cmd-xyz"])[:3:2], (1, "LaunchFailed"))


@case
def argv_sh_fallback(t):
    # § 22：argv 陣列走 glibc execvp：+x 但沒 #! 的檔改用 /bin/sh 跑（有 / 的、照 PATH 找到的都是）
    put(Path(t, "q", "noshebang"), 'echo "hi:$1"\n', 0o755)
    check("argv 陣列 ./沒 #! 的檔", run_with_json(t, ["./noshebang"], "a")[:2], (0, "hi:a\n"))
    tools = Path(t, "tools")
    put(tools / "mytool", 'echo "my:$1"\n', 0o755)
    put(tools / "good", "#!/bin/sh\necho good:$1\n", 0o755)
    put(tools / "nox", "#!/bin/sh\necho nox\n", 0o644)
    path = {"PATH": "%s:/usr/bin:/bin" % tools}
    put(Path(t, "q", "_exec.json"), ["mytool"])
    check("argv 陣列照 PATH 找到沒 #! 的檔", run(str(Path(t, "q")), t, "b", env=path)[:2], (0, "my:b\n"))
    put(Path(t, "q", "_exec.json"), ["good"])
    check("argv 陣列照 PATH 找到有 #! 的檔", run(str(Path(t, "q")), t, "x", env=path)[:2], (0, "good:x\n"))
    put(Path(t, "q", "_exec.json"), ["nox"])
    check("argv 陣列照 PATH 找到沒 +x 的檔", run(str(Path(t, "q")), t, env=path)[:3:2], (1, "LaunchFailed"))
    # PATH 裡同名的：前面那段沒 +x、後面那段有 → 用後面的（同 execvp）
    later = Path(t, "later")
    put(later / "nox", "#!/bin/sh\necho later\n", 0o755)
    env = {"PATH": "%s:%s:/usr/bin:/bin" % (tools, later)}
    check("PATH 前段沒 +x 就換下一段", run(str(Path(t, "q")), t, env=env)[:2], (0, "later\n"))


@case
def exec_replaces_process(t):
    # 可執行檔、argv 陣列都是 exec：入口的 $$ 就是 aos-exec 的 pid（不留監工）
    d = prog(t, "p", 'echo $$\n')
    put(Path(t, "q", "_exec.json"), ["sh", "-c", "echo $$"])
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    for path in (d, str(Path(t, "q"))):
        p = subprocess.Popen([BIN, path, t], stdout=subprocess.PIPE, text=True, env=e)
        out = p.communicate()[0]
        check("exec 不留行程 %s" % path, out.strip(), str(p.pid))


def run_with_json(t, doc, *args):
    put(Path(t, "q", "_exec.json"), doc)
    return run(str(Path(t, "q")), t, *args)


@case
def loop_config_is_not_entry(t):
    check("{run,max} 不是入口", run_with_json(t, {"run": "x", "max": 3})[:3:2], (1, "EntryBad"))


@case
def json_exec_key(t):
    check("_exec 是陣列", run_with_json(t, {"_exec": ["sh", "-c", "echo hi"]})[:2], (0, "hi\n"))
    # 10-21 晚起一路往下（原「只往下一層」撤回，ideas 10-21 § 6）
    check("_exec 是物件沒 argv＝一路往下", run_with_json(t, {"_exec": {"_exec": ["echo", "deep"]}})[:2], (0, "deep\n"))
    check("一路往下取不到 _exec", run_with_json(t, {"_exec": {"x": ["true"]}})[:3:2], (1, "EntryBad"))
    check("_exec 是數字", run_with_json(t, {"_exec": 3})[:3:2], (1, "EntryBad"))
    check("頂層是數字", run_with_json(t, 3)[:3:2], (1, "EntryBad"))
    check("空陣列", run_with_json(t, [])[:3:2], (1, "EntryBad"))
    check("陣列有非字串", run_with_json(t, ["echo", 1])[:3:2], (1, "EntryBad"))
    put(Path(t, "r", "main.json"), {"main": ["echo", "m"], "_exec": ["echo", "no"]})
    check("自訂 AOS_ENTRY 也用在 JSON 裡", run(str(Path(t, "r")), t, env={"AOS_ENTRY": "main"})[:2], (0, "m\n"))


@case
def string_redirect(t):
    prog(t, "a/sub", "echo sub:$1\n")
    put(Path(t, "a", "_exec.json"), {"_exec": "sub"})
    check("字串轉向資料夾", run(str(Path(t, "a")), t, "x")[:2], (0, "sub:x\n"))
    put(Path(t, "b", "tool.json"), ["sh", "-c", "pwd"])
    put(Path(t, "b", "_exec.json"), {"_exec": "tool.json"})
    check("字串轉向檔", run(str(Path(t, "b")), t)[:2], (0, str(Path(t, "b").resolve()) + "\n"))
    put(Path(t, "c", "tool.json"), ["echo", "補"])
    put(Path(t, "c", "_exec.json"), {"_exec": "tool"})
    check("字串轉向補 .json", run(str(Path(t, "c")), t)[:2], (0, "補\n"))
    # 轉向後相對路徑從「寫著它的檔」所在的資料夾算
    put(Path(t, "d", "x", "y.json"), {"_exec": "../z.json"})
    put(Path(t, "d", "z.json"), ["echo", "z"])
    check("轉向相對路徑從檔所在資料夾算", run(str(Path(t, "d", "x", "y.json")), t)[:2], (0, "z\n"))


@case
def string_redirect_loop(t):
    put(Path(t, "a.json"), {"_exec": "b.json"})
    put(Path(t, "b.json"), {"_exec": "a.json"})
    rc, _, err, stderr = run(str(Path(t, "a.json")), t)
    check("轉向繞圈", (rc, err, "→" in stderr), (1, "EntryBad", True))
    put(Path(t, "s", "_exec.json"), {"_exec": "."})
    check("轉向回自己的資料夾", run(str(Path(t, "s")), t)[:3:2], (1, "EntryBad"))


@case
def json_completion(t):
    put(Path(t, "prog.json"), ["echo", "p"])
    check("沒副檔名補 .json", run("prog", t, cwd=t)[:2], (0, "p\n"))
    put(Path(t, "prog.txt.json"), ["echo", "no"])
    check("有副檔名不補", run("prog.txt", t, cwd=t)[:3:2], (1, "EntryMissing"))


@case
def file_spec_cd(t):
    put(Path(t, "dir", "x.json"), ["sh", "-c", "pwd"])
    check("XXX 是檔就 cd 到它所在的資料夾", run("dir/x.json", t, cwd=t)[:2], (0, str(Path(t, "dir").resolve()) + "\n"))


@case
def pointer(t):
    put(Path(t, "cfg.json"), {"tools": {"stamp": ["echo", "st"], "deep": {"_exec": ["echo", "dp"]}}, "a/b": ["echo", "esc"]})
    check("#/ 指標", run("cfg.json#/tools/stamp", t, cwd=t)[:2], (0, "st\n"))
    check("#/ 指到物件再找 _exec", run("cfg.json#/tools/deep", t, cwd=t)[:2], (0, "dp\n"))
    check("#/ ~1 跳脫", run("cfg.json#/a~1b", t, cwd=t)[:2], (0, "esc\n"))
    check("沒副檔名補 .json 再加指標", run("cfg#/tools/stamp", t, cwd=t)[:2], (0, "st\n"))
    check("# 後沒 /", run("cfg.json#tools", t, cwd=t)[:3:2], (1, "EntryBad"))
    check("檔#", run("cfg.json#", t, cwd=t)[:3:2], (1, "EntryBad"))
    check("指不到", run("cfg.json#/nope", t, cwd=t)[:3:2], (1, "EntryMissing"))
    prog(t, "p", "echo hi\n")
    check("可執行檔帶 #/", run("p/_exec#/x", t, cwd=t)[:3:2], (1, "EntryBad"))
    check("資料夾帶 #/", run("p#/x", t, cwd=t)[:3:2], (1, "EntryBad"))
    put(Path(t, "r.json"), {"_exec": "cfg.json#/tools/stamp"})
    check("轉向字串帶 #/", run("r.json", t, cwd=t)[:2], (0, "st\n"))


@case
def cf_cd(t):
    d = prog(t, "p", 'echo "$AOS_CF|$AOS_CD|$(pwd)"\n')
    real = Path(d).resolve()
    check("AOS_CF／AOS_CD", run(d, t)[1].strip(), "%s/_exec|%s|%s" % (real, real, real))
    # 由 _exec.json 進來時 AOS_CF＝那個 .json
    put(Path(t, "j", "_exec.json"), ["sh", "-c", 'echo "$AOS_CF|$AOS_CD"'])
    rj = Path(t, "j").resolve()
    check("AOS_CF＝.json", run(str(Path(t, "j")), t)[1].strip(), "%s/_exec.json|%s" % (rj, rj))
    # 字串轉向後＝最後那個檔
    put(Path(t, "k", "_exec.json"), {"_exec": "sub/t.json"})
    put(Path(t, "k", "sub", "t.json"), ["sh", "-c", 'echo "$AOS_CF|$AOS_CD"'])
    rk = Path(t, "k", "sub").resolve()
    check("轉向後 AOS_CF", run(str(Path(t, "k")), t)[1].strip(), "%s/t.json|%s" % (rk, rk))
    # 捷徑：AOS_CF 是解開後的實際檔
    os.symlink(str(Path(t, "j")), str(Path(t, "link")))
    check("捷徑解開", run(str(Path(t, "link")), t)[1].strip(), "%s/_exec.json|%s" % (rj, rj))


@case
def cf_nested(t):
    inner = prog(t, "outer/inner", 'echo "in:$AOS_CF"\n')
    outer = prog(t, "outer", 'echo "out:$AOS_CF"; aos-exec inner; echo "out:$AOS_CF"\n')
    ro = Path(outer).resolve()
    rc, out, _, _ = run(outer, t)
    check("巢狀各層看到自己的 AOS_CF", (rc, out.split()),
          (0, ["out:%s/_exec" % ro, "in:%s/_exec" % Path(inner).resolve(), "out:%s/_exec" % ro]))


@case
def path_passed_as_is(t):
    # ideas § 24：aos 的程式都不動 PATH，原樣傳下去（不加自己的 bin）
    d = prog(t, "p", 'echo "$PATH"\n')
    for path in (BIN_DIR + ":/usr/bin:/bin", "/usr/bin:/bin"):
        check("PATH 原樣 %s" % path, run(d, t, env={"PATH": path})[1].strip(), path)


@case
def entry_is_dir(t):
    # 10-21 晚起 $AOS_ENTRY 指到資料夾＝走進去（資料夾贏過同名 .json，N-61）；裡面沒有入口＝EntryMissing
    Path(t, "p", "_exec").mkdir(parents=True)
    put(Path(t, "p", "_exec.json"), ["echo", "no"])
    check("AOS_ENTRY 指到資料夾、裡面沒入口", run(str(Path(t, "p")), t)[:3:2], (1, "EntryMissing"))
    put(Path(t, "p", "_exec", "_exec"), "#!/bin/sh\necho in\n", 0o755)
    check("AOS_ENTRY 指到資料夾＝走進去", run(str(Path(t, "p")), t)[:2], (0, "in\n"))


# ───────── C. inst 單子（§ 20：行程內交給 libaos 跑）─────────

def inst(t, doc, *args, **kw):
    """t/q/_exec.json＝doc，跑 aos-exec t/q t args…；回 run 的結果。"""
    put(Path(t, "q", "_exec.json"), doc)
    return run(str(Path(t, "q")), t, *args, **kw)


@case
def inst_exit_code(t):
    check("單子結束碼 3", inst(t, {"argv": ["sh", "-c", "exit 3"]})[:3:2], (3, None))
    check("單子結束碼 10", inst(t, {"argv": ["sh", "-c", "exit 10"]})[0], 10)
    check("單子被 SIGTERM＝143", inst(t, {"argv": ["sh", "-c", "kill -TERM $$"]})[0], 143)
    check("單子結束碼 0", inst(t, {"argv": ["true"]})[0], 0)


@case
def inst_only_json(t):
    # sh 版 test_exec.py 的「只有 _exec.json」：單子、args 接尾、AOS_WS
    ws = Path(t, "ws"); ws.mkdir()
    put(Path(t, "p", "_exec.json"), {"argv": ["sh", "-c", "echo $1:$AOS_WS; exit 5", "sh"]})
    rc, out, _, _ = run(str(Path(t, "p")), str(ws), "x")
    check("只有 _exec.json（單子）", (rc, out.strip()), (5, "x:%s" % ws.resolve()))


@case
def inst_stays_as_supervisor(t):
    # 跟 B 的「exec 不留行程」成對：單子入口的 $$ 不是 aos-exec 的 pid（aos-exec 留在行程裡當監工）
    put(Path(t, "q", "_exec.json"), {"argv": ["sh", "-c", "echo $$"]})
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    p = subprocess.Popen([BIN, str(Path(t, "q")), t], stdout=subprocess.PIPE, text=True, env=e)
    out = p.communicate()[0]
    check("單子留監工", (p.returncode, out.strip() != str(p.pid), out.strip().isdigit()), (0, True, True))


@case
def inst_shebang_not_x(t):
    # 沒 +x、第一行 #!/usr/bin/env aos-inst、底下是單子 → 第一行跳過、照跑（舊 P-28 (A) 拿掉 +x 的樣子）
    put(Path(t, "p", "_exec"), '#!/usr/bin/env aos-inst\n{"argv": ["echo", "sb"]}\n')
    check("shebang 開頭的非 +x 單子", run(str(Path(t, "p")), t, "x")[:2], (0, "sb x\n"))


@case
def inst_args_pointer_key(t):
    check("單子 args 接尾", inst(t, {"argv": ["echo", "a"]}, "b", "c")[:2], (0, "a b c\n"))
    put(Path(t, "cfg.json"), {"tools": {"stamp": {"argv": ["echo", "st"]}}})
    check("#/ 指到單子", run("cfg.json#/tools/stamp", t, "x", cwd=t)[:2], (0, "st x\n"))
    check("_exec 是單子", inst(t, {"_exec": {"argv": ["echo", "in"]}})[:2], (0, "in\n"))
    put(Path(t, "r.json"), {"_exec": "cfg.json#/tools/stamp"})
    check("字串轉向到單子", run("r.json", t, cwd=t)[:2], (0, "st\n"))


@case
def inst_streams(t):
    check("stdin／stdout 接呼叫者的", inst(t, {"argv": ["cat"]}, input="hi\n")[:2], (0, "hi\n"))
    rc, _, _, stderr = inst(t, {"argv": ["sh", "-c", "echo oops >&2"]})
    check("stderr 接呼叫者的", (rc, stderr), (0, "oops\n"))
    q = Path(t, "q")
    check("stdout 寫檔", (inst(t, {"argv": ["echo", "f"], "stdout": "out.txt"})[:2], (q / "out.txt").read_text()),
          ((0, ""), "f\n"))
    inst(t, {"argv": ["echo", "g"], "stdout": "out.txt", "stdout_append": True})
    check("stdout_append", (q / "out.txt").read_text(), "f\ng\n")
    put(q / "in.txt", "from file\n")
    check("stdin 讀檔", inst(t, {"argv": ["cat"], "stdin": "in.txt"}, input="ignored")[:2], (0, "from file\n"))
    inst(t, {"argv": ["sh", "-c", "echo e >&2"], "stderr": "err.txt"})
    check("stderr 寫檔", (q / "err.txt").read_text(), "e\n")
    Path(t, "q", "sub").mkdir()
    inst(t, {"argv": ["sh", "-c", "pwd"], "cwd": "sub", "stdout": "o.txt"})
    check("cwd 從入口資料夾算、串流從 cwd 算", (q / "sub" / "o.txt").read_text().strip(), str((q / "sub").resolve()))
    check("envs 疊在現有環境上", inst(t, {"argv": ["sh", "-c", "echo $A:$AOS_WS"], "envs": {"A": "1"}})[:2],
          (0, "1:%s\n" % Path(t).resolve()))


@case
def inst_env_directive(t):
    ws = Path(t).resolve()
    inst(t, {"argv": ["echo", "s"], "stdout": {"$env": "AOS_STACK", "$path": "out"}})
    check("$env＋path 寫到 $AOS_STACK/out", (ws / ".aos" / "out").read_text(), "s\n")
    rc, out, _, _ = inst(t, {"argv": ["echo", {"$env": "AOS_CD"}, {"$env": "AOS_CF"}]})
    q = Path(t, "q").resolve()
    check("$env 讀得到 AOS_CD／AOS_CF", (rc, out), (0, "%s %s/_exec.json\n" % (q, q)))
    check("$env 沒設", inst(t, {"argv": ["echo", {"$env": "AOS_NOPE_XYZ"}]})[:3:2], (1, "DirectiveBad"))


@case
def inst_timeout_kills_group(t):
    import time
    rc = inst(t, {"argv": ["sh", "-c", "sleep 100 & echo $! > pid; wait"], "timeout_ms": 200})[0]
    pid = int(Path(t, "q", "pid").read_text())
    time.sleep(0.1)
    alive = True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        alive = False
    if alive:
        os.kill(pid, 9)
    check("逾時整群殺", (rc, alive), (143, False))


def start(t, doc):
    put(Path(t, "q", "_exec.json"), doc)
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    return subprocess.Popen([BIN, str(Path(t, "q")), t], stdout=subprocess.PIPE, text=True, env=e)


@case
def inst_signal_forward(t):
    import signal
    import time
    p = start(t, {"argv": ["sh", "-c", "sleep 100 & echo $! > pid; wait"]})
    pidfile = Path(t, "q", "pid")
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text().strip():
            break
        time.sleep(0.02)
    p.send_signal(signal.SIGTERM)
    try:
        rc = p.wait(timeout=2)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = "還沒結束"
    pid = int(pidfile.read_text())
    time.sleep(0.1)
    alive = True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        alive = False
    if alive:
        os.kill(pid, 9)
    check("SIGTERM 轉給整群", (rc, alive), (143, False))

    p = start(t, {"argv": ["sh", "-c", "trap '' TERM; echo ok > ready; while :; do sleep 0.05; done"],
                  "grace_ms": 200})
    ready = Path(t, "q", "ready")
    for _ in range(100):
        if ready.exists():
            break
        time.sleep(0.02)
    t0 = time.monotonic()
    p.send_signal(signal.SIGTERM)
    try:
        rc = p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = "還沒結束"
    check("不理 SIGTERM 就過 grace_ms 被 SIGKILL", (rc, time.monotonic() - t0 < 2), (137, True))


@case
def inst_bad(t):
    put(Path(t, "q", "_exec"), "{not json")
    check("單子檔不是 JSON", run(str(Path(t, "q")), t)[:3:2], (1, "EntryBad"))
    import shutil
    shutil.rmtree(str(Path(t, "q")))
    check("argv 空", inst(t, {"argv": []})[:3:2], (1, "EntryBad"))
    check("argv 有非字串", inst(t, {"argv": ["echo", 1]})[:3:2], (1, "EntryBad"))
    check("timeout_ms 是字串", inst(t, {"argv": ["true"], "timeout_ms": "5"})[:3:2], (1, "EntryBad"))
    check("timeout_ms 是 0", inst(t, {"argv": ["true"], "timeout_ms": 0})[:3:2], (1, "EntryBad"))
    check("grace_ms 負的", inst(t, {"argv": ["true"], "grace_ms": -1})[:3:2], (1, "EntryBad"))
    check("stdout 是數字", inst(t, {"argv": ["true"], "stdout": 3})[:3:2], (1, "EntryBad"))
    check("envs 值不是字串", inst(t, {"argv": ["true"], "envs": {"A": 1}})[:3:2], (1, "EntryBad"))
    check("stdout_append 不是 bool", inst(t, {"argv": ["true"], "stdout_append": 1})[:3:2], (1, "EntryBad"))
    rc, _, err, stderr = inst(t, {"argv": ["no-such-cmd-xyz"]})
    check("argv[0] 不存在", (rc, err, "CommandNotFound" in stderr), (1, "LaunchFailed", True))
    rc, _, err, stderr = inst(t, {"argv": ["true"], "cwd": "nope"})
    check("cwd 不存在", (rc, err, "CwdMissing" in stderr), (1, "LaunchFailed", True))
    rc, _, err, stderr = inst(t, {"argv": ["true"], "stdout": "nodir/x"})
    check("串流開不了", (rc, err, "OpenFailed" in stderr), (1, "LaunchFailed", True))


@case
def inst_extra_keys_ignored(t):
    # 10-19 的單子只認 10 個 key；impls/aos-inst 認得的 stderr_merge、cwd_mkdir 等在這裡跟不認得的 key 一樣被忽略
    rc, out, _, stderr = inst(t, {"argv": ["sh", "-c", "echo o; echo e >&2"], "stderr_merge": True, "id": 3})
    check("stderr_merge 被忽略（不合併）", (rc, out, stderr), (0, "o\n", "e\n"))
    rc, _, err, _ = inst(t, {"argv": ["true"], "cwd": "made", "cwd_mkdir": True})
    check("cwd_mkdir 被忽略（cwd 不在就 LaunchFailed）", (rc, err, Path(t, "q", "made").exists()),
          (1, "LaunchFailed", False))



# ───────── D. 10-20 指示詞與 argv（ideas 2026-10-20 D1～D15；對照 proto8/tests/test_directive_argv.py、test_directive_lenient.py）─────────

def dq(t):
    """t/q/sub/data.json：共用的 $ref 目標。"""
    put(Path(t, "q", "sub", "data.json"), {"a": {"b": ["echo", "deep"], "w": "word"}, "msg": "hi", "s~/x": "esc"})


def tools(t):
    q = Path(t, "q")
    put(q / "tools" / "stamp" / "_exec", '#!/bin/sh\necho "stamp ws=$AOS_WS cf=$AOS_CF arg=$1"\n', 0o755)
    put(q / "tools" / "j.json", ["sh", "-c", 'echo "json cf=$AOS_CF"'])
    put(q / "tools" / "cfg.json", {"t": {"u": ["echo", "ptr"]}})
    put(q / "tools" / "x.sh", '#!/bin/sh\necho "x cf=$AOS_CF"\n', 0o755)


@case
def d1_ref_pointer_and_at(t):
    dq(t)
    check("D1 #/ 指標", inst(t, {"argv": ["echo", {"$ref": "sub/data.json#/a/w"}, {"$ref": "sub/data.json#/s~0~1x"}]})[:2],
          (0, "word esc\n"))
    check("D1 at", inst(t, {"argv": {"$ref": "sub/data.json", "at": "/a/b"}})[:2], (0, "deep\n"))
    check("D7 #/ 再接 at", inst(t, {"argv": {"$ref": "sub/data.json#/a", "at": "/b"}})[:2], (0, "deep\n"))
    check("D7 #/ 再接 at（元素）", inst(t, {"argv": ["echo", {"$ref": "sub/data.json#/a/b", "at": "/1"}]})[:2],
          (0, "deep\n"))
    check("讀不到", inst(t, {"argv": ["echo", {"$ref": "sub/nope.json"}]})[:3:2], (1, "DirectiveBad"))
    check("指不到", inst(t, {"argv": ["echo", {"$ref": "sub/data.json#/zz"}]})[:3:2], (1, "DirectiveBad"))
    put(Path(t, "q", "loop1.json"), {"x": {"$ref": "loop2.json"}})
    put(Path(t, "q", "loop2.json"), {"$ref": "loop1.json#/x"})
    rc, _, err, stderr = inst(t, {"argv": ["echo", {"$ref": "loop1.json#/x"}]})
    check("繞圈", (rc, err, "繞圈" in stderr), (1, "DirectiveBad", True))
    check("有 $ref 只看 $ref", inst(t, {"argv": ["echo", {"$ref": "sub/data.json#/msg", "$env": "AOS_NOPE_XYZ"}]})[:2],
          (0, "hi\n"))
    check("at 空字串＝物件、單子 argv 不是字串", inst(t, {"argv": ["echo", {"$ref": "sub/data.json#/a", "at": ""}]})[:3:2],
          (1, "EntryBad"))


@case
def d2_d8_argv_array_directives(t):
    dq(t)
    q = Path(t, "q").resolve()
    ws = Path(t).resolve()
    check("D2 argv 陣列 $env＋$path", run_with_json(t, ["sh", "-c", 'echo "$1"', "sh", {"$env": "AOS_CD", "$path": "x"}])[:2],
          (0, "%s/x\n" % q))
    check("D2 _exec 底下的陣列", run_with_json(t, {"_exec": ["echo", {"$env": "AOS_WS"}]})[:2], (0, "%s\n" % ws))
    check("D8 argv 陣列 $ref", run_with_json(t, [{"$ref": "sub/data.json#/a/b/0"}, {"$ref": "sub/data.json", "at": "/msg"}],
                                             "tail")[:2], (0, "hi tail\n"))
    check("$env 沒設＝入口壞", run_with_json(t, ["echo", {"$env": "AOS_NOPE_XYZ"}])[:3:2], (1, "EntryBad"))
    check("解出來不是字串＝入口壞", run_with_json(t, ["echo", {"$ref": "sub/data.json#/a"}])[:3:2], (1, "EntryBad"))
    check("讀不到＝入口壞", run_with_json(t, ["echo", {"$ref": "sub/nope.json"}])[:3:2], (1, "EntryBad"))
    check("普通物件＝入口壞", run_with_json(t, ["echo", {"k": 1}])[:3:2], (1, "EntryBad"))
    check("數字＝入口壞", run_with_json(t, ["echo", 1])[:3:2], (1, "EntryBad"))
    check("寫法不合留著＝入口壞", run_with_json(t, ["echo", {"$env": 3}])[:3:2], (1, "EntryBad"))
    check("$path＋$prefix", run_with_json(t, ["echo", {"$env": "AOS_WS", "$path": "a.txt", "$prefix": "--file="}])[:2],
          (0, "--file=%s/a.txt\n" % ws))
    check("單子：$fmt 不管、$prefix", inst(t, {"argv": ["echo", {"$env": "AOS_WS", "$fmt": "%s", "$prefix": "w="}]})[:2],
          (0, "w=%s\n" % ws))


@case
def d3_argv0_to_aos_exec(t):
    tools(t)
    q = Path(t, "q").resolve()
    ws = Path(t).resolve()
    stamp = q / "tools" / "stamp" / "_exec"
    check("D3 陣列：資料夾", run_with_json(t, ["tools/stamp"])[:2], (0, "stamp ws=%s cf=%s arg=\n" % (ws, stamp)))
    check("D3 陣列：沒 +x 的 JSON 檔", run_with_json(t, ["tools/j.json"])[:2], (0, "json cf=%s\n" % (q / "tools" / "j.json")))
    check("D3 陣列：不在（補找 .json）", run_with_json(t, ["tools/j"])[0], 0)
    check("D3 陣列：帶 #/", run_with_json(t, ["tools/cfg.json#/t/u"])[:2], (0, "ptr\n"))
    check("D3 +x 檔照舊直接 exec", run_with_json(t, ["tools/x.sh"])[:2], (0, "x cf=%s\n" % (q / "_exec.json")))
    other = Path(t, "other"); other.mkdir()
    # 10-21 起插進去的 aos-exec 後面接的是 args（工作區只由 --ws 給）
    rc, out, _, _ = run_with_json(t, ["tools/stamp", "a"])
    check("D5 第二個是 args", (rc, ("ws=%s " % ws) in out, out.endswith("arg=a\n")), (0, True, True))
    rc, out, _, _ = run_with_json(t, ["aos-exec", "--ws", str(other), "tools/stamp", "a"])
    check("D5 換工作區寫 --ws", (rc, ("ws=%s " % other.resolve()) in out, out.endswith("arg=a\n")), (0, True, True))
    rc, out, _, _ = run_with_json(t, ["tools/stamp"], "b")
    check("D5 呼叫時的 args 接在後面", (rc, out.endswith("arg=b\n")), (0, True))
    put(q / "stampdir" / "_exec", "#!/bin/sh\necho no\n", 0o755)
    check("D4 沒 / 照 PATH 找", run_with_json(t, ["stampdir"])[:3:2], (1, "LaunchFailed"))
    check("D4 單子沒 / 照 PATH 找", inst(t, {"argv": ["stampdir"]})[0], 1)
    check("D3 單子", inst(t, {"argv": ["tools/stamp", "a"]})[:2], (0, "stamp ws=%s cf=%s arg=a\n" % (ws, stamp)))
    check("D3 單子 cwd 另給、帶 #/", inst(t, {"argv": ["./tools/cfg.json#/t/u"], "cwd": str(q)})[:2], (0, "ptr\n"))
    rc, _, err, stderr = inst(t, {"argv": ["tools/stamp"]}, env={"PATH": "/usr/bin:/bin"})
    check("D3 PATH 上沒 aos-exec", (rc, err, "aos-exec" in stderr), (1, "LaunchFailed", True))


# ───────── E. 10-21：命令列旗標、.env、入口順序、一路往下、AOS_CO（對照 proto8/tests/test_exec_rules.py、test_exec_env.py）─────────

@case
def e_flags(t):
    d = prog(t, "p", 'echo "$AOS_WS|$*"\n')
    ws = Path(t, "ws"); ws.mkdir()
    rws = ws.resolve()
    check("--ws WS", raw("--ws", str(ws), d, "a")[:2], (0, "%s|a\n" % rws))
    check("--ws=WS", raw("--ws=%s" % ws, d, "a")[:2], (0, "%s|a\n" % rws))
    check("重複給最後一個算", raw("--ws", "/nope", "--ws", str(ws), d)[:2], (0, "%s|\n" % rws))
    check("--ws 蓋過 $AOS_WS", raw("--ws", str(ws), d, env={"AOS_WS": t})[:2], (0, "%s|\n" % rws))
    check("--ws - 沿用 $AOS_WS", raw("--ws", "-", d, env={"AOS_WS": str(ws)})[:2], (0, "%s|\n" % rws))
    check("--ws= 空＝沿用", raw("--ws=", d, env={"AOS_WS": str(ws)})[:2], (0, "%s|\n" % rws))
    check("XXX 之後不解析旗標", raw("--ws", str(ws), d, "--ws", "x")[:2], (0, "%s|--ws x\n" % rws))
    check("舊的位置 WS 變成 args", raw(d, str(ws), cwd=t)[:2], (0, "%s|%s\n" % (Path(t).resolve(), ws)))
    prog(t, "-dash", "echo dash\n")
    check("-- 結束旗標", raw("--", "-dash", cwd=t)[:2], (0, "dash\n"))
    check("不認得的旗標", raw("--nope", "x", d)[:3:2], (1, "Usage"))
    check("旗標缺值", raw("--ws")[:3:2], (1, "Usage"))
    check("只有旗標沒有 XXX", raw("--ws", str(ws))[:3:2], (1, "Usage"))
    rc, _, _, stderr = raw("--nope")
    check("usage 一行", stderr.startswith("aos-exec: Usage usage: aos-exec [--ws WS] [--dotenv-override] XXX [args...]"), True)


@case
def e_dotenv_basic(t):
    d = prog(t, "p", 'echo "$A|$B|$C|${D-unset}"\n')
    put(Path(d, ".env"), "# 註解\n\n  A=1\nB=${A}2\r\nC=x=y $HOME\n")
    check(".env 逐行、展開 ${名字}、= 只切第一個", raw("--ws", t, d)[:2], (0, "1|12|x=y $HOME|unset\n"))
    e = prog(t, "e", 'echo "${A-unset}"\n')
    check("沒有 .env", raw("--ws", t, e)[:2], (0, "unset\n"))


@case
def e_dotenv_priority(t):
    a, b, c = (Path(t, n) for n in "abc")
    for x in (a, b, c):
        x.mkdir()
    d = prog(t, "p", 'echo "$AOS_WS"\n')
    put(Path(d, ".env"), "AOS_WS=%s\n" % b)
    check("旗標 ＞ .env", raw("--ws", str(a), d, env={"AOS_WS": str(c)})[1], "%s\n" % a.resolve())
    # 10-22 起 .env 預設不蓋已有的：AOS_WS 讀 .env 前已 export，要 --dotenv-override 才改得了
    check(".env 不蓋外面（預設）", raw(d, env={"AOS_WS": str(c)})[1], "%s\n" % c.resolve())
    check("--dotenv-override：.env ＞ 外面", raw("--dotenv-override", d, env={"AOS_WS": str(c)})[1], "%s\n" % b)
    check("--dotenv-override 仍是旗標 ＞ .env", raw("--dotenv-override", "--ws", str(a), d)[1], "%s\n" % a.resolve())


@case
def e_dotenv_errors(t):
    d = prog(t, "p", "echo no\n")
    put(Path(d, ".env"), "A=1\nB=${NOPE_XYZ}SECRET\n")
    rc, out, err, stderr = raw("--ws", t, d)
    check(".env ${} 沒設", (rc, out, err, "第 2 行" in stderr, "SECRET" in stderr), (1, "", "EnvBad", True, False))
    for text in ("SECRET\n", "1A=SECRET\n", "A=${SECRET\n", "\ufeffA=1\n"):
        put(Path(d, ".env"), text)
        rc, out, err, stderr = raw("--ws", t, d)
        check(".env 壞 %r" % text, (rc, err, "SECRET" in stderr), (1, "EnvBad", False))
    Path(d, ".env").write_bytes(b"A=\xff\n")
    check(".env 不是 UTF-8", raw("--ws", t, d)[:3:2], (1, "EnvBad"))
    Path(d, ".env").unlink()
    Path(d, ".env").mkdir()
    check(".env 是資料夾", raw("--ws", t, d)[:3:2], (1, "EnvReadFailed"))


@case
def e_entry_after_env(t):
    # 讀完 .env 才照 $AOS_ENTRY 挑入口（10-21 晚 § 5）；一路往下、沿路的 .env 都讀（§ 6）
    d = prog(t, "p", "echo no\n")
    put(Path(d, "main"), '#!/bin/sh\necho "main|$AOS_CF"\n', 0o755)
    put(Path(d, ".env"), "AOS_ENTRY=main\n")
    check(".env 設的 AOS_ENTRY 有作用", raw("--ws", t, d)[:2], (0, "main|%s/main\n" % Path(d).resolve()))
    q = Path(t, "q")
    put(q / ".env", "X=top\n")
    put(q / "sub" / ".env", "X=${X}-sub\n")
    put(q / "sub" / "run", '#!/bin/sh\necho "$X|$AOS_CD"\n', 0o755)
    check("多段 $AOS_ENTRY 沿路讀 .env（加旗標才蓋）", raw("--dotenv-override", "--ws", t, str(q), env={"AOS_ENTRY": "sub/run"})[:2],
          (0, "top-sub|%s\n" % (q / "sub").resolve()))
    check("多段 $AOS_ENTRY 沿路讀 .env（不蓋＝外層贏）", raw("--ws", t, str(q), env={"AOS_ENTRY": "sub/run"})[:2],
          (0, "top|%s\n" % (q / "sub").resolve()))
    r = Path(t, "r")
    put(r / "_exec" / ".env", "Y=mid\n")
    put(r / "_exec" / "_exec" / "_exec", '#!/bin/sh\necho "$Y"\n', 0o755)
    check("挑到資料夾就走進去、一路往下", raw("--ws", t, str(r))[:2], (0, "mid\n"))
    check("走回走過的資料夾", raw("--ws", t, str(q), env={"AOS_ENTRY": "sub/../sub/run"})[:3:2], (1, "EntryBad"))


@case
def e_json_object_and_co(t):
    q = Path(t, "q")
    sh = ["sh", "-c", 'echo "$A|[$AOS_CO]"']
    put(q / "x.json", {".env": {"A": "1", "N": 3}, "_exec": {".env": {"A": "${A}2"}, "_exec": sh}})
    check("JSON .env key、一路往下、AOS_CO（加旗標才蓋）", raw("--dotenv-override", "--ws", t, str(q / "x.json"))[:2],
          (0, "12|[/_exec/_exec]\n"))
    check("JSON .env key 不蓋＝外層贏", raw("--ws", t, str(q / "x.json"))[:2], (0, "1|[/_exec/_exec]\n"))
    put(q / "c.json", {"a": {"_exec": sh}, "l": [sh]})
    check("檔#/指標也算進 AOS_CO", raw("--ws", t, str(q / "c.json") + "#/a")[:2], (0, "|[/a/_exec]\n"))
    put(q / "a.json", sh)
    check("整份檔就是入口＝空", raw("--ws", t, str(q / "a.json"))[:2], (0, "|[]\n"))
    put(q / "y.json", {".env": {"AOS_ENTRY": "alt"}, "alt": ["echo", "alt"]})
    check("JSON .env key 設 AOS_ENTRY", raw("--ws", t, str(q / "y.json"))[:2], (0, "alt\n"))
    put(q / "z.json", {".env": {"A": {"$env": "NOPE_XYZ"}}, "_exec": ["true"]})
    check("JSON .env 指示詞解不開", raw("--ws", t, str(q / "z.json"))[:3:2], (1, "EnvBad"))


@case
def e_redirect_is_fresh_hop(t):
    # 字串轉向＝全新的一跳：下一層讀自己的 .env、旗標不帶過去（但這一層蓋回去的 AOS_WS 已在環境裡）、args 照接
    a, b = Path(t, "a"), Path(t, "b")
    a.mkdir(); b.mkdir()
    r = Path(t, "r")
    put(r / ".env", "R=r\nAOS_WS=%s\n" % b)
    put(r / "_exec.json", json.dumps("../t"))
    put(Path(t, "t", ".env"), "T=t\n")
    put(Path(t, "t", "_exec"), '#!/bin/sh\necho "$R|$T|$AOS_WS|$*"\n', 0o755)
    check("轉向：下一層讀自己的 .env", raw("--ws", str(a), str(r), "x")[:2], (0, "r|t|%s|x\n" % a.resolve()))
    check("轉向：.env 不蓋已 export 的 AOS_WS", raw(str(r), cwd=t)[:2], (0, "r|t|%s|\n" % Path(t).resolve()))
    check("轉向：--dotenv-override 時 .env 的 AOS_WS 留著", raw("--dotenv-override", str(r), cwd=t)[:2], (0, "r|t|%s|\n" % b))

@case
def e_dotenv_subset(t):
    # 10-22 ideas § 3：.env 改 dotenv 基礎子集、預設不蓋、--dotenv-override 只管這一跳（對照 proto8/tests/test_exec_dotenv.py）
    d = prog(t, "p", 'printf "[%s]" "${X-unset}"\n')
    good = {
        "X=1": "1", "export X=1": "1", "export\tX=1": "1", "X = 1": "1", "  X=1": "1", "X=  a b  ": "a b",
        "X=a # c": "a", "X=a\t#c": "a", "X=a#b": "a#b", "X=#fff": "#fff", "X=": "", "X=''": "", "X='a b' # c": "a b",
        "X=\"${H}y\"": "hy", "X='${H'": None, "X='$H'": "$H", "X=$H": "$H", "X=${H}": "h",
        "X=\u3000a\u3000": "a", "X=a\u3000#c": "a", "X=a\u00a0": "a", "export=1": None, "export =1": None,
        "X= # c": None, "X='a\\b'": None, "X='${H}'": None, "X=\"un": None, "X='a'b": None, "X=${H:-y}": None,
        "\u3000X=1": None,
    }
    for line, want in good.items():
        put(Path(d, ".env"), line + "\n")
        rc, out, err, _ = raw("--ws", t, d, env={"H": "h"})
        if want is None:
            if line.startswith("export"):   # 名字 export＝不是 X，X 沒設（export 本身合規則）
                check(".env %r" % line, (rc, out), (0, "[unset]"))
            else:
                check(".env 壞 %r" % line, (rc, err), (1, "EnvBad"))
        else:
            check(".env %r" % line, (rc, out), (0, "[%s]" % want))
    put(Path(d, ".env"), "X=a 'x\n")
    check("沒引號開頭：中間的引號照字面", raw("--ws", t, d)[:2], (0, "[a 'x]"))
    put(Path(d, ".env"), "X='SECRET\n")
    rc, _, err, stderr = raw("--ws", t, d)
    check(".env 引號沒收尾不印值", (rc, err, "SECRET" in stderr, "第 1 行" in stderr), (1, "EnvBad", False, True))
    # 預設不蓋：開始讀那一刻已有的名字跳過（格式照驗）；同一份檔同名後者贏
    put(Path(d, ".env"), "X=1\nX=2\n")
    check("同一份檔後者贏", raw("--ws", t, d)[:2], (0, "[2]"))
    check("已有的不蓋", raw("--ws", t, d, env={"X": "old"})[:2], (0, "[old]"))
    check("--dotenv-override 蓋", raw("--dotenv-override", "--ws", t, d, env={"X": "old"})[:2], (0, "[2]"))
    check("重複給一樣", raw("--dotenv-override", "--dotenv-override", "--ws", t, d, env={"X": "old"})[:2], (0, "[2]"))
    check("--dotenv-override=V 是 usage 錯", raw("--dotenv-override=1", "--ws", t, d)[:3:2], (1, "Usage"))
    put(Path(d, ".env"), "X=1\nY=${NOPE_XYZ}\n")
    check("跳過的行照驗", raw("--ws", t, d, env={"Y": "y"})[:3:2], (1, "EnvBad"))
    # 旗標只管這一跳：字串轉向（全新一跳）不吃
    q = Path(t, "q")
    put(q / ".env", "X=q\n")
    put(q / "_exec.json", json.dumps("../r"))
    put(Path(t, "r", ".env"), "X=${X}r\n")
    put(Path(t, "r", "_exec"), '#!/bin/sh\nprintf "[%s]" "$X"\n', 0o755)
    check("轉向不吃旗標", raw("--dotenv-override", "--ws", t, str(q), env={"X": "old"})[:2], (0, "[q]"))
    # JSON 的 .env key：格式不變（引號照字面），只套蓋不蓋
    put(q / "j.json", {".env": {"X": "'a' # c"}, "_exec": ["sh", "-c", 'printf "[%s]" "$X"']})
    check("JSON .env key 格式不變", raw("--dotenv-override", "--ws", t, str(q / "j.json"), env={"X": "old"})[:2],
          (0, "['a' # c]"))
    check("JSON .env key 不蓋", raw("--ws", t, str(q / "j.json"), env={"X": "old"})[:2], (0, "[old]"))


for fn in cases:
    with tempfile.TemporaryDirectory() as tmp:
        fn(tmp)

print("%d 組、%d 個失敗" % (len(cases), failures))
sys.exit(1 if failures else 0)
