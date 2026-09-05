"""LLM 世界。WRITER-BRIEF 4.7、rulings F-02（LLM 是單獨一塊地）與 I-01（結果落點由投的人指定）。

一句話：`$AOS_HOME/.aos/llm/` 自己就是一塊地。別的地要用 LLM，就往它的
`.aos/inbox/` 投一個 `kind:"llm"` 的投遞物（`inbox.process()` 刻意不動這種信）。
這裡的圈＝取信 → 挑處理單元 → 打端點 → 回話寫進請求指定的 `result` →
錯誤寫 `<result>.status.json` → 帳簿記一行。
"""
import datetime
import json
import os
import time
import urllib.error
import urllib.request

from . import exits, fsutil, inbox, layout, status

# 處理完的請求搬到這裡（不要人間蒸發）
DONE_DIR = "llm-done"
# aos llm ask 的暫存 prompt／結果
ASK_DIR = "llm-ask"

DEFAULT_MAX_PARALLEL = 4
DEFAULT_MAX_WAIT_MS = 30000
DEFAULT_HTTP_TIMEOUT_MS = 60000

# outcome 的字彙（spec 只說有 `outcome` 欄，沒說有哪些值——見 FINDINGS）
OUT_OK = "ok"
OUT_BACKEND_ERROR = "backend_error"
OUT_QUEUE_TIMEOUT = "queue_timeout"
OUT_REJECTED = "rejected"

# 預設處理單元表：一律假後端，不打網路
DEFAULT_UNITS = [
    {"name": "echo-fast", "endpoint": "echo:", "model": "echo",
     "tier": "fast", "max_parallel": 2, "api_key_env": None},
    {"name": "echo-smart", "endpoint": "echo:", "model": "echo",
     "tier": "smart", "max_parallel": 1, "api_key_env": None},
]


# ---------------------------------------------------------------- 小工具

def _home(home=None):
    if home is None:
        return layout.Home()
    if isinstance(home, layout.Home):
        return home
    if isinstance(home, layout.Land):
        return layout.Home(home.root)
    return layout.Home(home)


def _user_config(home=None):
    return _home(home).load_config()


def _units(home=None):
    cfg = _user_config(home)
    u = cfg.get("units")
    if isinstance(u, list) and u:
        return u
    return []


def _parse_at(at):
    """`at` 是 fsutil.now_iso() 的格式：2026-09-05T12:00:00.000Z。"""
    if not isinstance(at, str):
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = datetime.datetime.strptime(at, fmt)
            return d.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    return None


def _waited_ms(obj):
    d = _parse_at(obj.get("at"))
    if d is None:
        return 0
    now = datetime.datetime.now(datetime.timezone.utc)
    return int((now - d).total_seconds() * 1000)


