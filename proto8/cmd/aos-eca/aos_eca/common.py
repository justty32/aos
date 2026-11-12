# aos_eca/common.py - 共用的名字、錯誤（Fail）、lib 模組的載入、aos-post 介面與 mailbox_warning。
import os

import aos_ws

# bin 入口把自己的資料夾放在最前；bin 旁邊有跟著帶的模組就用那份，否則用 lib/agent 的。
_BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
if os.path.isfile(os.path.join(_BIN, "cli_session.py")):
    import cli_session  # noqa: E402
else:
    import agent.cli_session as cli_session  # noqa: E402
if os.path.isfile(os.path.join(_BIN, "cooldown.py")):
    import cooldown  # noqa: E402
else:
    import agent.cooldown as cooldown  # noqa: E402
if os.path.isfile(os.path.join(_BIN, "hooks.py")):
    import hooks  # noqa: E402
else:
    import agent.hooks as hooks  # noqa: E402
if os.path.isfile(os.path.join(_BIN, "goal_state.py")):
    import goal_state  # noqa: E402
else:
    import agent.goal_state as goal_state  # noqa: E402

NAME = "aos-eca-turn"
NOT_FOUND = 10


class Fail(Exception):
    """自己這層或 cli_session 的錯：code＝代號。"""

    def __init__(self, code, reason):
        super().__init__(str(reason).replace("\n", " "))
        self.code = code


def names(box, stage):
    """某一格裡的信件名稱（. 開頭的不算，N-05），照處理順序（aos_ws.letter_key）排。"""
    try:
        return sorted((n for n in os.listdir(os.path.join(box, stage)) if not n.startswith(".")), key=aos_ws.letter_key)
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
        raise Fail("WriteFailed", "cannot write %s: %s" % (path, e))


def post(args, stdin_text=""):
    """叫共用的 aos-post 介面，把錯誤換成這層的 Fail。"""
    try:
        return aos_ws.run_post(args, stdin_text)
    except aos_ws.Error as e:
        raise Fail(e.code, e)


def must_post(args, stdin_text="", ok=(0,)):
    code, out = post(args, stdin_text)
    if code not in ok:
        raise Fail("PostFailed", "aos-post %s exited %d" % (args[0], code))
    return code, out

# ---- mailbox_warning.txt ----

def warn(stack, sig, why):
    """N-16 壞信記 mailbox_warning：$AOS_STACK/mailbox_warning.txt 一行、只留最後一封（11-03 前記在 trace）。"""
    write_atomic(os.path.join(stack, "mailbox_warning.txt"), "letter %s rejected: %s\n" % (sig, why.replace("\n", " ")))
