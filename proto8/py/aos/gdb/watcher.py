"""aos.gdb.watcher - 觀察者（丙）：另一支掛在 daemon 表上的普通 proc（名字 gdbw_ 開頭），每隔 every_ms 看一次目標 agent 的檔，條件成立（連續 times 次）就 ctl pause 目標並在它的 gdb/log.jsonl 留字條（by "watch"）；完全不碰目標的定義與 hook。

使用者 11-19：條件可以「另外開個proc，觸發之後直接把要debug的那個proc停下來」；「丙可以繼續」。圖紙：thinking/2026-11/19/aos-gdb-1119/05、07 的 T7
（輪詢 observed.jsonl、看到就 pause，約 2.5 秒內停住、晚一格）、aos-gdb-lib-第二版.md。
為什麼掛在 daemon 表上、不是 REPL 外的背景程式：REPL 關了照樣在；表上看得到（aos-daemon-ctl ls）、停得掉（rm）、daemon 收工就一起睡、重起一起醒；
自己壞了（設定壞、行程掛）＝表上那一列 stopped 帶原因，目標照跑。它就是一個 aos-loop：loop.json 的 exec 是 lib/tools/agent/gdb_watch，每一圈看一次。

檔（觀察者自己的 stack：<daemon>/procs/gdbw_<名>/）：
    watch_loop.json   交給 aos-daemon-ctl add 的 aos-loop 設定（daemon 再照它寫自己的 loop.json）（exec＝gdb_watch、interval_ms＝every_ms、ctl／state／state_flux）
    watch.json        設定：{"proc": 表上的名字, "targets": [名字...], "daemon": 絕對路徑, "kind": "sh" | "py", "sh": 字串, "py": {...},
                            "times": N, "once": bool, "about": 一句英文}
    watch_state.json  每個目標的數：{名字: {"seen", "streak", "fired", "armed", "last_error", "stack", "mem"}}
條件（每一圈、每個目標各判一次；目標停著（paused 或扣在斷點上）時不判）：
    py＝函式 f(t) 或運算式字串（變數 t）；t 是這個目標的 Look（t.name、t.stack、t.history(n)、t.observed(n)、t.where()、t.file(rel)、t.queue()…），
        t.mem 是一個跨圈留著的 dict（存進 watch_state.json，要是 JSON 值）——拿來看跨好幾格的事（例：記上次看到幾行）；20 秒沒回＝條件壞了。
    sh＝`sh -c 字串`，cwd＝目標的 stack，環境多 GDB_TARGET（名字）、GDB_STACK（stack），stdin＝{"target", "stack"}；退 0＝算、10＝不算、其他＝壞了。
防誤報：times＝連續幾圈都成立才算；停過一次之後要先看到一次「不成立」才會再停（armed），免得一個一直成立的條件在每次續了之後馬上又停。
不印東西、不 sys.exit；錯丟 trigger.Bad（設定不對）或 look.Failed（指令失敗）。"""
import json
import os
import signal

from aos.gdb import trigger
from aos.gdb.look import Look, Failed, run

PREFIX = "gdbw_"                                # 觀察者在 daemon 表上的名字一律以此開頭
SPEC = "watch.json"
STATE = "watch_state.json"
LOOP = "watch_loop.json"                   # 不能叫 loop.json：那是 daemon 在每個 proc 的 stack 裡自己寫的那份
BODY = {"$env": "AOS_HOME", "$path": "/lib/tools/agent/gdb_watch/_entry"}
KINDS = ("sh", "py")
PY_TIMEOUT_S = 20
PAUSE_S = 10


class Target(Look):
    """觀察者條件函式拿到的 t：一個目標 agent 的檢閱物件，外加 mem（跨圈留著的 dict）。"""

    def __init__(self, name, stack, daemon, mem=None):
        self.name, self.stack, self.daemon = name, stack, daemon
        self.mem = mem if isinstance(mem, dict) else {}

    def __repr__(self):
        return "<aos.gdb watch target %s (stack %s)>" % (self.name, self.stack)

    def agent(self, *args, quiet=True):
        return run(["aos-agent", "--daemon", self.daemon, "--target", self.name] + [str(x) for x in args], echo=False)


def validate(spec):
    """watch.json 的形狀；不對丟 trigger.Bad。"""
    if not isinstance(spec, dict):
        raise trigger.Bad("%s must be a JSON object" % SPEC)
    t = spec.get("targets")
    if not (isinstance(t, list) and t and all(isinstance(x, str) and x for x in t) and len(set(t)) == len(t)):
        raise trigger.Bad("targets must be a non-empty list of different agent names")
    if not (isinstance(spec.get("daemon"), str) and os.path.isabs(spec["daemon"])):
        raise trigger.Bad("daemon must be the absolute path of the daemon's stack")
    if not (isinstance(spec.get("proc"), str) and spec["proc"].startswith(PREFIX)):
        raise trigger.Bad("proc must be this watcher's name on the table (starting with %s)" % PREFIX)
    if spec.get("kind") not in KINDS:
        raise trigger.Bad("kind must be sh or py")
    if spec["kind"] == "sh" and not (isinstance(spec.get("sh"), str) and spec["sh"].strip()):
        raise trigger.Bad("kind sh needs a non-empty sh string")
    if spec["kind"] == "py" and not (isinstance(spec.get("py"), dict) and ("expr" in spec["py"] or "code" in spec["py"])):
        raise trigger.Bad("kind py needs py with code or expr")
    times = spec.get("times", 1)
    if not isinstance(times, int) or isinstance(times, bool) or times < 1:
        raise trigger.Bad("times must be a whole number >= 1")


