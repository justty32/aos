"""quiet - 「很久沒動靜」的共用讀寫：$AOS_STACK/quiet.json（不進 git）；aos-eca-turn（一輪 CLI 在跑）與 agent-fsm 的 wait.py（等腦回信）寫，誰都能讀。

使用者 11-15：「逾時不回應就當作掛掉這件事，我發現這個不實用，因爲AI一輪跑個二三十分鐘都很正常」「很久沒動靜算黃色，不殺掉。」
所以這只是一個**標記**：寫了不殺、不丟信、不記冷卻、不改任何行為；顯示端（任何讀 stack 的人）看到它就當「還活著、但很久沒動靜」。
格式（改 key 要讓讀的人一起改）：

    {"quiet": true, "what": "cli_turn", "since": "2026-11-15T08:00:00Z", "at": "2026-11-15T08:12:30Z", "quiet_s": 750, "pid": 12345}

what＝在等什麼（cli_turn＝eca 一輪 CLI 在跑；brain_reply＝agent-fsm 等 llm kernel 回信）；since＝最後一次看到動靜的時間；
at＝這份寫的時間；quiet_s＝寫的那刻已經安靜幾秒；pid＝活著就代表這份還算數的行程（eca＝aos-eca-turn 自己；agent-fsm 的 wait
是一拍一拍的短命格，寫的是 stack 的 state.json 記的 aos-loop pid；讀不到＝null）。時間是牆上時鐘、UTC、ISO 8601 到秒、結尾 Z（同 cooldown.json）。
沒動靜滿 AFTER_S（600 秒）才寫，之後每 REFRESH_S 更新一次 at／quiet_s；又有動靜或這輪結束就刪檔。
寫的行程被 SIGKILL 時檔會留著：讀者用 read()（pid 不在了＝當作沒有；pid 是 null 就不比），或自己比 pid。純標準庫，lib 不 import py。"""
import datetime
import json
import os
import threading
import time

NAME = "quiet.json"
AFTER_S = 600                                   # 沒動靜滿這麼久才標（同 agent-fsm wait.py 的 10 分鐘提醒）
REFRESH_S = 60                                  # 標著的時候多久更新一次 at／quiet_s
POLL_S = 15                                     # Watch 多久看一次動靜


def path(stack):
    return os.path.join(stack, NAME)


def iso(t):
    return datetime.datetime.fromtimestamp(int(t), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mark(stack, what, since, now=None, pid=None):
    """寫一份 quiet.json（先寫 . 開頭的暫存檔再改名，N-05）；回寫進去的 dict。pid 沒給＝自己；給 0＝null（不知道誰）。寫不成丟 OSError。"""
    now = time.time() if now is None else now
    rec = {"quiet": True, "what": str(what), "since": iso(since), "at": iso(now),
           "quiet_s": max(0, int(now - since)), "pid": os.getpid() if pid is None else pid or None}
    tmp = os.path.join(stack, ".%s.%d.tmp" % (NAME, os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path(stack))
    return rec


def clear(stack):
    """有動靜了或這輪結束：刪檔。本來就不在不算錯；刪不掉丟 OSError。"""
    try:
        os.remove(path(stack))
    except FileNotFoundError:
        pass


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read(stack):
    """讀 quiet.json：不在、壞了、或寫的行程已經不在＝None；好的＝dict。"""
    try:
        with open(path(stack), encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or rec.get("quiet") is not True:
        return None
    pid = rec.get("pid")
    if pid is not None and (not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or not alive(pid)):
        return None
    return rec


def latest_mtime(paths):
    """paths 裡還在的檔最新的修改時間（跟 symlink）；一個都沒有＝None。資料夾＝看它底下一層的檔。"""
    best = None
    for p in paths:
        try:
            names = [os.path.join(p, n) for n in os.listdir(p)] if os.path.isdir(p) else [p]
        except OSError:
            continue
        for n in names:
            try:
                t = os.stat(n).st_mtime
            except OSError:
                continue
            best = t if best is None or t > best else best
    return best


class Watch:
    """背景執行緒：看 paths（檔或資料夾）有沒有在變；從 start 起或最後一次變動起滿 after_s 就寫 quiet.json，又變了就刪，stop 時刪。
    只標記，什麼都不殺。寫不成就算了（不影響這輪）。用法：with quiet.Watch(stack, "cli_turn", [檔, …]): 跑那一輪"""

    def __init__(self, stack, what, paths, after_s=None, poll_s=None, refresh_s=None):
        self.stack, self.what, self.paths = stack, what, list(paths)
        self.after_s = AFTER_S if after_s is None else after_s            # 沒給＝建立時讀模組的值（測試可以改模組常數縮時）
        self.poll_s = POLL_S if poll_s is None else poll_s
        self.refresh_s = REFRESH_S if refresh_s is None else refresh_s
        self.done = threading.Event()
        self.thread = None
        self.marked_at = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False

    def start(self):
        self.began = time.time()
        try:
            clear(self.stack)                    # 上一次被 SIGKILL 留下的
        except OSError:
            pass
        self.thread = threading.Thread(target=self.run, name="quiet-watch", daemon=True)
        self.thread.start()

    def last_activity(self):
        t = latest_mtime(self.paths)
        return self.began if t is None or t < self.began else t

    def step(self, now=None):
        now = time.time() if now is None else now
        last = self.last_activity()
        try:
            if now - last >= self.after_s:
                if self.marked_at is None or now - self.marked_at >= self.refresh_s:
                    mark(self.stack, self.what, last, now)
                    self.marked_at = now
            elif self.marked_at is not None:
                clear(self.stack)
                self.marked_at = None
        except OSError:
            pass

    def run(self):
        while not self.done.wait(self.poll_s):
            self.step()

    def stop(self):
        self.done.set()
        if self.thread is not None:
            self.thread.join()
        try:
            clear(self.stack)
        except OSError:
            pass