def _est_tokens(text):
    """假後端沒有真的 token 數，用字數估：非空白字元數 / 4，至少 1。

    帳簿欄位名不准改（WRITER-BRIEF 4.7），所以估出來的數字跟真的長一樣——
    這件事寫進 FINDINGS。
    """
    n = len([c for c in (text or "") if not c.isspace()])
    return max(1, n // 4)


def _requester_land(obj):
    """`prompt`／`result` 的相對路徑基準＝投遞者那塊地的根（obj["from"]）。

    spec 沒明講基準是誰（見 FINDINGS）。這裡照 I-01「結果落點由投的人指定」，
    投的人講的相對路徑當然以他自己那塊地為準。
    """
    frm = obj.get("from") or "."
    return layout.Land(frm)


# ---------------------------------------------------------------- 這塊地

def llm_land(home=None):
    """LLM 世界那塊地。位置＝使用者層 config 的 `llm_world`，預設 $AOS_HOME/.aos/llm。"""
    return layout.Land(_home(home).llm_world)


def init_llm_world(home=None):
    """建好 LLM 世界那塊地，並確保使用者層 config.json 有 `units`（含假後端）。

    已經有的欄位一律不覆蓋。
    """
    h = _home(home)
    land, _created = layout.init(h.llm_world)
    fsutil.ensure_dir(land.rel(DONE_DIR))
    fsutil.ensure_dir(land.rel(ASK_DIR))

    fsutil.ensure_dir(h.aos)
    cfg = fsutil.read_json(h.config, None)
    changed = False
    if not isinstance(cfg, dict):
        cfg = {}
        changed = True
    if "format_version" not in cfg:
        cfg["format_version"] = 1
        changed = True
    if not isinstance(cfg.get("units"), list) or not cfg.get("units"):
        cfg["units"] = [dict(u) for u in DEFAULT_UNITS]
        changed = True
    if "max_parallel" not in cfg:
        cfg["max_parallel"] = DEFAULT_MAX_PARALLEL
        changed = True
    if "max_wait_ms" not in cfg:
        cfg["max_wait_ms"] = DEFAULT_MAX_WAIT_MS
        changed = True
    if "llm_world" not in cfg:
        cfg["llm_world"] = land.root
        changed = True
    if changed:
        fsutil.write_json(h.config, cfg)
    return land


# ---------------------------------------------------------------- 挑單元

def pick_unit(tier, home=None):
    """回傳 (單元, 說明)。沒有相符的 tier 就退回第一筆，並且**講出來**。"""
    units = _units(home)
    if not units:
        return None, "使用者層設定 %s 沒有 `units`；先跑 aos llm init" % _home(home).config
    if tier:
        for u in units:
            if u.get("tier") == tier:
                return u, None
    if tier:
        return units[0], "沒有 tier=%s 的處理單元，退回第一筆 %s（tier=%s）" % (
            tier, units[0].get("name"), units[0].get("tier"))
    return units[0], "請求沒寫 `tier`，用第一筆 %s" % units[0].get("name")


def parallel_cap(unit, home=None):
    """全域 `max_parallel` 與單元自己的 `max_parallel` 取小。"""
    cfg = _user_config(home)
    g = cfg.get("max_parallel")
    g = int(g) if isinstance(g, int) and g > 0 else DEFAULT_MAX_PARALLEL
    u = (unit or {}).get("max_parallel")
    u = int(u) if isinstance(u, int) and u > 0 else g
    return max(1, min(g, u))


# ---------------------------------------------------------------- 打後端

def _compose(prompt_text, tools=None):
    """`tools` 是「給模型看的工具行陣列」（4.7），原型就是接在 prompt 前面。"""
    if not tools:
        return prompt_text
    head = "可用工具：\n" + "\n".join("- %s" % t for t in tools)
    return head + "\n\n" + prompt_text


def call_unit(unit, prompt_text, tools=None):
    """實際打後端。回 {"ok","text","tokens_in","tokens_out","ms","error","retryable"}。

    endpoint 三種假後端（原型自己加的，見 FINDINGS）：
      `echo:`      不打網路，把 prompt 原樣回，前面加一行 `echo:<單元名>` 標記
      `fail:`      一定失敗，測錯誤路徑用
      `slow:<ms>`  睡 <ms> 毫秒再 echo，測排隊逾時用
    其餘 http(s):// 開頭＝真後端，OpenAI 相容 `<endpoint>/chat/completions`。
    """
    unit = unit or {}
    endpoint = (unit.get("endpoint") or "").strip()
    name = unit.get("name") or "?"
    body_text = _compose(prompt_text, tools)
    t0 = time.time()

    def done(ok, text="", error=None, retryable=False, tin=None, tout=None):
        return {
            "ok": ok,
            "text": text,
            "tokens_in": _est_tokens(body_text) if tin is None else tin,
            "tokens_out": _est_tokens(text) if tout is None else tout,
            "ms": int((time.time() - t0) * 1000),
            "error": error,
            "retryable": retryable,
        }

    if endpoint == "echo:":
        return done(True, "echo:%s\n%s" % (name, body_text))

    if endpoint.startswith("fail:"):
        why = endpoint[len("fail:"):].strip() or "假後端 fail: 一定失敗"
        return done(False, "", error="單元 %s（endpoint %s）：%s" % (name, endpoint, why),
                    retryable=True)

    if endpoint.startswith("slow:"):
        raw = endpoint[len("slow:"):].strip()
        try:
            ms = int(raw or "0")
        except ValueError:
            return done(False, "", error="單元 %s 的 endpoint 寫成 %s，slow: 後面要接毫秒整數"
                        % (name, endpoint), retryable=False)
        time.sleep(max(0, ms) / 1000.0)
        return done(True, "echo:%s（慢了 %d ms）\n%s" % (name, ms, body_text))

    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return _call_http(unit, body_text, t0, done)

    return done(False, "", error="單元 %s 的 `endpoint` 是 %r，認不得；要嘛 http(s)://…，"
                "要嘛假後端 echo: ／ fail: ／ slow:<ms>" % (name, endpoint), retryable=False)


def _call_http(unit, body_text, t0, done):
    endpoint = unit["endpoint"].rstrip("/")
    url = endpoint + "/chat/completions"
    payload = {
        "model": unit.get("model") or "",
        "messages": [{"role": "user", "content": body_text}],
    }
    headers = {"Content-Type": "application/json"}
    env_name = unit.get("api_key_env")
    if env_name:
        key = os.environ.get(env_name)
        if key:
            headers["Authorization"] = "Bearer " + key
    timeout_ms = unit.get("timeout_ms")
    timeout_ms = int(timeout_ms) if isinstance(timeout_ms, int) and timeout_ms > 0 \
        else DEFAULT_HTTP_TIMEOUT_MS
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_ms / 1000.0) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        return done(False, "", error="%s 回 HTTP %s：%s" % (url, e.code, detail),
                    retryable=e.code in (408, 409, 429) or e.code >= 500)
    except urllib.error.URLError as e:
        return done(False, "", error="連不上 %s：%s" % (url, e.reason), retryable=True)
    except OSError as e:
        return done(False, "", error="打 %s 出錯：%s" % (url, e), retryable=True)

    try:
        obj = json.loads(raw)
    except ValueError:
        return done(False, "", error="%s 回的不是 json：%s" % (url, raw[:200]), retryable=False)
    try:
        text = obj["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return done(False, "", error="%s 回的 json 沒有 choices[0].message.content：%s"
                    % (url, raw[:200]), retryable=False)
    usage = obj.get("usage") or {}
    tin = usage.get("prompt_tokens")
    tout = usage.get("completion_tokens")
    return done(True, text,
                tin=tin if isinstance(tin, int) else None,
                tout=tout if isinstance(tout, int) else None)


