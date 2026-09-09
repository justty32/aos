#!/usr/bin/env python3
"""aos-exec：單發執行器——把一個目標執行**一次**，回 `(結束狀態, 這是誰的碼)`。

    aos-exec xxx [--dir-target REL] [--timeout-ms N]

`xxx` 是什麼決定怎麼跑（proto4 筆記第 11.2 節）：

    普通檔案（副檔名不是 .json）  直接執行它，stdin/stdout/stderr 繼承 aos-exec 的
    .json 檔                     讀進來當 inst.json 解析、執行
    資料夾                       執行 xxx/<--dir-target>（預設 .aos/inst.json）

「反覆執行」不是這支程式的事，時限也只是命令列旗標——之後的 aos-run 會直接
`import aos_exec` 反覆叫 `run_target()`，所以核心就是那一個函式，命令列只是包它。

這支程式**不替你收輸出**：inst.json 裡沒寫的串流一律 `/dev/null`，不繼承、不抓回。
也**不注入任何 `AOS_*` 環境變數**。

`run_target()` 回的是 **`(code, kind)`**：`kind` 說這個碼是誰的——`"child"`＝子程式真的
跑完了一次（它的結束碼／128+N／126／127），`"aos"`＝aos-exec 自己失敗（inst.json 壞、
指示詞解不開、setup 做不到），`"usage"`＝用法錯。命令列的退出碼就是照 kind 換算：
`usage`→2、`aos`→**125**、`child`→原樣。125 是特意挑的：跟子程式的碼分得開。
"""
import argparse
import os
import signal
import subprocess
import sys

import aos_inst

DEFAULT_DIR_TARGET = os.path.join(".aos", "inst.json")
GRACE = 2.0             # 逾時：SIGTERM 之後給整個 process group 這麼久，還在就 SIGKILL
CHILD, AOS, USAGE = "child", "aos", "usage"      # run_target() 回的那個 kind
EXIT_AOS = 125          # kind=="aos" 時命令列的退出碼（不會跟子程式的碼撞號）


def run_target(xxx, dir_target=DEFAULT_DIR_TARGET, timeout_ms=0, on_spawn=None):
    """把 xxx 執行一次，回 `(code, kind)`。

    `kind` 說這個 code 是誰的：

    - `"child"`：子程式**真的跑完了一次**——它的結束碼、被訊號 N 砍＝128+N、
      找不到程式＝127、沒執行權＝126。有寫 `exit` 欄位的話寫進去的就是這個碼。
    - `"aos"`：**aos-exec 自己**失敗，那次根本沒跑——inst.json 讀不到／不是物件／
      格式壞／指示詞解不開、`exit` 檔的父目錄不存在、`cwd` 不是資料夾、重導向的檔
      開不起來。code 是 1（命令列會換成 125），不寫 exit 檔。
    - `"usage"`：用法錯——`xxx` 不存在、`--dir-target` 指的檔不存在。code 是 2。

    所以 `kind == "child"` ⇔「跑完了一次」⇔ exit 檔有被寫，這條線兩邊都對得起來。

    `on_spawn` 是給 aos-run 的鉤子：子行程一開起來就用那個 Popen 叫它一次，收完屍再用
    None 叫一次。aos-run 靠它在第二次訊號時砍掉正在跑的那個（命令列用不到，預設沒有）。
    """
    p = os.path.abspath(xxx)
    if not os.path.exists(p):
        return _err(2, USAGE, "找不到 %s" % xxx)
    if os.path.isdir(p):
        target = os.path.join(p, dir_target)
        if not os.path.isfile(target):
            return _err(2, USAGE, "資料夾 %s 裡沒有 %s" % (p, dir_target))
        return _run_inst(target, p, timeout_ms, on_spawn)
    if p.endswith(".json"):
        return _run_inst(p, os.path.dirname(p), timeout_ms, on_spawn)
    return _run_plain(p, timeout_ms, on_spawn)


def _err(code, kind, msg):
    sys.stderr.write("aos-exec: %s\n" % msg)
    return code, kind


def _run_plain(path, timeout_ms, on_spawn=None):
    """最陽春的那個指令集：一個檔讀進來就跑。

    argv 就是它自己（絕對路徑）、cwd 是它所在的資料夾、三條串流原樣繼承 aos-exec 的、
    環境就是繼承的、沒有 exit 檔。沒有執行位＝`(126, "child")`。
    """
    return _spawn([path], os.path.dirname(path), dict(os.environ),
                  None, None, None, timeout_ms, "", on_spawn)


