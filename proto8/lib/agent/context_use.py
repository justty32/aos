"""context_use - 一隻 agent 現在的 context 用了多少（給 aos 層的「快滿了先收尾再 compact」判斷，lib/agent/context_wrap）；各種腦各一個讀法，讀不到＝None。

使用者 11-15：「最好弄個hook，當context到達一定程度的時候跟agent說整理收尾，然後跑compact。」裁定「3.我們做通用的aos判斷，eca的話可以在這個基礎上接上claude hook。」
純標準庫，不 import py、不印東西、不報錯：讀不到、檔壞、格式不認得一律回 None（呼叫方就當「不知道」、不觸發）。

對外：
    read(stack, window=None) -> {"used": 本輪最後一次呼叫的輸入 token, "window": context 視窗, "percent": used/window*100,
                    "turn": 這份讀數屬於哪一輪（字串；同一輪讀幾次都一樣）, "source": 從哪讀的} | None
    PROVIDERS：照順序試，第一個回非 None 的算數。要讓別種腦也提供用量，往這裡加一個函式 (stack) -> 同上 | None。

讀法（照順序）：
  1. 通用檔 <stack>/context_usage.json：任何腦都可以在每輪結束時寫 {"used": 整數, "window": 整數, "turn": 字串}（turn 選填，沒寫＝用檔的 mtime）。
  2. claude 身（aos-eca-turn 的 claude -p --output-format stream-json）：<stack>/claude/live.jsonl（只接不重寫）。最後一個 result 事件
     跟它前一個 result 之間的那段＝最後答完的那一輪；那段裡最後一個主對話的 assistant 事件（parent_tool_use_id 空的）的 message.usage：
     input_tokens＋cache_read_input_tokens＋cache_creation_input_tokens＝那一刻的 context 大小（跟 statusline 的算法一樣）；
     視窗＝那個 result 的 modelUsage.<model>.contextWindow（取 assistant 那則的 model，找不到取最大的）。
     那段裡有 compact_boundary 事件，它前面的 usage 不算（壓過了）；那段沒有 assistant（例：/compact 那一輪）＝None。
     畫面開著時（tmux 裡的互動 claude）不寫 live.jsonl，讀到的是上一次 -p 那輪的數字（舊的）；呼叫方靠 turn 認新舊。
  3. fsm 腦：<stack>/observed.jsonl 最後 256 KiB 裡最後一則有用量的 think；視窗用 window 參數，或 think/brain_wait.json 指的 kernel 公開的 endpoints.json。
  explain(stack, window=None) 回一行英文讀數或讀不到的原因，不印東西。codex 身目前沒有讀法＝None。
"""
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


PROVIDERS = [from_file, from_claude_live, from_fsm_observed]


def read(stack, window=None):
    for provider in PROVIDERS:
        try:
            got = provider(stack, window=window) if provider is from_fsm_observed else provider(stack)
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
    try:
        reason = _fsm_reading(stack, window)[1]
    except Exception:
        reason = None
    return "no reading: " + (reason or "no provider knows this stack")
