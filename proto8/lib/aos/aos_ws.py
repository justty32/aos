"""aos_ws - 「放題、等答案、讀 stack」的共用小零件：給人用的 aos-say／aos-listen／aos-chat（proto8/extras/human）與給 AI 用的 aos-ai（proto8/extras/ai_tools）一起用。

10-24 遷移（tool-lib 遷移清單「human、aos-ai 的放題、等答案合成一份」）：兩邊各寫了一份同樣的事，收到這裡；不是工具（沒有 _entry），
是 lib/aos 的共用模組，兩支命令列用 realpath 找到這個資料夾再 import。純標準庫。
工作區的形狀照 CONVENTION 第四節（P-11～P-14）：題目 $AOS_WS/new/<題名>、認領 cur/、答案 out/<題名>、做完 done/；
stack 裡 fsm 每格一行 trace.jsonl（P-07）、agent-dan 式的對話 history.jsonl（P-41）。這裡只放題目、看答案、讀 stack，不改 stack 裡的東西。"""
import datetime, json, os, time

STAGES = ("new", "cur", "out", "done")


class Error(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def names(ws, stage):
    """某個階段資料夾裡的題名（. 開頭的是別人寫到一半的暫存檔，不算）。"""
    try:
        return sorted(n for n in os.listdir(os.path.join(ws, stage)) if not n.startswith("."))
    except (FileNotFoundError, NotADirectoryError):
        return []


def where(ws, name):
    """這題現在在哪幾個階段資料夾。"""
    return [s for s in STAGES if os.path.lexists(os.path.join(ws, s, name))]


def read(path, default=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return default


def new_name():
    """題名＝現在的 UTC 時間，ISO 8601 基本格式到毫秒（沒有冒號），加 .txt；檔名排序＝丟進來的先後（agent 照檔名排序取題，P-12）。"""
    t = datetime.datetime.now(datetime.timezone.utc)
    return t.strftime("%Y%m%dT%H%M%S.") + "%03dZ.txt" % (t.microsecond // 1000)


def put(ws, text, name=None, tag="say"):
    """把一段文字變成一道題丟進 new/：先寫工作區頂層的暫存檔 .<tag>-<pid>.tmp，再 link 成 new/<題名>（N-05；
    link 不蓋已有的檔）。暫存檔不放 new/ 裡，免得 agent 列 new/ 時看到半份。沒給題名＝new_name()。回題名。錯＝Error("NameBad")。"""
    if name is not None:
        if not name or name.startswith(".") or "/" in name or name in ("..",):
            raise Error("NameBad", "題名不能空、不能 . 開頭、不能有 /：%r" % name)
        used = where(ws, name)
        if used:
            raise Error("NameBad", "題名 %s 用過了（在 %s/）；換一個名字，免得拿到舊的答案" % (name, "、".join(used)))
    if not text.endswith("\n"):
        text += "\n"
    os.makedirs(os.path.join(ws, "new"), exist_ok=True)
    tmp = os.path.join(ws, ".%s-%d.tmp" % (tag, os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        for _ in range(1000):
            n = name or new_name()
            if name is None and where(ws, n):      # 同一毫秒剛好撞名（或 out/ 已有同名的舊答案）：等一下再取
                time.sleep(0.002)
                continue
            try:
                os.link(tmp, os.path.join(ws, "new", n))
                return n
            except FileExistsError:
                if name is not None:
                    raise Error("NameBad", "題名 %s 剛好被別人用了" % name)
                time.sleep(0.002)
        raise Error("NameBad", "一直撞名，取不到新的題名")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def answer_name(ws, name):
    """out/ 裡這題的答案叫什麼（給的題名、或補上 .txt）；還沒有＝None。"""
    for q in (name, name + ".txt"):
        if os.path.isfile(os.path.join(ws, "out", q)):
            return q
    return None


def answer_text(ws, name):
    """out/<題名> 的內容（是資料夾就讀裡面的 answer.txt，P-13）；還沒有＝None。"""
    p = os.path.join(ws, "out", name)
    if os.path.isdir(p):
        return read(os.path.join(p, "answer.txt"), "")
    return read(p)


def tail_jsonl(path, n):
    """一份 .jsonl 最後 n 行（解不開的那行放 {"bad_line": 前 200 字}）；檔不在＝[]。"""
    text = read(path)
    if text is None:
        return []
    lines = [l for l in text.splitlines() if l.strip()]
    rows = []
    for l in lines[-n:] if n > 0 else []:
        try:
            rows.append(json.loads(l))
        except ValueError:
            rows.append({"bad_line": l[:200]})
    return rows


def last_jsonl(path):
    """一份 .jsonl 最後一行解得開的；沒有＝None（stack 的 trace.jsonl 看最後一格用）。"""
    for line in reversed((read(path, "") or "").splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None
