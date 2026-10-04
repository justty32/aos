"""step 包的子工作包裝程式：跑實際命令、檢查宣告的產物、原子發布槽外結果檔（spec.md §4）。

    aos7-step-result --result P --job J --inst I --step S --request R --attempt A [--expect 路徑]... -- 命令...

由直譯器登記的 once 起（argv 由直譯器展開），cwd＝node。結果檔是工作交付的依據；寫結果是最後一個動作，
被 kill（整個程序群組一起收）就沒有結果——直譯器看到「結束了卻沒結果」只能說不知道，不會誤報成功。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # proto7-2/
sys.path.insert(0, os.path.join(TOP, "lib"))
from aos7_fs import now  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def publish(path, obj):
    """原子、不覆寫地發布：寫暫存檔、os.link 到目的地（已存在就失敗）、刪暫存檔。回 True＝發布了。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, ".%s.tmp.%d" % (os.path.basename(path), os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    try:
        os.link(tmp, path)
        return True
    except FileExistsError:
        return False
    finally:
        os.unlink(tmp)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-step-result")
    for k in ("result", "job", "inst", "step", "request", "attempt"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--expect", action="append", default=[])
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        print("aos7-step-result: 要在 -- 後面給命令", file=sys.stderr)
        return 2
    if os.path.lexists(a.result):
        # 同一個 attempt 只該跑一次；已有結果＝不碰它（不覆寫已交付的事實）
        print("aos7-step-result: %s 已存在，不跑、不覆寫" % a.result, file=sys.stderr)
        return 2
    try:
        code = subprocess.call(cmd)   # 同一個程序群組：kill 收槽時連包裝程式一起收，結果就不會寫
    except OSError as e:
        print("aos7-step-result: 起不了命令：%r" % e, file=sys.stderr)
        code = 127
    arts, missing = {}, []
    for p in a.expect:
        try:
            arts[p] = sha256(p)
        except OSError:
            missing.append(p)
    tid, run = os.environ.get("AOS7_TID"), os.environ.get("AOS7_RUN")
    res = {"job": a.job, "inst": a.inst, "step": a.step, "request": a.request, "attempt": a.attempt,
           "run": "%s#%s" % (tid, run) if tid and run else None, "slot": tid, "code": code,
           "ok": code == 0 and not missing, "artifacts": arts, "missing": missing, "at": now()}
    if not publish(a.result, res):
        print("aos7-step-result: %s 已存在，沒覆寫" % a.result, file=sys.stderr)
        return 2
    return code if 0 <= code < 256 else 128 + (-code if code < 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