# ---------------------------------------------------------------- 帳簿

def _ledger(home, obj, unit_name, tier, tin, tout, ms, outcome):
    h = _home(home)
    line = {
        "at": fsutil.now_iso(),
        "request_id": obj.get("id"),
        "from": obj.get("from"),
        "unit": unit_name,
        "tier": tier,
        "tokens_in": tin,
        "tokens_out": tout,
        "ms": ms,
        "outcome": outcome,
    }
    fsutil.append_line(h.ledger, json.dumps(line, ensure_ascii=False))
    return line


# ---------------------------------------------------------------- 一筆請求

def _archive(land, obj):
    """處理完把收件匣那個檔挪到 .aos/llm-done/（不刪，要看得見）。"""
    obj_id = obj.get("id") or ""
    src = os.path.join(land.inbox, "%s.json" % obj_id)
    dst = os.path.join(land.rel(DONE_DIR), "%s.json" % obj_id)
    fsutil.ensure_dir(land.rel(DONE_DIR))
    try:
        os.replace(src, dst)
        return dst
    except OSError:
        return None


def _fail(land, obj, result_path, reason, message, home, unit_name, tier, ms=0):
    if result_path:
        status.write_failed(result_path, reason, message)
    outcome = {
        status.QUEUE_TIMEOUT: OUT_QUEUE_TIMEOUT,
        status.BACKEND_ERROR: OUT_BACKEND_ERROR,
        status.REJECTED: OUT_REJECTED,
    }.get(reason, reason)
    _ledger(home, obj, unit_name, tier, 0, 0, ms, outcome)
    _archive(land, obj)
    return {
        "id": obj.get("id"), "ok": False, "outcome": outcome, "reason": reason,
        "message": message, "result": result_path, "status": (
            status.status_path(result_path) if result_path else None),
        "unit": unit_name, "tier": tier, "ms": ms,
    }


