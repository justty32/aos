# mcp_server_file.py - 外部 MCP 的 server 檔：讀一份、驗形狀、讀金鑰檔；給 cli_session 翻成 codex 的 -c 與只給 CLI 行程的環境（11-12 external-mcp 02／03 步 1）
"""一台外部 MCP server＝一份 server 檔（external-mcp 02）：{"description": …, "mcp_server": {"name", "transport", …}}。

http：url、bearer_token_env（變數名）、env_file（金鑰檔位置，起 CLI 那一刻才讀、只拿那一個變數）、ca_file（選填，設 SSL_CERT_FILE／CODEX_CA_CERTIFICATE）。
stdio：command、args、env、env_file；server 在 server 檔的資料夾起（cwd），command 與 args 的相對路徑都從那裡算（stdio_launch）。兩種共用 only／except（兩個都寫＝壞）。
鍵寫錯種類、不認的鍵＝壞。env_file／ca_file 可寫指示詞（directive_value），相對路徑從 server 檔的資料夾算。
壞＝tool_io.Error（PackMissing／PackBad／PathMissing／DotenvBad），由 cli_session 印 warning、跳過那台（X8）。
金鑰的值只回給呼叫者放進 CLI 行程的環境，不寫檔、不上命令列、不進任何錯誤句（句子只講變數名與檔的位置）。

也是一支小啟動器（畫面那條路用）：python3 mcp_server_file.py --exec SPEC -- 指令…——SPEC 是一份 JSON
{"set": {變數: 值}, "from": [[變數, env 檔], …]}（只有路徑與變數名，沒有值），讀完把變數放進自己的環境再 exec 成那支指令；
值只活在那支指令的行程裡（tmux 與 cli_session 的環境都沒有）。"""
import json
import os
import re
import sys

from tool_io import Error

NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
COMMON = {"name", "transport", "only", "except", "env_file"}
KEYS = {"http": COMMON | {"url", "bearer_token_env", "ca_file"},
        "stdio": COMMON | {"command", "args", "env"}}


def _path(value, server_file, key):
    """env_file／ca_file：指示詞先解；相對路徑從 server 檔的資料夾算；回絕對路徑。"""
    if isinstance(value, dict):
        from directive_value import resolve_path
        value = resolve_path(value, server_file, key)
    if not isinstance(value, str) or not value:
        raise Error("PackBad", "%s: %s must be a path (a non-empty string)" % (server_file, key))
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(server_file)), os.path.expanduser(value)))


def _names(value, server_file, key):
    if not isinstance(value, list) or not value or not all(isinstance(n, str) and n for n in value):
        raise Error("PackBad", "%s: %s must be a non-empty array of tool names" % (server_file, key))
    return list(value)


