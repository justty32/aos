# aos/apps/agent/ctl/kit.py - ctl add／set-def 的 --kit：把 kit 夾的 system.txt、tools.json 寫成這隻 agent 在 stack 裡自己那份（定義不動；已有的直接蓋），退回＝system reset、tools reset。
# 使用者 11-18：「aos-kit也不用了，刪掉，功能整合進現有的。」選項框選「併進 aos-agent ctl (Recommended)」（thinking 2026-11/18/aos-kit-併進ctl.md）。
# 為什麼寫 stack 不寫定義：system／tools 本來就有「stack 那份在＝蓋過定義那份」（aos-agent system set、tools add 寫的那層），
#   agent-fsm 每格重讀、eca 每題重讀；寫那裡＝不就地改使用者的定義夾、不用另存舊檔、退回用現成的 reset。
# 11-18 晚使用者選項框：寫到哪「寫進 stack (Recommended)」；「eca 定義也能套 kit」要；「換包可以直接蓋」要（已有自己那份＝直接蓋，不用先 reset）。
import json
import os
from aos.declared_files import declared_files
from ..common import Fail, note

FILES = ("system", "tools")                     # 宣告鍵；kit 夾裡固定叫 system.txt、tools.json
KIT_NAMES = {"system": "system.txt", "tools": "tools.json"}

HELP_FLAG = """      --kit KIT       lay a kit over it: KIT is a kit folder holding system.txt and tools.json
                      (shipped ones: $AOS_HOME/templates/agents/kits/gather, .../review). They are written
                      as the agent's own copies in its stack (as aos-agent system set and tools add
                      do); the definition is not changed. Own copies already there (an earlier
                      kit, system set, tools add) are replaced, so a second --kit swaps kits. On an
                      eca definition (with cli.json) the kit's system text is appended to the CLI's
                      own and its tools replace the aos tools; the CLI's built-in tools (Bash...)
                      stay, so the kit's limits do not hold there (a cli.json naming tools itself =
                      KitBad). To drop the kit later: aos-agent -t NAME system reset -y, then
                      aos-agent -t NAME tools reset -y"""


def read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        raise Fail("KitBad", "cannot read %s: %s" % (path, e.strerror or e))


def is_eca(def_folder):
    return os.path.exists(os.path.join(def_folder, "cli.json"))


def plan(kit_arg, def_folder, stack, name):
    """先全部檢查、什麼都不寫。回 [(宣告鍵, 內容, stack 裡的路徑, "create"|"replace"|"unchanged")]。"""
    kit = os.path.abspath(kit_arg)
    if not os.path.isdir(kit):
        raise Fail("KitMissing", "%s is not a folder (--kit takes a kit folder, e.g. $AOS_HOME/templates/agents/kits/gather)" % kit_arg)
    for key in FILES:
        if not os.path.isfile(os.path.join(kit, KIT_NAMES[key])):
            raise Fail("KitMissing", "%s has no %s (a kit folder holds system.txt and tools.json)" % (kit, KIT_NAMES[key]))
    if is_eca(def_folder):                      # 11-18 晚「eca 定義也能套 kit」：要；cli.json 明寫 tools＝eca 不看 stack 那份（cli_cfg.stack_copies），套了也沒用
        try:
            with open(os.path.join(def_folder, "cli.json"), encoding="utf-8") as f:
                cli = json.load(f)
        except (OSError, ValueError) as e:
            raise Fail("KitBad", "cannot read %s: %s" % (os.path.join(def_folder, "cli.json"), e)) from e
        if isinstance(cli, dict) and "tools" in cli:
            raise Fail("KitBad", "%s names its tools in cli.json (tools key), so an eca agent never reads its own tools copy; "
                       "a kit cannot be laid on it" % def_folder)
    try:
        rels = declared_files(def_folder)
    except ValueError as e:
        raise Fail("InterfaceBad", str(e)) from e
    missing = [k for k in FILES if k not in rels]
    if missing:
        raise Fail("KitBad", "%s does not declare %s in interfaces.json (a kit needs both system and tools, as in the agent-fsm template)"
                   % (def_folder, " and ".join(missing)))
    tools = read_bytes(os.path.join(kit, KIT_NAMES["tools"]))
    try:
        if not isinstance(json.loads(tools.decode("utf-8")), dict):
            raise ValueError("not a JSON object")
    except (ValueError, UnicodeError) as e:
        raise Fail("KitBad", "%s is not a tools registry (a JSON object): %s" % (os.path.join(kit, KIT_NAMES["tools"]), e)) from e
    new = {"system": read_bytes(os.path.join(kit, KIT_NAMES["system"])), "tools": tools}
    steps = []
    for key in FILES:
        dest = os.path.join(stack, rels[key])
        if os.path.isdir(dest):
            raise Fail("KitBad", "%s is a folder" % dest)
        if os.path.lexists(dest):               # 11-18 晚「換包可以直接蓋」：要＝已有自己那份（上一包、system set、tools add）就蓋掉
            steps.append((key, new[key], dest, "unchanged" if read_bytes(dest) == new[key] else "replace"))
            continue
        steps.append((key, new[key], dest, "create"))
    return steps


def write(steps):
    """寫 create／replace 那幾份（暫存檔再 rename 上去）。回 [(路徑, 原內容或 None)]（失敗時給 undo 還原）。"""
    made = []
    try:
        for key, data, dest, action in steps:
            if action == "unchanged":
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                old = read_bytes(dest) if os.path.lexists(dest) else None   # 寫的當下再讀一次：plan 之後有人動過也還原得回去
            except Fail:
                old = None
            tmp = os.path.join(os.path.dirname(dest), ".%s.kit.%d" % (os.path.basename(dest), os.getpid()))
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            made.append((dest, old))
    except OSError as e:
        undo(made)
        raise Fail("WriteFailed", "cannot write the kit into the stack: %s" % (e.strerror or e)) from e
    return made


UNSURE = ("WaitFailed", "DaemonFailed")         # 信寄出了、結果說不準（之後還可能掛上）：不收回


def undo(made, err=None):
    """掛不上時收回剛寫的（只收這次寫的：新建的拿掉、蓋掉的寫回原內容；原本就在、內容相同的不動）。err 是說不準的那幾種＝留著、提醒一行。"""
    if err is not None and getattr(err, "code", None) in UNSURE:
        if made:
            note("kept the kit files just written (%s): the daemon may still attach it" % ", ".join(p for p, _ in made))
        return
    for p, old in reversed(made):               # 原本沒有＝拿掉剛寫的；原本有（換包蓋掉的）＝寫回原內容
        try:
            if old is None:
                os.unlink(p)
            else:
                with open(p, "wb") as f:
                    f.write(old)
        except OSError:
            pass


def said(steps, kit_arg, name, def_folder):
    """一行說明（stderr 的 warning 行；stdout 留給 ctl add 印 stack）。eca 定義多一句：CLI 自帶的工具還在。"""
    verb = {"create": "wrote", "replace": "replaced", "unchanged": "kept (same)"}
    parts = ["%s %s" % (verb[a], d) for _, _, d, a in steps]
    eca = (" (eca definition: the system text is appended to the CLI's own, and the CLI's built-in tools such as Bash stay, "
           "so the kit's tool limits do not hold)") if is_eca(def_folder) else ""
    return ("kit %s: %s, as %s's own copies (the definition is not changed; to drop the kit: "
            "aos-agent -t %s system reset -y, aos-agent -t %s tools reset -y)%s" % (kit_arg, "; ".join(parts), name, name, name, eca))
