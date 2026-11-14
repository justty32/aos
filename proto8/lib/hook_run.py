"""hook_run - hook 的共用引擎：事件表由呼叫的人給，這裡只管驗格的共通鍵、比 condition、寫 event.json、用 aos-exec 跑 handler、解回話、on_error。

圖紙：proto8/thinking/2026-11/12/kernel-framework（K-F22；01-框架零件「hook 三個時機」）。從 lib/agent/hooks.py 抽出來，行為逐項相同；
agent 的 hooks.py 與通用 kernel 框架都用這份。放 lib 最底層：純標準庫，不 import lib/agent、不 import py。
不印東西、不 sys.exit：錯丟 HooksBad（格的形狀不對）／HookFailed（on_error stop 的 hook 自己失敗），由呼叫方說自己那一行。
清單從哪讀、幾份疊、事件專用的鍵（例如 agent 的 on_clock 那幾個）都是呼叫方自己的事，這裡不管。

對外：
    events（呼叫方給）＝{事件: {"condition": 事件 JSON 裡拿來比 condition 的欄位名或 None（不收 condition）,
                              "intercept": 能改的鍵（tuple）, "block": 能不能攔（結束碼 10）}}
    DEFAULTS = {"intercept": True, "async": False, "on_error": "stop", "timeout_ms": 60000}
    validate_entry(entry, events) -> None；不對丟 HooksBad（原因不含名字，呼叫方自己加）；只驗共通的鍵
    validate_name(name) -> None；不對丟 HooksBad（原因不含名字與檔路徑，呼叫方自己加）
    complete(entry, path) -> 格＝原格的鍵＋DEFAULTS 補齊＋"from"（來自哪份檔）＋"base"（解 handler 相對路徑的資料夾）
    matches(entry, events, data) -> 這格的 condition 合不合這次的 data
    target(entry, name=None) -> handler 解成 aos-exec 的目標路徑；解不開丟 OSError
    run(name, entry, event, data, stack) -> (結束碼, stdout 字串)；async true＝(None, "")；自己失敗丟 OSError／TimeoutError
    fire(event, data, entries, stack, events, warn=None, only=None, check=None) -> {"data": 改過的 data（新 dict）,
                    "changed": [改過的鍵], "blocked": bool, "hook": 攔下的 hook 名或 None, "text": 攔下那個 hook 的 stdout 或 ""}
"""
import copy
import json
import os
import signal
import subprocess
import time

DEFAULTS = {"intercept": True, "async": False, "on_error": "stop", "timeout_ms": 60000}
BLOCK = 10                                       # 攔下（N-43：10＝「不要」，不是錯）
CELLS = "hooks"                                  # 小格：<stack>/hooks/<名>/


class HooksBad(ValueError):
    """hooks 清單的格（或名字）形狀不對。"""


class HookFailed(RuntimeError):
    """on_error: stop 的 hook 自己失敗（結束碼不是 0／10、逾時、起不來、回話不合）。"""


def validate_entry(entry, events):
    """單格驗證，只驗共通的鍵；不認得的鍵不管（C-48）。不對＝HooksBad。"""
    if not isinstance(entry, dict):
        raise HooksBad("must be a JSON object or null")
    on = entry.get("event")
    if on not in events:
        raise HooksBad("event must be one of %s" % ", ".join(events))
    target = entry.get("handler")
    if not ((isinstance(target, str) and target) or (isinstance(target, dict) and target)):
        raise HooksBad("handler must be a non-empty string or a directive object")
    for key in ("intercept", "async"):
        if key in entry and not isinstance(entry[key], bool):
            raise HooksBad("%s must be true or false" % key)
    if "condition" in entry:
        m = entry["condition"]
        if not (isinstance(m, str) or (isinstance(m, list) and all(isinstance(x, str) for x in m))):
            raise HooksBad("condition must be a string or an array of strings")
        if events[on]["condition"] is None:
            raise HooksBad("event %s takes no condition" % on)
    if "on_error" in entry and entry["on_error"] not in ("stop", "continue"):
        raise HooksBad("on_error must be stop or continue")
    if "timeout_ms" in entry:
        t = entry["timeout_ms"]
        if not isinstance(t, int) or isinstance(t, bool) or t < 0:
            raise HooksBad("timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit)")


def validate_name(name):
    """hook 的名字（也是小格的資料夾名）：非空、不含 /、不以 . 開頭。不對＝HooksBad（句子不帶名字與檔路徑）。"""
    if not name or "/" in name or name.startswith("."):
        raise HooksBad("must be non-empty, without / and not start with .")


def complete(entry, path):
    """一格補齊預設值，加 from（path）與 base（path 所在的資料夾）。"""
    full = dict(DEFAULTS, **entry)
    full["from"], full["base"] = path, os.path.dirname(path)
    return full


def matches(entry, events, data):
    field = events[entry["event"]]["condition"]
    if field is None or "condition" not in entry:
        return True
    m = entry["condition"]
    return data.get(field) in ([m] if isinstance(m, str) else m)


