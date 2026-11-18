"""context_use - 一隻 agent 現在的 context 用了多少（給 aos 層的「快滿了先收尾再 compact」判斷，py/tools/agent/context_wrap）；各種腦各一個讀法，讀不到＝None。

使用者 11-15：「最好弄個hook，當context到達一定程度的時候跟agent說整理收尾，然後跑compact。」裁定「3.我們做通用的aos判斷，eca的話可以在這個基礎上接上claude hook。」
純標準庫，不 import py、不印東西、不報錯：讀不到、檔壞、格式不認得一律回 None（呼叫方就當「不知道」、不觸發）。

對外：
    read(stack, window=None) -> {"used": 本輪最後一次呼叫的輸入 token, "window": context 視窗, "percent": used/window*100,
                    "turn": 這份讀數屬於哪一輪（字串；同一輪讀幾次都一樣）, "source": 從哪讀的} | None
    PROVIDERS：照順序試（claude 身是 from_claude：2a 找得到 transcript 就用它，否則 2），第一個回非 None 的算數。要讓別種腦也提供用量，往這裡加一個函式 (stack) -> 同上 | None（要收 hook 的 config.window 就寫成 (stack, window=None) 並列進 TAKES_WINDOW）。

讀法（照順序）：
  1. 通用檔 <stack>/context_usage.json：任何腦都可以在每輪結束時寫 {"used": 整數, "window": 整數, "turn": 字串}（turn 選填，沒寫＝用檔的 mtime）。
  2. claude 身（aos-eca-turn 的 claude -p --output-format stream-json）：<stack>/claude/live.jsonl（只接不重寫）。最後一個 result 事件
     跟它前一個 result 之間的那段＝最後答完的那一輪；那段裡最後一個主對話的 assistant 事件（parent_tool_use_id 空的）的 message.usage：
     input_tokens＋cache_read_input_tokens＋cache_creation_input_tokens＝那一刻的 context 大小（跟 statusline 的算法一樣）；
     視窗＝那個 result 的 modelUsage.<model>.contextWindow（取 assistant 那則的 model，找不到取最大的）。
     那段裡有 compact_boundary 事件，它前面的 usage 不算（壓過了）；那段沒有 assistant（例：/compact 那一輪）＝None。
     畫面開著時（tmux 裡的互動 claude）不寫 live.jsonl，所以 claude 身先讀 2a。
  2a. claude 的 transcript（11-16 ok-small；from_claude）：<stack>/claude/session.txt 的 id → 小格的 transcripts/claude-<id>.jsonl，
     或 CLAUDE_CONFIG_DIR（預設 ~/.claude）/projects/*/<id>.jsonl。畫面開著（互動）與 -p 的每一輪 claude 都寫進這份。最後一則主對話
     （isSidechain 不是 true）、stop_reason 是講完一輪（end_turn 等，不含 tool_use）、usage 完整的 assistant 的 message.usage，算法同 2；
     從檔尾往前讀（最多 64 MiB），先碰到 compact_boundary＝前面的不算。transcript 沒有 contextWindow：視窗＝window 參數（hook 的 config.window），
     沒給＝live.jsonl 舊 result 記的 contextWindow（同 model，找不到取最小的），都沒有＝None（explain 說要設 config.window）。
     transcript 找得到就以它為準：它讀不到＝None，不退回 live（免得壓完讀到壓之前的數字又觸發）；找不到才讀 2 的 live.jsonl。
     實測 claude 2.1.325（11-16）：transcript 的 assistant 行有 usage（數字同 stream）、stop_reason；-p /compact 那輪沒有 assistant。
     畫面開著時 context_wrap 寄的 /compact 怎麼進畫面（aos/apps/eca/slash.py slash_turn→on_screen）：畫面正在答（busy.txt）＝不打、信留 cur/ 下一輪再試；
     claude 的輸入框有人打了字或看不出來（screen_slash.input_clear）＝也不打、信留著（不用 C-u 清，會吃掉人的字）；
     否則 tmux send-keys 打字、0.5 秒後 Enter，等畫面的 hook 換掉 history（上限 120 秒）才回信，等不到只在回信裡說一句、不重打。
  3. fsm 腦：<stack>/observed.jsonl 最後 256 KiB 裡最後一則有用量的 think；視窗用 window 參數，或 think/brain_wait.json 指的 kernel 公開的 endpoints.json。
  explain(stack, window=None) 回一行英文讀數或讀不到的原因，不印東西。codex 身目前沒有讀法＝None。
"""
import glob
import hashlib
import json
import os

