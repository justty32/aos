"""aos_ai_explain - aos-ai explain：印概念速成（claude_skill/aos/concepts.md 的一節），或算出「現在 aos-exec XXX」的具體值。

使用者 10-24「方便生成相關json，也要包括讓AI能充分理解aos的各種概念，包括WS/ENTRY/STACK等」。
--here 是照 N-58、N-59、N-61、N-62 模擬（不跑入口）：工作區、stack、讀了哪些 .env、挑到哪個入口、種類、AOS_CF／CD／CO。以 aos-exec 為準。"""
import json, os, re
from pathlib import Path

CONCEPTS = Path(__file__).resolve().parent.parent / "claude_skill" / "aos" / "concepts.md"


def sections():
    """concepts.md 照「## 名字」切成 {名字: 內文}（照檔裡的順序）。"""
    out, name, buf = {}, None, []
    for line in CONCEPTS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"## (\S+)\s*$", line)
        if m:
            if name:
                out[name] = "\n".join(buf).strip()
            name, buf = m.group(1), []
        elif name:
            buf.append(line)
    if name:
        out[name] = "\n".join(buf).strip()
    return out


def find(key):
    secs = sections()
    for k in secs:
        if k.lower() == key.lower():
            return k, secs[k]
    alias = {"ws": "AOS_WS", "stack": "AOS_STACK", "entry_name": "AOS_ENTRY", "cf": "AOS_CF", "cd": "AOS_CD",
             "co": "AOS_CO", "_metainfo": "metainfo", "ctl": "window", "state": "window", "env_file": "dotenv",
             ".env": "dotenv", "单子": "inst", "單子": "inst", "exec": "inline", "exit_code": "exit"}
    k = alias.get(key.lower()) or alias.get(key)
    return (k, secs[k]) if k in secs else (None, None)


# ---------- --here：模擬 aos-exec ----------

