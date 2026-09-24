#!/usr/bin/env python3
"""aos-exec：單發執行器——把一個目標執行**一次**，回 `(結束狀態, 這是誰的碼)`。

    aos-exec [xxx] [--dir-target REL] [--timeout-ms N] [--stderr PATH|-] [-- ARG...]

`xxx` 是什麼決定怎麼跑（命令列說明在 ../spec/aos-exec.md）：

    普通檔案（副檔名不是 .json）  直接執行它，stdin/stdout/stderr 繼承 aos-exec 的
    .json 檔                     讀進來當 inst.json 解析、執行（不存在＝125，見下）
    資料夾                       執行 xxx/<--dir-target>（預設 .aos/inst.json）

inst.json 怎麼讀、怎麼驗在 aos_inst.py；「照一份 inst 跑一次」是什麼意思照
../spec/inst-posix.md 第 6 節做：驗完才跑、mkdir／append／inherit／merge、環境清空或疊加、
新 process group、逾時 SIGTERM → 2 秒 → SIGKILL、exit 檔十進位＋換行並 fsync 檔與父目錄。

「反覆執行」不是這支程式的事，時限也只是命令列旗標——之後的 aos-run 會直接
`import aos_exec` 反覆叫 `run_target()`，所以核心就是那一個函式，命令列只是包它。

`run_target()` **不替你收輸出**：inst.json 裡沒寫的串流一律 `/dev/null`，不繼承、不抓回
（要繼承就自己在那一格開 `{"$opt":"inherit"}`）。也**不注入任何 `AOS_*` 環境變數**。
`run_inst(inst, stdin_text)` 給 agent 跑記憶體裡解好的 inst：stdin 送 UTF-8、stdout 收回字串，
stderr／exit／cwd／envs 照 inst，前置檢查、啟動與逾時都跟 `run_target()` 共用。

`run_target()` 回的是 **`(code, kind)`**：`kind` 說這個碼是誰的——`"child"`＝子程式真的
跑完了一次（它的結束碼／128+N／126／127）、`"aos"`＝aos-exec 自己失敗（inst.json 壞、
指示詞解不開、前置檢查沒過）、`"usage"`＝用法錯。命令列的退出碼照 kind 換算：
`usage`→2、`aos`→**125**、`child`→原樣。125 是特意挑的：跟子程式的碼分得開。

`run_target_full()` 是 cpu.md §4.1 的新增入口：保留三種目標的語意，另回真實的
timed_out／stopped 與耗時；等待期間可輪詢控制訊息，強停只處理工作的 process group。
`spawn_target()` 是 daemon.md §2 的非同步入口：接管控制 pipe、同 session 開新 group，
將登記／go／收屍的時機交給 daemon；前置檢查與 stderr／exit 仍照 inst。
"""
import argparse
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import time

import aos_inst
from aos_directives import Context, DirectiveError, Document, resolve_located

__all__ = ["run_target", "run_inst", "terminate", "InstResult", "main", "DEFAULT_DIR_TARGET", "GRACE", "CHILD", "AOS", "USAGE", "EXIT_AOS"]
__all__ += ["run_target_full", "TargetResult"]
__all__ += ["spawn_target", "Spawned", "SpawnError"]

DEFAULT_DIR_TARGET = os.path.join(".aos", "inst.json")
GRACE = 2.0             # 逾時：SIGTERM 之後給整個 process group 這麼久，還在就 SIGKILL
CHILD, AOS, USAGE = "child", "aos", "usage"      # run_target() 回的那個 kind
EXIT_AOS = 125          # kind=="aos" 時命令列的退出碼（不會跟子程式的碼撞號）


class InstResult(tuple):
    """`run_inst()` 的三元素 tuple，另帶 `timed_out`，不靠退出碼猜是否逾時。

    舊呼叫者的三值解包、索引與 tuple 比較照舊；期限到了即為 True，即使子程式收到
    SIGTERM 後自行以 0 結束也一樣。
    """

    def __new__(cls, code, kind, stdout_text, timed_out=False):
        result = super().__new__(cls, (code, kind, stdout_text))
        result.timed_out = timed_out
        return result