def loop_config(every_ms):
    return {"description": "aos.gdb watcher: every round, check the targets once (lib/tools/agent/gdb_watch); a hit pauses the target.",
            "_entry": ["aos-loop", {"$env": "AOS_CF"}], "exec": {"argv": [BODY]}, "interval_ms": every_ms,
            "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"}


def _alarm(signum, frame):
    raise TimeoutError("no answer in %d s" % PY_TIMEOUT_S)


def check(spec, t):
    """這一圈對這個目標成不成立；條件壞了丟 trigger.Bad。"""
    if spec["kind"] == "sh":
        env = dict(os.environ, GDB_TARGET=t.name, GDB_STACK=t.stack)
        return trigger.run_sh(spec["sh"], json.dumps({"target": t.name, "stack": t.stack}), cwd=t.stack, env=env)
    fn = trigger.unpack_py(spec["py"])
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(PY_TIMEOUT_S)
    try:
        return trigger.call_py(fn, t)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def stack_of(name, daemon):
    """目標的 stack（aos-agent ctl state --json who）；找不到丟 Failed。"""
    out = run(["aos-agent", "--daemon", daemon, "--target", name, "ctl", "state", "--json", "who"], echo=False)
    stack = json.loads(out).get("who", {}).get("stack")
    if not isinstance(stack, str) or not stack:
        raise Failed("watch", "cannot tell where the stack of %s is" % name)
    return stack


def stopped(stack):
    """目標現在停著或正要停：ctl pause 已套用（state.json 的 paused）、扣在斷點上（gdb/hold.json 的 handler 還活著），
    或 ctl.json 裡有還沒套用的 pause／stop（那一格還沒做完；Argon A7：不然同一格裡會重複發 pause）。"""
    st = trigger.read_json(os.path.join(stack, "state.json"), {}) or {}
    return st.get("paused") is True or trigger.read_hold(stack) is not None or trigger.ctl_unapplied(stack) is not None


def pause(name, daemon):
    """aos-agent ctl pause --no-wait；回 "sent" 或失敗的一句。"""
    try:
        run(["aos-agent", "--daemon", daemon, "--target", name, "ctl", "pause", "--no-wait"], echo=False)
    except Failed as e:
        return "failed: %s" % e
    return "sent"


def round_(spec, state, warn=None):
    """一圈：每個目標判一次，成立（連續 times 次、armed）就停它、留字條。回新的 state（不寫檔）。"""
    state = dict(state or {})
    for name in spec["targets"]:
        st = dict({"seen": 0, "streak": 0, "fired": 0, "armed": True, "last_error": None, "stack": None, "mem": {}}, **(state.get(name) or {}))
        state[name] = st
        if spec.get("once") and st["fired"]:
            continue
        if st["stack"] and (st["seen"] % 20 == 19 or not os.path.isdir(st["stack"])):
            try:                                 # 偶爾重核一次 stack（目標被 rm 又加回來會換 stack；Argon A8）
                now = stack_of(name, spec["daemon"])
            except (Failed, ValueError, AttributeError):
                now = None
            if now != st["stack"]:
                st.update(stack=None, streak=0, armed=True, mem={})
        if not st["stack"]:
            try:
                st["stack"] = stack_of(name, spec["daemon"])
            except (Failed, ValueError, AttributeError) as e:
                st["last_error"] = "cannot find %s: %s" % (name, e)
                if warn:
                    warn(st["last_error"])
                continue
        if stopped(st["stack"]):
            continue
        t = Target(name, st["stack"], spec["daemon"], st["mem"])
        st["seen"] += 1
        try:
            hit = check(spec, t)
            stage = t.where()                    # 判中那一刻的位置（Argon A9）
            json.dumps(t.mem)
        except trigger.Bad as e:
            hit, st["last_error"] = None, str(e)
        except (TypeError, ValueError) as e:
            hit, st["last_error"] = None, "t.mem must hold plain JSON values: %s" % e
        if hit is None:
            st["streak"] = 0
            if warn:
                warn("%s on %s: %s (counted as no hit)" % (spec["proc"], name, st["last_error"]))
            continue
        st["mem"] = t.mem
        if not hit:
            st["streak"], st["armed"] = 0, True
            continue
        if not st["armed"]:
            continue
        st["streak"] += 1
        if st["streak"] < spec.get("times", 1):
            continue
        result = pause(name, spec["daemon"])
        if result == "sent":                     # 停成了才算一次、才要等不成立再上膛（Argon A6：失敗下一圈照試）
            st["streak"], st["armed"] = 0, False
            st["fired"] += 1
        note = {"kind": "stop" if result == "sent" else "pause_failed", "at": trigger.now(), "by": "watch", "trigger": spec["proc"],
                "event": "watch", "how": "pause", "about": spec.get("about"), "times": spec.get("times", 1), "fired": st["fired"],
                "ctl_seq": trigger.ctl_seq(st["stack"]), "detail": {"target": name, "stage": stage}}
        if result != "sent":
            note["why"] = result
            st["stack"] = None                   # 下一圈重找（可能被 rm 又加回來、換了 stack）
            if warn:
                warn("%s: cannot pause %s: %s" % (spec["proc"], name, result))
        try:
            trigger.append_log(t.stack, note)
        except OSError as e:
            if warn:
                warn("%s: cannot write the note in %s: %s" % (spec["proc"], t.stack, e))
    return state