FILE = "context_usage.json"
TAIL = 4 * 1024 * 1024                     # live.jsonl 只讀最後這麼多 bytes（一輪的事件遠小於它）
INPUT_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _whole(n):
    return isinstance(n, int) and not isinstance(n, bool) and n >= 0


def _row(used, window, turn, source):
    if not (_whole(used) and _whole(window) and window > 0):
        return None
    return {"used": used, "window": window, "percent": used * 100.0 / window, "turn": str(turn), "source": source}


def from_file(stack):
    path = os.path.join(stack, FILE)
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        mtime = os.path.getmtime(path)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    turn = doc.get("turn") if isinstance(doc.get("turn"), str) and doc.get("turn") else "mtime:%r" % mtime
    return _row(doc.get("used"), doc.get("window"), turn, path)


def _events(path):
    """live.jsonl 最後 TAIL bytes 的 [(原始行 bytes, 事件 dict)]；第一行可能被切半，丟掉。"""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL))
            raw = f.read()
    except OSError:
        return []
    lines = raw.split(b"\n")
    if size > TAIL:
        lines = lines[1:]
    out = []
    for line in lines:
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            out.append((line, ev))
    return out


def from_claude_live(stack):
    path = os.path.join(stack, "claude", "live.jsonl")
    evs = _events(path)
    ends = [i for i, (_, ev) in enumerate(evs) if ev.get("type") == "result"]
    if not ends:
        return None
    last = ends[-1]
    start = ends[-2] + 1 if len(ends) > 1 else 0
    usage, model = None, None
    for _, ev in evs[start:last]:
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "compact_boundary":
            usage, model = None, None                # 壓過了：前面的數字不算
        elif kind == "assistant" and not ev.get("parent_tool_use_id"):
            msg = ev.get("message")
            u = msg.get("usage") if isinstance(msg, dict) else None
            if isinstance(u, dict):
                usage, model = u, msg.get("model")
    if usage is None:
        return None
    if not all(_whole(usage.get(k, 0)) for k in INPUT_KEYS):
        return None
    used = sum(usage.get(k, 0) for k in INPUT_KEYS)
    mu = evs[last][1].get("modelUsage")
    windows = {}
    if isinstance(mu, dict):
        for name, row in mu.items():
            if isinstance(row, dict) and _whole(row.get("contextWindow")) and row["contextWindow"] > 0:
                windows[name] = row["contextWindow"]
    if not windows:
        return None
    window = windows.get(model) or max(windows.values())
    turn = "claude:" + hashlib.sha256(evs[last][0]).hexdigest()[:16]
    return _row(used, window, turn, path)


TRANSCRIPT_DONE = ("end_turn", "stop_sequence", "max_tokens", "pause_turn", "refusal")   # 講完一輪的 stop_reason（不含 tool_use 與 None）
SID_CHARS = set("0123456789abcdefABCDEF-")


def _transcript_path(cell):
    """claude 的 session id（cell/session.txt）指的 transcript：先找小格的 transcripts/claude-<id>.jsonl symlink（cli_cell.link_transcript），
    再找 CLI 自己的帳號資料夾（CLAUDE_CONFIG_DIR 或 ~/.claude）的 projects/*/<id>.jsonl。找不到＝None。"""
    try:
        with open(os.path.join(cell, "session.txt"), encoding="utf-8") as f:
            sid = f.read().strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not sid or not set(sid) <= SID_CHARS:            # 只認 uuid 形狀：不讓 session.txt 的字變成 glob
        return None
    link = os.path.join(cell, "transcripts", "claude-%s.jsonl" % sid)
    if os.path.isfile(link):
        return link
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    found = [p for p in glob.glob(os.path.join(glob.escape(base), "projects", "*", sid + ".jsonl")) if os.path.isfile(p)]
    return max(found, key=os.path.getmtime) if found else None    # 同一個 id 在兩個專案夾：取最新寫的