def handle_request(land, obj, home=None):
    """處理一筆 `kind:"llm"` 請求。回一個講得出「做了什麼」的 dict。"""
    h = _home(home)
    cfg = h.load_config()
    tier = obj.get("tier")
    src = _requester_land(obj)

    result_raw = obj.get("result")
    result_path = src.resolve(result_raw) if result_raw else None
    if not result_path:
        # 沒有落點連錯誤都沒地方寫，只能記帳簿＋搬走
        return _fail(land, obj, None, status.REJECTED,
                     "請求少了 `result`（結果落點，路徑；I-01 由投的人指定）", h, None, tier)

    prompt_raw = obj.get("prompt")
    if not prompt_raw:
        return _fail(land, obj, result_path, status.REJECTED,
                     "請求少了 `prompt`（指向 prompt 檔的路徑）", h, None, tier)
    prompt_path = src.resolve(prompt_raw)

    # 排隊逾時：在收件匣待太久就不打後端了
    max_wait = obj.get("max_wait_ms")
    if not isinstance(max_wait, int) or max_wait <= 0:
        mw = cfg.get("max_wait_ms")
        max_wait = mw if isinstance(mw, int) and mw > 0 else DEFAULT_MAX_WAIT_MS
    waited = _waited_ms(obj)
    if waited > max_wait:
        return _fail(land, obj, result_path, status.QUEUE_TIMEOUT,
                     "在 %s 的收件匣排了 %d ms，超過 `max_wait_ms`=%d，沒打後端就放棄"
                     % (land.root, waited, max_wait), h, None, tier, ms=waited)

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
    except OSError as e:
        return _fail(land, obj, result_path, status.REJECTED,
                     "讀不到 prompt 檔 %s（`prompt`=%r，相對路徑以投遞者那塊地 %s 為基準）：%s"
                     % (prompt_path, prompt_raw, src.root, e), h, None, tier)

    unit, note = pick_unit(tier, h)
    if unit is None:
        return _fail(land, obj, result_path, status.REJECTED, note, h, None, tier)
    unit_name = unit.get("name")

    tools = obj.get("tools") if isinstance(obj.get("tools"), list) else None
    res = call_unit(unit, prompt_text, tools=tools)

    if not res["ok"]:
        out = _fail(land, obj, result_path, status.BACKEND_ERROR, res["error"], h,
                    unit_name, tier, ms=res["ms"])
        out["retryable"] = res["retryable"]
        if note:
            out["note"] = note
        return out

    # 成功：回話原文寫進 result（純文字），順手把上一輪的狀態檔清掉
    try:
        os.unlink(status.status_path(result_path))
    except FileNotFoundError:
        pass
    fsutil.atomic_write_text(result_path, res["text"])
    _ledger(h, obj, unit_name, tier, res["tokens_in"], res["tokens_out"], res["ms"], OUT_OK)
    _archive(land, obj)
    out = {
        "id": obj.get("id"), "ok": True, "outcome": OUT_OK, "result": result_path,
        "unit": unit_name, "tier": tier, "ms": res["ms"],
        "tokens_in": res["tokens_in"], "tokens_out": res["tokens_out"],
        "waited_ms": waited,
    }
    if note:
        out["note"] = note
    return out


# ---------------------------------------------------------------- 一格

def _sort_key(item):
    _p, obj = item
    pr = obj.get("priority")
    pr = pr if isinstance(pr, int) else 0
    return (pr, obj.get("at") or "", obj.get("id") or "")


