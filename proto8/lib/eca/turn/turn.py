# turn.py - 外部 coding agent（claude／codex，eca）的一輪：從 stack 的 queue 認領一則、交給 CLI 答、回答接進 history、收信
"""叫法（eca B 結論 2、P-43 草稿）：aos-exec <turn 格> <定義資料夾絕對路徑> [--one]
  （定義的 loop.json 叫它：{"exec": {"argv": ["aos-parts", "run", "turn", {"$env": "AOS_CD"}]}}；_entry 是一行 argv 轉這支）

定義資料夾＝eca 的定義（demo/eca-claude 那種）：頂層 cli.json（kind claude｜codex、flags、print_flags、timeout_ms；
  cli_session 讀的同一份）、選填 prompt.txt（開場白）。定義不被寫（P-15）；寫的都在 $AOS_STACK。

平級形（沒有 --one）——一次替它答一則（照 queue 格與 round 的順序，「問腦」換成「叫 CLI」）：
  ① queue/cur/ 有信先接（P-12；Q-1 的順序：當掉重跑接得上）：列在 $AOS_STACK/current.txt＝user 已接進 history；
     沒列＝上次死在 aos-post claim 之後，照 ② 補完。cur/ 空＝aos-post claim 一封（new/ 空＝不起 aos-post）。
     history 空、queue 也空、定義有非空的 prompt.txt＝先把它當一則 user 投進 queue（aos-post send --ordered）再認領。
  ② 讀信（aos-post check）：body 不是 {"role": "user", "content": 非空字串}＝壞信，aos-post finish 丟掉、trace 記一行
     letter_warning、退 0（衝突 5、Q-4）；好信 body 原樣接進 history（最後一則已是 user＝接過了、不接兩次），信號寫進 current.txt。
  ③ content 交給 cli_session（小格＝$AOS_STACK/<kind>/）：畫面開著＝貼進畫面等 hook；沒開＝claude -p --resume／codex exec resume
     （第一次開新的）——兩條路照 10-24，跟工具形是同一段（cli_session 的函式）。
  ④ 回答接成一則 {"role": "assistant", "content": 回答} 進 history，才 aos-post finish 那封（刪掉）、清掉 current.txt。
     重跑時最後一則已是 assistant（死在 ④ 接完、收信之前）＝不再問 CLI，直接收信。
  ⑤ queue 空（cur/、new/ 都沒信）：ECA_ON_EMPTY＝stop（預設）退 10（loop 收工＝射後不理）、idle 退 0（loop 隔 interval_ms 再來）；不寫 trace（Q-9）。
  ⑥ 每則在 $AOS_STACK/trace.jsonl 接一行 {"started_at", "unit": "turn", "question": 信號, "code", "elapsed_ms", "error"?, "letter_warning"?}
     （aos-listen 的 Q-13 判法看得懂）。
  ⑦ 拿到 session id 就在小格建 transcripts/<kind>-<id>.jsonl symlink（cli_session.link_transcript，C-15～17）。
  SessionBad（有人接在畫面上、畫面正在跑一輪、attach 正在開畫面）＝這次退 0 不動、信留在 cur/、不寫 trace，下一次再試（interval_ms）。
  人在畫面上自己打的話不進 history（沒經 queue；eca 方向題 2）。
  每次把 {"kind", "ws", "template"} 寫進 $AOS_STACK/eca.json（有變才寫；template＝定義資料夾）。
--one（工具形，P-41 工具契約）：stdin {"prompt"} → stdout 回答，對話在 $AOS_STACK 這格本身（cli_session.call_main，跟 lib/agent/claude 同一條路）；
  錯照 lib 契約 stderr 與 stdout 各一行「<定義資料夾名>: 代號 原因」、退 1。
PATH 上要有 aos-post。設定（這格的 env：parts.json 的 env 或這格的 .env）：ECA_ON_EMPTY（stop｜idle，沒設或空＝stop）。
錯（平級形）：stderr 一行「turn: 代號 原因」、退 1；CLI 那層的錯同時記進 trace 的 error、信留在 cur/（P-20 停下等人）。
  代號：ArgumentsBad、AgentBad、StackMissing、SettingBad、HistoryBad、PostFailed、WriteFailed，
  加 cli_session 的 CfgMissing、CfgBad、CliMissing、CliFailed、ReplyMissing（SessionBad 不算錯，見上）。"""
import datetime, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))       # lib/agent/cli_session.py
import cli_session  # noqa: E402

NAME = "turn"
NOT_FOUND = 10
USAGE = "usage: aos-exec <turn 格> <定義資料夾絕對路徑> [--one]"
ORDERED = re.compile(r"^[0-9]{12}\.")      # 有序信的名字：<N 零填 12 位>.<信號>（N-16）


