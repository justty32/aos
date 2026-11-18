# aos/apps/agent/common.py - 共用分層 help、錯誤指路、旗標、找 daemon 與表上的一隻（設了 AOS_KERNEL 先問表在哪再讀；ctl 動作才用的寄信等回信在 ctl/shared.py）。
import json
import os
import textwrap
from . import PROG
from aos import flags as aos_flags
from aos import daemon_ctl as dc

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))     # proto8/ (this file is lib/aos/apps/agent/common.py)
TOOLS = os.path.join(ROOT, "bin", "aos-tools")
dc.PROG = PROG
POLL = 0.2                                      # listen 看一次的間隔（秒）
DECL = "interfaces.json"                        # 宣告檔（03）
IFACE = "aos-agent"

# ---------------------------------------------------------------- daemon（共用 daemon_ctl 模組）

TOP = {}                                        # main 的頂層 opts（--daemon、--target；11-10 Q1 起寫在子命令後的也寫回這份）
TOP_TARGET = None                               # main 裡從子命令前的 --target 定（坑-68）
QUERY_S = None                                  # ctl ls／who／where／state 的 --timeout-s：等查詢信回信的秒數（None＝daemon_ctl 的預設 3 秒）


class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(str(msg).replace("\n", " "))
        self.code = code


def in_stack(path, a):
    """訊息裡寫 agent stack 裡的檔：「<相對 stack> in the stack of <名>」，不在它的 stack 裡＝照原樣（11-12 線 errpath：
    self_* 工具把錯誤行接進 history，history 進 git；N-67 ⑦、同 history 結果行的 where_said）。呼叫者給的路徑照字面印，不經這裡。"""
    if a is None:
        return path
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(a.stack))
    if rel == ".." or rel.startswith(".." + os.sep):
        return path
    return "the stack of %s" % a.name if rel == "." else "%s in the stack of %s" % (rel, a.name)


def note(msg):
    """提醒（不是錯）：stderr 一行 `aos-agent: warning: 句子`（11-05 R1；原本是括號一行）。"""
    aos_flags.warn(PROG, msg)


def usage_of(help):
    """HELP 的第一個 usage 是錯誤行與群組導航的唯一來源（接成一行的規則在 aos_flags.usage_of）。"""
    return aos_flags.usage_of(help, USAGE_STOP)


USAGE_STOP = ("aos-agent ", "...")   # help 裡第二種寫法的開頭（`aos-agent X --help`、`... | aos-agent …`）：usage 接到這裡停


def bad_args(help, reason):
    return Fail("ArgumentsBad", "%s (usage: %s)" % (reason, usage_of(help)))


def actions(helps, prefix):
    """由動作的 usage 與 NAME 生群組導航，不重抄命令語法或摘要。"""
    out = []
    for help in helps:
        usage = usage_of(help).removeprefix(prefix)
        name = help.splitlines()[0].split(" - ", 1)[1]
        entry = "  %s%s" % (usage.ljust(max(24, len(usage) + 2)), name)
        if len(entry) <= 100:
            out.append(entry)
        else:
            out.append("  " + usage)
            out.extend(textwrap.wrap(name, width=100, initial_indent="                          ",
                                     subsequent_indent="                          "))
    return "\n".join(out)


def parse(argv, flags=None, switches=None, *, help=None, short=None, sub=None, keep=None):
    try:
        return aos_flags.parse(argv, flags or {}, switches, help=help, short=short, sub=sub, keep=keep)
    except aos_flags.Error as e:
        if e.code == "ArgumentsBad" and help:
            raise bad_args(help, str(e)) from e
        path = help.splitlines()[0].split(" - ", 1)[0] if help else PROG
        raise Fail(e.code, "%s (see %s --help)" % (e, path)) from e


def call_dc(fn, *args, **kwargs):
    """共用模組的錯只在這裡換成這支的代號。"""
    try:
        return fn(*args, **kwargs)
    except dc.Fail as e:
        raise Fail({"ProcMissing": "InstanceMissing"}.get(e.code, e.code), str(e)) from e


def via_kernel():
    """走 kernel 那條路（kernel-framework 03）：設了 AOS_KERNEL，而且沒明給 --daemon。"""
    return dc.via_kernel(TOP.get("daemon"))


def table_ref():
    """這次讀的那份表：沒走 kernel＝daemon 的資料夾（照舊）；走 kernel＝寄查詢信問來的表檔（TableFile，一次執行只問一次；
    問不到＝KernelFailed，不退回去讀 AOS_DAEMON）。daemon_ctl 的 rows／row_of／cell_of／names_of／write_ctl 兩種都吃。"""
    if not via_kernel():
        return call_dc(dc.find_daemon, TOP.get("daemon"))
    return call_dc(dc.state_path, TOP.get("daemon"), QUERY_S)


def daemon_path():
    """沒走 kernel＝那台 daemon 的 stack（--daemon ＞ $AOS_DAEMON ＞ ./.stack）；走 kernel＝問來那份表所在的資料夾
    （ctl who --json 的 daemon 欄照字面＝這次讀的表在哪個資料夾；daemon 自己答時就是它的 stack）。"""
    ref = table_ref()
    return os.path.dirname(ref) if isinstance(ref, dc.TableFile) else ref


def table():
    """讀表：daemon 的表，或走 kernel 時問來的那份（路徑欄已拼回絕對）。"""
    return {n: r for n, r in call_dc(dc.rows, table_ref()).items() if isinstance(r, dict)}


def under(path, top):
    p, t = os.path.realpath(path), os.path.realpath(top).rstrip("/")
    return p == t or p.startswith(t + "/")


