#!/usr/bin/env python3
# quiet_hook.py - before_queue hook：清淨期間擋下「[aos] new_mail」「[aos] kernel_hold」兩種通知（原文附加到 quiet/deferred.jsonl、退 10 丟掉）。
# 放行：寄件人含 <stack>/quiet/config.json 的 urgent_senders 任一名字的 new_mail（repo-aos 設 xiaosi：小廝只轉要緊的事與彙整；不設＝沒有人特別放行）、其他所有訊息（人打的、不是 [aos] 開頭的、cross-session 的）、沒開清淨或已過期。
# 介面：stdin＝事件 JSON（event、stack＝agent 的 stack、letter、content）；退 0 無輸出＝照常放行、退 10＝丟掉。讀不懂的一律放行（寧可吵也不吞）。
# 使用者 11-14 清淨時段；指令與共用函式在 quiet.py。掛它用 on_error: continue。
import json, os, re, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import quiet as q

MARKS = ("[aos] new_mail", "[aos] kernel_hold")
FROM = re.compile(r"letters? from (.*?)\. Look with", re.S)


def urgent(stack, content):
    """new_mail from an urgent sender (config urgent_senders, substring, any case) is let through."""
    if not content.startswith("[aos] new_mail"):
        return False
    m = FROM.search(content)
    return bool(m) and q.has_any(m.group(1), q.config(stack)["urgent"])


def main():
    try:
        ev = json.load(sys.stdin)
        stack, content = ev["stack"], ev["content"]
    except (ValueError, KeyError, TypeError):
        return 0
    if not isinstance(stack, str) or not isinstance(content, str) or not content.startswith(MARKS):
        return 0
    if not q.active(stack) or urgent(stack, content):
        return 0
    d = q.qdir(stack)
    row = json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "epoch": time.time(), "content": content}, ensure_ascii=False) + "\n"
    try:
        os.makedirs(d, exist_ok=True)
        fd = os.open(os.path.join(d, q.DEFERRED), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, row.encode("utf-8"))       # 一次寫一整行（append 不會跟 tick 的改名撕裂）
        finally:
            os.close(fd)
    except OSError as e:
        sys.stderr.write("quiet_hook: error: WriteFailed cannot keep the notice (%s); let it through\n" % e)
        return 0                                    # 存不下就放行，不吞
    print("held by quiet time")
    return 10


sys.exit(main())
