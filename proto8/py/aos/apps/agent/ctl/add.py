# aos/apps/agent/ctl/add.py - 宣告檢查、掛上 agent 並等待 daemon 上表。
from aos import flags as aos_flags
from aos import daemon_ctl as dc
import json
import os
import re
from ..common import bad_args, Agent, Fail, IFACE, call_dc, daemon_path, note, owner_row, row_named, table, via_kernel
from .shared import ctl_wait, need_table, queued_opt, timeout_opt
from ..decl import read_decl
from . import kit as kit_mod


# ---------------------------------------------------------------- 子命令：動它的（步 5）

HELP = """aos-agent ctl add - attach one agent to the daemon

usage: aos-agent [--daemon D] ctl add [-n N] [-w WS | --ws-json J] [-s S | --stack-json J] [--path-json J] [--limits JSON] [--envs K=V ...] [--parent P] [--notify-box B] [--dotenv-override] [--auto-restart] [--kit KIT] [--timeout-s S] [--on-queued fail|ok] XXX

XXX is the agent folder (not a folder = PathMissing). Its interfaces.json may declare aos-agent;
without that the folder itself is the entry. A declared "entry" must be a relative path that exists
in the folder (else InterfaceBad). The letter goes through $AOS_KERNEL when that is set (a
warning line says so). Waits until the agent is on the table, then prints its stack; the
daemon refusing it = AddRejected.
With $AOS_KERNEL set (and no --daemon) it reads only the reply to its own letter: no table
lookup first, no check that the daemon is up; it prints the stack only when -s gave one
(otherwise a warning says to ask aos-agent ctl where N); paths in the letter stay absolute.

Paths on the table: one you type as an absolute path stays that absolute path; a relative one
(from the current directory, also the default workspace) is stored relative to the daemon's
stack, so moving the whole tree keeps working. A JSON string given to --ws-json or --stack-json
goes into the letter as written (a relative one counts from the daemon's cwd); one given to
--path-json is read like XXX.

flags:
  -n, --name N        its name on the table (default: the folder name of XXX)
  -w, --ws WS         its workspace (default: non-empty $AOS_WS, else the current directory)
  -s, --stack S       its stack (default: <daemon stack>/procs/<name>/)
      --ws-json J     the workspace as JSON put into the table as written: a string, or a directive
                      such as '{"$env": "PROJ"}'; resolved again on every start (excludes -w)
      --stack-json J  the same for the stack (excludes -s)
      --path-json J   the agent folder as JSON instead of XXX: a string, or {"$env": "X", "$path": "/sub"};
                      the table keeps the directive and resolves it again on every start
      --envs K=V      child environment variable (repeatable; set through an exec single)
                      the value is stored in plain text in procs/<name>/exec.json and shows on
                      the command line: never pass secrets here (an MCP token goes in the
                      server file's env_file, see external-mcp)
      --parent P      who asked for this agent: a root stack, absolute, no .. ('' = none); stored as
                      AOS_PARENT_STACK in its envs. Only an add that carries envs (--envs, --parent,
                      --notify-box; subagent and fork always do) records a parent; without --parent it
                      is the deepest table row holding $AOS_STACK (a tool's cell counts as its agent),
                      '' when there is none. An add without envs records nothing (parent is null)
      --notify-box B  the mailbox folder its notices go to (AOS_NOTIFY_BOX), absolute, no ..
                      ('' = none); not given = none (only subagent add defaults it to its parent)
                      --parent / --notify-box and --envs with the same name and another value = ArgumentsBad.
                      Both are what the requester wrote, not proof; see aos-agent ctl who.
                      Giving either one sets envs, so the row is attached like --envs: its exec
                      column is null and ctl set-def refuses it (rm, then add)
      --dotenv-override   start the definition with aos-exec --dotenv-override: its .env may
                          override names already set, e.g. PATH=${HOME}/bin:${PATH}
                          (stored in the row's exec; only that hop)
      --limits JSON   resource limits, the aos-sandbox keys ('{}' = none)
      --auto-restart  the daemon restarts it whenever it exits (row gets "auto_restart": true);
                      only for agents that stay up; a fire-and-forget agent (eca with
                      --on-empty stop) would end, restart and end again until the daemon
                      stops it after 3 quick exits. To turn it on later: aos-agent ctl rm N
                      (keeps the stack unless --purge), then ctl add --auto-restart
""" + kit_mod.HELP_FLAG + """
                      The files are written before the add letter goes out (taken back if the
                      daemon refuses it); so ctl add must know the stack: with $AOS_KERNEL set,
                      or with --stack-json, give -s too (else ArgumentsBad)
      --timeout-s S   seconds to wait for the daemon (default 30)
      --on-queued MODE  fail or ok when still queued (default fail)
  -h, --help          show this help

exit codes: 0 attached; 1 error (InstanceExists, AddRejected, DaemonMissing, DaemonFailed,
  KitMissing, KitBad...).
"""