def serve_once(land=None, home=None):
    """走一格：取信 → 排序 → 依並行上限處理 → 回報做了什麼。"""
    h = _home(home)
    land = land or llm_land(h)
    rep = {"land": land.root, "handled": [], "rejected": [], "left": [],
           "notes": [], "idle": True}
    if not land.is_land():
        rep["notes"].append("%s 不是一塊地；先跑 aos llm init" % land.root)
        rep["error"] = "not_a_land"
        return rep

    # 一塊地同時只准一支在走格（跟 exec／run 共用同一把鎖）。
    # spec 沒講 LLM 世界的圈算不算「走格」（見 FINDINGS）；不鎖的話兩支
    # serve 會把同一筆請求打兩次。
    try:
        lock = fsutil.Lock(land.lock, wait_ms=0).acquire()
    except fsutil.LockBusy as e:
        rep["notes"].append("%s；這一格不做事" % e)
        rep["error"] = "lock_busy"
        return rep
    try:
        return _serve_locked(land, h, rep)
    finally:
        lock.release()


def _serve_locked(land, h, rep):
    items = inbox.scan(land, kinds=("llm",))
    # 無效的先隔離（inbox.process 不碰 kind:llm，所以驗證是我們的事）
    good = []
    for path, obj in items:
        try:
            inbox.validate(obj)
        except inbox.Rejected as e:
            obj_id = (obj or {}).get("id") or os.path.basename(path)[:-5]
            fsutil.ensure_dir(land.inbox_rejected)
            try:
                os.replace(path, os.path.join(land.inbox_rejected, "%s.json" % obj_id))
            except OSError:
                pass
            rep["rejected"].append({"id": obj_id, "reason": e.reason, "message": e.message})
            rep["notes"].append("隔離無效請求 %s（%s）：%s → %s"
                                % (obj_id, e.reason, e.message, land.inbox_rejected))
            continue
        good.append((path, obj))

    good.sort(key=_sort_key)
    rep["pending"] = len(good)
    if not good:
        rep["notes"].append("收件匣沒有 kind:llm 的請求")
        return rep

    # 並行上限：全域 max_parallel 與單元自己的 max_parallel 取小。
    # 原型不開執行緒，改成「這一格最多處理幾筆」（見 FINDINGS）。
    cfg = h.load_config()
    g = cfg.get("max_parallel")
    g = int(g) if isinstance(g, int) and g > 0 else DEFAULT_MAX_PARALLEL
    used = {}
    n = 0
    for _path, obj in good:
        if n >= g:
            rep["left"].append(obj.get("id"))
            continue
        unit, _note = pick_unit(obj.get("tier"), h)
        uname = (unit or {}).get("name")
        cap = parallel_cap(unit, h)
        if used.get(uname, 0) >= cap:
            rep["left"].append(obj.get("id"))
            rep["notes"].append("單元 %s 這一格已經吃滿 %d 筆，請求 %s 留到下一格"
                                % (uname, cap, obj.get("id")))
            continue
        out = handle_request(land, obj, h)
        used[uname] = used.get(uname, 0) + 1
        n += 1
        rep["handled"].append(out)
        if out.get("note"):
            rep["notes"].append(out["note"])

    rep["idle"] = not rep["left"]
    return rep


# ---------------------------------------------------------------- 指令面

def _err(msg, hint=None):
    import sys
    sys.stderr.write("錯誤：%s\n" % msg)
    if hint:
        sys.stderr.write("下一步：%s\n" % hint)


def _land_from_args(args, home=None):
    if getattr(args, "land", None):
        return layout.Land(args.land)
    return llm_land(home)


def _print_report(rep, as_json=False):
    if as_json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
        return
    print("LLM 世界 %s" % rep["land"])
    for n in rep.get("notes", []):
        print("  " + n)
    for h in rep.get("handled", []):
        if h.get("ok"):
            print("  ✓ %s  單元 %s  tier %s  %d ms  tokens %s/%s  → %s"
                  % (h["id"], h["unit"], h.get("tier"), h["ms"],
                     h.get("tokens_in"), h.get("tokens_out"), h["result"]))
        else:
            print("  ✗ %s  %s：%s" % (h["id"], h.get("reason"), h.get("message")))
            if h.get("status"):
                print("      狀態檔：%s" % h["status"])
    if rep.get("left"):
        print("  還留 %d 筆在收件匣（下一格再處理）" % len(rep["left"]))