def _stop_group(p):
    """TERM 整群、寬限 2 秒後 KILL（同 agent-fsm act.py）。"""
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        p.poll()
        try:
            os.killpg(p.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def target(entry, name=None):
    """handler → aos-exec 的目標（絕對路徑）；解不開＝丟 OSError 帶原因（當成起不來）。指示詞物件經 aos-directive --file 解。
    name＝hook 名：給了＝handler 在清單裡的位置是 /hooks/<name>/handler（agent 與 kernel 的清單都把表放在檔根的 hooks），
    交給 aos-directive --at，#./、#../ 從那一格算（11-13 線址二）；沒給＝照舊包成 {"v": …}（不知道位置）。"""
    t = entry["handler"]
    if isinstance(t, dict):
        if name is None:
            argv, doc, unwrap = ["aos-directive", "--file", entry["from"]], {"v": t}, True
        else:
            at = "".join("/" + k.replace("~", "~0").replace("/", "~1") for k in ("hooks", name, "handler"))
            argv, doc, unwrap = ["aos-directive", "--file", entry["from"], "--at", at], t, False
        try:
            r = subprocess.run(argv, input=json.dumps(doc), stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, cwd=entry["base"])   # #/… ＝ 這格所在的那份清單
            t = (json.loads(r.stdout).get("v") if unwrap else json.loads(r.stdout)) if r.returncode == 0 else None
        except (OSError, ValueError, AttributeError) as e:
            raise OSError("cannot resolve handler directive: %s" % e) from e
        if not isinstance(t, str) or not t:
            raise OSError("handler directive did not resolve to a non-empty path")
    return t if os.path.isabs(t) else os.path.join(entry["base"], t)


def run(name, entry, event, data, stack):
    """跑一個 hook。回 (結束碼, stdout 字串)；async true＝(None, "")。自己失敗丟 OSError／TimeoutError 帶原因。"""
    cell = os.path.join(os.path.abspath(stack), CELLS, name)
    os.makedirs(cell, exist_ok=True)
    doc = {"event": event, "hook": name, "stack": os.path.abspath(stack)}
    doc.update({k: v for k, v in data.items() if k not in doc})
    path, tmp = os.path.join(cell, "event.json"), os.path.join(cell, ".event.json.tmp")   # N-05：先寫暫存再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    argv = ["aos-exec", "--stack", cell + "/", target(entry, name)]
    wait = not entry["async"]
    with open(path, "rb") as stdin:
        p = subprocess.Popen(argv, stdin=stdin, stdout=subprocess.PIPE if wait else subprocess.DEVNULL,
                             start_new_session=True)   # 自成一群；stderr 不攔、原樣透出
    if not wait:
        return None, ""
    limit = None if entry["timeout_ms"] == 0 else entry["timeout_ms"] / 1000.0  # 0＝不限時
    try:
        try:
            out, _ = p.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            _stop_group(p)
            try:
                p.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                p.stdout.close()
                p.wait()
            raise TimeoutError("did not finish in %d ms (its process group was killed)" % entry["timeout_ms"])
    except BaseException as e:                   # Ctrl-C／TERM：hook 不再跟自己的群，離開前收掉
        if not isinstance(e, TimeoutError):
            _stop_group(p)
            p.wait()
        raise
    return p.returncode, out.decode("utf-8", "replace")


def _changes(event, out, events, check):
    """intercept 的 hook 結束碼 0／10 時 stdout → {鍵: 值}；stdout 空＝{}。不合丟 ValueError（值合不合由呼叫方的 check 說）。"""
    if not out.strip():
        return {}
    try:
        reply = json.loads(out)
    except ValueError as e:
        raise ValueError("stdout is not JSON: %s" % e) from None
    if not isinstance(reply, dict):
        raise ValueError("stdout is not a JSON object")
    got = {}
    for key in events[event]["intercept"]:
        if key not in reply:
            continue
        v = reply[key]
        if check is not None:
            check(event, key, v)
        got[key] = v
    return got


def fire(event, data, entries, stack, events, warn=None, only=None, check=None):
    """跑 event 相同、condition 符合的 hook（照名字排序；前一個改過的後一個看得到；被攔下就停）。
    沒有符合的＝什麼都不做（不起子行程）。entries＝呼叫方已讀好補齊的 {名: 格}；events＝呼叫方的事件表。
    warn＝收一行英文的函式（on_error continue 時叫）；None＝不說。only＝只跑這些名字。
    check(event, key, value)＝hook 改回來的值合不合（不合丟 ValueError、句子由它給）；None＝不檢查。"""
    if event not in events:
        raise ValueError("unknown hook event %s" % event)
    result = {"data": copy.deepcopy(data), "changed": [], "blocked": False, "hook": None, "text": ""}
    names = sorted(n for n, e in entries.items() if e["event"] == event and matches(e, events, data)
                   and (only is None or n in only))
    for name in names:
        entry = entries[name]
        try:
            try:
                code, out = run(name, entry, event, result["data"], stack)
            except (OSError, TimeoutError) as e:
                raise ValueError(str(e)) from None
            if code is None:
                continue
            if code not in (0, BLOCK):
                raise ValueError("exited %d" % code)
            if not entry["intercept"] or not (events[event]["intercept"] or events[event]["block"]):
                continue                         # 不看回話：關掉的、或這個事件本來沒東西能改能擋（不報錯）
            got = _changes(event, out, events, check) if not (code == BLOCK and events[event]["block"]) else {}
        except ValueError as e:
            why = "hook %s (event %s) failed: %s" % (name, event, e)
            if entry["on_error"] == "stop":
                raise HookFailed(why) from None
            if warn:
                warn(why + "; going on without it (on_error: continue)")
            continue
        if code == BLOCK and events[event]["block"]:
            result.update(blocked=True, hook=name, text=out)
            return result
        for key, v in got.items():
            result["data"][key] = v
            if key not in result["changed"]:
                result["changed"].append(key)
    return result
