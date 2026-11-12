"""def_edit - agent_def 的細的定義動作：tools（ls／get／add／rm，轉 aos-tools --file 定義那份）、llm（ls／set／rm，轉 aos-json）、system（get／set）；改的是定義本身，不碰任何 stack。

使用者 11-12「Q09:b-都做，除了移除子(兩者不要耦合)」（Q09＝thinking 2026-11/10/agents-split「之後可加」的細的定義動作）。
args 的形狀照 self_tools／self_llm／self_system（同一份參數，目標換成定義）；定義沒有「疊在上面的那份」，所以沒有 reset、llm／system 沒有 long。
宣告的檔位置照 aos-agent（interfaces.json 的 aos-agent.tools／llm／system，lib/agent/agent_files.py）。
相對路徑（add 的 path、env_file）從 $AOS_WS 算：下層都在工作區跑。下層 stderr 原樣透出，它退非 0＝最後一行錯誤行接成自己的（C-52 例外 ⑤，同 agent_def check）。
"""
import json, os

import tool_io

try:
    from agent_files import declared_files
except ModuleNotFoundError as error:
    if error.name != "agent_files":
        raise
    from agent.agent_files import declared_files

die = tool_io.die
ARGS = {"tools": {"ls": ("long",), "get": ("name",), "add": ("path", "path_json", "name", "replace", "envs", "env_file", "no_cache"),
                  "rm": ("name",)},
        "llm": {"ls": (), "set": ("settings",), "rm": ("keys",)},
        "system": {"get": (), "set": ("text",)}}
MISSING = {"tools": "ToolsMissing", "llm": "LlmMissing", "system": "SystemMissing"}
EXAMPLE = {"tools": "tools.json", "llm": "llm.json", "system": "system.txt"}


def check_args(what, a):
    """args＝self_<what> 收的那份物件；不認得的 op＝OpUnknown，多給的鍵＝ArgumentsBad。回 op。"""
    if not isinstance(a, dict):
        die("ArgumentsBad", "args must be an object like {\"op\": \"%s\"} (the same arguments as self_%s)" % (next(iter(ARGS[what])), what))
    ops = ARGS[what]
    op = a.get("op")
    if op is None:
        die("ArgumentsBad", "args needs op (%s)" % ", ".join(ops))
    if op not in ops:
        why = " (a definition has no own copy to reset; edit it with set / add / rm)" if op == "reset" else ""
        die("OpUnknown", "%s args op must be one of %s (got %r)%s" % (what, ", ".join(ops), op, why))
    extra = sorted(k for k in a if k != "op" and k not in ops[op])
    if extra:
        die("ArgumentsBad", "%s %s does not take %s (it takes %s)" % (what, op, ", ".join(extra), ", ".join(ops[op]) or "nothing else"))
    return op


def declared(defdir, what):
    """定義裡宣告的那個檔（絕對路徑）。沒宣告＝ToolsMissing／LlmMissing／SystemMissing；宣告壞了＝DefBad。"""
    try:
        rel = declared_files(defdir).get(what)
    except ValueError as e:
        die("DefBad", str(e))
    if rel is None:
        die(MISSING[what], "%s does not declare %s (write {\"aos-agent\": {\"%s\": \"%s\"}} in its interfaces.json)"
            % (defdir, what, what, EXAMPLE[what]))
    return os.path.join(defdir, rel)


def text(a, key, need=False):
    v = a.get(key)
    if v is None and not need:
        return None
    if not isinstance(v, str) or not v:
        die("ArgumentsBad", "%s %s a non-empty string" % (key, "needs" if v is None else "must be"))
    return v


def flag(a, key):
    v = a.get(key, False)
    if not isinstance(v, bool):
        die("ArgumentsBad", "%s must be true or false" % key)
    return v


def emit(out):
    if out:
        print(out, end="" if out.endswith("\n") else "\n")


def after(what):
    print("(changed the definition: agents that use it see this from their next brain call, unless they %s)"
          % ("have their own system text" if what == "system" else "changed that %s for themselves" % ("tool" if what == "tools" else "key")))


def tools(run, defdir, a, op):
    """= aos-tools --file <定義的 tools 檔> ls｜get｜add｜rm（旗標同 self_tools ⇄ aos-agent tools）。"""
    cmd = ["aos-tools", "--file", declared(defdir, "tools"), op]
    if op == "ls":
        cmd += ["--long"] if flag(a, "long") else []
    elif op in ("get", "rm"):
        cmd += [text(a, "name", True)]
    else:
        envs = a.get("envs", {})
        if not isinstance(envs, dict) or not all(isinstance(k, str) and k and "=" not in k and isinstance(v, str) for k, v in envs.items()):
            die("ArgumentsBad", "envs must be an object of strings, like {\"AOS_DATA\": \"/data\"}")
        if ("path" in a) == ("path_json" in a):
            die("ArgumentsBad", "add needs path (a tool folder, JSON file or executable) or path_json, not both")
        name, env_file = text(a, "name"), text(a, "env_file")
        cmd += (["--name", name] if name else []) + (["--replace"] if flag(a, "replace") else []) \
            + [x for k in sorted(envs) for x in ("--envs", "%s=%s" % (k, envs[k]))] \
            + (["--env-file", env_file] if env_file else []) + (["--no-cache"] if flag(a, "no_cache") else [])
        if "path_json" in a:
            pj = a["path_json"]
            if not isinstance(pj, dict) or not pj:
                die("ArgumentsBad", "path_json must be a directive object like {\"$env\": \"AOS_HOME\", \"$path\": \"/lib/base/math\"}")
            cmd += ["--path-json", json.dumps(pj, ensure_ascii=False)]
        else:
            cmd += [text(a, "path", True)]
    emit(run(cmd))
    if op in ("add", "rm"):
        after("tools")


