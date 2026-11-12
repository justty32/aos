# cli_base.py - cli_session 各分檔共用的底：錯誤行與提醒行（PROG／ECHO 決定開頭與要不要也印 stdout）、時間、共用常數、找 lib 的 tool_io
import datetime, os, sys

# hook 直接執行此檔時只補父層 lib；import 後還原，不影響呼叫者的查找順序。
_lib = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_added_lib = os.path.basename(_lib) == "lib" and os.path.isfile(os.path.join(_lib, "tool_io.py"))
if _added_lib:
    sys.path.insert(0, _lib)
try:
    import tool_io
finally:
    if _added_lib:
        sys.path.pop(0)

# hook／guard 叫回的入口：拆檔後仍是同層的 cli_session.py（以前是 os.path.abspath(__file__)）
SELF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli_session.py")
TMUX_SESSION = "cli"
PROG, ECHO = "cli_session", False                    # 錯誤行開頭、要不要也印到 stdout（call_main 改成工具名、True）
RESEED_BYTES, SCREEN_RESEED_BYTES = 48000, 8000      # 開新對話時紀錄的上限：cli.json 的 reseed_bytes 預設、畫面那條路的天花板（05）


def die(code, reason):
    tool_io.die(code, " ".join(str(reason).splitlines()), prog=PROG, echo=ECHO)


def warn(sentence):
    """提醒行（stdio-unify R1）：stderr 一句、不帶代號。"""
    tool_io.warn(" ".join(str(sentence).splitlines()), prog=PROG)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
