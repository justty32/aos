# aos_agent/ctl/add.py - 宣告檢查、掛上 agent 並等待 daemon 上表。
import daemon_ctl as dc
import json
import os
import re
from ..common import Agent, Fail, IFACE, call_dc, ctl_wait, daemon_path, need_table, note, parse, row_named
from ..decl import read_decl


# ---------------------------------------------------------------- 子命令：動它的（步 5）

def cmd(argv):
    opts, rest = parse(argv, {"--name": "name", "--ws": "ws", "--stack": "stack", "--limits": "limits"})
    if len(rest) != 1:
        raise Fail("ArgumentsBad", "add takes one agent folder XXX (aos-agent ctl add [--name N] [--ws WS] [--stack S] [--limits JSON] XXX)"
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
            raise Fail("ArgumentsBad", "--limits is not JSON: %s" % e)
        call_dc(dc.check_limits, limits, "--limits", "ArgumentsBad")
    else:
        limits = decl.get("limits")
        if limits is not None:
            call_dc(dc.check_limits, limits, "the limits declared by %s" % xxx, "InterfaceBad")
    ws = os.path.abspath(opts.get("ws") or ".")
    if not os.path.isdir(ws):
        raise Fail("PathMissing", "--ws is not a folder: %s" % ws)
    stack = opts.get("stack")
    if stack is not None:
        if not stack:
            raise Fail("ArgumentsBad", "--stack must not be empty")
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
                                  def_dir=def_dir, limits=limits)
        row = ctl_wait("add", request,
                       lambda letter: row_named(name) or rejected(letter),
                       "the daemon has not put %s on the table yet (see aos-agent ctl ls and the daemon's log)" % name, "AddRejected")
    except KeyboardInterrupt:                         # 11-04 夜邊緣實測：信已寄出，Ctrl-C 不撤；原本安靜退 130，人以為沒掛上
        note("the add letter was sent, the daemon will still attach %s; if you do not want it, aos-agent ctl rm %s (check with aos-agent ctl ls)" % (name, name))
        raise
    print(Agent(name, row).stack)


def rejected(letter):
    """daemon 不收這封 add 信（11-04 夜 09 題 3，使用者「add被拒絕則應該按照推薦」）：procs_state.json 的 mailbox_warning
    寫的是哪封信、為什麼不採用（只留最後一封壞信）；只認裡面有沒有這封的信件名稱、不靠字樣（11-05 程式輸出改英文）。是這封＝AddRejected、原因原樣轉；不是或讀不到＝None（照等）。"""
    w = call_dc(dc.state, daemon_path()).get("mailbox_warning")
    if letter and isinstance(w, str) and re.search(r"(^|\s)%s(\s|:|$)" % re.escape(letter), w):   # 只認信件名稱，不靠 daemon 的字樣
        raise Fail("AddRejected", "the daemon refused it: %s" % w)
    return None