class TargetResult:
    """一次完整執行的結果；旗標不從退出碼推測。"""

    def __init__(self, code, kind, timed_out=False, ms=0, stopped=False):
        self.code, self.kind = code, kind
        self.timed_out, self.ms, self.stopped = timed_out, ms, stopped


class SpawnError(Exception):
    """daemon 的 Usage 或 SpawnFailed；尚未交出孩子，不登記。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code, self.msg = code, msg


class Spawned:
    """daemon 擁有的孩子與 exit 檔收尾；控制 pipe 由呼叫者關閉。"""

    def __init__(self, process, exit_path="", exit_append=False):
        self.process = process
        self.exit_path, self.exit_append = exit_path, exit_append

    def finish(self, code=None):
        """收屍後呼叫；省略 code 時將 Popen 的負訊號碼轉為 128+N。"""
        if code is None:
            code = self.process.poll()
            if code is None:
                raise SpawnError("SpawnFailed", "孩子尚未退出，不能寫 exit")
            code = code if code >= 0 else 128 - code
        return _finish(code, self.exit_path, None, self.exit_append)


def spawn_target(xxx, dir_target=DEFAULT_DIR_TARGET):
    """daemon.md §2：讀目標、開控制 pipe，回孩子；登記與 go 由 daemon 做。

    與同步執行共用 inst 的前置檢查、環境、stderr 及 exit；孩子使用獨立 pgid、同一
    session。Popen 起不來（包括普通執行的 126／127）都丟 SpawnFailed，不登記假 pid。
    """
    p = os.path.abspath(xxx)
    if os.path.isdir(p):
        target, base = os.path.join(p, dir_target), p
        if not os.path.isfile(target):
            raise SpawnError("SpawnFailed", "資料夾 %s 裡沒有 %s" % (p, dir_target))
    elif p.endswith(".json"):
        target, base = p, os.path.dirname(p)
    else:
        if not os.path.exists(p):
            raise SpawnError("SpawnFailed", "找不到 %s" % xxx)
        return _spawn_control([p], os.path.dirname(p), dict(os.environ), None,
                              None, None, 0, "")
    inst = _load_control_inst(target, base)
    diagnostic = io.StringIO()
    try:
        with contextlib.redirect_stderr(diagnostic):
            result = _execute_inst(inst, 0, launcher=_spawn_control)
    except ValueError as e:
        raise SpawnError("SpawnFailed", "FieldTypeMismatch: 無法執行 inst：%s" % e)
    if not isinstance(result, Spawned):
        raise SpawnError("SpawnFailed", diagnostic.getvalue().strip())
    return result


def _load_control_inst(target, base):
    """只讀一份快照，檢查頂層顯式串流，再以原文件位置解 inst。"""
    try:
        with open(target, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise SpawnError("SpawnFailed", "ReadFailed: %s" % e)
    except UnicodeError as e:
        raise SpawnError("SpawnFailed", "JsonSyntax: %s" % e)
    try:
        obj = json.loads(raw)
    except ValueError as e:
        raise SpawnError("SpawnFailed", "JsonSyntax: %s" % e)
    try:
        top = resolve_located(obj, Context(Document(target, obj), base_dir=base), [])
        if isinstance(top.value, dict) and any(key in top.value for key in ("stdin", "stdout")):
            raise SpawnError("Usage", "daemon 孩子的 stdin／stdout 由控制 pipe 接管，不可寫在 inst")
        # load_obj 會丟掉原文件與 subtree 位置；指回已在記憶體的文件，保留 $ref:"" 語意。
        reference = {"$ref": ""}
        if top.position:
            reference["$at"] = "/" + "/".join(str(x).replace("~", "~0").replace("/", "~1")
                                               for x in top.position)
        ctx = Context(top.ctx.doc, base_dir=base, env=top.ctx.env)
        return aos_inst._load(reference if top.position else top.value, ctx, base)
    except (aos_inst.InstError, DirectiveError) as e:
        raise SpawnError("SpawnFailed", str(e))


def _spawn_control(argv, cwd, env, fin, fout, ferr, timeout_ms, exit_path,
                   on_spawn=None, exit_append=False, *unused):
    """Popen 自己開的四個 pipe 端都是 CLOEXEC；只 dup 子端到 fd 0／1。"""
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, process_group=0, close_fds=True,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=ferr,
                             bufsize=0)
    except (OSError, ValueError) as e:
        raise SpawnError("SpawnFailed", "無法啟動子程式：%s" % e)
    os.set_blocking(p.stdin.fileno(), False)
    os.set_blocking(p.stdout.fileno(), False)
    return Spawned(p, exit_path, exit_append)


def run_target_full(xxx, dir_target=DEFAULT_DIR_TARGET, timeout_ms=0, on_spawn=None,
                    stderr=None, args=None, on_target=None, *, on_poll=None, poll_ms=20):
    """`run_target` 的完整結果版本，舊入口的兩值 tuple 完全保留。

    `on_poll(p)` 每 poll_ms 毫秒接到仍活著的子行程；回真值代表強停。
    強停只 TERM 該 process group，寬限 GRACE 秒再 KILL；等待仍持續回呼。
    kind=usage 沿用舊契約，由 cpu 映射為 JSON-RPC 的 Usage 錯誤。
    """
    started = time.monotonic()
    details = {"timed_out": False, "stopped": False,
               "on_poll": on_poll, "poll": max(1, poll_ms) / 1000}
    p = os.path.realpath(xxx) if on_target else os.path.abspath(xxx)
    if os.path.isdir(p):
        if args is not None:
            code, kind = _inst_args_error()
        else:
            target = os.path.join(p, dir_target)
            if on_target:
                target = os.path.realpath(target)
                on_target(target)
            if not os.path.isfile(target):
                code, kind = _err(2, USAGE, "資料夾 %s 裡沒有 %s" % (p, dir_target))
            else:
                code, kind = _run_inst(target, p, timeout_ms, on_spawn, stderr, details)
    else:
        if on_target:
            on_target(p)
        if p.endswith(".json"):
            if args is not None:
                code, kind = _inst_args_error()
            else:
                code, kind = _run_inst(p, os.path.dirname(p), timeout_ms, on_spawn,
                                       stderr, details)
        elif not os.path.exists(p):
            code, kind = _err(2, USAGE, "找不到 %s" % xxx)
        else:
            code, kind = _run_plain(p, timeout_ms, on_spawn, stderr, args, details)
    return TargetResult(code, kind, details["timed_out"],
                        int((time.monotonic() - started) * 1000), details["stopped"])


def run_target(xxx, dir_target=DEFAULT_DIR_TARGET, timeout_ms=0, on_spawn=None, stderr=None,
               args=None, on_target=None):
    """把 xxx 執行一次，回 `(code, kind)`。

    `kind` 說這個 code 是誰的：

    - `"child"`：子程式**真的跑完了一次**——它的結束碼、被訊號 N 砍＝128+N、找不到程式＝127、
      沒執行權＝126。有寫 `exit` 欄位的話寫進去的就是這個碼。
    - `"aos"`：**aos-exec 自己**失敗，那次根本沒跑——inst.json 讀不到（`.json` 路徑**不存在也
      算這種**，不是用法錯：之後的 daemon 收一個還沒出現的 inst.json 時靠的就是這條）／格式壞
      ／指示詞解不開／`mkdir` 建不起來／`exit` 檔的父目錄不存在／`cwd` 不是資料夾／重導向的
      檔開不起來。code 是 1（命令列會換成 125），不寫 exit 檔。
    - `"usage"`：用法錯——`xxx` 是不存在的**非** `.json` 路徑、`--dir-target` 指的檔不存在、
      inst 目標卻給了 `--`。code 是 2。

    所以 `kind == "child"` ⇔「跑完了一次」⇔ exit 檔有被寫，這條線兩邊都對得起來。

    `on_spawn` 是給 aos-run 的鉤子：子行程一開起來就用那個 Popen 叫它一次，收完屍再用 None
    叫一次（aos-run 靠它砍正在跑的那個；命令列用不到）。

    `on_target` 在目標路徑選定後、讀 inst 前接到絕對路徑；給 aos-run 公布 busy 目標。

    `stderr` 只蓋子程式這一條流：None＝照 inst.json，`-`＝繼承呼叫者的 stderr，字串＝以
    呼叫者當時的 cwd 為中心開檔；蓋的是 inst.json 的**整個** stderr 設定（含 merge／inherit／
    append／mkdir）。普通檔案模式也吃這個覆蓋。`args` 只對普通檔案有效；None 表示沒給 `--`，
    陣列（包括空陣列）表示有給。
    """
    p = os.path.realpath(xxx) if on_target else os.path.abspath(xxx)
    if os.path.isdir(p):
        if args is not None:
            return _inst_args_error()
        target = os.path.join(p, dir_target)
        if on_target:
            target = os.path.realpath(target)
        if on_target:
            on_target(target)
        if not os.path.isfile(target):
            return _err(2, USAGE, "資料夾 %s 裡沒有 %s" % (p, dir_target))
        return _run_inst(target, p, timeout_ms, on_spawn, stderr)
    if on_target:
        on_target(p)
    if p.endswith(".json"):                 # 不存在也走這條：讀不到＝aos 自己失敗（125）
        if args is not None:
            return _inst_args_error()
        return _run_inst(p, os.path.dirname(p), timeout_ms, on_spawn, stderr)
    if not os.path.exists(p):
        return _err(2, USAGE, "找不到 %s" % xxx)
    return _run_plain(p, timeout_ms, on_spawn, stderr, args)


def run_inst(inst, stdin_text, timeout_ms=0):
    """跑 `aos_inst.load_obj()` 解好的 inst，回 `(code, kind, stdout_text)`。

    stdin／stdout 由呼叫者接管；stderr 沒寫＝/dev/null。錯誤跟 `run_target()` 一樣印 stderr，
    kind 也是 child／aos；stdout 用 UTF-8 解碼，壞位元組換成替代字元。
    回傳的 `InstResult.timed_out` 表示真的撞到期限，跟子程式自己的退出碼分開。
    """
    output = []
    timed_out = [False]
    code, kind = _execute_inst(inst, timeout_ms, input_bytes=stdin_text.encode("utf-8"),
                              output=output, timed_out=timed_out)
    return InstResult(code, kind, (output[0] if output else b"").decode("utf-8", errors="replace"),
                      timed_out[0])


def _err(code, kind, msg):
    sys.stderr.write("aos-exec: %s\n" % msg)
    return code, kind


def _inst_args_error():
    return _err(2, USAGE, "inst 目標的參數寫在 inst.json 的 argv 裡")


def _run_plain(path, timeout_ms, on_spawn=None, stderr=None, args=None, details=None):
    """普通檔案：一個檔讀進來就跑。

    argv[0] 是它自己（絕對路徑），args 原樣接在後面；cwd 是它所在的資料夾，三條串流原樣繼承
    aos-exec 的、環境就是繼承的、沒有 exit 檔。沒有執行位＝`(126, "child")`。
    """
    argv = [path] + list(args or ())
    if stderr in (None, "-"):
        return _spawn(argv, os.path.dirname(path), dict(os.environ), None, None, None,
                      timeout_ms, "", on_spawn, details=details)
    try:
        ferr = open(stderr, "wb")
    except OSError as e:
        return _err(1, AOS, "重導向的檔案開不起來：%s" % e)
    try:
        return _spawn(argv, os.path.dirname(path), dict(os.environ), None, None, ferr,
                      timeout_ms, "", on_spawn, details=details)
    finally:
        ferr.close()


def _run_inst(target, base, timeout_ms, on_spawn=None, stderr=None, details=None):
    """把一份 inst.json 解開、做前置檢查、開好串流、跑一次。base＝這份 inst 的家。

    照 inst-posix.md 第 6 節：`mkdir` 在 chdir／開檔前 `makedirs`（建不起來＝aos-exec 自己失敗）、
    `append` 用 `ab` 開檔、`inherit` 那條串流傳 None 給 Popen、stderr 的 `merge` 傳
    `subprocess.STDOUT`（所以 stdout 是 append／inherit 它就跟著）。
    """
    try:
        inst = aos_inst.load(target, base)
    except UnicodeError as e:
        return _err(1, AOS, "JsonSyntax: %s 不是 UTF-8：%s" % (target, e))
    except aos_inst.InstError as e:
        return _err(1, AOS, str(e))
    try:
        return _execute_inst(inst, timeout_ms, on_spawn, stderr, details=details)
    except ValueError as e:
        return _err(1, AOS, "FieldTypeMismatch: 無法執行 inst：%s" % e)


def _execute_inst(inst, timeout_ms, on_spawn=None, stderr=None, input_bytes=None, output=None,
                  timed_out=None, details=None, launcher=None):
    """共用的前置檢查與串流設定；有 input_bytes 時改走 stdin／stdout 管線。"""

    # 先建該建的目錄：cwd 自己，再來是三個輸出檔的父目錄。建不起來＝沒跑成（125）。
    to_make = [("cwd", inst["cwd"])] if inst["cwd_mkdir"] else []
    for name in ("stdout", "stderr", "exit"):
        if name == "stdout" and (input_bytes is not None or launcher is not None):
            continue                            # 收回 stdout，不開 inst 的輸出檔
        if name == "stderr" and stderr is not None:
            continue                            # 命令列蓋掉了，inst 的 stderr 設定整個不算
        if inst[name]["mkdir"]:
            to_make.append((name, os.path.dirname(inst[name]["path"]) or "."))
    for name, d in to_make:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:
            return _err(1, AOS, "%s 的 mkdir 建不起來 %s：%s" % (name, d, e))

    exit_path = inst["exit"]["path"]
    if exit_path:                       # 父目錄不存在＝aos-exec 自己失敗（沒開 mkdir 就不幫建）
        d = os.path.dirname(exit_path) or "."
        if not os.path.isdir(d):
            return _err(1, AOS, "exit 檔的父目錄不存在（沒開 mkdir 不會幫你建）：%s" % d)
    if not os.path.isdir(inst["cwd"]):  # 連 chdir 都做不到＝aos-exec 自己失敗，沒跑成
        return _err(1, AOS, "cwd 不是資料夾：%s" % inst["cwd"])

    env = {} if inst["envs_clear"] else dict(os.environ)
    env.update(inst["envs"])             # 只加不減；清空型式就是從空的開始加

    opened = []
    try:
        try:
            if input_bytes is not None or launcher is not None:
                fin, fout = subprocess.PIPE, subprocess.PIPE
            else:
                fin = None if inst["stdin"]["inherit"] else open(
                    inst["stdin"]["path"] or os.devnull, "rb")
                opened.append(fin)
                fout = _open_out(inst["stdout"])
                opened.append(fout)
            if stderr == "-":
                ferr = sys.stderr                # 繼承 aos-exec 的 stderr，不能 close
            elif stderr is not None:
                ferr = open(stderr, "wb")        # 命令列路徑以呼叫 aos-exec 時的 cwd 為中心
                opened.append(ferr)
            elif inst["stderr"]["merge"]:        # 跟 stdout 同一條，stdout 怎麼設它就怎麼走
                ferr = subprocess.STDOUT
            else:
                ferr = _open_out(inst["stderr"])
                opened.append(ferr)
        except OSError as e:
            return _err(1, AOS, "重導向的檔案開不起來：%s" % e)
        return (launcher or _spawn)(inst["argv"], inst["cwd"], env, fin, fout, ferr,
                      timeout_ms, exit_path, on_spawn, inst["exit"]["append"], input_bytes, output,
                      timed_out, details)
    finally:
        for f in opened:
            if f is not None:                    # inherit 的那條是 None，沒東西可關
                f.close()


def _open_out(field):
    """stdout／stderr 一格：inherit＝None（Popen 就繼承）、append＝`ab`、不然 `wb`（建立並清空）；
    沒寫路徑＝/dev/null。"""
    if field["inherit"]:
        return None
    return open(field["path"] or os.devnull, "ab" if field["append"] else "wb")


def _spawn(argv, cwd, env, fin, fout, ferr, timeout_ms, exit_path, on_spawn=None,
           exit_append=False, input_bytes=None, output=None, timed_out=None, details=None):
    """跑一次、等它、逾時就砍，回 `(結束狀態, "child")`（順便寫 exit 檔）。

    argv[0] 走**疊加後**的 env 裡的 PATH（subprocess 帶 env= 時本來就這樣查；env 被清空、
    裡面沒有 PATH 時，Python 的 `os.get_exec_path()` 退回 `os.defpath`）。找不到＝127、
    沒執行權＝126，這兩種都算「跑完了一次」。
    """
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True,
                             stdin=fin, stdout=fout, stderr=ferr)
    except ValueError as e:
        return _err(1, AOS, "FieldTypeMismatch: 無法啟動子程式：%s" % e)
    except PermissionError as e:
        return _finish(126, exit_path, "沒有執行權：%s（exit 126）" % e, exit_append)
    except (FileNotFoundError, NotADirectoryError) as e:
        return _finish(127, exit_path, "找不到程式：%s（exit 127）" % e, exit_append)
    except OSError as e:
        return _finish(126, exit_path, "起不了子行程：%s（exit 126）" % e, exit_append)

    if on_spawn:
        on_spawn(p)                                 # 開起來了：aos-run 要拿得到它才砍得掉
    if details is not None:
        _wait_full(p, timeout_ms, details)
        if on_spawn:
            on_spawn(None)
        code = p.returncode
        return _finish(code if code >= 0 else 128 + (-code), exit_path, None, exit_append)
    deadline = time.monotonic() + timeout_ms / 1000.0 if timeout_ms else None
    captured = b""
    pending_input = input_bytes
    while not getattr(p, "_aos_stop", None):
        limit = max(0, deadline - time.monotonic()) if deadline is not None else None
        if on_spawn is not None:
            limit = min(limit, 0.05) if limit is not None else 0.05
        try:
            if input_bytes is None:
                p.wait(timeout=limit)
            else:
                captured, _ = p.communicate(input=pending_input, timeout=limit)
            break
        except subprocess.TimeoutExpired:
            pending_input = None
            if deadline is not None and time.monotonic() >= deadline:
                if timed_out is not None:
                    timed_out[0] = True
                terminate(p)
    if getattr(p, "_aos_stop", None):
        until, groups = p._aos_stop
        # 父進程先退出也給後代同一個寬限；nested run_inst 另開的 session 也在快照裡。
        try:
            remaining = max(0, until - time.monotonic())
            if input_bytes is None:
                p.wait(timeout=remaining)
            else:
                captured, _ = p.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            pass
        # 沒有活後代就不必等滿；killpg(0) 把 zombie 當存在，至多多等兩秒。
        while time.monotonic() < until and any(_group_exists(g) for g in groups):
            time.sleep(min(0.02, max(0, until - time.monotonic())))
        _signal_groups(groups, signal.SIGKILL)
        if input_bytes is None:
            p.wait()
        else:
            captured, _ = p.communicate()
    if output is not None:
        output.append(captured)
    code = p.returncode
    if on_spawn:
        on_spawn(None)                              # 收完屍：那個 pid 別再被砍
    return _finish(code if code >= 0 else 128 + (-code), exit_path, None, exit_append)


def _wait_full(p, timeout_ms, details):
    """cpu 專用等待：取消／逾時都只處理一個 pgid，控制回呼不中斷。"""
    deadline = time.monotonic() + timeout_ms / 1000 if timeout_ms else None
    until = None
    while True:
        alive = p.poll() is None
        if until is None and not alive:
            return
        cancel = bool(details["on_poll"](p)) if details["on_poll"] else False
        now = time.monotonic()
        if cancel and p.poll() is None:
            details["stopped"] = True
        if until is None and p.poll() is None:
            expired = deadline is not None and now >= deadline
            if cancel or expired:
                details["timed_out"] = expired
                _signal_groups({p.pid}, signal.SIGTERM)
                until = now + GRACE
        if until is not None:
            if not _group_exists(p.pid):
                p.wait()
                return
            if now >= until:
                _signal_groups({p.pid}, signal.SIGKILL)
                p.wait()
                return
        pause = details["poll"]
        limit = until if until is not None else deadline
        if limit is not None:
            pause = min(pause, max(0, limit - time.monotonic()))
        time.sleep(pause)


def terminate(p):
    """第一次取消：快照後代 groups、TERM；_spawn 在兩秒期限後 KILL 並收屍。

    Linux /proc 補上 nested run_inst 的 setsid 邊界；其他 POSIX 至少處理原 group。
    不追捕終止開始後才新生或已脫離親子樹的 daemon。
    """
    if getattr(p, "_aos_stop", None):
        return
    groups = {p.pid}
    parents = {}
    try:
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open("/proc/%s/stat" % name) as f:
                    fields = f.read().rsplit(")", 1)[1].split()
                parents[int(name)] = (int(fields[1]), int(fields[2]))
            except (OSError, ValueError, IndexError):
                continue
    except OSError:
        pass
    descendants = {p.pid}
    while True:
        added = {pid for pid, (parent, _) in parents.items() if parent in descendants} - descendants
        if not added:
            break
        descendants.update(added)
    groups.update(parents[pid][1] for pid in descendants if pid in parents)
    groups.discard(os.getpgrp())
    p._aos_stop = (time.monotonic() + GRACE, groups)
    _signal_groups(groups, signal.SIGTERM)


def _signal_groups(groups, sig):
    for group in groups:
        try:
            os.killpg(group, sig)
        except ProcessLookupError:
            pass


def _group_exists(group):
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False


def _finish(status, exit_path, note, exit_append=False):
    """收尾：該說的說一句、該寫的 exit 檔寫掉，回 `(那個結束狀態, "child")`。

    走到這裡就代表**跑完了一次**（126／127／逾時也算），所以 kind 是 child、exit 檔照寫；
    只有 exit 檔本身寫不進去才翻成 aos。`exit_append`＝接在檔尾（`exit` 的 append 選項）。
    """
    if note:
        sys.stderr.write("aos-exec: %s\n" % note)
    if exit_path:
        try:
            _write_exit(exit_path, status, exit_append)
        except OSError as e:
            return _err(1, AOS, "exit 檔寫不進去 %s：%s" % (exit_path, e))
    return status, CHILD


def _write_exit(path, status, append=False):
    """`exit` 欄位：十進位結束碼＋一個換行，fsync 檔案與它的父目錄（崩潰後對帳的證據）。
    `append`＝不清空、接在檔尾（一次一行）；不然建立並清空。"""
    d = os.path.dirname(path) or "."
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC), 0o666)
    try:
        os.write(fd, ("%d\n" % status).encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def main(argv=None):
    """命令列：解旗標、叫 `run_target()`、把 kind 換算成退出碼（usage→2、aos→125、child→原樣）。"""
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        separator = raw.index("--")
    except ValueError:
        child_args = None
    else:
        child_args = raw[separator + 1:]
        raw = raw[:separator]
    ap = argparse.ArgumentParser(
        prog="aos-exec", description="把一個目標（檔案／.json／資料夾）執行一次")
    ap.add_argument("xxx", nargs="?", default=".",
                    help="要執行的東西：普通檔案、.json 檔，或資料夾；留空＝. （現在所在的資料夾）")
    ap.add_argument("--dir-target", default=DEFAULT_DIR_TARGET,
                    help="xxx 是資料夾時要跑的相對路徑（預設 .aos/inst.json）")
    ap.add_argument("--timeout-ms", type=int, default=0,
                    help="這一次執行的上限（毫秒），0 或不給＝不限")
    ap.add_argument("--stderr", metavar="PATH",
                    help="蓋掉子程式的 stderr；- ＝印到 aos-exec 自己的 stderr")
    a = ap.parse_args(raw)
    if a.timeout_ms < 0:
        ap.error("--timeout-ms 不能是負數")      # argparse 的用法錯＝退出碼 2
    code, kind = run_target(a.xxx, a.dir_target, a.timeout_ms, stderr=a.stderr,
                            args=child_args)
    return EXIT_AOS if kind == AOS else code


if __name__ == "__main__":
    sys.exit(main())
