# cli_a2a.py - cli_session 往開著的 claude 畫面投署名訊息（Claude Code 的 cross-session messaging socket）：記 socket、包信封、投遞、等 hook 回執
"""畫面開著的 claude 身，最後一哩不貼字，改往 CLI 自己的收件口（每個 session 一條 Unix socket）寫一行 JSON（11-13 使用者裁
「a2a這個按照建議。馬上送，eca他會自己處理。」；thinking 2026-11/13/eca-a2a-notify）。

小格裡兩個檔（都是暫時的、跟這台機器與這次開的畫面綁在一起，開畫面時 cli_screen.start 先刪）：
  a2a.json        {"socket": 路徑}——畫面 hook 在 SessionStart 從 CLAUDE_CODE_MESSAGING_SOCKET 抄來（note_socket）；
                  投了沒回執＝改寫成 {"off": 原因}（mark_off），這個畫面之後照舊貼字，到下一次 SessionStart 才再試。
  a2a_acks.jsonl  一行 {"at", "id"}——畫面 hook 在 UserPromptSubmit 看到我們的信封（from="aos-<id>"）就記一行（note_ack）＝CLI 真的收進對話了。
socket 本身沒有回話（實測 claude 2.1.323：連上、寫完、對方不回任何字），所以「格式還吃不吃」只能靠這份回執認。

信封是 CLI 沒寫進文件的內部字樣（<cross-session-message from= from-name=>，畫面顯示「Message from @名字」）；改版換掉的症狀是
沒回執或名字不顯示，不是資料壞掉——沒回執就退回貼字（cli_ask.live）。一封信一個信封，一批一次寫完（實測：同一條連線連寫幾行＝
畫面各顯示一則、UserPromptSubmit 各叫一次、合成一輪回答）。沒寫寄件人的一律署名 NOTIFY（機器通知：新信、時鐘信、goal 提醒、
開場白、換台提要）；aos-agent say／chat 的信帶 body 的 name＝真正的寄件人。

pi 身（11-18 eca-pi 丙案）：沒有 socket，改由 aos 的畫面外掛（pi_aos_screen.mjs）當收件口——a2a.json 記 {"inbox": 小格的 pi_inbox/}
（畫面 hook 在 session_start 寫，note_inbox），aos 一封一個 .json（{"id", "text"}，不包信封、不署名，同 pi 非互動那條）寫進去（先寫暫存再改名），
外掛每 0.5 秒收一次、刪檔、用 pi.sendUserMessage 送進對話（答題中＝steer），再叫 hook 記回執（同一份 a2a_acks.jsonl，note_acks）。

一步關掉：定義的 cli.json 寫 "a2a": false（下一輪起那隻照舊貼字）；或把下面 ENABLED 改成 False（全部）。"""
import json, os, re, socket, stat, time, uuid

from aos.agentlib.cli_base import now

ENABLED = True
NOTIFY = "aos通知中心"                 # 機器通知的署名（使用者 11-13 原話「對象就寫aos通知中心，一個假的目標這樣」）
SOCKET_ENV = "CLAUDE_CODE_MESSAGING_SOCKET"
STATE, ACKS = "a2a.json", "a2a_acks.jsonl"
HOOK_MARK = "a2a"                      # 畫面 hook 指令的最後一個參數：有它的畫面才記 socket 與回執（接線之前開的畫面沒有＝照舊貼字）
CONNECT_S = 3
ACK_GRACE_S = 30                       # CLI 閒著卻這麼久沒回執＝這版不吃這個格式（實測閒著時 20 ms 內就有；留長是讓人手打的 /compact 這類不算一輪的事做完）
NOTE = "(delivered by aos, not by a Claude session: answer in your normal reply, do not use SendMessage for it)"
SETTINGS = {"crossSessionInbound": "accept"}     # 開畫面時併進 --settings：無人看的 worker 直接收、不停在畫面等人批（官方文件建議）
_ID = re.compile(r'^\s*<cross-session-message from="aos-([0-9a-f]{12})"')
_NAME_BAD = re.compile(r'[\x00-\x1f\x7f"<>&]')
NAME_MAX = 64


class Undelivered(Exception):
    """沒投出去（一行都沒寫進 socket）：呼叫者退回貼字。"""


def name_ok(name):
    """寄件人名字能不能放進信封：非空、一行、不超過 NAME_MAX 個字、沒有 " < > & 與控制字元。"""
    return isinstance(name, str) and bool(name.strip()) and len(name) <= NAME_MAX and not _NAME_BAD.search(name)


def envelope(name, text, ident):
    """一封信的信封字樣。name 不合格（或沒給）＝NOTIFY；內文裡的結尾標籤拆開，免得提早收尾。"""
    who = name if name_ok(name) else NOTIFY
    body = text.replace("</cross-session-message", "< /cross-session-message")
    return '<cross-session-message from="aos-%s" from-name="%s">\n%s\n%s\n</cross-session-message>' % (ident, who, body, NOTE)


