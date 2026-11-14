# cli_stream.py - 非互動那條路的「中途收信」版：claude -p --input-format stream-json，stdin 先不關，回答途中把新信一行一行投進去
import json, os, selectors, subprocess, threading, time

if __package__:
    from . import cli_base
else:
    import cli_base

MID_FLAGS = ["--input-format", "stream-json", "--replay-user-messages"]
CAP = {"letters": 5, "seconds": 300}     # 一輪中途最多投幾封、起行程後幾秒內才投
STALL = 30                               # 看過 result、沒有背景任務、stdout 又這麼多秒沒動靜＝CLI 不會再動了：關 stdin（不等到逾時）


def user_line(text):
    """stdin 的一行：stream-json 的 user 訊息（寄件人不寫，跟一批信的 prompt 一致）。"""
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}}, ensure_ascii=False) + "\n"


def events(lines):
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            yield ev


def results_text(lines):
    """每個 type＝result、result 是非空字串的，依序用空行接起來（中途的信讓 CLI 多跑一輪＝多一個 result）；壞行跳過。"""
    return "\n\n".join(ev["result"] for ev in events(lines)
                       if ev.get("type") == "result" and isinstance(ev.get("result"), str) and ev["result"])


def answer_text(lines):
    """這一輪的回答：每個 result，加上「中途的信被取走之後、下一次用工具之前」模型說的話（它常先回一句、再接著做原本的事，
    那句不在 result 裡；wake-1114 sonnet 改檔實測），照時間順序用空行接起來。跟緊接著的 result 一字不差的那段不重複收。"""
    parts, said, echoes, listening = [], [], 0, False
    for ev in events(lines):
        kind = ev.get("type")
        if kind == "user" and ev.get("isReplay"):
            echoes += 1
            listening = echoes > 1                    # 第一行是題目本身；之後的是中途的信
        elif kind == "assistant" and listening:
            content = ev.get("message", {}).get("content") if isinstance(ev.get("message"), dict) else None
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    listening = False
                    break
                if block.get("type") == "text" and isinstance(block.get("text"), str) and block["text"].strip():
                    said.append(block["text"])
        elif kind == "result":
            text = ev.get("result") if isinstance(ev.get("result"), str) else ""
            if said and said[-1].strip() == text.strip():
                said.pop()
            parts += said + ([text] if text else [])
            said, listening = [], False
    return "\n\n".join(parts + said)


def run_claude_stream_mid(argv, prompt, ws, seconds, live_path, handed=None, env=None, more=None, cap=None, preexec_fn=None):
    """像 cli_print.run_claude_stream，但 stdin 不關：題目寫一行、叫 handed，之後每次醒來（最多 0.5 秒）從 more 拿新信投進去。
    more＝有 take()（回 [(name, content), ...]，沒有回 []）、sent()、unsent() 的物件；拿到的每一項恰好叫一次 sent 或 unsent。
    CLI 回 isReplay 的 user 事件＝模型取走一行（acked）；看到 result 時全取走了，就再投一次，沒新信才關 stdin 讓它收尾。
    seconds＝None 不限時；回 (結束碼, 全部行)。stderr 不攔、原樣透出（R10）。"""
    cap = CAP if cap is None else cap
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=ws, preexec_fn=preexec_fn,
                             env=dict(os.environ, **env) if env else None)
    except FileNotFoundError:
        cli_base.die("CliMissing", "%s is not on PATH" % argv[0])
    start = time.time()
    deadline = None if seconds is None else start + seconds
    st = {"open": True, "written": 1, "acked": 0, "mid": 0, "after_result": False, "last_out": start, "bg": 0}

    def shut():
        st["open"] = False
        try:
            p.stdin.close()
        except OSError:
            pass

    def send(text):
        p.stdin.write(text.encode("utf-8"))
        p.stdin.flush()

    def post():
        """投信：反覆 take 到回 [] 或到上限；回這次寫出幾封。逾時之後（Timer 已 kill 或快了）不再投。"""
        n = 0
        while (st["open"] and more is not None and st["mid"] < cap["letters"]
               and time.time() - start < cap["seconds"] and (deadline is None or time.time() < deadline)):
            items = more.take()
            if not items:
                break
            for _name, content in items:
                if not st["open"] or st["mid"] >= cap["letters"]:
                    more.unsent()                     # 這批多拿的、或管子斷了之後剩的：退回
                    continue
                try:
                    send(user_line(content))
                except (BrokenPipeError, OSError):
                    more.unsent()
                    shut()
                    continue
                more.sent()
                st["written"] += 1
                st["mid"] += 1
                n += 1
        return n

    def seen(ev):
        if ev.get("type") == "system" and ev.get("subtype") == "background_tasks_changed":
            tasks = ev.get("tasks")                   # 現在還在跑的背景任務（整份清單）：在跑＝CLI 還會醒來、還能收信
            st["bg"] = len(tasks) if isinstance(tasks, list) else st["bg"]
            return                                    # 不算「result 之後又動了」
        st["after_result"] = ev.get("type") == "result"
        if ev.get("type") == "user" and ev.get("isReplay"):
            st["acked"] += 1
        elif ev.get("type") == "result" and st["open"]:
            if ev.get("is_error"):
                shut()
            elif st["acked"] >= st["written"] and st["bg"] == 0 and post() == 0:
                shut()                                # 全取走了、沒有背景任務、也沒新信：關 stdin，CLI 做完手上的就退
            # 還有背景任務：CLI 等它做完會再跑一輪，這段時間的信照樣投（wake-1114 bg 實測）
            # acked < written：還有信沒被取走，CLI 會再跑一輪，繼續等

    try:
        send(user_line(prompt))
    except (BrokenPipeError, OSError):
        shut()
    if handed:
        handed()
    timer = None if seconds is None else threading.Timer(seconds, p.kill)
    if timer is not None:
        timer.start()
    lines, buf, fd = [], b"", p.stdout.fileno()
    sel = selectors.DefaultSelector()
    sel.register(fd, selectors.EVENT_READ)
    try:
        with open(live_path, "a", encoding="utf-8") as live:      # 10-28：只接不重寫（副產物留著）
            def got(raw):
                st["last_out"] = time.time()
                line = raw.decode("utf-8", errors="replace")
                lines.append(line)
                live.write(line)
                live.flush()
                for ev in events([line]):
                    seen(ev)
            while True:
                if sel.select(0.5):
                    chunk = os.read(fd, 65536)
                    if not chunk:
                        if buf:
                            got(buf)                  # 最後一段沒換行也算一行
                        break
                    buf += chunk
                    while b"\n" in buf:
                        raw, buf = buf.split(b"\n", 1)
                        got(raw + b"\n")
                post()
                if st["open"] and st["after_result"] and st["bg"] == 0 and time.time() - st["last_out"] > STALL:
                    shut()                            # result 之後 CLI 不再動（寫進去的行沒被取走等）：別讓它空等到逾時
        p.wait()
    finally:
        if timer is not None:
            timer.cancel()
        sel.close()
        if st["open"]:
            shut()
        p.stdout.close()
    if deadline is not None and time.time() > deadline:
        cli_base.die("CliFailed", "%s did not finish within %d s" % (argv[0], seconds))
    return p.returncode, lines
