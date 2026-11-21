"""kernel_spec - 給人寫 kernel 定義的輔助（寫 kernel.py 的人叫它 defs：from aos.py.kernel import defs）：defs.Kernel(...) 宣告一個 kernel，.compile(夾) 編出一份定義夾、.dry_run() 只算；kernel.py 最後一行是 defs.main(物件)。

使用者 11-20 選項框待裁第 9 題「from aos.py.kernel import defs」（設計稿 thinking/2026-11/20/aos-pylib-plan-1120/02「kernel 以後怎麼接上」）；
11-21「編譯的kernel入口那塊可以派」（線 top-1121-kdefs）。寫法比照 agent 那邊（aos/agent_spec）：一個物件、兩個方法（.dry_run()／.compile(夾)），
命令列殼與 Unit 共用 aos/spec_unit，例外與寫檔後端共用 aos/spec_base，@fn.hook 的函數照樣抽成 fn/<名>.py（aos/fn_spec）。
編譯出的夾就是 templates/kernel/ 那幾種手寫夾的樣子（procs-kernel、daemon-kernel、llm-kernel）：重新編譯直接蓋，產出後的 json 照常能改（C 與 .o）。

宣告用的（寫錯在 .dry_run()／.compile()／defs.main 才報 SpecBad）：
  Kernel(說明, knobs=None, hooks=None, program="kernel", body=None)
      program  "kernel"＝框架站（掛 proc 那一站：白名單、同時幾個…）、"kernel_llm"＝llm kernel（問腦那一站；多一份 interfaces.json 的 aos-ledger）
      knobs    kernel.json 的其餘鍵，原樣寫進去（鍵的意思看 templates/kernel/README.md；不認得的鍵程式不管，這裡也不驗）
      hooks    一張表 {名字: 一格}、@fn.hook 的函數、或它們的串列（後面的同名蓋前面、None 拿掉）；
               判前、判後、代回之前三個點寫進 kernel.json 的 hooks；身體是 loop 時 aos-loop 的四個點寫進 loop_hooks.json
      body     defs.loop(every_ms=300)＝掛成 daemon 底下的一列（aos-loop loop.json，同 procs-kernel）、
               defs.daemon(every_ms=300)＝自己一台 daemon（aos-daemon daemon.json，帶清道夫列，同 daemon-kernel、llm-kernel）；
               兩個都收任意鍵，原樣寫進那份 json、不檢查、同名蓋過編譯寫的（11-21 使用者「任意鍵照傳」，同 agent 的 defs.loop）；
               不給＝照起手範本 start-api：kernel 用 loop、kernel_llm 用 daemon
  home(路徑)／env(變數, 路徑)  指示詞，同 agent 那邊
main(物件)：kernel.py 最後一行；--compile [資料夾]、--dry-run、--help。
不做的（回報列著）：defs.load、defs.extern、files=、endpoint 程式（llm-kernel 的 endpoints/、fake_slow 照舊手寫、編譯不碰）。
"""
import json, os, sys

from aos import flags
from aos import fn_spec, hook_point, hook_run
from aos import spec_base, spec_unit
from aos.spec_base import SpecBad, DefBad  # noqa: F401（對外的名字：defs.SpecBad、defs.DefBad）
from aos.agent_spec import home, env  # noqa: F401（對外的名字：defs.home、defs.env，同 agent 那邊）
from aos.agent_spec import _every     # defs.loop／defs.daemon 跟 agent 的 defs.loop 同一套（every_ms＋任意鍵照傳，11-21）

PUBLIC = ("Kernel", "main", "loop", "daemon", "home", "env", "SpecBad", "DefBad")
FIELDS = ("description", "knobs", "hooks", "program", "body")
PROGRAMS = ("kernel", "kernel_llm")
DEFAULT_BODY = {"kernel": "loop", "kernel_llm": "daemon"}      # 照 templates/start-api：perm 是 loop、llm 是 daemon
_LIB = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))   # py/ 或裝好的 lib/
KERNEL_POINTS = os.path.join(_LIB, "tools", "aos", "kernel", "hook_points.json")   # kernel、kernel_llm 共用這三個點
LOOP_POINTS_ENV = {"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_points.json"}
LOOP_HOOKS = "loop_hooks.json"
SWEEPER = {"exec": {"argv": ["aos-sweeper", "--retention-days", "7", "--report", {"$env": "AOS_STACK", "$path": "sweeper_report.json"}]},
           "interval_ms": 600000, "auto_restart": True, "stuck_after_ms": 600000}   # 同 templates/kernel/daemon-kernel 的 _sweeper 列