def _live_windows(stack):
    """live.jsonl（-p 那幾輪）的 result 裡記過的 contextWindow：{model: window}，後面的蓋前面的。"""
    windows = {}
    for _, ev in _events(os.path.join(stack, "claude", "live.jsonl")):
        mu = ev.get("modelUsage") if ev.get("type") == "result" else None
        if isinstance(mu, dict):
            for name, row in mu.items():
                if isinstance(row, dict) and _whole(row.get("contextWindow")) and row["contextWindow"] > 0:
                    windows[name] = row["contextWindow"]
    return windows


TRANSCRIPT_BLOCK = 1024 * 1024
TRANSCRIPT_SCAN = 64 * 1024 * 1024    # 倒著讀最多這麼多：transcript 很大（含整份 request 的 api-request-blob），一輪的工具呼叫可以好幾 MiB


def _transcript_rows(path):
    """transcript 的行，從檔尾往前（新的先）；只 parse 看起來像 assistant 或 compact_boundary 的行。讀到檔頭或 TRANSCRIPT_SCAN 為止。"""
    try:
        f = open(path, "rb")
    except OSError:
        return
    with f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        rest, read = b"", 0
        while pos > 0 and read < TRANSCRIPT_SCAN:
            step = min(TRANSCRIPT_BLOCK, pos)
            pos -= step
            read += step
            f.seek(pos)
            lines = (f.read(step) + rest).split(b"\n")
            rest = lines.pop(0) if pos > 0 else b""          # 最前面那段可能被切半，留給下一塊
            for line in reversed(lines):
                if b'"assistant"' not in line and b"compact_boundary" not in line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if isinstance(ev, dict):
                    yield ev


def _turn_usage(ev):
    """一則講完一輪的主對話 assistant 的 (usage, model, id)；不是或 usage 不完整＝None。"""
    msg = ev.get("message")
    if not isinstance(msg, dict) or msg.get("stop_reason") not in TRANSCRIPT_DONE:
        return None
    u = msg.get("usage")
    if not isinstance(u, dict) or not any(k in u for k in INPUT_KEYS) or not all(_whole(u.get(k, 0)) for k in INPUT_KEYS):
        return None
    mid = next((x for x in (msg.get("id"), ev.get("uuid")) if isinstance(x, str) and x), None)
    return u, msg.get("model"), mid