def definition(arg, verb="add"):
    """XXX 是不是一份掛得上的 agent 定義（add 與 set-def 共用）：是資料夾、宣告了 entry 的話 entry 在（沒宣告 aos-agent 也收，11-21）。
    回 (定義絕對路徑, 宣告, 入口, def_dir)；宣告 entry 時入口與定義資料夾分開給（def_dir＝定義），沒宣告＝def_dir None。"""
    xxx = os.path.abspath(arg)
    if not os.path.isdir(xxx):
        raise Fail("PathMissing", "%s does not exist (%s takes an agent folder)" % (arg, verb))
    decl, why = read_decl(xxx, IFACE)
    if decl is None:                                  # 11-21 宣告只是參考（使用者 kernel 第 4 題「沒宣告的照樣跑」）：沒宣告 aos-agent＝當作 {}，入口就是夾本身
        decl = {}
    entry_target, def_dir = xxx, None
    ent = decl.get("entry")
    if ent is not None:
        if not isinstance(ent, str) or not ent or os.path.isabs(ent) or ".." in ent.split("#")[0].split("/"):
            raise Fail("InterfaceBad", "the entry declared by %s must be a relative path to an entry in the definition (e.g. \"body.json\"), not %s" % (xxx, json.dumps(ent, ensure_ascii=False)))
        if not os.path.exists(os.path.join(xxx, ent.partition("#")[0])):
            raise Fail("InterfaceBad", "the entry declared by %s does not exist: %s" % (xxx, os.path.join(xxx, ent)))
        entry_target, def_dir = os.path.join(xxx, ent), xxx
    return xxx, decl, entry_target, def_dir


