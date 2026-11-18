# cli_pi_rpc.py - pi 身非互動那條的 rpc 行程（11-18 eca-pi 乙案）：送題目、等回答時又來的信 steer 進去、agent_settled 之後收工；/compact 那一問一答
import json, os, selectors, subprocess, threading, time

from aos.agentlib import cli_base

# 結構照 cli_stream.run_claude_stream_mid（claude 的 live_mail）：stdin 先不關，每次醒來（最多 0.5 秒）從 more 拿新信。
# pi 的 rpc 比 claude 的 stream-json 好認：送出的每一則 user（題目、steer 進去的信）真的交給模型時，事件流有一則 role user 的 message_end；
# 答完以 agent_settled 為準。所以：
#   - 答題中（agent_start 之後、agent_end 之前）拿到的信＝{"type": "steer"}；agent_end 之後不 steer（pi 可能已經不會再讀 queue）。
#   - agent_settled：還有 steer 了沒送到的（user message_end 比寫出去的少）＝clear_queue 拿回來；加上這時又來的信，有＝接成一則再送一次 prompt
#     （這時 pi 閒著，prompt 會開新的一段），沒有＝關 stdin 讓 pi 收工。
#   - 題目的 response 是 success false（例 pi 正在忙）＝refused，關 stdin。
# 只用 LF 切行（文件：Node 的 readline 會在 U+2028 切錯，pi 只認 LF）。


def run_pi_rpc(argv, prompt, ws, seconds, live_path, handed=None, more=None, cap=None, preexec_fn=None):
    """起 pi --mode rpc、送題目、叫 handed，等到 agent_settled 又沒有新信就關 stdin。more＝有 take()／sent()／unsent() 的物件（midturn.More）；
    拿到的每一項恰好叫一次 sent 或 unsent；cap＝{"letters", "seconds"}（cli_print.live_cap）。seconds＝None 不限時。
    回 (結束碼, 全部行, refused＝題目被拒的原因或 None)。stderr 不攔、原樣透出（R10）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=ws, preexec_fn=preexec_fn)
    except FileNotFoundError:
        cli_base.die("CliMissing", "%s is not on PATH" % argv[0])
    start = time.time()
    deadline = None if seconds is None else start + seconds
    st = {"open": True, "written": 0, "acked": 0, "mid": 0, "running": False, "n": 0, "refused": None, "clearing": None,
          "steers": {}, "back": []}

    def shut():
        st["open"] = False
        try:
            p.stdin.close()
        except OSError:
            pass

    def send(cmd):
        st["n"] += 1
        cmd = dict(cmd, id="aos-%d" % st["n"])
        p.stdin.write((json.dumps(cmd, ensure_ascii=False) + "\n").encode("utf-8"))
        p.stdin.flush()
        return cmd["id"]

    def take(limit):
        """從 more 拿信到 limit 封或沒有為止；回 [內文]（每封已叫 sent；寫不出去的呼叫者自己處理）。"""
        got = []
        while (more is not None and st["open"] and st["mid"] < cap["letters"] and len(got) < limit
               and time.time() - start < cap["seconds"] and (deadline is None or time.time() < deadline)):
            items = more.take()
            if not items:
                break
            for _name, content in items:
                if st["mid"] >= cap["letters"]:
                    more.unsent()
                    continue
                more.sent()
                st["mid"] += 1
                got.append(content)
        return got

    def steer():
        if not st["running"]:
            return
        for content in take(1):
            try:
                st["steers"][send({"type": "steer", "message": content})] = content
            except (BrokenPipeError, OSError):
                shut()                                # 已經叫過 sent：信接進 history 了，這一封等於丟了（同 claude 管子斷）
                return
            st["written"] += 1

    def settled():
        if st["acked"] < st["written"]:              # steer 了還沒送到：拿回來，跟新信一起當下一段的題目
            st["clearing"] = send({"type": "clear_queue"})
            return
        resend(take(cap["letters"]) if more is not None else [])

    def resend(texts):
        texts, st["back"] = [t for t in st["back"] + texts if t], []
        if not texts or not st["open"]:
            shut()
            return
        try:
            send({"type": "prompt", "message": "\n\n".join(texts)})
        except (BrokenPipeError, OSError):
            shut()
            return
        st["written"] += 1

    def seen(ev):
        kind = ev.get("type")
        if kind == "agent_start":
            st["running"] = True
        elif kind == "agent_end":
            st["running"] = False
        elif kind == "message_end" and isinstance(ev.get("message"), dict) and ev["message"].get("role") == "user":
            st["acked"] += 1
        elif kind == "response" and ev.get("command") == "steer" and ev.get("success") is False:
            st["back"].append(st["steers"].get(ev.get("id"), ""))      # 沒收下的 steer：agent_settled 之後跟新信一起當題目再送
            st["written"] -= 1
        elif kind == "response" and ev.get("command") == "prompt" and ev.get("success") is False:
            if ev.get("id") == "aos-1":
                st["refused"] = str(ev.get("error") or "no reason given")
            shut()                                    # 之後再送的那段被拒：那幾封已接進 history、這輪不會有它們的回答
        elif kind == "response" and ev.get("id") == st["clearing"]:
            st["clearing"] = None
            data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
            back = [t for k in ("steering", "followUp") for t in data.get(k) or [] if isinstance(t, str)]
            st["written"] = st["acked"]               # 拿回來的不再等它的 user 事件
            resend(back + (take(cap["letters"]) if more is not None else []))
        elif kind == "agent_settled" and st["open"]:
            settled()

    try:
        send({"type": "prompt", "message": prompt})
        st["written"] = 1
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
        with open(live_path, "a", encoding="utf-8") as live:      # 只接不重寫（同 claude 的 live.jsonl）
            def got(raw):
                line = raw.decode("utf-8", errors="replace")
                lines.append(line)
                live.write(line)
                live.flush()
                try:
                    ev = json.loads(line)
                except ValueError:
                    return
                if isinstance(ev, dict):
                    seen(ev)
            while True:
                if sel.select(0.5):
                    chunk = os.read(fd, 65536)
                    if not chunk:
                        if buf:
                            got(buf)
                        break
                    buf += chunk
                    while b"\n" in buf:
                        raw, buf = buf.split(b"\n", 1)
                        got(raw + b"\n")
                if st["open"] and more is not None:
                    steer()
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
    return p.returncode, lines, st["refused"]


def rpc_once(argv, cmd, ws, seconds, live_path):
    """起 pi --mode rpc、送一個指令、讀到它的 response（id 對得上）才關 stdin；回 (結束碼, response 或 None)。事件也接進 live.jsonl。"""
    from aos.agentlib.cli_print import parent_death_term
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=ws, preexec_fn=parent_death_term())
    except FileNotFoundError:
        cli_base.die("CliMissing", "pi is not on PATH")
    timer = threading.Timer(seconds, p.kill) if seconds else None
    if timer:
        timer.start()
    reply = None
    try:
        p.stdin.write(json.dumps(cmd) + "\n")
        p.stdin.flush()
        with open(live_path, "a", encoding="utf-8") as live:
            for line in p.stdout:
                live.write(line)
                live.flush()
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if isinstance(ev, dict) and ev.get("type") == "response" and ev.get("id") == cmd.get("id"):
                    reply = ev
                    break
        p.stdin.close()
        p.wait()
    finally:
        if timer:
            timer.cancel()
    return p.returncode, reply