def load(server_file):
    """讀一份 server 檔、驗形狀；回一層 dict（file、name、transport，加上那種形狀用得到的鍵，路徑都已解成絕對）。"""
    try:
        with open(server_file, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        raise Error("PackMissing", "server file not found: %s" % server_file) from None
    except (OSError, ValueError) as e:
        raise Error("PackBad", "%s: %s" % (server_file, e)) from None
    s = doc.get("mcp_server") if isinstance(doc, dict) else None
    if not isinstance(s, dict):
        raise Error("PackBad", "%s: must be an object with an mcp_server object" % server_file)
    name, kind = s.get("name"), s.get("transport")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise Error("PackBad", "%s: mcp_server.name must match [a-z][a-z0-9_]* (at most 32 chars)" % server_file)
    if name == "aos":
        raise Error("PackBad", "%s: the name aos is taken by aos's own server" % server_file)
    if kind not in KEYS:
        raise Error("PackBad", "%s: mcp_server.transport must be \"http\" or \"stdio\"" % server_file)
    extra = sorted(set(s) - KEYS[kind])
    if extra:
        raise Error("PackBad", "%s: keys not allowed for transport %s: %s" % (server_file, kind, ", ".join(extra)))
    if "only" in s and "except" in s:
        raise Error("PackBad", "%s: write only or except, not both" % server_file)
    out = {"file": os.path.abspath(server_file), "name": name, "transport": kind}
    for k in ("only", "except"):
        if k in s:
            out[k] = _names(s[k], server_file, k)
    if "env_file" in s:
        out["env_file"] = _path(s["env_file"], server_file, "env_file")
        if not os.path.isfile(out["env_file"]):
            raise Error("PathMissing", "%s: env_file not found: %s" % (server_file, out["env_file"]))
    if kind == "http":
        if not isinstance(s.get("url"), str) or not re.match(r"https?://", s["url"]):
            raise Error("PackBad", "%s: url must be an http(s):// address" % server_file)
        out["url"] = s["url"]
        if "bearer_token_env" in s:
            if not isinstance(s["bearer_token_env"], str) or not ENV_NAME_RE.match(s["bearer_token_env"]):
                raise Error("PackBad", "%s: bearer_token_env must be an environment variable name" % server_file)
            out["bearer_token_env"] = s["bearer_token_env"]
        if "ca_file" in s:
            out["ca_file"] = _path(s["ca_file"], server_file, "ca_file")
            if not os.path.isfile(out["ca_file"]):
                raise Error("PathMissing", "%s: ca_file not found: %s" % (server_file, out["ca_file"]))
    else:
        if not isinstance(s.get("command"), (str, dict)) or not s["command"]:
            raise Error("PackBad", "%s: stdio needs a command" % server_file)
        if not isinstance(s.get("args", []), (list, dict)):
            raise Error("PackBad", "%s: args must be an array" % server_file)
        if not isinstance(s.get("env", {}), dict):
            raise Error("PackBad", "%s: env must be an object" % server_file)
        out.update(command=s["command"], args=s.get("args", []), env=s.get("env", {}))
    return out


def read_env_file(path):
    """KEY=VALUE 一行一個；空行與 # 開頭略過；可有 export 前綴；值兩邊成對的引號拿掉。認不得的行＝DotenvBad（句子只講第幾行）。"""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeError) as e:
        raise Error("DotenvBad", "cannot read env file %s: %s" % (path, e.__class__.__name__)) from None
    env = {}
    for i, line in enumerate(lines, 1):
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        if t.startswith("export "):
            t = t[7:].lstrip()
        k, eq, v = t.partition("=")
        k = k.strip()
        if not eq or not ENV_NAME_RE.match(k):
            raise Error("DotenvBad", "env file %s line %d is not KEY=VALUE" % (path, i))
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        env[k] = v
    return env


def bearer_value(server):
    """這台的 bearer token 值（只給呼叫者放進 CLI 行程環境）；沒寫 bearer_token_env＝None。
    寫了 env_file 卻沒有那個變數＝PackBad；沒寫 env_file＝None（用 CLI 行程本來繼承到的）。"""
    var = server.get("bearer_token_env")
    if not var or "env_file" not in server:
        return None
    env = read_env_file(server["env_file"])
    if not env.get(var):
        raise Error("PackBad", "%s: env_file %s has no %s" % (server["file"], server["env_file"], var))
    return env[var]


def http_plan(servers, warn):
    """codex 用：http server 逐台備好。回 (留下的 servers, 要放進 CLI 行程的環境, 給畫面啟動器的 spec)。
    某台金鑰讀不到、ca_file 跟前面那台不同＝warn 跳過那台（X8、04 第 26 條代定：第一台算數）。"""
    kept, env, spec = [], {}, {"set": {}, "from": []}
    ca = None
    for s in servers:
        try:
            val = bearer_value(s)
        except Error as e:
            warn("external MCP server %s skipped: %s %s" % (s["name"], e.code, e))
            continue
        if "ca_file" in s:
            if ca and s["ca_file"] != ca:
                warn("external MCP server %s skipped: its ca_file differs from an earlier server's (%s); one CLI process takes one CA bundle"
                     % (s["name"], ca))
                continue
            ca = s["ca_file"]
        kept.append(s)
        if val is not None:
            env[s["bearer_token_env"]] = val
            spec["from"].append([s["bearer_token_env"], s["env_file"]])
    if ca:
        env.update(SSL_CERT_FILE=ca, CODEX_CA_CERTIFICATE=ca)
        spec["set"].update(SSL_CERT_FILE=ca, CODEX_CA_CERTIFICATE=ca)
    return kept, env, spec