def _rep_exit(rep):
    """一格的退出碼。4.7 只給了 0／2／75／130，沒說「請求本身寫壞了」算哪個
    （見 FINDINGS）；原型把它算成用法錯 2，因為重試也沒用。"""
    if rep.get("error") == "not_a_land":
        return exits.NOT_A_LAND
    if rep.get("error") == "lock_busy":
        return exits.LOCK_BUSY
    code = exits.OK
    for h in rep.get("handled", []):
        if h.get("ok"):
            continue
        if h.get("outcome") in (OUT_BACKEND_ERROR, OUT_QUEUE_TIMEOUT):
            return exits.LLM_BACKEND
        code = exits.USAGE
    if rep.get("rejected"):
        code = exits.USAGE if code == exits.OK else code
    return code


def _op_init(args):
    land = init_llm_world()
    h = _home()
    print("LLM 世界建在：%s" % land.root)
    print("  設定：%s" % h.config)
    print("  帳簿：%s" % h.ledger)
    print("  收件匣：%s" % land.inbox)
    print("  處理完的請求：%s" % land.rel(DONE_DIR))
    for u in _units(h):
        print("  單元 %-12s tier=%-6s endpoint=%-24s model=%s max_parallel=%s"
              % (u.get("name"), u.get("tier"), u.get("endpoint"), u.get("model"),
                 u.get("max_parallel")))
    print("投一筆請求：python3 proto/aos.py deliver %s '<kind:llm 的 json>'" % land.root)
    return exits.OK


def _op_tick(args):
    land = _land_from_args(args)
    if not land.is_land():
        _err("%s 不是一塊地" % land.root, "python3 proto/aos.py llm init")
        return exits.NOT_A_LAND
    rep = serve_once(land)
    _print_report(rep, args.json)
    return _rep_exit(rep)


def _op_serve(args):
    land = _land_from_args(args)
    if not land.is_land():
        _err("%s 不是一塊地" % land.root, "python3 proto/aos.py llm init")
        return exits.NOT_A_LAND
    steps = args.steps
    until = args.until
    if steps is None and until is None:
        # spec 沒講 serve 沒帶旗標時停在哪（見 FINDINGS）；原型當成 --until idle
        until = "idle"
        print("（沒給 --steps／--until，當成 --until idle：收件匣空了就停）")
    every = (args.every or 0) / 1000.0
    code = exits.OK
    i = 0
    try:
        while True:
            rep = serve_once(land)
            _print_report(rep, args.json)
            c = _rep_exit(rep)
            if c != exits.OK:
                code = c
            i += 1
            if steps is not None and i >= steps:
                break
            if until == "idle" and not rep.get("handled") and not rep.get("left"):
                break
            if every:
                time.sleep(every)
    except KeyboardInterrupt:
        print("（收到中斷，停在第 %d 格）" % i)
        return exits.CANCELLED
    return code


