"""daemon_ctl 基礎：共用錯誤類別與 daemon 檔名常數。"""
STATE = "procs_state.json"
PATHS = ("stack", "ws", "exec", "def")
NAMES = {"procs_loop": "loop.json", "procs_ctl_mailbox": "procs_ctl_mailbox", "procs_stderr": "stderr.txt"}

class Fail(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code