def toml_table(d):
    """一層字串表寫成 TOML inline table（鍵、值都用 JSON 字串，同時是合法的 TOML 字串）；cli_session 的 aos 那台也用這份。"""
    return "{" + ", ".join("%s = %s" % (json.dumps(k), json.dumps(v, ensure_ascii=False)) for k, v in d.items()) + "}"


def codex_argv(servers, launcher=None, stdio_env=None):
    """server 翻成 codex 的 -c（值照 TOML：JSON 字串與字串陣列同時是合法的 TOML）。http＝url（＋bearer_token_env_var）；
    stdio＝command＝launcher（aos-mcp-launch）、args＝[server 檔]、env＝stdio_env（codex 不替 MCP server 帶父行程環境，11-11；給 AOS_HOME 之類讓指示詞解得開）。
    列了＝整台免核准（題三）；only＝enabled_tools、except＝disabled_tools（沒實測，代定）；有 bearer＝自動補 shell_environment_policy.exclude。"""
    argv, hidden = [], []
    for s in servers:
        p = "mcp_servers.%s." % s["name"]
        if s["transport"] == "stdio":
            argv += ["-c", p + "command=" + json.dumps(launcher), "-c", p + "args=" + json.dumps([s["file"]])]
            if stdio_env:
                argv += ["-c", p + "env=" + toml_table(stdio_env)]
        else:
            argv += ["-c", p + "url=" + json.dumps(s["url"])]
        if s.get("bearer_token_env"):
            argv += ["-c", p + "bearer_token_env_var=" + json.dumps(s["bearer_token_env"])]
            hidden.append(s["bearer_token_env"])
        argv += ["-c", p + "default_tools_approval_mode=" + json.dumps("approve")]
        if "only" in s:
            argv += ["-c", p + "enabled_tools=" + json.dumps(s["only"])]
        if "except" in s:
            argv += ["-c", p + "disabled_tools=" + json.dumps(s["except"])]
    if hidden:
        argv += ["-c", "shell_environment_policy.exclude=" + json.dumps(sorted(set(hidden)))]
    return argv


def claude_entries(servers, launcher=None):
    """http server 翻成 claude --mcp-config 的 mcpServers 格（跟 aos 那格並排）與放行旗標（11-12 步 3，實測 claude 2.1.x）。
    bearer＋env_file＝headersHelper 叫本檔 --headers（token 只經管線給 claude，不進 claude 的環境＝它的 Bash 看不到，實測）；
    bearer 沒寫 env_file＝headers 寫 "Bearer ${變數}"（claude 會展開，實測；值得在 claude 的環境裡，它的 Bash 看得到）。
    回 (mcpServers 的 dict, --allowedTools 要加的, --disallowedTools 要加的)。"""
    import shlex
    entries, allowed, denied = {}, [], []
    me = os.path.abspath(__file__)
    for s in servers:
        if s["transport"] == "stdio":
            e = {"command": launcher, "args": [s["file"]]}
        else:
            e = {"type": "http", "url": s["url"]}
        var = s.get("bearer_token_env")
        if var and "env_file" in s:
            e["headersHelper"] = " ".join(shlex.quote(a) for a in (sys.executable, me, "--headers", s["env_file"], var))
        elif var:
            e["headers"] = {"Authorization": "Bearer ${%s}" % var}
        entries[s["name"]] = e
        if "only" in s:
            allowed += ["mcp__%s__%s" % (s["name"], t) for t in s["only"]]
        else:
            allowed.append("mcp__%s" % s["name"])
        denied += ["mcp__%s__%s" % (s["name"], t) for t in s.get("except", [])]
    return entries, allowed, denied


