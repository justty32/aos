# aos_agent/ctl/add.py - 宣告檢查、掛上 agent 並等待 daemon 上表。
import aos_flags
import daemon_ctl as dc
import json
import os
import re
from ..common import bad_args, Agent, Fail, IFACE, call_dc, daemon_path, note, row_named
from .shared import ctl_wait, need_table, queued_opt, timeout_opt
from ..decl import read_decl


# ---------------------------------------------------------------- 子命令：動它的（步 5）

HELP = """aos-agent ctl add - attach one agent to the daemon

usage: aos-agent [--daemon D] ctl add [-n N] [-w WS | --ws-json J] [-s S | --stack-json J] [--path-json J] [--limits JSON] [--envs K=V ...] [--auto-restart] [--timeout-s S] [--on-queued fail|ok] XXX

XXX is the agent folder; it must declare aos-agent in interfaces.json. The letter goes
through $AOS_KERNEL when that is set (a warning line says so). Waits until the agent is on
the table, then prints its stack; the daemon refusing it = AddRejected.

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
      --limits JSON   resource limits, the aos-sandbox keys ('{}' = none)
      --auto-restart  the daemon restarts it whenever it exits (row gets "auto_restart": true);
                      only for agents that stay up; a fire-and-forget agent (eca with
                      --on-empty stop) would end, restart and end again until the daemon
                      stops it after 3 quick exits. To turn it on later: aos-agent ctl rm N
                      (keeps the stack unless --purge), then ctl add --auto-restart
      --timeout-s S   seconds to wait for the daemon (default 30)
      --on-queued MODE  fail or ok when still queued (default fail)
  -h, --help          show this help

exit codes: 0 attached; 1 error (InterfaceMissing, InstanceExists, AddRejected, DaemonMissing, DaemonFailed...).
"""

def cmd(argv):
    try:
        opts, rest = aos_flags.parse(argv, {"--name": "name", "--ws": "ws", "--stack": "stack", "--limits": "limits", "--timeout-s": "timeout_s", "--on-queued": "on_queued",
                                             "--ws-json": "ws_json", "--stack-json": "stack_json", "--path-json": "path_json"},
                                     switches={"--auto-restart": "auto_restart"}, help=HELP, short=("-n", "-w", "-s"),
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
    xxx = os.path.abspath(rest[0])
    if not os.path.isdir(xxx):
        raise Fail("PathMissing", "%s does not exist (add takes an agent folder)" % rest[0])
    decl, why = read_decl(xxx, IFACE)
    if decl is None:
        raise Fail("InterfaceMissing", "%s does not declare the aos-agent interface (%s); put interfaces.json at its top: {\"aos-agent\": {}}" % (xxx, why))
    entry_target, def_dir = xxx, None               # 宣告 entry 時，入口與定義資料夾分開給
    ent = decl.get("entry")
    if ent is not None:
        if not isinstance(ent, str) or not ent or os.path.isabs(ent) or ".." in ent.split("#")[0].split("/"):
            raise Fail("InterfaceBad", "the entry declared by %s must be a relative path to an entry in the definition (e.g. \"body.json\"), not %s" % (xxx, json.dumps(ent, ensure_ascii=False)))
        if not os.path.exists(os.path.join(xxx, ent.partition("#")[0])):
            raise Fail("InterfaceBad", "the entry declared by %s does not exist: %s" % (xxx, os.path.join(xxx, ent)))
        entry_target, def_dir = os.path.join(xxx, ent), xxx
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
    need_table()
    row = row_named(name)
    if row is not None:
        hint = {"stopped": "; it is stopped, to carry on: aos-agent ctl start --target %s" % name,
                "sleeping": "; it is asleep, to carry on: aos-agent ctl wake --target %s" % name}.get(row.get("phase"), "")
        raise Fail("InstanceExists", "%s is already on the daemon; pick another name (--name), or first aos-agent ctl rm %s%s" % (name, name, hint))
    try:
        _, request = call_dc(dc.add_letter, entry_target, name=name, ws=ws, stack=stack,
                                  def_dir=def_dir, limits=limits, envs=envs,
                                  auto_restart=opts.get("auto_restart", False),
                                  daemon=daemon_path(), written=written, kept=kept)   # 11-10：--envs 的目標寫成相對 daemon stack 的指示詞，搬家照樣起
        row = ctl_wait("add", request,
                       lambda letter: row_named(name) or rejected(letter),
                       "the daemon has not put %s on the table yet (see aos-agent ctl ls and the daemon's log)" % name, "AddRejected", secs=secs, on_queued=on_queued, name=name)
    except KeyboardInterrupt:                         # 11-04 夜邊緣實測：信已寄出，Ctrl-C 不撤；原本安靜退 130，人以為沒掛上
        note("the add letter was sent, the daemon will still attach %s; if you do not want it, aos-agent ctl rm %s (check with aos-agent ctl ls)" % (name, name))
        raise
    if row is not None:
        print(Agent(name, row).stack)


def rejected(letter):
    """daemon 不收這封 add 信（11-04 夜 09 題 3，使用者「add被拒絕則應該按照推薦」）：state_flux.json 的 mailbox_warning
    寫的是哪封信、為什麼不採用（只留最後一封壞信）；只認裡面有沒有這封的信件名稱、不靠字樣（11-05 程式輸出改英文）。是這封＝AddRejected、原因原樣轉；不是或讀不到＝None（照等）。"""
    w = call_dc(dc.state, daemon_path()).get("mailbox_warning")
    if letter and isinstance(w, str) and re.search(r"(^|\s)%s(\s|:|$)" % re.escape(letter), w):   # 只認信件名稱，不靠 daemon 的字樣
        raise Fail("AddRejected", "the daemon refused it: %s" % w)
    return None
