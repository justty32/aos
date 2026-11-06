"""daemon_ctl 基礎：共用錯誤類別、用法與 daemon 檔名常數。"""
USAGE = ("aos-daemon-ctl [--daemon D] add [--reply-to BOX] [--name N] [--ws WS] [--stack S] [--def DEF] [--limits JSON] XXX [-- ARGS...]"
         " | rm|stop|start|sleep|wake [--reply-to BOX] NAME | pause NAME | resume NAME | ls [--json] | where --stack NAME | ping [--timeout-s S]")
STATE = "procs_state.json"
PATHS = ("stack", "ws", "exec", "def")
NAMES = {"procs_loop": "loop.json", "procs_ctl_mailbox": "procs_ctl_mailbox", "procs_stderr": "stderr.txt"}

class Fail(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code