def cmd(argv):
    try:
        opts, rest = aos_flags.parse(argv, {"--name": "name", "--ws": "ws", "--stack": "stack", "--limits": "limits", "--timeout-s": "timeout_s", "--on-queued": "on_queued",
                                             "--ws-json": "ws_json", "--stack-json": "stack_json", "--path-json": "path_json",
                                             "--parent": "parent", "--notify-box": "notify_box", "--kit": "kit"},
                                     switches={"--auto-restart": "auto_restart", "--dotenv-override": "dotenv_override"}, help=HELP, short=("-n", "-w", "-s"),
                                     multi={"--envs": "envs"})
    except aos_flags.Error as e:
        raise bad_args(HELP, str(e)) if e.code == "ArgumentsBad" else Fail(e.code, str(e))
    envs = {}
    for value in opts.get("envs", []):
        key, eq, val = value.partition("=")
        if not eq or not key or "\0" in value:
            raise bad_args(HELP, "--envs needs NAME=VALUE, not %s" % value)
        envs[key] = val
    secs = timeout_opt(opts, HELP)
    on_queued = queued_opt(opts, HELP)
    written = None
    if opts.get("path_json") is not None:             # 11-10 B01：定義資料夾寫成 JSON（指示詞原樣進表、每次起再解），跟 XXX 二選一
        if rest:
            raise bad_args(HELP, "--path-json and XXX exclude each other")
        pj = dc.path_json(opts["path_json"], "--path-json")
        rest = [dc.resolve_here(pj, "--path-json") if isinstance(pj, dict) else pj]
        if isinstance(pj, dict):
            written = (pj, rest[0])
    if len(rest) != 1:
        raise bad_args(HELP, "add takes one agent folder XXX"
                       + ("; extra argument %s (add takes no -- arguments)" % rest[1] if len(rest) > 1 else ""))
    xxx, decl, entry_target, def_dir = definition(rest[0])
    if opts.get("limits") is not None:                # 11-05 feat-proto 件 5：--limits 整份蓋過宣告
        try:
            limits = json.loads(opts["limits"])
        except ValueError as e:
            raise bad_args(HELP, "--limits is not JSON: %s" % e)
        try:
            call_dc(dc.check_limits, limits, "--limits", "ArgumentsBad")
        except Fail as e:
            if e.code == "ArgumentsBad":
                raise bad_args(HELP, str(e)) from e
            raise
    else:
        limits = decl.get("limits")
        if limits is not None:
            call_dc(dc.check_limits, limits, "the limits declared by %s" % xxx, "InterfaceBad")
    for plain in ("ws", "stack"):                      # 11-10 B01：--ws-json／--stack-json 跟 -w／-s 二選一
        if opts.get(plain + "_json") is not None and opts.get(plain) is not None:
            raise bad_args(HELP, "--%s and --%s-json exclude each other" % (plain, plain))
    # 11-10 晚 B01（使用者選「絕對路徑原樣存」）：使用者寫成絕對路徑的格表上原樣存（kept）；相對的、沒寫的（$AOS_WS、目前目錄）
    # 照舊換算成相對 daemon 的 stack；--ws-json／--stack-json 的純字串照字面送（dc.AsIs）
    kept = set()
    if not written and os.path.isabs(rest[0]):
        kept |= {"exec", "def"}
    if opts.get("ws_json") is not None:
        ws = dc.path_json(opts["ws_json"], "--ws-json")   # 指示詞原樣進表、每次起再解；字串照字面
    else:
        ws = opts.get("ws") or os.environ.get("AOS_WS") or "."
    if isinstance(ws, str) and (opts.get("ws") or isinstance(ws, dc.AsIs)) and os.path.isabs(ws):
        kept.add("ws")
    if isinstance(ws, str) and not isinstance(ws, dc.AsIs):
        ws = os.path.abspath(ws)
        if not os.path.isdir(ws):
            raise Fail("WsMissing", "workspace does not exist: %s" % ws)
    stack = dc.path_json(opts["stack_json"], "--stack-json") if opts.get("stack_json") is not None else opts.get("stack")
    if isinstance(stack, str) and os.path.isabs(stack):
        kept.add("stack")
    if isinstance(stack, str) and not isinstance(stack, dc.AsIs):
        if not stack:
            raise bad_args(HELP, "--stack must not be empty")
        stack = os.path.abspath(stack)
    name = opts.get("name") or os.path.basename(xxx.rstrip("/"))
    parent, notify_box = opts.get("parent"), opts.get("notify_box")
    try:                                              # ok-devt-1114 05 修訂 1：只有帶 envs 的 add 才登記 parent／notify_box
        envs = call_dc(dc.registered_envs, envs, parent, notify_box, looked_up_parent(envs, parent, notify_box))
    except Fail as e:
        if e.code == "ArgumentsBad":
            raise bad_args(HELP, str(e)) from e
        raise
    if via_kernel():
        made = lay_kit(opts, xxx, stack, name, None)
        try:
            return add_via_kernel(name, entry_target, ws, stack, def_dir, limits, envs, opts, written, kept, secs, on_queued)
        except Fail as e:
            kit_mod.undo(made, e)
            raise
    need_table()
    row = row_named(name)
    if row is not None:
        hint = {"stopped": "; it is stopped, to carry on: aos-agent ctl start --target %s" % name,
                "sleeping": "; it is asleep, to carry on: aos-agent ctl wake --target %s" % name}.get(row.get("phase"), "")
        raise Fail("InstanceExists", "%s is already on the daemon; pick another name (--name), or first aos-agent ctl rm %s%s" % (name, name, hint))
    made = lay_kit(opts, xxx, stack, name, daemon_path())
    try:
        _, request = call_dc(dc.add_letter, entry_target, daemon=daemon_path(),   # 11-10：--envs 的目標寫成相對 daemon stack 的指示詞，搬家照樣起
                             **add_kwargs(name, ws, stack, def_dir, limits, envs, opts, written, kept))
        row = ctl_wait("add", request,
                       lambda letter: row_named(name) or rejected(letter),
                       "the daemon has not put %s on the table yet (see aos-agent ctl ls and the daemon's log)" % name, "AddRejected", secs=secs, on_queued=on_queued, name=name)
    except KeyboardInterrupt:                         # 11-04 夜邊緣實測：信已寄出，Ctrl-C 不撤；原本安靜退 130，人以為沒掛上
        note("the add letter was sent, the daemon will still attach %s; if you do not want it, aos-agent ctl rm %s (check with aos-agent ctl ls)" % (name, name))
        raise
    except Fail as e:
        kit_mod.undo(made, e)                         # --kit：確定沒掛上＝收回剛寫進 stack 的（逾時說不準、排隊中 --on-queued ok：留著）
        raise
    if row is not None:
        print(Agent(name, row).stack)


