# aos_agent/llm.py - 分層解析腦設定命令（ls／set／rm／reset）並管理 agent 的覆蓋鍵與重設確認。
import json
import os
import subprocess
import sys
import aos_flags
from . import PROG
from .common import Fail, actions, bad_args, note, parse, target
from .decl import agent_decl, warn_shared



HELPS = {
    "ls": """aos-agent llm ls - list this agent's effective brain settings

usage: aos-agent [--daemon D] llm [--target NAME] ls [-l | --json]
       aos-agent llm ls --help

flags:
  -l, --long   also where each key comes from: definition, or agent (changed for
               this agent; the definition's value follows when it has one)
  -j, --json   print one JSON array of {"key", "value", "from", "definition"?}
  -h, --help   show this help

Print KEY=VALUE per line: the definition's settings with this agent's changed keys on top.
exit codes: 0 listed; 1 error (TargetMissing, LlmMissing, LlmBad...).
""",
    "set": """aos-agent llm set - change brain settings for this agent

usage: aos-agent [--daemon D] llm [--target NAME] set KEY=VALUE...
       aos-agent llm set --help

flags:
  -h, --help   show this help

Store only changed keys in this agent's stack, then print effective settings.
Values are strings. A key the body does not read (llm_keys in the definition's
interfaces.json) is stored anyway, with a warning.
exit codes: 0 changed; 1 error (ArgumentsBad, LlmBad, CommandMissing...).
""",
    "rm": """aos-agent llm rm - drop keys changed for this agent

usage: aos-agent [--daemon D] llm [--target NAME] rm KEY...
       aos-agent llm rm --help

flags:
  -h, --help   show this help

Each KEY goes back to the definition's value (or to the body's default when the
definition has none), then print effective settings.
exit codes: 0 removed; 1 error (KeyMissing, ArgumentsBad, LlmBad...).
""",
    "reset": """aos-agent llm reset - delete this agent's changed brain settings

usage: aos-agent [--daemon D] llm [--target NAME] reset [-y]
       aos-agent llm reset --help

flags:
  -y, --yes    skip confirmation
  -h, --help   show this help

Return to the definition's settings, then print them; asks on a terminal; -y skips.
exit codes: 0 reset or nothing done; 1 error (LlmMissing, LlmBad...); 130 Ctrl-C.
""",
}
HELP = """aos-agent llm - list and change this agent's brain settings

usage: aos-agent [--daemon D] llm [--target NAME] [ACTION] [FLAGS...] [ARGS...]
       aos-agent llm ACTION --help

actions:
%s

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

No ACTION means ls. Only changed keys are stored; the rest follows the definition.
exit codes: 0 ok; 1 error (TargetMissing, LlmMissing, LlmBad...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] llm [--target NAME] ")
SUBS = {name: name for name in HELPS}

def llm_paths(a):
    """宣告 llm＝定義裡那份腦設定檔的相對路徑（11-04 晚 think-as-function 03 § 4，跟 tools 同一種寫法）；這隻改過的鍵＝stack 裡同一個相對路徑那份（只放改過的鍵）。
    回 (定義, 定義那份, stack 那份, 身體認的鍵或 None)。沒宣告＝LlmMissing；宣告的是資料夾＝LlmBad。定義那份不在＝當 {}。
    身體認的鍵＝同一個宣告的 llm_keys（字串陣列，11-10 晚使用者「跳warinig就好」；沒寫＝不知道、不提醒）。"""
    folder, decl = agent_decl(a)
    rel = decl.get("llm")
    if not isinstance(rel, str) or not rel:
        raise Fail("LlmMissing", "%s does not declare llm (write {\"aos-agent\": {\"llm\": \"llm.json\"}} in the definition's interfaces.json)" % a.name)
    orig = os.path.join(folder, rel)
    if os.path.isdir(orig) or os.path.isabs(rel) or ".." in rel.split("/"):
        raise Fail("LlmBad", "the llm declared by %s must be a relative path to a settings file in the definition (e.g. \"llm.json\"), not %s" % (folder, rel))
    keys = decl.get("llm_keys")
    if keys is not None and not (isinstance(keys, list) and all(isinstance(k, str) for k in keys)):
        raise Fail("InterfaceBad", "llm_keys in %s/interfaces.json must be an array of key names" % folder)
    return folder, orig, os.path.join(a.stack, rel), keys


def read_llm(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise Fail("LlmBad", "cannot read %s: %s" % (path, e))
    if not isinstance(d, dict):
        raise Fail("LlmBad", "%s must be a flat JSON object" % path)
    return d


def text(v):
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def ls_llm(orig, copy, long=False, as_json=False):
    """定義那份疊 stack 那份（改過的鍵）。預設一行一個 鍵=值；-l 多一欄來源（definition｜agent，蓋掉定義的再接定義的值）；--json 一個陣列。不遮罩（金鑰不在 agent 這邊）。"""
    base, over = read_llm(orig), read_llm(copy)
    vals = dict(base)
    vals.update(over)
    rows = []
    for k, v in vals.items():
        row = {"key": k, "value": v, "from": "agent" if k in over else "definition"}
        if k in over and k in base:
            row["definition"] = base[k]
        rows.append(row)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False))
        return
    if not vals:
        note("no settings (definition %s has no keys and none were changed here): the body uses its own defaults" % orig)
    for r in rows:
        line = "%s=%s" % (r["key"], text(r["value"]))
        if long:
            line += "\t" + r["from"] + ("\tdefinition: " + text(r["definition"]) if "definition" in r else "")
        print(line)


def write_obj(path, d):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def cmd(argv):
    """llm ls｜set 鍵=值…｜rm 鍵…｜reset：aos-json 的語法糖（只碰這隻 stack 裡那份改過的鍵；改定義＝人直接 aos-json set <定義>/llm.json#/鍵 值）。
    11-10 晚使用者「換」：show 換成 ls（比照 tools：-l、--json）、加 rm。鍵由那隻身體認（定義的 llm_keys 有寫就對著提醒，照存）；值一律字串。"""
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",), sub=True)
    act, args = (rest[0], rest[1:]) if rest else ("ls", [])
    if act not in SUBS:
        raise Fail("CommandUnknown", "llm: unknown subcommand %s (ls, set, rm, reset; see aos-agent llm --help)" % act)
    switches = {"reset": {"--yes": "yes"}, "ls": {"--json": "json", "--long": "long"}}.get(act, {})
    shorts = {"reset": ("-y",), "ls": {"-j": "--json", "-l": "--long"}}.get(act, ())
    aopts, args = parse(args, {}, switches, help=HELPS[act], short=shorts)
    a = target(opts)
    folder, orig, copy, known = llm_paths(a)
    if act in ("ls", "reset") and args:
        raise bad_args(HELPS[act], "%s takes no arguments" % act)
    if act == "ls":
        if aopts.get("json") and aopts.get("long"):
            raise bad_args(HELPS[act], "give -l or --json, not both")
        ls_llm(orig, copy, aopts.get("long", False), aopts.get("json", False))
        return 0
    if act == "rm":
        if not args:
            raise bad_args(HELPS[act], "rm needs at least one KEY")
        over = read_llm(copy)
        missing = [k for k in args if k not in over]
        if missing:
            raise Fail("KeyMissing", "%s not changed for %s (changed: %s); nothing removed" % (", ".join(missing), a.name, ", ".join(over) or "none"))
        for k in args:
            del over[k]
        if over:
            write_obj(copy, over)
        else:
            os.unlink(copy)
            note("no changed keys left; deleted %s" % copy)
        warn_shared(a, folder)
    elif act == "reset":
        if os.path.isfile(copy):
            question = "delete the changed llm keys %s of %s (back to the definition's %s)?" % (copy, a.name, orig)
            if not aos_flags.confirm(PROG, question, yes=aopts.get("yes", False)):
                aos_flags.warn(PROG, "nothing done")
                return 0
            os.unlink(copy)
            note("deleted %s (the changed keys); back to the definition's %s" % (copy, orig))
    elif act == "set":
        pairs = []
        for x in args:
            k, eq, v = x.partition("=")
            if not eq or not k or "/" in k or "~" in k:
                raise bad_args(HELPS[act], "expected KEY=VALUE: %s" % x)
            pairs.append((k, v))
        if not pairs:
            raise bad_args(HELPS[act], "set needs at least one KEY=VALUE")
        if known is not None:
            for k, _ in pairs:
                if k not in known:
                    note("%s is not a setting the body of %s reads (it reads: %s); stored anyway" % (k, a.name, ", ".join(known) or "none"))
        if not os.path.isfile(copy):
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            write_obj(copy, {})
            note("created %s (only the changed keys, the rest follows the definition; llm rm KEY or llm reset undoes)" % copy)
        for k, v in pairs:
            try:
                r = subprocess.run(["aos-json", "set", "--str", "%s#/%s" % (copy, k), v])   # aos-json 的錯原樣（C-53）
            except OSError as e:
                raise Fail("CommandMissing", "cannot run aos-json (proto8/impls/aos-json/bin must be on PATH): %s" % e)
            if r.returncode != 0:
                sys.exit(1)
        warn_shared(a, folder)
    ls_llm(orig, copy)