def claude_plan(servers, warn):
    """claude 用：跟 http_plan 同樣逐台檢查（金鑰檔、ca_file），但 token 不放環境（走 headersHelper）；
    ca_file＝NODE_EXTRA_CA_CERTS（claude 是 node，實測吃）。回 (留下的 servers, 給 claude 行程的環境, 畫面啟動器的 spec)。"""
    kept, env, _ = http_plan(servers, warn)
    ca = env.get("SSL_CERT_FILE")
    cenv = {"NODE_EXTRA_CA_CERTS": ca} if ca else {}
    return kept, cenv, ({"set": dict(cenv), "from": []} if cenv else None)


def stdio_launch(server_file):
    """aos-mcp-launch 與 mcp_client 用：讀 stdio 的 server 檔，回 (argv, 環境, cwd)。command／args（整個或其中一個元素）的指示詞這一刻才解；
    cwd＝server 檔的資料夾（Q2 代定 G13：command 與 args 的相對路徑都從這裡算——command 含 / 的由這裡接成絕對、args 由 server 自己照 cwd 解）；
    環境＝目前的＋env（明文）＋env_file 整份（金鑰，只進 server 行程；目前的整份照給，Q1 使用者裁不做白名單）。http 的檔＝PackBad。"""
    s = load(server_file)
    if s["transport"] != "stdio":
        raise Error("PackBad", "%s: transport is %s; aos-mcp-launch only starts stdio servers" % (server_file, s["transport"]))
    from directive_value import resolve
    base = os.path.dirname(s["file"])
    cmd = resolve(s["command"], base)
    args = resolve(s["args"], base) if isinstance(s["args"], dict) else [resolve(a, base) for a in s["args"]]
    if not isinstance(cmd, str) or not cmd:
        raise Error("PackBad", "%s: command must resolve to a non-empty string" % server_file)
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise Error("PackBad", "%s: args must resolve to an array of strings" % server_file)
    if "/" in cmd:
        cmd = os.path.normpath(os.path.join(base, cmd))
    env = dict(os.environ)
    for k, v in s["env"].items():
        if not ENV_NAME_RE.match(k) or not isinstance(v, str):
            raise Error("PackBad", "%s: env must map variable names to strings" % server_file)
        env[k] = v
    if "env_file" in s:
        env.update(read_env_file(s["env_file"]))
    return [cmd] + args, env, base


def exec_main(argv):
    """--exec SPEC -- 指令…：照 SPEC 讀 env 檔、放進環境，exec 成指令。讀不到＝stderr 一行、退 1。"""
    if len(argv) < 4 or argv[0] != "--exec" or argv[2] != "--":
        sys.stderr.write("usage: mcp_server_file.py --exec SPEC -- COMMAND [ARGS...]\n")
        return 2
    spec = json.loads(argv[1])
    env = dict(os.environ)
    env.update(spec.get("set", {}))
    try:
        for var, path in spec.get("from", []):
            val = read_env_file(path).get(var)
            if not val:
                raise Error("PackBad", "env file %s has no %s" % (path, var))
            env[var] = val
    except Error as e:
        sys.stderr.write("mcp_server_file: error: %s %s\n" % (e.code, e))
        return 1
    os.execvpe(argv[3], argv[3:], env)


def headers_main(argv):
    """--headers ENV_FILE VAR：claude 的 headersHelper 用——印 {"Authorization": "Bearer <值>"} 一行給 claude 讀（值只經管線進 claude，不進任何環境）。"""
    if len(argv) != 3:
        sys.stderr.write("usage: mcp_server_file.py --headers ENV_FILE VAR\n")
        return 2
    try:
        val = read_env_file(argv[1]).get(argv[2])
        if not val:
            raise Error("PackBad", "env file %s has no %s" % (argv[1], argv[2]))
    except Error as e:
        sys.stderr.write("mcp_server_file: error: %s %s\n" % (e.code, e))
        return 1
    sys.stdout.write(json.dumps({"Authorization": "Bearer " + val}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(headers_main(sys.argv[1:]) if sys.argv[1:2] == ["--headers"] else exec_main(sys.argv[1:]))