def wire(parts):
    """parts＝[(寄件人名字或 None, 內文)] → ([回執 id], 要寫進 socket 的 bytes：一封一行 JSON)。"""
    ids, lines = [], []
    for name, text in parts:
        ident = uuid.uuid4().hex[:12]
        ids.append(ident)
        lines.append(json.dumps({"type": "user", "message": {"role": "user", "content": envelope(name, text, ident)}},
                                ensure_ascii=False) + "\n")
    return ids, "".join(lines).encode("utf-8")


# ---- 小格的兩個檔 ----

def note_socket(cell, environ=None):
    """畫面 hook（SessionStart）：把這個 session 的收件 socket 路徑抄進小格。環境裡沒有（功能被關、舊版 CLI）＝刪掉舊的。"""
    path = (os.environ if environ is None else environ).get(SOCKET_ENV) or ""
    if path:
        cell.write(STATE, json.dumps({"socket": path}) + "\n")
    else:
        forget(cell)


def note_ack(cell, prompt):
    """畫面 hook（UserPromptSubmit）：這則是我們投的信封＝記一行回執。回 True＝記了。"""
    m = _ID.match(prompt) if isinstance(prompt, str) else None
    if not m:
        return False
    with open(cell.file(ACKS), "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), "id": m.group(1)}) + "\n")
    return True


def note_inbox(cell, path):
    """pi 畫面 hook（session_start）：建收件夾、記進 a2a.json。"""
    os.makedirs(path, exist_ok=True)
    cell.write(STATE, json.dumps({"inbox": path}) + "\n")


def note_acks(cell, ids):
    """pi 畫面 hook（外掛送進對話之後）：每個 id 記一行回執。"""
    with open(cell.file(ACKS), "a", encoding="utf-8") as f:
        for ident in ids if isinstance(ids, list) else []:
            if isinstance(ident, str):
                f.write(json.dumps({"at": now(), "id": ident}) + "\n")


def forget(cell):
    """開新畫面之前：上一個畫面留下的 socket 路徑與回執都不算數。"""
    for name in (STATE, ACKS):
        try:
            os.remove(cell.file(name))
        except OSError:
            pass


def mark_off(cell, why):
    """投了沒回執：這個畫面之後不再試（到下一次 SessionStart 重抄為止）。"""
    try:
        cell.write(STATE, json.dumps({"off": why}) + "\n")
    except OSError:
        pass


def socket_path(cfg, cell):
    """這格現在能不能投：回 socket 路徑（pi＝收件夾）；不能＝None（沒開、不是 claude／pi、cli.json 關掉、沒記到路徑、那裡不是 socket／資料夾）。"""
    if not ENABLED or cfg.get("kind") not in ("claude", "pi") or cfg.get("a2a", True) is False:
        return None
    if cfg["kind"] == "pi":
        try:
            path = json.loads(cell.read(STATE) or "null").get("inbox")
            return path if isinstance(path, str) and os.path.isdir(path) else None
        except (ValueError, AttributeError):
            return None
    try:
        path = json.loads(cell.read(STATE) or "null").get("socket")
        if isinstance(path, str) and path and stat.S_ISSOCK(os.stat(path).st_mode):
            return path
    except (ValueError, AttributeError, OSError):
        pass
    return None


def acks_size(cell):
    try:
        return os.path.getsize(cell.file(ACKS))
    except OSError:
        return 0


def acked(cell, offset, ids):
    """回執檔從 offset 之後、屬於 ids 的那幾行：{id: at}。"""
    got = {}
    try:
        with open(cell.file(ACKS), encoding="utf-8") as f:
            f.seek(offset)
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("id") in ids:
                    got[row["id"]] = row.get("at") or ""
    except OSError:
        pass
    return got


# ---- 投遞 ----

def post(cfg, path, parts):
    """投一批：claude＝包信封寫 socket（wire、deliver）；pi＝一封一個檔寫進收件夾（deliver_inbox）。回 [回執 id]；投不出去＝Undelivered。"""
    if cfg.get("kind") == "pi":
        return deliver_inbox(path, parts)
    ids, data = wire(parts)
    deliver(path, data)
    return ids


def deliver_inbox(path, parts):
    """pi 的收件夾：一封一個 <時間>-<序>-<id>.json（{"id", "text"}），先寫 .tmp 再改名（外掛只讀 .json）。"""
    ids, stamp = [], "%.6f" % time.time()
    try:
        for i, (_name, text) in enumerate(parts):
            ident = uuid.uuid4().hex[:12]
            tmp = os.path.join(path, ".%s.tmp" % ident)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"id": ident, "text": text}, f, ensure_ascii=False)
            os.replace(tmp, os.path.join(path, "%s-%03d-%s.json" % (stamp, i, ident)))
            ids.append(ident)
    except OSError as e:
        if not ids:
            raise Undelivered("%s: %s" % (path, e.strerror or e))
    return ids


def deliver(path, data):
    """連上 socket、整批寫完、關掉。連不上或寫不進去＝Undelivered（呼叫者退回貼字）。"""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(CONNECT_S)
        s.connect(path)
        s.sendall(data)
        s.shutdown(socket.SHUT_WR)
    except OSError as e:
        s.close()
        raise Undelivered("%s: %s" % (path, e.strerror or e))
    try:
        s.settimeout(1)
        s.recv(4096)                     # 等對方讀完收線（它不回字）；等不到不算錯
    except OSError:
        pass
    s.close()