def owner_row(s, rows):
    """S 落在哪一列的 stack 裡（那列的 stack 是 S 本身或 S 的上層；好幾列都包住＝取最深的）；回 (名, 列) 或 None。ctl who 與 ctl add 查 parent 共用。"""
    hit = None
    for n, r in rows.items():
        st = r.get("stack")
        if isinstance(st, str) and st and under(s, st):
            if hit is None or len(os.path.realpath(st)) > len(os.path.realpath(hit[1]["stack"])):
                hit = (n, r)
    return hit


REGISTERED = (("parent", dc.PARENT_ENV), ("notify_box", dc.NOTIFY_ENV))   # ok-devt-1114 05 定稿 1.3：表的欄、啟動單子 envs 的名字（名字定義在 daemon_ctl）


def _launch_single(row, base):
    """列的啟動單子（物件）或 None。帶 envs 掛的列，daemon 把 launch.exec 記成指到小格的一條指標：exec 型 ["procs/<名>/exec.json#/exec"]，
    loop 型 ["procs/<名>/loop.json#/_entry"]（單子在同檔的 /exec）；相對路徑從表所在的資料夾（base）算。內嵌物件也認。
    讀不到（檔不在、經 kernel 刪減過的表、指標壞）＝None。"""
    launch = row.get("launch")
    ex = launch.get("exec") if isinstance(launch, dict) else None
    if isinstance(ex, dict):
        return ex
    if isinstance(ex, list) and ex:
        ex = ex[0]
    if not isinstance(ex, str) or "#" not in ex:
        return None
    f, _, ptr = ex.partition("#")
    if not f.endswith(".json"):
        return None
    if not os.path.isabs(f):
        if base is None:
            return None
        f = os.path.join(base, f)
    try:
        with open(f, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    node = doc
    for part in [p.replace("~1", "/").replace("~0", "~") for p in ptr.split("/")[1:]]:
        node = node.get(part) if isinstance(node, dict) else None
    if isinstance(node, dict) and "argv" in node:
        return node
    single = doc.get("exec")                 # loop 型：指標指 /_entry，單子在 /exec
    return single if isinstance(single, dict) else None


def _registered(row, single, field, env, mine):
    """一格登記（parent 或 notify_box）照 05 定稿 1.3 的順序讀：① 列上的欄（第 2 期 daemon 寫）；② 那列啟動單子的 envs（第 1 期）；
    ③ 查的是自己＝自己的環境變數。前一處有這個鍵（含空字串＝明確沒有）就不看後面；空白、非字串、全讀不到＝None。
    只取這一個名字，不輸出別的 envs（可能帶金鑰）。"""
    if field in row:
        v = row[field]
        return v.strip() or None if isinstance(v, str) else None
    envs = single.get("envs") if isinstance(single, dict) else None
    if isinstance(envs, dict) and env in envs:
        v = envs[env]
        return v.strip() or None if isinstance(v, str) else None
    if mine:
        return os.environ.get(env, "").strip() or None
    return None


def registered_of(row, base=None):
    """{"parent": …, "notify_box": …}：add 時請求方寫的登記，字串或 None；是登記不是證明。base＝表所在的資料夾（daemon_path()）。"""
    row = row if isinstance(row, dict) else {}
    stack = row.get("stack")
    me = os.environ.get("AOS_STACK", "")
    mine = bool(me and isinstance(stack, str) and stack and under(me, stack))
    single = None if all(field in row for field, _ in REGISTERED) else _launch_single(row, base)
    return {field: _registered(row, single, field, env, mine) for field, env in REGISTERED}


class Agent:
    """表上的一隻：name、row（那一列；路徑欄 daemon_ctl 已拼回絕對）、stack、ws、phase、reason。"""

    def __init__(self, name, row):
        self.name, self.row = name, row
        self.stack = (row.get("stack") or "").rstrip("/") or "/"
        self.ws = row.get("ws") or os.getcwd()
        self.phase = row.get("phase")
        r = row.get("reason")
        self.reason = None if r is None else str(r).replace("\n", " ")


def kernel_box():
    """$AOS_KERNEL（ctl 的信先寄那裡給判官，11-05 kernel-daemon）；沒設＝None。"""
    k = os.environ.get("AOS_KERNEL", "")
    return os.path.realpath(k) if k else None


def queue_position(letter):
    k = kernel_box()
    if not k:
        return None
    try:
        with open(os.path.join(os.path.dirname(k), "queue.json"), encoding="utf-8") as fh:
            rows = json.load(fh).get("queued", [])
        return next((i for i, row in enumerate(rows, 1) if isinstance(row, dict) and row.get("letter") == letter), None)
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def row_named(name):
    return table().get(name)


def find(name):
    r = table().get(name)
    if r is None or not isinstance(r.get("stack"), str) or not r.get("stack"):
        raise Fail("InstanceMissing", "%s is not on the daemon table (removed with rm, exited 0, or an adopted body ended with unknown status; known nonzero exits stay stopped with a reason; the stack may still be there: aos-agent ctl add with the same name to pick it up again)" % name)
    return Agent(name, r)


def target_name(opts):
    """子命令後的 --target ＞ 子命令前的 --target ＞ $AOS_AGENT；前後都給又不同＝ArgumentsBad（11-10 坑-68 代定）。"""
    sub = opts.get("target")
    if sub and TOP_TARGET and sub != TOP_TARGET:
        raise Fail("ArgumentsBad", "two different targets: %s before the subcommand, %s after it; give --target once" % (TOP_TARGET, sub))
    return sub or TOP_TARGET or os.environ.get("AOS_AGENT", "")


def target(opts):
    """target_name；都沒有＝TargetMissing。"""
    name = target_name(opts)
    if not name:
        raise Fail("TargetMissing", "no target: add --target NAME, or export AOS_AGENT=NAME (or source using-aos-agent.sh NAME)")
    return find(name)