LEDGER = {"description": "Declare the stack ledger interface", "aos-ledger": {"file": "ledger.jsonl"}}   # 同 templates/kernel/llm-kernel
RENAME_LAST = {"daemon.json": 1, "loop.json": 1, "interfaces.json": 2, "_entry": 3}   # 被指的檔先換、_entry 最後（其他＝0）
HELP = """\
usage: python3 kernel.py --compile [FOLDER] | --dry-run | --help
Compile kernel.py into an aos kernel definition (a folder of JSON files), like a C compiler
turning a .c file into a .o file. kernel.py declares the kernel as an object and ends with
defs.main(it): k = defs.Kernel("what it does", knobs={"max_running": 2}, hooks=[...]).
  --compile [FOLDER]  compile and write the definition files into FOLDER (default: the folder
                      of kernel.py). Compiling again overwrites, as a whole, every file kernel.py
                      declares; README.md is written only when it is missing; every other file
                      (.env, endpoint programs...) is left alone.
  --dry-run           compile and print everything --compile would write, as one JSON object
                      {"file name": content}, and write nothing.
program="kernel" (the default) is the station that admits procs; program="kernel_llm" is the llm kernel.
knobs= is the rest of kernel.json, written as given (keys: templates/kernel/README.md).
body=defs.loop(every_ms=300) mounts it as one row of a daemon (aos-loop); body=defs.daemon(every_ms=300)
makes it a daemon of its own, with a sweeper row. Default: loop for kernel, daemon for kernel_llm.
Any other keyword of defs.loop / defs.daemon goes into loop.json / daemon.json as it is, unchecked, and
replaces a key of the same name that compiling writes (like defs.daemon(procs={...}): no sweeper row then).
hooks= takes a dict {name: entry}, functions marked @fn.hook("before_verdict") (from aos.py import fn),
or a list of those; a function is pulled out into a program fn/<name>.py of the folder. Hooks of
before_verdict, after_verdict and before_reply go into kernel.json; with body=defs.loop(...), hooks of
after_start, after_stop, before_run and after_run go into loop_hooks.json.
Without defs.main (a build script, the REPL): k.dry_run() gives the files, k.compile(FOLDER) writes them.
Then mount it: aos-daemon-ctl add FOLDER (or copy it under the tree first).
On a wrong declaration: one line "NAME: error: SpecBad ..." on stderr, exit 1, nothing written.
"""


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    raise AttributeError("defs has no %s (it has %s)" % (name, ", ".join(PUBLIC)))


def loop(*, every_ms=None, **keys):
    """body=defs.loop(every_ms=300)：掛成 daemon 底下的一列，aos-loop 每 every_ms 毫秒跑一輪（loop.json；不給＝300）。
    其他鍵原樣寫進 loop.json、不檢查，同名蓋過編譯寫的（11-21 使用者「任意鍵照傳」，同 agent 的 defs.loop）。"""
    return _every("loop", every_ms, keys)


def daemon(*, every_ms=None, **keys):
    """body=defs.daemon(every_ms=300)：自己一台 daemon，每 every_ms 毫秒跑一輪（daemon.json，帶清道夫列；不給＝300）。
    其他鍵原樣寫進 daemon.json、不檢查，同名蓋過編譯寫的（procs 也是：給了就沒有清道夫列）。"""
    return _every("daemon", every_ms, keys)


def _points(body):
    """{事件: 宣告} 這個 kernel 收的 hook 點、哪些寫進 loop_hooks.json。"""
    points = hook_point.read([KERNEL_POINTS])
    loop_points = hook_point.read([hook_point.provider_path("aos-loop")]) if body == "loop" else {}
    return points, loop_points


def _stack_hooks(hooks, events):
    """hooks 疊起來 → {名字: 格}：一張表、@fn.hook 的函數、或它們的串列；後面的同名蓋前面、None 拿掉；每格照 hook 引擎驗（事件照 events）。"""
    layers = list(hooks) if isinstance(hooks, (list, tuple)) else [hooks]
    table, by_fn = {}, {}
    for layer in layers:
        if callable(layer) and not isinstance(layer, dict):
            name, entry = fn_spec.hook_entry(layer)
            if name in by_fn:
                raise SpecBad("hooks: two functions are both hook %s (%s and %s): give one another name, @fn.hook(..., name=\"...\")"
                              % (name, by_fn[name], layer.__name__))
            by_fn[name] = layer.__name__
            layer = {name: entry}
        if not isinstance(layer, dict):
            raise SpecBad("hooks must be a dict {hook name: entry}, a function marked @fn.hook, or a list of those (later ones win, None drops a hook)")
        for name, entry in layer.items():
            if not isinstance(name, str):
                raise SpecBad("hooks: hook name %r must be a string" % (name,))
            table.pop(name, None)
            if entry is None:
                continue
            try:
                hook_run.validate_name(name)
            except hook_run.HooksBad as e:
                raise SpecBad("hooks: hook name %r %s" % (name, e))
            try:
                hook_run.validate_entry({k: v for k, v in entry.items() if k != fn_spec.KEY} if isinstance(entry, dict) else entry, events)
            except hook_run.HooksBad as e:
                raise SpecBad("hooks: hook %s: %s" % (name, e))
            table[name] = entry
    return table


