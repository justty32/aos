"""daemon_ctl 基礎：共用錯誤類別與 daemon 檔名常數。"""
STATE = "procs_state.json"
STATE_FLUX = "state_flux.json"
PATHS = ("stack", "ws", "exec", "def")
NAMES = {"procs_loop": "loop.json", "procs_requests": "procs_requests", "procs_stderr": "stderr.txt"}

class Fail(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code


class Already(Exception):
    """要的狀態本來就是了（cli-sweep Q4＝A，使用者 11-10：已停再停兩支都算成功）：呼叫者印這一句、退 0，不寄信。"""