def _run_inst(target, base, timeout_ms, on_spawn=None):
    """把一份 inst.json 解開、開好串流、跑一次。base ＝ `xxx`（cwd 相對路徑的起點）。"""
    try:
        inst = aos_inst.load(target, base)
    except aos_inst.InstError as e:
        return _err(1, AOS, str(e))

    if inst["exit"]:                    # 父目錄不存在＝aos-exec 自己失敗，不幫忙 mkdir
        d = os.path.dirname(inst["exit"]) or "."
        if not os.path.isdir(d):
            return _err(1, AOS, "exit 檔的父目錄不存在（不會幫你建）：%s" % d)
    if not os.path.isdir(inst["cwd"]):  # 連 chdir 都做不到＝aos-exec 自己失敗，沒跑成
        return _err(1, AOS, "cwd 不是資料夾：%s" % inst["cwd"])

    env = {} if inst["envs_clear"] else dict(os.environ)
    env.update(inst["envs"])             # 只加不減；清空型式就是從空的開始加

    opened = []
    try:
        try:
            fin = open(inst["stdin"] or os.devnull, "rb")
            opened.append(fin)
            fout = open(inst["stdout"] or os.devnull, "wb")
            opened.append(fout)
            if inst["stderr_merge"]:            # {"$opt":"merge"}＝跟 stdout 同一條
                ferr = fout
            else:
                ferr = open(inst["stderr"] or os.devnull, "wb")
                opened.append(ferr)
        except OSError as e:
            return _err(1, AOS, "重導向的檔案開不起來：%s" % e)
        return _spawn(inst["argv"], inst["cwd"], env, fin, fout, ferr,
                      timeout_ms, inst["exit"], on_spawn)
    finally:
        for f in opened:
            f.close()


def _spawn(argv, cwd, env, fin, fout, ferr, timeout_ms, exit_path, on_spawn=None):
    """跑一次、等它、逾時就砍，回 `(結束狀態, "child")`（順便寫 exit 檔）。

    argv[0] 走**疊加後**的 env 裡的 PATH（subprocess 帶 env= 時本來就這樣查；env 被
    清空、裡面沒有 PATH 時，Python 的 `os.get_exec_path()` 退回 `os.defpath`）。
    找不到＝127、沒執行權＝126，這兩種都算「跑完了一次」。
    """
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True,
                             stdin=fin, stdout=fout, stderr=ferr)
    except PermissionError as e:
        return _finish(126, exit_path, "沒有執行權：%s（exit 126）" % e)
    except (FileNotFoundError, NotADirectoryError) as e:
        return _finish(127, exit_path, "找不到程式：%s（exit 127）" % e)
    except OSError as e:
        return _finish(126, exit_path, "起不了子行程：%s（exit 126）" % e)

    if on_spawn:
        on_spawn(p)                                 # 開起來了：aos-run 要拿得到它才砍得掉
    limit = (timeout_ms / 1000.0) if timeout_ms else None
    try:
        p.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        _sig_group(p, signal.SIGTERM)               # 先好好講：整個 process group
        try:
            p.wait(timeout=GRACE)
        except subprocess.TimeoutExpired:
            _sig_group(p, signal.SIGKILL)
            p.wait()
        _sig_group(p, signal.SIGKILL)               # 直接子行程死了不代表群組空了
    code = p.returncode
    if on_spawn:
        on_spawn(None)                              # 收完屍：那個 pid 別再被砍
    return _finish(code if code >= 0 else 128 + (-code), exit_path, None)


def _sig_group(p, sig):
    """砍整個 process group：留在群組裡的孫行程要跟著走。空群組＝ESRCH，無害。"""
    try:
        os.killpg(os.getpgid(p.pid), sig)
    except OSError:
        pass


def _finish(status, exit_path, note):
    """收尾：該說的說一句、該寫的 exit 檔寫掉，回 `(那個結束狀態, "child")`。

    走到這裡就代表**跑完了一次**（126／127／逾時也算），所以 kind 是 child、exit 檔照寫；
    只有 exit 檔本身寫不進去才翻成 aos。
    """
    if note:
        sys.stderr.write("aos-exec: %s\n" % note)
    if exit_path:
        try:
            _write_exit(exit_path, status)
        except OSError as e:
            return _err(1, AOS, "exit 檔寫不進去 %s：%s" % (exit_path, e))
    return status, CHILD


def _write_exit(path, status):
    """`exit` 欄位：十進位結束碼＋一個換行，fsync 檔案與它的父目錄（崩潰後對帳的證據）。"""
    d = os.path.dirname(path) or "."
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)
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
    ap = argparse.ArgumentParser(
        prog="aos-exec", description="把一個目標（檔案／.json／資料夾）執行一次")
    ap.add_argument("xxx", help="要執行的東西：普通檔案、.json 檔，或資料夾")
    ap.add_argument("--dir-target", default=DEFAULT_DIR_TARGET,
                    help="xxx 是資料夾時要跑的相對路徑（預設 .aos/inst.json）")
    ap.add_argument("--timeout-ms", type=int, default=0,
                    help="這一次執行的上限（毫秒），0 或不給＝不限")
    a = ap.parse_args(argv)
    if a.timeout_ms < 0:
        ap.error("--timeout-ms 不能是負數")      # argparse 的用法錯＝退出碼 2
    code, kind = run_target(a.xxx, a.dir_target, a.timeout_ms)
    return EXIT_AOS if kind == AOS else code


if __name__ == "__main__":
    sys.exit(main())