def lay_kit(opts, xxx, stack, name, daemon):
    """--kit（11-18 aos-kit 併進 ctl）：寄 add 信之前把 kit 寫進它的 stack（agent 一起來就用得到）。stack 要拿得到：
    -s 給的，或沒走 kernel 時 daemon 的預設 <daemon stack>/procs/<name>；--stack-json、走 kernel 又沒 -s＝ArgumentsBad。回寫了的路徑。"""
    if opts.get("kit") is None:
        return []
    if isinstance(stack, str) and not isinstance(stack, dc.AsIs):
        where = stack
    elif stack is None and daemon:
        where = os.path.join(daemon, "procs", name)
    else:
        raise bad_args(HELP, "--kit needs to know the stack: give -s STACK (with --stack-json, or through $AOS_KERNEL, ctl add cannot tell where it is)")
    steps = kit_mod.plan(opts["kit"], xxx, where, name)
    made = kit_mod.write(steps)
    note(kit_mod.said(steps, opts["kit"], name, xxx))
    return made


def add_kwargs(name, ws, stack, def_dir, limits, envs, opts, written, kept):
    """dc.add_letter 除了目標與 daemon= 以外的參數，ctl add 兩條路（直寄 daemon、經 $AOS_KERNEL）與 set-def 共用一份：
    加旗標只改這裡，不會一條路帶、一條路漏（wf/advices「ctl add 兩條路各自組參數」；0a3ffe5c4 曾漏 dotenv_override）。
    opts 只讀開關 auto_restart、dotenv_override（沒給＝False）。"""
    return {"name": name, "ws": ws, "stack": stack, "def_dir": def_dir, "limits": limits, "envs": envs,
            "auto_restart": opts.get("auto_restart", False), "dotenv_override": opts.get("dotenv_override", False),
            "written": written, "kept": kept}


def add_via_kernel(name, entry_target, ws, stack, def_dir, limits, envs, opts, written, kept, secs, on_queued):
    """走 kernel（kernel-framework 03）：只看這封 add 信自己的回信（applied: true，或 false＋代號＝AddRejected），
    不先讀表查重名、不核 daemon 活不活、不等表上出現。不知道那台 daemon 在哪＝envs 的目標照舊寫絕對（daemon=None）。"""
    try:
        _, request = call_dc(dc.add_letter, entry_target, daemon=None,
                             **add_kwargs(name, ws, stack, def_dir, limits, envs, opts, written, kept))
        got = ctl_wait("add", request, lambda _: True, "the add letter for %s has no reply yet" % name, "AddRejected",
                       secs=secs, on_queued=on_queued, name=name, replied=True)
    except KeyboardInterrupt:
        note("the add letter was sent, the daemon will still attach %s; if you do not want it, aos-agent ctl rm %s (check with aos-agent ctl ls)" % (name, name))
        raise
    if got is None:                                   # 排隊中、--on-queued ok：ctl_wait 已印 queued 那行
        return
    if isinstance(stack, str) and os.path.isabs(stack):
        print(stack.rstrip("/") or "/")
        return
    note("%s attached; the daemon chose its stack, ask for it with: aos-agent ctl where %s" % (name, name))


def looked_up_parent(envs, parent, notify_box):
    """ok-devt-1114 05 修訂 1：這個 add 會帶 envs、又沒明給 parent 時，parent＝表上包住 $AOS_STACK 的最深那列的 stack（同 ctl who；
    工具的小格 <agent stack>/tools/<名>、hook 的小格 hookeds/<名> 都認成那隻 agent；設了 AOS_KERNEL 就經 kernel 查表）。
    不帶 envs、明給了、沒有 AOS_STACK、表讀不到、沒找到＝None。查不到不擋 add：parent 只是登記。"""
    if parent is not None or dc.PARENT_ENV in envs or not (envs or notify_box is not None):
        return None
    s = os.environ.get("AOS_STACK", "")
    if not s:
        return None
    try:
        hit = owner_row(s, table())
    except Fail:
        return None
    st = hit[1].get("stack") if hit else None
    return st if isinstance(st, str) and os.path.isabs(st) else None


def rejected(letter):
    """daemon 不收這封 add 信（11-04 夜 09 題 3，使用者「add被拒絕則應該按照推薦」）：state_flux.json 的 mailbox_warning
    寫的是哪封信、為什麼不採用（只留最後一封壞信）；只認裡面有沒有這封的信件名稱、不靠字樣（11-05 程式輸出改英文）。是這封＝AddRejected、原因原樣轉；不是或讀不到＝None（照等）。"""
    w = call_dc(dc.state, daemon_path()).get("mailbox_warning")
    if letter and isinstance(w, str) and re.search(r"(^|\s)%s(\s|:|$)" % re.escape(letter), w):   # 只認信件名稱，不靠 daemon 的字樣
        raise Fail("AddRejected", "the daemon refused it: %s" % w)
    return None