def _op_ls(args):
    land = _land_from_args(args)
    h = _home()
    if not land.is_land():
        _err("%s 不是一塊地" % land.root, "python3 proto/aos.py llm init")
        return exits.NOT_A_LAND
    items = inbox.scan(land, kinds=("llm",))
    items.sort(key=_sort_key)
    rows = []
    for _p, obj in items:
        rows.append({
            "id": obj.get("id"), "from": obj.get("from"), "tier": obj.get("tier"),
            "priority": obj.get("priority") if isinstance(obj.get("priority"), int) else 0,
            "waited_ms": _waited_ms(obj),
            "max_wait_ms": obj.get("max_wait_ms"),
            "result": obj.get("result"),
        })
    units = _units(h)
    if args.json:
        print(json.dumps({"land": land.root, "pending": rows, "units": units},
                         ensure_ascii=False, indent=2))
        return exits.OK
    print("LLM 世界 %s" % land.root)
    print("待處理請求：%d 筆" % len(rows))
    for r in rows:
        print("  %s  priority=%s tier=%s  等了 %d ms  from %s  → %s"
              % (r["id"][:12], r["priority"], r["tier"], r["waited_ms"], r["from"], r["result"]))
    print("處理單元（%s 的 `units`）：%d 筆" % (h.config, len(units)))
    for u in units:
        print("  %-12s tier=%-6s endpoint=%-24s model=%-12s max_parallel=%s api_key_env=%s"
              % (u.get("name"), u.get("tier"), u.get("endpoint"), u.get("model"),
                 u.get("max_parallel"), u.get("api_key_env")))
    if not units:
        print("  （空的）先跑：python3 proto/aos.py llm init")
    return exits.OK


def _op_ask(args):
    land = _land_from_args(args)
    if not land.is_land():
        _err("%s 不是一塊地" % land.root, "python3 proto/aos.py llm init")
        return exits.NOT_A_LAND
    rest = list(args.rest or [])
    if not rest:
        _err("aos llm ask 要一個 prompt 檔或一段字串",
             "python3 proto/aos.py llm ask '你好' [tier]")
        return exits.USAGE
    text_or_path = rest[0]
    tier = rest[1] if len(rest) > 1 else None

    req_id = fsutil.new_id()
    ask_dir = land.rel(ASK_DIR)
    fsutil.ensure_dir(ask_dir)
    if os.path.isfile(text_or_path):
        prompt_path = os.path.abspath(text_or_path)
    else:
        prompt_path = os.path.join(ask_dir, "%s.prompt" % req_id)
        fsutil.atomic_write_text(prompt_path, text_or_path)
    result_path = os.path.join(ask_dir, "%s.out" % req_id)

    obj = inbox.make("llm", land.root, id=req_id, prompt=prompt_path, result=result_path,
                     tier=tier, priority=0,
                     max_wait_ms=_home().load_config().get("max_wait_ms", DEFAULT_MAX_WAIT_MS))
    ok, info = inbox.deliver(land, obj)
    if not ok:
        _err("投不進去：%s" % info, "換一個 id 再投")
        return exits.USAGE

    rep = serve_once(land)
    hit = None
    for hh in rep.get("handled", []):
        if hh.get("id") == req_id:
            hit = hh
            break
    if hit is None:
        _err("請求 %s 這一格沒被處理（並行上限吃滿了？）" % req_id,
             "再跑一次：python3 proto/aos.py llm tick")
        return exits.LLM_BACKEND
    if not hit.get("ok"):
        _err("%s：%s" % (hit.get("reason"), hit.get("message")),
             "看狀態檔 %s" % hit.get("status"))
        return exits.LLM_BACKEND
    with open(result_path, "r", encoding="utf-8") as f:
        text = f.read()
    if args.json:
        print(json.dumps({"request": obj, "outcome": hit, "text": text},
                         ensure_ascii=False, indent=2))
        return exits.OK
    if hit.get("note"):
        print("（%s）" % hit["note"])
    print("--- 回話（單元 %s，%d ms，tokens %s/%s）---"
          % (hit["unit"], hit["ms"], hit.get("tokens_in"), hit.get("tokens_out")))
    print(text)
    print("--- 落點：%s ---" % result_path)
    return exits.OK


_OPS = {
    "init": _op_init,
    "tick": _op_tick,
    "serve": _op_serve,
    "ls": _op_ls,
    "ask": _op_ask,
}


def cli_llm(args):
    fn = _OPS.get(getattr(args, "op", None))
    if fn is None:
        _err("認不得 aos llm 的 op：%r" % getattr(args, "op", None),
             "只有 init／serve／tick／ls／ask")
        return exits.USAGE
    try:
        return fn(args)
    except KeyboardInterrupt:
        return exits.CANCELLED
