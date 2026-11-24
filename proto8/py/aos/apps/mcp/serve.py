# serve.py - aos-mcp 的收發台：tools/call 各開一條執行緒跑，長等的呼叫（subagent listen 等 600 秒）不擋同時叫的別的工具
"""11-24 晚（線 home-listen-1124，narr-amber 回報②）：以前 aos-mcp 讀一行、做完、回完才讀下一行，一次只處理一則；
eca 的 main 對下屬 listen 時，同時叫的 subagent state、mailbox_read 全排在後面、等 listen 結束才回。現在：
- tools/call 一則一條執行緒（Server.spawn），回覆照請求 id 寫回，不照到達順序；stdout 一次寫一則（Server.send 拿鎖），不會交錯。
- 工具的 _metainfo 寫 "parallel": false（同一個工具不能同時跑兩份）＝同名的呼叫排隊（Server.gate），不同名的照樣同時跑；沒寫＝可以同時（tool_spec 的預設）。
- notifications/cancelled（MCP：用戶端不要那次的結果了）＝收掉那次的行程群（TERM→2 秒→KILL）、不回覆；還在排隊的就不跑。
- stdin 讀完＝等還在跑的都回完再走（跟以前一樣：讀到的每一則都有回覆）。"""
import contextlib
import json
import sys
import threading

from aos import process_group  # noqa: E402  py/aos/process_group.py：收整群（TERM→等→KILL）


class Job:
    """一次 tools/call：跑工具的行程（call 起了就記上）與取消旗。"""

    def __init__(self):
        self.proc, self.cancelled, self._lock = None, False, threading.Lock()

    def started(self, p):
        """call 起好行程時叫；已經被取消了＝馬上收掉。"""
        with self._lock:
            self.proc = p
            stop = self.cancelled
        if stop:
            process_group.stop(p, 2, 2)

    def cancel(self):
        """取消：記旗；行程在跑＝另一條執行緒去收（收整群最多等 4 秒，不卡讀 stdin 的那條）。"""
        with self._lock:
            self.cancelled = True
            p = self.proc
        if p is not None:
            threading.Thread(target=process_group.stop, args=(p, 2, 2), daemon=True).start()


class Server:
    def __init__(self, out=None):
        self.out = out
        self._out_lock, self._jobs_lock, self._gates_lock = threading.Lock(), threading.Lock(), threading.Lock()
        self.jobs, self._gates, self._threads = {}, {}, []
        self.after = None                        # 每次 tools/call 做完叫一次 → 要緊跟在回覆後面送的通知（main 拿來比清單、送 list_changed）

    def send(self, *objs):
        """寫 JSON-RPC 到 stdout（給幾則就連著寫完、中間不插別的）；用戶端已經關了管子＝不寫了、不吵。"""
        line = "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in objs)
        with self._out_lock:
            try:
                out = self.out or sys.stdout
                out.write(line)
                out.flush()
            except (BrokenPipeError, ValueError):
                pass

    def gate(self, name, parallel):
        """parallel false＝同名一次一份（拿那個名字的鎖）；可以同時＝不擋。"""
        if parallel:
            return contextlib.nullcontext()
        with self._gates_lock:
            return self._gates.setdefault(name, threading.Lock())

    @staticmethod
    def key(mid):
        return json.dumps(mid)                   # 1 與 "1" 是不同的 id

    def spawn(self, mid, fn):
        """開一條執行緒跑 fn(job) → 回覆（None＝不回）；取消了就不回。"""
        job = Job()
        with self._jobs_lock:
            self.jobs[self.key(mid)] = job
        t = threading.Thread(target=self._run, args=(mid, job, fn), daemon=True)
        self._threads = [x for x in self._threads if x.is_alive()] + [t]
        t.start()
        return job

    def _run(self, mid, job, fn):
        try:
            reply = fn(job)
        finally:
            with self._jobs_lock:
                if self.jobs.get(self.key(mid)) is job:
                    del self.jobs[self.key(mid)]
        notes = self.after() if self.after is not None else []
        if job.cancelled:
            reply = None
        self.send(*([reply] if reply is not None else []) + notes)   # 回覆與它帶出的 list_changed 連著寫：用戶端看到回覆時通知已經在後面

    def cancel(self, mid):
        """notifications/cancelled 的 requestId；不認得（已經回了、或沒這則）＝照規格不理。"""
        with self._jobs_lock:
            job = self.jobs.get(self.key(mid))
        if job is not None:
            job.cancel()

    def wait(self):
        """stdin 讀完：等每條還在跑的回完。"""
        for t in list(self._threads):
            t.join()