DOTENV_LINE = re.compile(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def read_dotenv(path):
    """只取名字與粗略的值（給人看；格式細節照 aos-exec，這裡不驗）。"""
    pairs = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = DOTENV_LINE.match(line)
        if m:
            v = m.group(2).strip()
            if v[:1] in "\"'" and v[-1:] == v[:1] and len(v) >= 2:
                v = v[1:-1]
            else:
                v = re.split(r"\s+#", v)[0].strip()
            pairs.append((m.group(1), v))
    return pairs


class Sim:
    def __init__(self, env, override):
        self.env, self.override = dict(env), override
        self.steps, self.dotenvs = [], []

    def note(self, text):
        self.steps.append(text)

    def apply_env(self, pairs, where):
        took, skipped = [], []
        for k, v in pairs:
            v = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", lambda m: self.env.get(m.group(1), ""), v)
            if k in self.env and not self.override:
                skipped.append(k)
            else:
                self.env[k] = v
                took.append(k)
        self.dotenvs.append({"from": where, "set": took, "skipped_already_set": skipped})

    def enter_dir(self, d):
        self.env["AOS_CD"], self.env["AOS_CF"], self.env["AOS_CO"] = str(d), str(d), ""
        self.note("cd %s" % d)
        if (d / ".env").is_file() and self.env.get("AOS_ENTRY", "_entry") != ".env":
            self.apply_env(read_dotenv(d / ".env"), str(d / ".env"))

    def entry_name(self):
        return self.env.get("AOS_ENTRY") or "_entry"


def classify_json(sim, f, node, ptr):
    """N-61 的種類判斷；沒 argv 的物件一路往下（JSON 的 .env key 也套）。回 (種類, 值, 指標)。"""
    while True:
        if isinstance(node, dict) and "argv" in node:
            return "inst", node, ptr
        if isinstance(node, list):
            return ("argv" if node else "bad"), node, ptr
        if isinstance(node, str):
            return "redirect", node, ptr
        if not isinstance(node, dict):
            return "bad", node, ptr
        name = sim.entry_name()
        if name != ".env" and isinstance(node.get(".env"), dict):
            pairs = [(k, v) for k, v in node[".env"].items() if isinstance(v, str)]
            sim.apply_env(pairs, "%s#%s/.env" % (f, ptr))
            name = sim.entry_name()
        if name not in node:
            return "bad", None, ptr + "/" + name   # aos-exec：EntryBad「不是單子、也沒有 X」
        sim.note("沒 argv 的物件＝資料夾：取 %s#%s/%s" % (f.name, ptr, name))
        node, ptr = node[name], ptr + "/" + name.replace("~", "~0").replace("/", "~1")


def load_json(f):
    text = f.read_text(encoding="utf-8", errors="replace")
    if text.startswith("#!"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    return json.loads(text)


def pointer(doc, ptr):
    node = doc
    for raw in [p for p in ptr.split("/")[1:]] if ptr else []:
        k = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and k in node:
            node = node[k]
        elif isinstance(node, list) and k.isdigit() and int(k) < len(node):
            node = node[int(k)]
        else:
            raise KeyError(ptr)
    return node


def from_file(sim, f, ptr):
    f = f.resolve()
    sim.enter_dir(f.parent)
    sim.env["AOS_CF"] = str(f)
    if ptr is None and os.access(f, os.X_OK):
        return {"kind": "executable", "file": str(f)}
    try:
        doc = load_json(f)
    except ValueError as e:
        return {"kind": "bad", "why": "沒 +x 又不是 JSON：%s" % e}
    try:
        node = pointer(doc, ptr or "")
    except KeyError:
        return {"kind": "missing", "why": "%s#%s 指不到" % (f, ptr)}
    kind, val, at = classify_json(sim, f, node, ptr or "")
    sim.env["AOS_CO"] = at
    return {"kind": kind, "file": str(f), "pointer": at, "value": val}


def from_dir(sim, d, seen):
    d = d.resolve()
    if d in seen:
        return {"kind": "bad", "why": "走回走過的資料夾：%s" % d}
    seen.add(d)
    sim.enter_dir(d)
    name = sim.entry_name()
    p = d / name
    if p.is_dir():
        sim.note("$AOS_ENTRY（%s）是資料夾＝走進去" % name)
        return from_dir(sim, p, seen)
    if p.is_file():
        return from_file(sim, p, None)
    if (d / (name + ".json")).is_file():
        return from_file(sim, d / (name + ".json"), None)
    return {"kind": "missing", "why": "%s 裡沒有 %s，也沒有 %s.json" % (d, name, name)}


def here(target, ws_flag, env, override=False):
    sim = Sim(env, override)
    ws = Path(ws_flag if ws_flag not in (None, "-") else env.get("AOS_WS") or os.getcwd()).resolve()
    sim.env["AOS_WS"] = str(ws)
    stack = env.get("AOS_STACK") or str(ws / ".stack")
    sim.env["AOS_STACK"] = str(Path(stack).resolve()) + "/"
    sim.note("工作區＝%s（%s）" % (ws, "--ws" if ws_flag not in (None, "-") else "沿用 $AOS_WS" if env.get("AOS_WS") else "cwd"))
    sim.note("stack＝%s（%s）" % (sim.env["AOS_STACK"], "沿用 $AOS_STACK" if env.get("AOS_STACK") else "預設 $AOS_WS/.stack/，aos-exec 會建"))
    file, _, ptr = target.partition("#")
    if _ and not ptr.startswith("/"):
        res = {"kind": "bad", "why": "# 後面要是 /"}
    else:
        p = Path(file)
        if p.is_dir():
            res = {"kind": "bad", "why": "資料夾不能帶 #/"} if _ else from_dir(sim, p, set())
        elif p.is_file():
            res = from_file(sim, p, ptr if _ else None)
        elif not p.suffix and Path(file + ".json").is_file():
            sim.note("找不到 %s，順道找 %s.json" % (file, file))
            res = from_file(sim, Path(file + ".json"), ptr if _ else None)
        else:
            res = {"kind": "missing", "why": "找不到 %s" % file}
    keys = ("AOS_ENTRY", "AOS_WS", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO")
    shown = {k: sim.env.get(k) for k in keys}
    if shown["AOS_ENTRY"] is None:
        shown["AOS_ENTRY"] = "（沒設＝_entry；aos-exec 不 export）"
    what = {"executable": "exec 這個檔（有 #! 照 shebang，沒有用 /bin/sh），結束碼就是它的",
            "inst": "單子：aos-exec 在行程內跑、當監工（timeout_ms、轉訊號），以子程式的碼結束",
            "argv": "argv 陣列：解指示詞後 exec；argv[0] 帶 / 又 exec 不了＝前面插 aos-exec",
            "redirect": "字串轉向：交給下一層、全新的一次 aos-exec（旗標不帶過去）",
            "missing": "aos-exec 會退 1：EntryMissing", "bad": "aos-exec 會退 1：EntryBad"}[res["kind"]]
    return {"ok": res["kind"] not in ("missing", "bad"), "target": target, "entry": res, "will": what,
            "env_at_start": shown, "cwd_at_start": shown["AOS_CD"], "dotenvs": sim.dotenvs, "steps": sim.steps,
            "note": "照 N-58／N-59／N-61 模擬、沒真的跑；以 aos-exec 為準（概念：aos-ai explain entry）"}