def _plain(out):
    try:
        return json.loads(json.dumps(out, allow_nan=False))
    except (TypeError, ValueError) as e:
        raise SpecBad("a declared value cannot be written as JSON (%s); use strings, numbers, lists and dicts" % e)


class Kernel(spec_unit.Unit):
    """一個 kernel 的定義：defs.Kernel(說明, knobs=None, hooks=None, program="kernel", body=None)。欄位是普通屬性、可以改。"""

    def __init__(self, description, *, knobs=None, hooks=None, program="kernel", body=None):
        self.description, self.knobs, self.hooks, self.program, self.body = description, knobs, hooks, program, body

    def __setattr__(self, name, value):
        if not name.startswith("_") and name not in FIELDS:
            raise AttributeError("defs.Kernel has no field %s (fields: %s)" % (name, ", ".join(FIELDS)))
        object.__setattr__(self, name, value)

    def __repr__(self):
        return "<defs.Kernel(%r)>" % (self.description,)

    def _body(self):
        if self.program not in PROGRAMS:
            raise SpecBad("program must be one of %s, got %r" % (", ".join(PROGRAMS), self.program))
        body = self.body if self.body is not None else {"kind": DEFAULT_BODY[self.program], "every_ms": None, "keys": {}}
        if isinstance(body, dict) and body.get("kind") == "bad":
            raise SpecBad(body["bad"])
        if not isinstance(body, dict) or body.get("kind") not in ("loop", "daemon"):
            raise SpecBad("body must come from defs.loop(every_ms=...) or defs.daemon(every_ms=...), got %r" % (body,))
        every_ms, keys = body.get("every_ms"), body.get("keys") or {}
        given = keys.get("interval_ms")                 # 直接給 interval_ms（照傳、不驗）：說明裡的毫秒數跟著它，是整數才跟
        if every_ms is None and isinstance(given, int) and not isinstance(given, bool):
            every_ms = given
        return body["kind"], 300 if every_ms is None else every_ms, keys

    def events(self):
        """這個 kernel 收的 hook 事件表（引擎的形狀）：kernel 的三個點，身體是 loop 時再加 aos-loop 的四個。"""
        points, loop_points = _points(self._body()[0])
        return hook_point.engine_table(dict(points, **loop_points))

    def _files(self, folder, warn):
        """→ {檔名: 內容}；全部驗完才回，錯丟 SpecBad。"""
        description = self.description
        if not isinstance(description, str) or not description.strip():
            raise SpecBad("description must be a non-empty string: one sentence saying what the kernel does")
        description = description.strip()
        body, every_ms, body_keys = self._body()
        knobs = {} if self.knobs is None else self.knobs
        if not isinstance(knobs, dict) or not all(isinstance(k, str) for k in knobs):
            raise SpecBad("knobs must be a dict of kernel.json keys, like {\"max_running\": 2} ({} = manage nothing, pass everything on)")
        for k, use in (("description", "the first argument of defs.Kernel"), ("hooks", "hooks=")):
            if k in knobs:
                raise SpecBad("knobs must not set %s: use %s" % (k, use))
        points, loop_points = _points(body)
        events = self.events()
        kernel_json = dict({"description": description}, **knobs)
        loop_hooks = None
        if self.hooks is not None:
            table = _stack_hooks(self.hooks, events)
            kernel_json["hooks"] = {n: e for n, e in table.items() if e["event"] in points}
            if body == "loop":
                loop_hooks = {"description": "Hooks on the four aos-loop points of this kernel (after_start, after_stop, before_run, after_run).",
                              "hooks": {n: e for n, e in table.items() if e["event"] in loop_points}}
        exec_ = {"argv": ["aos-exec", home("/lib/tools/aos/%s" % self.program), {"$env": "AOS_CD", "$path": "kernel.json"}]}
        out = {}
        if body == "loop":
            out["_entry"] = {"description": "Mount this kernel as one row of the current daemon: aos-loop with loop.json.",
                             "argv": ["aos-loop", "loop.json"]}
            out["loop.json"] = {**_loop_json(exec_, every_ms), **body_keys}       # 任意鍵照傳、你給的蓋過去（11-21）
        else:
            out["_entry"] = {"description": "Start this kernel as a daemon of its own, with stdout logs.",
                             "argv": ["aos-daemon", "--enable-logs", "daemon.json"]}
            out["daemon.json"] = {"description": "Run %s over kernel.json every %d ms; the _sweeper row cleans old stacks."
                                                 % (self.program, every_ms),
                                  "exec": exec_, "interval_ms": every_ms, "procs": {"_sweeper": SWEEPER}, **body_keys}
        out["kernel.json"] = kernel_json
        if loop_hooks is not None:
            out[LOOP_HOOKS] = loop_hooks
        if self.program == "kernel_llm":
            out["interfaces.json"] = LEDGER
        out["README.md"] = description + "\n"
        out = _plain(out)
        programs = {}
        for doc, file in (("kernel.json", "kernel.json"), (LOOP_HOOKS, LOOP_HOOKS)):
            if doc in out and out[doc].get("hooks"):
                more = fn_spec.programs(None, None, out[doc], file, events)
                for name in more:
                    if name in programs:
                        raise SpecBad("%s is the program of two hooks: give one another name (name=)" % name)
                programs.update(more)
        out.update(programs)                    # fn/<名>.py：程式檔（755），不經 _plain
        return out

    def _write(self, folder, files):
        """files 寫進 folder；README.md 在就不寫，其餘交給 spec_base.write_files（暫存檔＋照 RENAME_LAST 改名）。"""
        plan = {n: v for n, v in files.items() if not (n == "README.md" and os.path.lexists(os.path.join(folder, n)))}
        spec_base.write_files(folder, plan, last=RENAME_LAST)
        done = ["wrote %s" % os.path.join(folder, name) for name in plan]
        if len(plan) < len(files):
            done.append("kept %s (it is already there)" % os.path.join(folder, "README.md"))
        return done


