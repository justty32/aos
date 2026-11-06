# aos_agent/llm.py - 顯示與修改 agent 的腦設定覆蓋鍵。
import json
import os
import subprocess
import sys
from .common import Fail, note, parse, target
from .decl import agent_decl, warn_shared


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
    opts, rest = parse(argv, {"--target": "target"})
    a = target(opts)
    folder, orig, copy = llm_paths(a)
    act, args = (rest[0], rest[1:]) if rest else ("show", [])
    if act == "show":
        if args:
            raise Fail("ArgumentsBad", "llm show takes no arguments")
    elif act == "reset":
        if args:
            raise Fail("ArgumentsBad", "llm reset takes no arguments")
        if os.path.isfile(copy):
            os.unlink(copy)
            note("deleted %s (the changed keys); back to the definition's %s" % (copy, orig))
    elif act == "set":
        pairs = []
        for x in args:
            k, eq, v = x.partition("=")
            if not eq or not k or "/" in k or "~" in k:
                raise Fail("ArgumentsBad", "expected KEY=VALUE: %s" % x)
            pairs.append((k, v))
        if not pairs:
            raise Fail("ArgumentsBad", "llm set needs at least one KEY=VALUE")
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
    else:
        raise Fail("CommandUnknown", "llm: unknown action %s (show, set KEY=VALUE..., reset)" % act)
    show_llm(orig, copy)
