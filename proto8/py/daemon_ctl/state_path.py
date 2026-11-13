"""daemon_ctl 狀態位址：設了 AOS_KERNEL 先寄查詢信問表檔在哪（問不到＝KernelFailed）、沒設照舊找 daemon；讀表吃表檔路徑，相對路徑照表檔所在夾解成絕對。"""
import datetime
import json
import os
import time

import aos_flags
import daemon_ctl as _pkg

from .base import Fail, NAMES, STATE

# 這支的上層只 import base：table.py 可以在檔頭 import 這裡（TableFile、state_at、names_at），不會繞成一圈；
# 用到 table／post 的地方都在函數裡才 import。

QUERY_S = 3      # 等查詢回信的預設秒數（同 ping）
_asked = {}      # 一次執行只問一次、記在行程內、不落檔：{AOS_KERNEL 的絕對路徑: TableFile}


class TableFile(str):
    """一份表檔的路徑（不是 daemon 的資料夾）：查詢信問來的那份；檔名不一定叫 procs_state.json，表裡的相對路徑從它所在的資料夾算。"""


def via_kernel(flag=None):
    """走不走 kernel 那條路：設了 AOS_KERNEL，而且指令沒明給 --daemon（明給＝指名那一台）。"""
    return bool(os.environ.get("AOS_KERNEL", "")) and not flag


def kernel_reply_box():
    """走 kernel 那條路等回信的信箱：有 AOS_STACK＝$AOS_STACK/daemon_reply/（同 post.reply_box）；
    沒有（人的殼）＝$AOS_KERNEL/reply/。超過十分鐘的舊回信順手收掉。"""
    from . import post
    if os.environ.get("AOS_STACK", ""):
        return post.reply_box(None)
    kernel = os.environ.get("AOS_KERNEL", "")
    if not kernel:
        raise Fail("KernelFailed", "AOS_KERNEL is not set")
    box = os.path.join(os.path.abspath(kernel), "reply")
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        post._post(["init", box])
    with post._reply_lock(box):
        cutoff = datetime.datetime.now(datetime.timezone.utc).timestamp() - 600
        for stage in ("new", "cur"):
            for name in post._letters(box, stage):
                letter = post._letter(os.path.join(box, stage, name))
                try:
                    stamp = datetime.datetime.fromisoformat(letter["sent_at"].replace("Z", "+00:00"))
                    if stamp.tzinfo is None or stamp.timestamp() >= cutoff:
                        continue
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
                if stage == "new" and not post._claim(box, name):
                    continue
                post._post(["done", box, name])
    return box


def _ask_kernel(kernel, secs):
    """寄 {"procs_state_path": true} 到 AOS_KERNEL、等自己那封的回信；回表檔路徑。"""
    from . import post
    box = kernel_reply_box()
    letter = post.send(None, {"procs_state_path": True}, reply_to=box)
    end = time.monotonic() + secs
    while True:
        got = post.take_reply(box, letter)
        if got is not None:
            break
        if time.monotonic() >= end:
            post.regret(kernel, letter)             # 沒人領的查詢信撤回，不留在信箱裡
            raise Fail("KernelFailed", "no reply from AOS_KERNEL=%s within %g s (nothing there answered the state query; "
                       "AOS_DAEMON is not read instead; to look at one daemon directly: aos-daemon-ctl -d D ls)" % (kernel, secs))
        time.sleep(min(0.05, max(0, end - time.monotonic())))
    if got.get("applied") is False:
        err = got.get("error") if isinstance(got.get("error"), dict) else {}
        raise Fail("KernelFailed", "the state query sent to AOS_KERNEL=%s was refused: %s %s" % (kernel, err.get("code", "?"), err.get("msg", "")))
    if "procs_state_path" not in got:
        raise Fail("KernelFailed", "the reply from AOS_KERNEL=%s does not carry procs_state_path (what answered does not know the state query)" % kernel)
    path = got["procs_state_path"]
    if path is None:
        raise Fail("StateMissing", "the daemon behind AOS_KERNEL=%s has no procs_state window (procs_state is off)" % kernel)
    if not isinstance(path, str) or not os.path.isabs(path):
        raise Fail("StateBad", "the reply from AOS_KERNEL=%s gives procs_state_path %s, not an absolute path" % (kernel, json.dumps(path, ensure_ascii=False)))
    return path


def state_path(flag=None, timeout_s=None):
    """這次要讀的那份表檔（TableFile）：
    明給 --daemon D＝D/procs_state.json，不問；設了 AOS_KERNEL＝寄查詢信問（預設等 3 秒；問不到＝KernelFailed，不退回去讀 AOS_DAEMON）；
    沒設＝照 find_daemon（$AOS_DAEMON，再來 cwd 的 ./.stack）算 <那台>/procs_state.json，不寄信。"""
    from .table import find_daemon
    if not via_kernel(flag):
        return TableFile(os.path.join(find_daemon(flag), STATE))
    kernel = os.path.abspath(os.environ["AOS_KERNEL"])
    if kernel not in _asked:
        _asked[kernel] = TableFile(_ask_kernel(kernel, QUERY_S if timeout_s is None else timeout_s))
    return _asked[kernel]


def names_at(path):
    """同 table.names_of，讀的是給定的那份表檔。"""
    st = aos_flags.read_window(_pkg.PROG, path)
    out = dict(NAMES)
    if isinstance(st, dict):
        for key in NAMES:
            value = st.get(key)
            if isinstance(value, str) and value:
                out[key] = value
            elif key == "procs_requests" and key in st and value is None:
                out[key] = None
    return out


def state_at(path):
    """同 table.state，讀的是給定的那份表檔：切檔與各列的相對路徑（stack、ws、exec、def）都從表檔所在的資料夾算、交出去一律絕對。"""
    from .table import mailbox_warning, resolve, table
    base = os.path.dirname(os.path.abspath(path))
    if not os.path.isfile(path):
        raise Fail("StateMissing", "%s not found (daemon not started yet, or procs_state is off)" % path)
    for attempt in range(2):
        try:
            with open(path, encoding="utf-8") as fh:
                st = json.load(fh)
            procs = table(base, st.get("procs", {}))
            return {"daemon": st.get("daemon"),
                    "mailbox_warning": mailbox_warning(base),
                    "procs": {n: resolve(base, r) if isinstance(r, dict) else r for n, r in procs.items()}}
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            if attempt:
                raise Fail("StateBad", "cannot parse %s: %s" % (path, exc))
            time.sleep(0.05)


def rows_at(path):
    return state_at(path)["procs"]