def _loop_json(exec_, every_ms):
    """同 templates/kernel/procs-kernel/loop.json：aos-loop 的四個點經 aos-hook fire 接到同夾的 loop_hooks.json（檔不在＝沒有 hook）。"""
    def fire(point):
        return {"argv": ["aos-hook", "fire", "-q", "--points", dict(LOOP_POINTS_ENV), "--list",
                         {"$env": "AOS_CD", "$path": "/" + LOOP_HOOKS}, point]}
    return {"description": "Run the kernel once every %d ms over kernel.json. The four aos-loop hook points (after_start, after_stop, "
                           "before_run = before each round, after_run = after it) fire through aos-hook with the hooks of loop_hooks.json "
                           "next to this file (no such file = no hooks); before_run / after_run only while their flag file is in the stack "
                           "(hook_before_run.flag, hook_after_run.flag, set at start and by aos-hook check)." % every_ms,
            "exec": exec_, "interval_ms": every_ms,
            "on_start": fire("after_start"), "on_stop": fire("after_stop"),
            "on_before_run": fire("before_run"), "on_before_run_if": {"$env": "AOS_STACK", "$path": "/hook_before_run.flag"},
            "on_after_run": fire("after_run"), "on_after_run_if": {"$env": "AOS_STACK", "$path": "/hook_after_run.flag"}}


def main(*args, **kw):
    """kernel.py 的最後一行：defs.main(defs.Kernel(...))。只收一個物件。被普通 import（叫它的模組不是 __main__）＝印一行 warning、什麼都不做。"""
    caller = sys._getframe(1)
    script = os.path.realpath(caller.f_code.co_filename)
    prog = spec_base.prog_name(script, "kernel.py")
    unit = args[0] if len(args) == 1 and not kw else None
    if caller.f_globals.get("__name__") != "__main__":
        flags.warn(prog, "%s was imported, not run, so its defs.main(...) does nothing" % script)
        return
    if not isinstance(unit, Kernel):
        got = ("keyword arguments %s" % ", ".join("%s=" % k for k in kw) if kw else
               "%d arguments" % len(args) if len(args) != 1 else "a value of type %s" % type(args[0]).__name__)
        flags.die(prog, "SpecBad", "defs.main takes one kernel: defs.main(defs.Kernel(\"what it does\", knobs={...})); got %s "
                                   "(fix the declaration in %s)" % (got, os.path.basename(script)))
    spec_unit.main(unit, script, "kernel.py", HELP)