class Fail(Exception):
    """自己這層或 cli_session 的錯：code＝代號。"""

    def __init__(self, code, reason):
        super().__init__(str(reason).replace("\n", " "))
        self.code = code


def die(code, reason):
    print("%s: %s %s" % (NAME, code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def now_ms():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def names(box, stage):
    try:
        return sorted(n for n in os.listdir(os.path.join(box, stage)) if not n.startswith("."))
    except (FileNotFoundError, NotADirectoryError):
        return []


def write_atomic(path, text):
    """N-05：先寫同資料夾 . 開頭的暫存檔再改名。"""
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        raise Fail("WriteFailed", "寫不了 %s：%s" % (path, e))


def post(args, stdin_text=""):
    """叫 aos-post；回 (結束碼, stdout, stderr 第一行)。"""
    try:
        r = subprocess.run(["aos-post"] + args, input=stdin_text, capture_output=True, text=True)
    except OSError as e:
        raise Fail("PostFailed", "aos-post 起不來（要在 PATH 上）：%s" % e)
    return r.returncode, r.stdout, (r.stderr.strip().splitlines() or ["退 %d、沒說原因" % r.returncode])[0]


def must_post(args, stdin_text="", ok=(0,)):
    code, out, err = post(args, stdin_text)
    if code not in ok:
        raise Fail("PostFailed", "aos-post %s 退 %d：%s" % (args[0], code, err))
    return code, out


# ---- history（$AOS_STACK/history.jsonl，一行一則 OpenAI message，只附加；P-41）----

def history_rows(stack):
    rows = []
    try:
        with open(os.path.join(stack, "history.jsonl"), encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    m = json.loads(line)
                except ValueError:
                    m = None
                if not isinstance(m, dict):
                    raise Fail("HistoryBad", "history.jsonl 第 %d 行不是 JSON 物件" % i)
                rows.append(m)
    except FileNotFoundError:
        pass
    except OSError as e:
        raise Fail("HistoryBad", "讀不了 history.jsonl：%s" % e)
    return rows


def append_history(stack, msg):
    try:
        with open(os.path.join(stack, "history.jsonl"), "a", encoding="utf-8") as f:   # 一次寫一整行
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    except OSError as e:
        raise Fail("WriteFailed", "接不進 history.jsonl：%s" % e)


def last_role(stack):
    rows = history_rows(stack)
    return rows[-1].get("role") if rows else None


# ---- trace、eca.json、current.txt ----

def trace(stack, sig, started, t0, code, error=None, warning=None):
    line = {"started_at": started, "unit": NAME, "question": sig, "code": code,
            "elapsed_ms": int((time.monotonic() - t0) * 1000)}
    if error:
        line["error"] = error
    if warning:
        line["letter_warning"] = warning
    try:
        with open(os.path.join(stack, "trace.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError as e:
        raise Fail("WriteFailed", "接不進 trace.jsonl：%s" % e)


def note_instance(stack, kind, ws, template):
    want = {"kind": kind, "ws": ws, "template": template}
    try:
        with open(os.path.join(stack, "eca.json"), encoding="utf-8") as f:
            if json.load(f) == want:
                return
    except (OSError, ValueError):
        pass
    write_atomic(os.path.join(stack, "eca.json"), json.dumps(want, ensure_ascii=False) + "\n")


def read_current(stack):
    try:
        with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    except OSError:
        return []


def clear_current(stack):
    try:
        os.unlink(os.path.join(stack, "current.txt"))
    except FileNotFoundError:
        pass
    except OSError as e:
        raise Fail("WriteFailed", "清不掉 current.txt：%s" % e)


# ---- 一則 ----

def letter_body(box, sig):
    """好信回 (body, None)；壞信回 (None, 原因)。"""
    if not ORDERED.match(sig):
        return None, "名字不是有序的 <12 位序號>.<信號>"
    code, out, err = post(["check", box, sig])
    if code != 0:
        return None, err
    try:
        body = json.loads(out).get("body")
    except (ValueError, AttributeError):
        return None, "aos-post check 印的不是 JSON 物件"
    if not (isinstance(body, dict) and body.get("role") == "user" and isinstance(body.get("content"), str)
            and body["content"].strip()):
        return None, "body 要是 {\"role\": \"user\", \"content\": 非空字串}"
    return body, None


def opening(stack, box, template):
    """history 空、queue 也空、有 prompt.txt＝把開場白投進 queue（射後不理那種的第一則）。回 True＝投了。"""
    try:
        with open(os.path.join(template, "prompt.txt"), encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return False
    except OSError as e:
        raise Fail("AgentBad", "讀不了 prompt.txt：%s" % e)
    text = text[:-1] if text.endswith("\n") else text           # 同 aos-say：結尾一個換行不算
    if not text.strip() or history_rows(stack):
        return False
    must_post(["send", "--ordered", box], json.dumps({"role": "user", "content": text}, ensure_ascii=False))
    return True


def pick(stack, box, template):
    """回 (信號, 已接進 history 嗎)；queue 空＝(None, False)。"""
    cur = names(box, "cur")
    if cur:
        return cur[0], cur[0] in read_current(stack)
    if not names(box, "new") and not opening(stack, box, template):
        return None, False
    code, out = must_post(["claim", box], ok=(0, NOT_FOUND))     # new/ → cur/
    if code == NOT_FOUND:                                          # 剛好被撤回
        return None, False
    return out.strip(), False


def ask(cfg, cell, template, ws, prompt):
    """交給 CLI（cli_session 的兩條路；跟 call_main 同一段）→ 回答文字。"""
    cli_session.note_cell(cell, template, ws)
    f, ok = cell.lock()
    if not ok:
        raise Fail("SessionBad", "這段對話有人在用（attach 正在開畫面）")
    with f:
        if cell.alive():
            text = cli_session.live(cfg, cell, prompt)
        elif cfg["kind"] == "claude":
            text = cli_session.print_claude(cfg, cell, ws, prompt)
        else:
            text = cli_session.print_codex(cfg, cell, ws, prompt)
        cli_session.link_transcript(cell, cfg["kind"])
    return text


def one_turn(template, stack, ws, empty_code):
    box = os.path.join(stack, "queue")
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        must_post(["init", box])                                   # 先建好，aos-say／listen 認得
    cfg = cli_session.load_cfg(template)
    cell = cli_session.Cell(os.path.join(stack, cfg["kind"]))
    note_instance(stack, cfg["kind"], ws, template)
    sig, listed = pick(stack, box, template)
    if sig is None:
        return empty_code
    started, t0 = now_ms(), time.monotonic()
    if not listed:                                                  # ② 讀信、接進 history、寫 current.txt
        body, why = letter_body(box, sig)
        if body is None:
            post(["finish", box, sig])                             # 壞信一律丟（N-16、決定 27 不通知寄信人）
            trace(stack, sig, started, t0, 0, warning=why)
            return 0
        if last_role(stack) != "user":
            append_history(stack, body)
        write_atomic(os.path.join(stack, "current.txt"), sig + "\n")
        prompt = body["content"]
    elif last_role(stack) == "assistant":                          # 上次答完、接進 history 了，死在收信之前
        prompt = None
    else:                                                           # 上次接進 history 了、還沒答（CLI 失敗、SessionBad）
        body, why = letter_body(box, sig)
        if body is None:                                            # 列過就是好信；真的讀不了也照壞信丟
            post(["finish", box, sig])
            clear_current(stack)
            trace(stack, sig, started, t0, 0, warning=why)
            return 0
        prompt = body["content"]
    if prompt is not None:
        try:
            text = ask(cfg, cell, template, ws, prompt)
        except Fail as e:
            if e.code == "SessionBad":
                return 0                                            # 信留 cur/，下一次再試
            trace(stack, sig, started, t0, 1, error="%s %s" % (e.code, e))
            raise
        append_history(stack, {"role": "assistant", "content": text[:-1] if text.endswith("\n") else text})
    must_post(["finish", box, sig])                                # 回答已在 history 才收信（A-5）
    clear_current(stack)
    trace(stack, sig, started, t0, 0)
    return 0


def _cli_die(code, reason):                    # cli_session 出錯時本來 exit；平級形改成丟例外，turn 自己記 trace、說一行
    raise Fail(code, reason)


def main():
    args = sys.argv[1:]
    one = "--one" in args
    args = [a for a in args if a != "--one"]
    if len(args) != 1 or any(a.startswith("--") for a in args):
        die("ArgumentsBad", USAGE)
    template = args[0]
    if not os.path.isabs(template) or not os.path.isdir(template):
        die("AgentBad", "定義資料夾要是存在的絕對路徑（aos-exec 走進格以後 cwd 不在定義那邊），收到 %r" % template)
    template = os.path.normpath(template)
    if one:
        cli_session.call_main(template)                            # 工具形：跟 lib/agent/claude、codex 同一條路
        return
    empty = os.environ.get("ECA_ON_EMPTY") or "stop"
    if empty not in ("stop", "idle"):
        die("SettingBad", "ECA_ON_EMPTY 要是 stop 或 idle，收到 %r" % empty)
    stack = os.environ.get("AOS_STACK")
    if not stack:
        die("StackMissing", "沒設定 AOS_STACK")
    stack = os.path.abspath(stack)
    ws = os.path.abspath(os.environ.get("AOS_WS") or ".")
    cli_session.die = _cli_die
    try:
        code = one_turn(template, stack, ws, NOT_FOUND if empty == "stop" else 0)
    except Fail as e:
        die(e.code, e)
    sys.exit(code)


main()