def _transcript_reading(stack, window=None):
    """(有沒有 transcript, 讀數或 None, 讀不到的原因)。transcript＝claude 自己存的對話檔，畫面開著（互動）跟 -p 的每一輪都寫在裡面；
    從檔尾往前找最後一則主對話（isSidechain 不是 true）、stop_reason 是講完一輪、usage 完整的 assistant 的 message.usage（算法同 live）；
    先碰到主對話的 compact_boundary＝壓完還沒講完一輪＝None。transcript 沒有 contextWindow：
    視窗＝window 參數（hook 的 config.window），沒給＝live.jsonl 舊 result 記的（同 model，找不到取最小的），都沒有＝None。"""
    path = _transcript_path(os.path.join(stack, "claude"))
    if path is None:
        return False, None, None
    hit = None
    for ev in _transcript_rows(path):                    # 新的先：第一個主對話的 compact_boundary 或講完一輪的 assistant 定案
        if ev.get("isSidechain") is True:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "compact_boundary":
            break                                         # 壓過了、壓完還沒講完一輪
        if ev.get("type") == "assistant":
            hit = _turn_usage(ev)                         # usage 壞掉的那則略過，看更早的
            if hit is not None:
                break
    if hit is None:
        return True, None, ("claude transcript: no finished turn with usage since the last compaction "
                            "(read back at most %d MiB) in %s" % (TRANSCRIPT_SCAN // 1048576, path))
    usage, model, mid = hit
    if window is None:
        windows = _live_windows(stack)
        window = (windows.get(model) or min(windows.values())) if windows else None   # 不知道 model：取小的，寧早勿晚
        if window is None:
            return True, None, ("claude transcript: no context window known (claude/live.jsonl has no result with "
                                "contextWindow yet); set config.window in the hook entry")
    turn = "claude-transcript:%s" % (mid or hashlib.sha256(json.dumps(usage, sort_keys=True).encode()).hexdigest()[:16])
    got = _row(sum(usage.get(k, 0) for k in INPUT_KEYS), window, turn, path)
    return True, got, None if got is not None else "claude transcript: window must be a positive integer"


def from_claude(stack, window=None):
    """claude 身：transcript 找得到就以它為準（畫面開著也讀得到；它讀不到＝None，不退回 live，免得壓完讀到壓之前的數字），
    找不到（還沒有 session、--no-session-persistence、檔被 CLI 清掉）才讀 live.jsonl。"""
    has, got, _ = _transcript_reading(stack, window)
    return got if has else from_claude_live(stack)


OBSERVED = "observed.jsonl"
OBSERVED_TAIL = 256 * 1024


def _fsm_used(usage):
    if not isinstance(usage, dict):
        return None
    if "prompt_tokens" in usage:
        used = usage["prompt_tokens"]
        return used if _whole(used) else None
    if any(k in usage for k in INPUT_KEYS) and all(_whole(usage.get(k, 0)) for k in INPUT_KEYS):
        return sum(usage.get(k, 0) for k in INPUT_KEYS)
    return None


def _fsm_reading(stack, window=None):
    path = os.path.join(stack, OBSERVED)
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            start = max(0, f.tell() - OBSERVED_TAIL)
            f.seek(start)
            if start > 0:
                f.readline()                       # Only a nonzero seek can leave a partial first row.
            lines = f.read().splitlines()
    except OSError:
        return None, None
    row, used = None, None
    for line in reversed(lines):
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if not isinstance(doc, dict) or doc.get("kind") != "think":
            continue
        value = _fsm_used(doc.get("usage"))
        letter = doc.get("letter")
        if value is not None and isinstance(letter, str) and letter:
            row, used = doc, value
            break
    if row is None:
        return None, "fsm: no valid think row with input token usage and a letter in %s" % path
    if window is None:
        wait_path = os.path.join(stack, "think", "brain_wait.json")
        try:
            with open(wait_path, encoding="utf-8") as f:
                wait = json.load(f)
        except (OSError, ValueError):
            return None, "fsm: cannot read the kernel from %s" % wait_path
        kernel = wait.get("kernel") if isinstance(wait, dict) else None
        if not isinstance(kernel, str) or not os.path.isabs(kernel):
            return None, "fsm: no absolute kernel path in %s" % wait_path
        endpoints_path = os.path.join(kernel, "endpoints.json")
        try:
            with open(endpoints_path, encoding="utf-8") as f:
                endpoints = json.load(f)
        except (OSError, ValueError):
            return None, "fsm: cannot read %s; set config.window in the hook entry" % endpoints_path
        endpoint = row.get("endpoint")
        pack = endpoints.get(endpoint) if isinstance(endpoints, dict) and isinstance(endpoint, str) else None
        window = pack.get("context") if isinstance(pack, dict) else None
        if not _whole(window) or window == 0:
            return None, ('fsm: pack %s has no positive integer context in %s; set "context" in the pack '
                          'or config.window in the hook entry' % (json.dumps(endpoint), endpoints_path))
    got = _row(used, window, "fsm:" + row["letter"], path)
    return got, None if got is not None else "fsm: window must be a positive integer"


def from_fsm_observed(stack, window=None):
    return _fsm_reading(stack, window)[0]


PROVIDERS = [from_file, from_claude, from_fsm_observed]
TAKES_WINDOW = (from_claude, from_fsm_observed)          # 這幾個收 window（hook 的 config.window）


def read(stack, window=None):
    for provider in PROVIDERS:
        try:
            got = provider(stack, window=window) if provider in TAKES_WINDOW else provider(stack)
        except Exception:                        # 讀法本身出錯也當讀不到（介面約定：不報錯）
            got = None
        if got is not None:
            return got
    return None


def explain(stack, window=None):
    got = read(stack, window=window)
    if got is not None:
        return "%.1f%% (%d of %d tokens), turn %s, from %s" % (
            got["percent"], got["used"], got["window"], got["turn"], got["source"])
    reason = None
    for why in (lambda: _transcript_reading(stack, window)[2], lambda: _fsm_reading(stack, window)[1]):
        try:
            reason = why()
        except Exception:
            reason = None
        if reason:
            break
    return "no reading: " + (reason or "no provider knows this stack")
