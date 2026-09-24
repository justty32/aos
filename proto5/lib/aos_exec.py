#!/usr/bin/env python3
"""aos-exec：單發執行器——把一個目標執行**一次**，回 `(結束狀態, 這是誰的碼)`。

    aos-exec [xxx] [--dir-target REL] [--timeout-ms N] [--stderr PATH|-] [-- ARG...]

`xxx` 是什麼決定怎麼跑（命令列說明在 ../spec/aos-exec/）：

    普通檔案（副檔名不是 .json）  直接執行它，stdin/stdout/stderr 繼承 aos-exec 的
    .json 檔                     讀進來當 inst.json 解析、執行（不存在＝125，見下）
    資料夾                       執行 xxx/<--dir-target>（預設 .aos/inst.json）

inst.json 怎麼讀、怎麼驗在 aos_inst.py；「照一份 inst 跑一次」是什麼意思照
../spec/inst-posix/ 第 6 節做：驗完才跑、mkdir／append／inherit／merge、環境清空或疊加、
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

底層（開串流、起子行程、等、寫 exit 檔）在 aos_exec_run.py；daemon.md §2 的非同步入口
`spawn_target()` 在 aos_exec_spawn.py。
"""
import argparse
import os
import sys
import time

import aos_inst
from aos_exec_run import (
    AOS, CHILD, DEFAULT_DIR_TARGET, GRACE, USAGE, _err, _execute_inst, _spawn,
)

__all__ = ["run_target", "run_inst", "InstResult", "main", "DEFAULT_DIR_TARGET", "GRACE", "CHILD", "AOS", "USAGE", "EXIT_AOS"]
__all__ += ["run_target_full", "TargetResult"]

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
