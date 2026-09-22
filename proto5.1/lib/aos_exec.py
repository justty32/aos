#!/usr/bin/env python3
"""aos-exec：單發執行器——把一個目標執行**一次**，回 `(結束狀態, 這是誰的碼)`。

    aos-exec [xxx] [--dir-target REL] [--timeout-ms N] [--stderr PATH|-] [-- ARG...]

`xxx` 是什麼決定怎麼跑（命令列說明在 ../spec/exec.md）：

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
"""
import argparse
import os
import signal
import subprocess
import sys

import aos_inst

__all__ = ["run_target", "run_inst", "main", "DEFAULT_DIR_TARGET", "GRACE", "CHILD", "AOS", "USAGE", "EXIT_AOS"]

DEFAULT_DIR_TARGET = os.path.join(".aos", "inst.json")
GRACE = 2.0             # 逾時：SIGTERM 之後給整個 process group 這麼久，還在就 SIGKILL
CHILD, AOS, USAGE = "child", "aos", "usage"      # run_target() 回的那個 kind
EXIT_AOS = 125          # kind=="aos" 時命令列的退出碼（不會跟子程式的碼撞號）


def run_target(xxx, dir_target=DEFAULT_DIR_TARGET, timeout_ms=0, on_spawn=None, stderr=None,
               args=None):
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

    `stderr` 只蓋子程式這一條流：None＝照 inst.json，`-`＝繼承呼叫者的 stderr，字串＝以
    呼叫者當時的 cwd 為中心開檔；蓋的是 inst.json 的**整個** stderr 設定（含 merge／inherit／
    append／mkdir）。普通檔案模式也吃這個覆蓋。`args` 只對普通檔案有效；None 表示沒給 `--`，
    陣列（包括空陣列）表示有給。
    """
    p = os.path.abspath(xxx)
    if os.path.isdir(p):
        if args is not None:
            return _inst_args_error()
        target = os.path.join(p, dir_target)
        if not os.path.isfile(target):
            return _err(2, USAGE, "資料夾 %s 裡沒有 %s" % (p, dir_target))
        return _run_inst(target, p, timeout_ms, on_spawn, stderr)
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
    """
    output = []
    code, kind = _execute_inst(inst, timeout_ms, input_bytes=stdin_text.encode("utf-8"), output=output)
    return code, kind, (output[0] if output else b"").decode("utf-8", errors="replace")


def _err(code, kind, msg):
    sys.stderr.write("aos-exec: %s\n" % msg)
    return code, kind


def _inst_args_error():
    return _err(2, USAGE, "inst 目標的參數寫在 inst.json 的 argv 裡")


def _run_plain(path, timeout_ms, on_spawn=None, stderr=None, args=None):
    """普通檔案：一個檔讀進來就跑。

    argv[0] 是它自己（絕對路徑），args 原樣接在後面；cwd 是它所在的資料夾，三條串流原樣繼承
    aos-exec 的、環境就是繼承的、沒有 exit 檔。沒有執行位＝`(126, "child")`。
    """
    argv = [path] + list(args or ())
    if stderr in (None, "-"):
        return _spawn(argv, os.path.dirname(path), dict(os.environ), None, None, None,
                      timeout_ms, "", on_spawn)
    try:
        ferr = open(stderr, "wb")
    except OSError as e:
        return _err(1, AOS, "重導向的檔案開不起來：%s" % e)
    try:
        return _spawn(argv, os.path.dirname(path), dict(os.environ), None, None, ferr,
                      timeout_ms, "", on_spawn)
    finally:
        ferr.close()


def _run_inst(target, base, timeout_ms, on_spawn=None, stderr=None):
    """把一份 inst.json 解開、做前置檢查、開好串流、跑一次。base＝這份 inst 的家。

    照 inst-posix.md 第 6 節：`mkdir` 在 chdir／開檔前 `makedirs`（建不起來＝aos-exec 自己失敗）、
    `append` 用 `ab` 開檔、`inherit` 那條串流傳 None 給 Popen、stderr 的 `merge` 傳
    `subprocess.STDOUT`（所以 stdout 是 append／inherit 它就跟著）。
    """
    try:
        inst = aos_inst.load(target, base)
    except aos_inst.InstError as e:
        return _err(1, AOS, str(e))
    return _execute_inst(inst, timeout_ms, on_spawn, stderr)


def _execute_inst(inst, timeout_ms, on_spawn=None, stderr=None, input_bytes=None, output=None):
    """共用的前置檢查與串流設定；有 input_bytes 時改走 stdin／stdout 管線。"""

    # 先建該建的目錄：cwd 自己，再來是三個輸出檔的父目錄。建不起來＝沒跑成（125）。
    to_make = [("cwd", inst["cwd"])] if inst["cwd_mkdir"] else []
    for name in ("stdout", "stderr", "exit"):
        if name == "stdout" and input_bytes is not None:
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
            if input_bytes is not None:
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
        return _spawn(inst["argv"], inst["cwd"], env, fin, fout, ferr,
                      timeout_ms, exit_path, on_spawn, inst["exit"]["append"], input_bytes, output)
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
           exit_append=False, input_bytes=None, output=None):
    """跑一次、等它、逾時就砍，回 `(結束狀態, "child")`（順便寫 exit 檔）。

    argv[0] 走**疊加後**的 env 裡的 PATH（subprocess 帶 env= 時本來就這樣查；env 被清空、
    裡面沒有 PATH 時，Python 的 `os.get_exec_path()` 退回 `os.defpath`）。找不到＝127、
    沒執行權＝126，這兩種都算「跑完了一次」。
    """
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True,
                             stdin=fin, stdout=fout, stderr=ferr)
    except PermissionError as e:
        return _finish(126, exit_path, "沒有執行權：%s（exit 126）" % e, exit_append)
    except (FileNotFoundError, NotADirectoryError) as e:
        return _finish(127, exit_path, "找不到程式：%s（exit 127）" % e, exit_append)
    except OSError as e:
        return _finish(126, exit_path, "起不了子行程：%s（exit 126）" % e, exit_append)

    if on_spawn:
        on_spawn(p)                                 # 開起來了：aos-run 要拿得到它才砍得掉
    limit = (timeout_ms / 1000.0) if timeout_ms else None
    captured = b""
    try:
        if input_bytes is None:
            p.wait(timeout=limit)
        else:
            captured, _ = p.communicate(input=input_bytes, timeout=limit)
    except subprocess.TimeoutExpired:
        _sig_group(p, signal.SIGTERM)               # 先好好講：整個 process group
        try:
            if input_bytes is None:
                p.wait(timeout=GRACE)
            else:
                captured, _ = p.communicate(timeout=GRACE)
        except subprocess.TimeoutExpired:
            _sig_group(p, signal.SIGKILL)
            if input_bytes is None:
                p.wait()
            else:
                captured, _ = p.communicate()
        _sig_group(p, signal.SIGKILL)               # 直接子行程死了不代表群組空了
    if output is not None:
        output.append(captured)
    code = p.returncode
    if on_spawn:
        on_spawn(None)                              # 收完屍：那個 pid 別再被砍
    return _finish(code if code >= 0 else 128 + (-code), exit_path, None, exit_append)


def _sig_group(p, sig):
    """砍整個 process group：留在群組裡的孫行程要跟著走。空群組＝ESRCH，無害。"""
    try:
        os.killpg(p.pid, sig)                      # setsid 後 pgid＝pid；父行程收屍後仍能砍孫行程
    except OSError:
        pass


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
