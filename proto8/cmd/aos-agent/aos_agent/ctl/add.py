# aos_agent/ctl/add.py - 宣告檢查、掛上 agent 並等待 daemon 上表。
import aos_flags
import daemon_ctl as dc
import json
import os
import re
from ..common import bad_args, Agent, Fail, IFACE, call_dc, ctl_wait, daemon_path, need_table, note, row_named, timeout_opt, queued_opt
from ..decl import read_decl


# ---------------------------------------------------------------- 子命令：動它的（步 5）

HELP = """aos-agent ctl add - attach one agent to the daemon

usage: aos-agent [--daemon D] ctl add [-n N] [-w WS] [-s S] [--limits JSON] [--envs K=V ...] [--auto-restart] [--timeout-s S] [--on-queued fail|ok] XXX

XXX is the agent folder; it must declare aos-agent in interfaces.json. The letter goes
through $AOS_KERNEL when that is set (a warning line says so). Waits until the agent is on
the table, then prints its stack; the daemon refusing it = AddRejected.

flags:
  -n, --name N        its name on the table (default: the folder name of XXX)
  -w, --ws WS         its workspace (default: non-empty $AOS_WS, else the current directory)
  -s, --stack S       its stack (default: <daemon stack>/procs/<name>/)
      --envs K=V      child environment variable (repeatable; set through an exec single)
      --limits JSON   resource limits, the aos-sandbox keys ('{}' = none)
      --auto-restart  the daemon restarts it whenever it exits (row gets "auto_restart": true);
                      only for agents that stay up; a fire-and-forget agent (eca with
                      --on-empty stop) would end, restart and end again until the daemon
                      stops it after 3 quick exits. To turn it on later: ctl rm, then
                      ctl add --auto-restart (rm keeps the stack, it carries on)
      --timeout-s S   seconds to wait for the daemon (default 30)
      --on-queued MODE  fail or ok when still queued (default fail)
  -h, --help          show this help

exit codes: 0 attached; 1 error (InterfaceMissing, InstanceExists, AddRejected, DaemonMissing, DaemonFailed...).
"""

def cmd(argv):
    try:
        opts, rest = aos_flags.parse(argv, {"--name": "name", "--ws": "ws", "--stack": "stack", "--limits": "limits", "--timeout-s": "timeout_s", "--on-queued": "on_queued"},
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
    ws = os.path.abspath(opts.get("ws") or os.environ.get("AOS_WS") or ".")
    if not os.path.isdir(ws):
        raise Fail("WsMissing", "workspace does not exist: %s" % ws)
    stack = opts.get("stack")
    if stack is not None:
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
                                  auto_restart=opts.get("auto_restart", False))
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