# ---- 庫：起、列、拿掉（aos.gdb 的 watch／watchers／unwatch 叫這些）----

def _table(daemon):
    out = run(["aos-daemon-ctl", "--daemon", daemon, "ls", "-j"], echo=False)
    return json.loads(out).get("procs", {}) or {}


def stack_dir(daemon, proc):
    return os.path.join(daemon, "procs", proc)


def add(daemon, targets, sh=None, py=None, times=1, once=False, every_ms=500, name=None, replace=False, echo=True):
    """起一個觀察者（aos-daemon-ctl add）；回它的短名（不含 gdbw_）。"""
    if isinstance(targets, str):
        targets = [targets]
    targets = list(targets or [])
    if (sh is None) == (py is None):
        raise Failed("watch", "give one condition: sh or py")
    if not isinstance(every_ms, int) or isinstance(every_ms, bool) or every_ms < 100:
        raise Failed("watch", "every_ms must be a whole number of milliseconds >= 100")
    table = _table(daemon)
    missing = [t for t in targets if t not in table]
    if missing:
        raise Failed("watch", "not on the daemon table: %s" % ", ".join(missing))
    if name is None:
        i = 1
        while "%sw%d" % (PREFIX, i) in table:
            i += 1
        name = "w%d" % i
    proc = PREFIX + name
    spec = {"proc": proc, "targets": targets, "daemon": daemon, "kind": "sh" if sh is not None else "py",
            "times": times, "once": bool(once), "every_ms": every_ms}
    try:
        if sh is not None:
            spec["sh"] = sh
        else:
            spec["py"] = trigger.pack_py(py, var="t", what="the target t")
        spec["about"] = "%s on %s%s%s" % ("sh `%s` exits 0" % sh if sh is not None else "the py condition is true", ", ".join(targets),
                                          " (%d checks in a row)" % times if times > 1 else "", ", once" if once else "")
        validate(spec)
    except trigger.Bad as e:
        raise Failed("watch", str(e)) from None
    if proc in table:
        if not replace:
            raise Failed("watch", "there is already a watcher named %s (replace=True to replace it)" % name)
        run(["aos-daemon-ctl", "--daemon", daemon, "rm", proc], echo=echo)
    stack = stack_dir(daemon, proc)
    os.makedirs(stack, exist_ok=True)
    trigger.write_json(os.path.join(stack, SPEC), spec)
    trigger.write_json(os.path.join(stack, STATE), {})
    trigger.write_json(os.path.join(stack, LOOP), loop_config(every_ms))
    run(["aos-daemon-ctl", "--daemon", daemon, "add", "--name", proc, "--stack", stack, os.path.join(stack, LOOP)], echo=echo)
    return name


def ls(daemon):
    """這個 daemon 上的觀察者：名字、表上的 phase／pid／reason、看誰、條件、每個目標的數。"""
    out = []
    for proc, row in sorted(_table(daemon).items()):
        if not proc.startswith(PREFIX):
            continue
        stack = stack_dir(daemon, proc)
        spec = trigger.read_json(os.path.join(stack, SPEC), {}) or {}
        state = trigger.read_json(os.path.join(stack, STATE), {}) or {}
        out.append({"name": proc[len(PREFIX):], "phase": row.get("phase"), "pid": row.get("pid"), "reason": row.get("reason"),
                    "targets": spec.get("targets"), "about": spec.get("about"), "every_ms": spec.get("every_ms"),
                    "per_target": {t: {k: v for k, v in (state.get(t) or {}).items() if k not in ("mem", "stack")}
                                   for t in spec.get("targets") or []}})
    return out


def rm(daemon, name, echo=True):
    """拿掉一個觀察者（aos-daemon-ctl rm：先停、等它退出，再從表上拿掉；它的 stack 留著給人看）。"""
    return run(["aos-daemon-ctl", "--daemon", daemon, "rm", PREFIX + name], echo=echo)
