# aos_agent/llm.py - 分層解析腦設定命令並管理 agent 的覆蓋鍵與重設確認。
import json
import os
import subprocess
import sys
import aos_flags
from . import PROG
from .common import Fail, actions, bad_args, note, parse, target
from .decl import agent_decl, warn_shared



HELPS = {
    "show": """aos-agent llm show - print this agent's effective brain settings

usage: aos-agent [--daemon D] llm [--target NAME] show
       aos-agent llm show --help

flags:
  -h, --help   show this help

Print one KEY=VALUE per line, merging the definition with this agent's changed keys.
exit codes: 0 printed; 1 error (TargetMissing, LlmMissing, LlmBad...).
""",
    "set": """aos-agent llm set - change brain settings for this agent

usage: aos-agent [--daemon D] llm [--target NAME] set KEY=VALUE...
       aos-agent llm set --help

flags:
  -h, --help   show this help

Store only changed keys in this agent's stack, then print effective settings.
Values are strings; the body decides which keys it understands.
exit codes: 0 changed; 1 error (ArgumentsBad, LlmBad, CommandMissing...).
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
HELP = """aos-agent llm - show and change this agent's brain settings

usage: aos-agent [--daemon D] llm [--target NAME] [ACTION] [FLAGS...] [ARGS...]
       aos-agent llm ACTION --help

actions:
%s

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

No ACTION means show. Only changed keys are stored; the rest follows the definition.
exit codes: 0 ok; 1 error (TargetMissing, LlmMissing, LlmBad...); 130 Ctrl-C.
""" % actions(HELPS.values(), "aos-agent [--daemon D] llm [--target NAME] ")
SUBS = {name: name for name in HELPS}

def llm_paths(a):
    """宣告 llm＝定義裡那份腦設定檔的相對路徑（11-04 晚 think-as-function 03 § 4，跟 tools 同一種寫法）；這隻改過的鍵＝stack 裡同一個相對路徑那份（只放改過的鍵，11-05 前叫副本）。
    回 (定義, 定義那份, stack 那份)。沒宣告＝LlmMissing；宣告的是資料夾（舊的子介面 "llm": "llm"）＝LlmBad。定義那份不在＝當 {}。"""
    folder, decl = agent_decl(a)
    rel = decl.get("llm")
    if not isinstance(rel, str) or not rel:
        raise Fail("LlmMissing", "%s does not declare llm (write {\"aos-agent\": {\"llm\": \"llm.json\"}} in the definition's interfaces.json)" % a.name)
    orig = os.path.join(folder, rel)
    if os.path.isdir(orig) or os.path.isabs(rel) or ".." in rel.split("/"):
        raise Fail("LlmBad", "the llm declared by %s must be a relative path to a settings file in the definition (e.g. \"llm.json\"), not %s" % (folder, rel))
    return folder, orig, os.path.join(a.stack, rel)


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


def show_llm(orig, copy):
    """定義那份疊 stack 那份（改過的鍵），一行一個 鍵=值（字串原樣、其他印 JSON）；哪些鍵是改過的印在 stderr。不認鍵、不遮罩（金鑰不在 agent 這邊）。"""
    vals, over = read_llm(orig), read_llm(copy)
    vals.update(over)
    if over:
        note("keys changed for this agent: %s" % " ".join(over))
    if not vals:
        note("no settings (definition %s has no keys and none were changed here): the body uses its own defaults" % orig)
    for k, v in vals.items():
        print("%s=%s" % (k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))


def cmd(argv):
    """llm show｜set 鍵=值…｜reset：aos-json 的語法糖（只碰這隻 stack 裡那份改過的鍵；改定義＝人直接 aos-json set <定義>/llm.json#/鍵 值）。
    鍵由那隻身體認（fsm：endpoint、model；eca：model），這裡不認、不擋；值一律字串。"""
    opts, rest = parse(argv, {"--target": "target"}, help=HELP, short=("-t",))
    act, args = (rest[0], rest[1:]) if rest else ("show", [])
    if act not in SUBS:
        raise Fail("CommandUnknown", "llm: unknown subcommand %s (show, set, reset; see aos-agent llm --help)" % act)
    switches = {"--yes": "yes"} if act == "reset" else {}
    shorts = ("-y",) if act == "reset" else ()
    aopts, args = parse(args, {}, switches, help=HELPS[act], short=shorts)
    a = target(opts)
    folder, orig, copy = llm_paths(a)
    if act != "set" and args:
        raise bad_args(HELPS[act], "%s takes no arguments" % act)
    pairs = []
    if act == "set":
        for x in args:
            k, eq, v = x.partition("=")
            if not eq or not k or "/" in k or "~" in k:
                raise bad_args(HELPS[act], "expected KEY=VALUE: %s" % x)
            pairs.append((k, v))
        if not pairs:
            raise bad_args(HELPS[act], "set needs at least one KEY=VALUE")
    if act == "reset":
        if os.path.isfile(copy):
            question = "delete the changed llm keys %s of %s (back to the definition's %s)?" % (copy, a.name, orig)
            if not aos_flags.confirm(PROG, question, yes=aopts.get("yes", False)):
                aos_flags.warn(PROG, "nothing done")
                return 0
            os.unlink(copy)
            note("deleted %s (the changed keys); back to the definition's %s" % (copy, orig))
    elif act == "set":
        if not os.path.isfile(copy):
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            tmp = os.path.join(os.path.dirname(copy), "." + os.path.basename(copy) + ".tmp")   # N-05
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("{}\n")
            os.replace(tmp, copy)
            note("created %s (only the changed keys, the rest follows the definition; llm reset deletes it)" % copy)
        for k, v in pairs:
            try:
                r = subprocess.run(["aos-json", "set", "--str", "%s#/%s" % (copy, k), v])   # aos-json 的錯原樣（C-53）
            except OSError as e:
                raise Fail("CommandMissing", "cannot run aos-json (proto8/impls/aos-json/bin must be on PATH): %s" % e)
            if r.returncode != 0:
                sys.exit(1)
        warn_shared(a, folder)
    show_llm(orig, copy)