def pointer(key):
    return "/" + key.replace("~", "~0").replace("/", "~1")


def read_llm(path):
    """定義那份腦設定（扁平物件）；檔不在＝{}（同 aos-agent llm）。"""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, UnicodeError) as e:
        die("DefBad", "cannot read %s: %s" % (tool_io.place(path), tool_io.os_reason(e)))
    if not isinstance(d, dict):
        die("DefBad", "%s must be a flat JSON object" % tool_io.place(path))
    return d


def body_keys(defdir):
    """interfaces.json 的 aos-agent.llm_keys（身體認的鍵）；沒寫＝None（不提醒）。"""
    try:
        with open(os.path.join(defdir, "interfaces.json"), encoding="utf-8") as f:
            keys = json.load(f).get("aos-agent", {}).get("llm_keys")
    except (OSError, ValueError, AttributeError):
        return None
    return keys if isinstance(keys, list) and all(isinstance(k, str) for k in keys) else None


def llm(run, defdir, a, op):
    """ls＝印 KEY=VALUE；set＝aos-json set --str <llm 檔>#/KEY VALUE（檔不在先建 {}）；rm＝aos-json del。改完印一次。"""
    path = declared(defdir, "llm")
    if op == "set":
        s = a.get("settings")
        if not isinstance(s, dict) or not s or not all(isinstance(k, str) and k and isinstance(v, str) for k, v in s.items()):
            die("ArgumentsBad", "set needs settings: an object of strings, like {\"model\": \"smart-high\"}")
        if "system" in s:                       # 同 self_llm（11-11 使用者「報錯並指路」）
            die("ArgumentsBad", "system is not a brain setting: change the definition's system text with "
                "{\"op\": \"system\", \"path\": ..., \"args\": {\"op\": \"set\", \"text\": \"...\"}}; nothing stored")
        read_llm(path)
        known = body_keys(defdir)
        for k in s:
            if known is not None and k not in known:
                print("(%s is not a setting the body reads (it reads: %s); stored anyway)" % (k, ", ".join(known) or "none"))
        if not os.path.exists(path):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("{}\n")
            except OSError as e:
                die("WriteFailed", "cannot create %s: %s" % (tool_io.place(path), tool_io.os_reason(e)))
        for k in s:
            run(["aos-json", "set", "--str", path + "#" + pointer(k), s[k]])
    elif op == "rm":
        keys = a.get("keys")
        if not isinstance(keys, list) or not keys or not all(isinstance(k, str) and k for k in keys):
            die("ArgumentsBad", "rm needs keys: a list of key names, like [\"temperature\"]")
        have = read_llm(path)
        missing = [k for k in keys if k not in have]
        if missing:
            die("KeyMissing", "%s not in %s (it has: %s); nothing removed" % (", ".join(missing), tool_io.place(path), ", ".join(have) or "none"))
        for k in keys:
            run(["aos-json", "del", path + "#" + pointer(k)])
    vals = read_llm(path)
    for k, v in vals.items():
        print("%s=%s" % (k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))
    if not vals:
        print("(no settings: the body uses its defaults)")
    if op != "ls":
        after("llm")


def system(defdir, a, op):
    """get＝印定義那份全文；set＝整份換成 text（空字串也收；先寫同層暫存檔再改名）。"""
    path = declared(defdir, "system")
    if op == "get":
        try:
            with open(path, encoding="utf-8") as f:
                body = f.read()
        except FileNotFoundError:
            body = None
        except (OSError, UnicodeError) as e:
            die("DefBad", "cannot read %s: %s" % (tool_io.place(path), tool_io.os_reason(e)))
        if body:
            emit(body)
        else:
            print("(no system text: %s %s)" % (path, "is empty" if body is not None else "does not exist"))
        return
    body = a.get("text")
    if not isinstance(body, str):
        die("ArgumentsBad", "set needs text: the whole new system text as a string (\"\" = none)")
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(body)
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        os.replace(tmp, path)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        die("WriteFailed", "cannot write %s: %s" % (tool_io.place(path), tool_io.os_reason(e)))
    print("set the system text of the definition: %s (%d bytes)" % (path, len(body.encode("utf-8"))))
    after("system")


def do(run, defdir, what, a):
    op = check_args(what, a)
    if what == "tools":
        tools(run, defdir, a, op)
    elif what == "llm":
        llm(run, defdir, a, op)
    else:
        system(defdir, a, op)
