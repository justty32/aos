# 「自己跑」零件：把一件工作掛成 daemon 的 proc、看表收成品、逾時、重掛一次、拔列；去處由呼叫的包給。
import json
import os
import subprocess
import sys
import time

PROC_JSON = "proc.json"
GIVE_UP_S = 300          # 列被人 stop 後等多久才放棄（從第一次看到它停著起算）


class Failed(Exception):
    """寄信或落檔失敗；code 與 msg 交給呼叫的包決定怎麼說。"""

    def __init__(self, code, msg):
        super().__init__("%s %s" % (code, msg))
        self.code, self.msg = code, msg


def read_json(path):
    """讀一份 JSON 物件；不在、讀不懂、不是物件都回 None。"""
    try:
        with open(path, encoding="utf-8") as stream:
            doc = json.load(stream)
    except (OSError, ValueError, UnicodeError):
        return None
    return doc if isinstance(doc, dict) else None


def write_json(path, doc):
    """同夾暫存再改名；鍵照原順序、縮排兩格。"""
    folder, name = os.path.split(path)
    tmp = os.path.join(folder, ".%s.%d.tmp" % (name, os.getpid()))
    try:
        os.makedirs(folder, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(doc, indent=2, ensure_ascii=False))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except OSError as error:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise Failed("WriteFailed", "cannot write %s: %s" % (path, error.strerror or error)) from None


def error_of(stderr, prog, fallback):
    """從下層指令的錯誤行拿代號與原因；其餘行照轉到自己的 stderr。"""
    found = None
    mark = prog + ": error: "
    for line in stderr.splitlines():
        if found is None and line.startswith(mark):
            code, _, msg = line[len(mark):].partition(" ")
            found = (code, msg)
        else:
            sys.stderr.write(line + "\n")
    return found or fallback


def send(box, body):
    """寄一封信進 box，回信名；寄不進丟 Failed（代號照 aos-post 的錯誤行）。"""
    try:
        result = subprocess.run(["aos-post", "send", box], input=json.dumps(body, ensure_ascii=False),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as error:
        raise Failed("CommandMissing", "aos-post failed to start (must be on PATH): %s" % error) from None
    if result.returncode != 0:
        raise Failed(*error_of(result.stderr, "aos-post",
                               ("PostFailed", "aos-post send exited %d" % result.returncode)))
    sys.stderr.write(result.stderr)
    return result.stdout.strip()


def remove(box, name):
    """請 daemon 拔掉那一列；寄不進不算錯（下一輪還會再看到）。"""
    try:
        send(box, {"procs_removed": [name]})
    except Failed:
        pass


def read_table(daemon):
    """回 (表上的列, mailbox_warning)；窗不在或讀不懂當空的，daemon 剛起時就是這樣。"""
    warning = ""
    flux = read_json(os.path.join(daemon, "state_flux.json"))
    if flux and isinstance(flux.get("mailbox_warning"), str):
        warning = flux["mailbox_warning"]
    state = read_json(os.path.join(daemon, "procs_state.json"))
    if not state:
        return {}, warning
    procs = state.get("procs", {})
    if isinstance(procs, dict) and "$ref" in procs:     # 超過百列的切檔
        try:
            result = subprocess.run(["aos-directive"], input=json.dumps(procs), stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, cwd=daemon)
            procs = json.loads(result.stdout) if result.returncode == 0 else None
        except (OSError, ValueError):
            procs = None                                # 分檔正在換：這輪當沒看到
    return (procs if isinstance(procs, dict) else {}), warning


def host_ref(target, daemon):
    """執行目標寫成相對 AOS_DAEMON，整棵樹搬家後在途的工作跑新位置那份。"""
    path, _, pointer = target.partition("#")
    if not path.startswith("/") or not daemon:
        return target
    rel = os.path.relpath(path, daemon)
    return {"$env": "AOS_DAEMON", "$path": rel + ("#" + pointer if pointer else "")}


def mount(job, name, target, proc, box, daemon, timeout_ms=None, stdin="request.json", stdout="reply.json"):
    """寄掛信、寫 proc.json，回寫好的那份；job 是這件工作的資料夾，也是那個 proc 的 stack 與 cwd。"""
    spec = {"argv": ["aos-exec", host_ref(target, daemon)], "cwd": job, "stdin": stdin, "stdout": stdout}
    if timeout_ms is not None:
        spec["timeout_ms"] = timeout_ms
    proc = dict(proc, name=name, exec=target)
    proc["mount_letter"] = send(box, {"procs_added": {name: {"exec": spec, "max": 1, "stack": job}}})
    # 首次掛上沿用呼叫的人給的時間；重掛只更新這次的計時。
    if "mounted_at" not in proc or proc.get("retries", 0) > 0:
        proc["mounted_at"] = time.time()
    proc.setdefault("retries", 0)
    write_json(os.path.join(job, PROC_JSON), proc)
    return proc


def _save(job, proc):
    try:
        write_json(os.path.join(job, PROC_JSON), proc)
    except Failed:
        pass


def settle(job, proc, table, box, daemon, timeout_ms=None, name=None, target_for=None, accept=None,
           give_up_s=GIVE_UP_S, stdin="request.json", stdout="reply.json"):
    """看一件掛出去的工作現在怎樣。回 None＝還在飛；否則回一個結果：
      {"kind": "exit", "code": 結束碼, "timed_out": 布林}   跑完了，成品在 job/<stdout>、job/stderr.txt
      {"kind": "launch", "msg": 原因}                       掛信寄不進，或 daemon 說不收
      {"kind": "twice"}                                     重掛過一次還是沒結果
      {"kind": "stopped", "name": 名字, "seconds": 秒}      列被人停著太久，放棄
      {"kind": "write", "msg": 原因}                        proc.json 寫不了
    target_for(proc)＝重掛時要跑的目標（沒給＝proc.json 記的）；accept(code)＝退非 0 時包認不認這份成品。"""
    procs, warning = table
    name = proc.get("name", name)
    args = dict(timeout_ms=timeout_ms, stdin=stdin, stdout=stdout)
    target = lambda: target_for(proc) if target_for else proc.get("exec")
    if proc.get("remount") is True:
        if name in procs:
            return None                                  # 舊列還沒拔：等
        proc = dict(proc)
        del proc["remount"]
        try:
            mount(job, name, target(), proc, box, daemon, **args)
        except Failed as error:
            return {"kind": "launch", "msg": "remount letter could not be sent: %s %s" % (error.code, error.msg)}
        return None
    state = read_json(os.path.join(job, "state.json"))
    phase = state.get("phase") if state else ""
    held = name in procs
    if held:
        row = procs[name]
        failed = isinstance(row, dict) and isinstance(row.get("reason"), str)
        stopped = isinstance(row, dict) and row.get("phase") == "stopped"
        if not stopped or (phase != "done" and not failed):
            if not stopped or phase == "done":
                if "stopped_seen_at" in proc:            # 又跑起來了：重算
                    proc = dict(proc)
                    del proc["stopped_seen_at"]
                    _save(job, proc)
                return None
            # 停著、沒寫原因、沒跑完＝有人下了 stop：等，但有上限。
            now, seen = time.time(), proc.get("stopped_seen_at")
            if isinstance(seen, bool) or not isinstance(seen, (int, float)):
                _save(job, dict(proc, stopped_seen_at=now))
                return None
            if now - seen < give_up_s:
                return None
            remove(box, name)
            return {"kind": "stopped", "name": name, "seconds": int(give_up_s)}
        remove(box, name)
    elif state is None:
        letter = proc.get("mount_letter", "")
        if letter and isinstance(letter, str) and letter in warning:
            return {"kind": "launch", "msg": "daemon rejected the add letter: " + warning}
        return None                                      # daemon 還沒套那封掛信：照算在飛
    code = -1
    if state and phase in ("done", "stopped") and isinstance(state.get("code"), int) \
            and not isinstance(state.get("code"), bool):
        code = state["code"]
    if phase == "done" and code == 0:
        return {"kind": "exit", "code": 0, "timed_out": False}
    mounted = proc.get("mounted_at", 0.0)
    if isinstance(mounted, bool) or not isinstance(mounted, (int, float)):
        mounted = 0.0
    late = timeout_ms is not None and time.time() - mounted >= timeout_ms / 1000.0
    if phase == "done" and code in (143, 137) and late:
        return {"kind": "exit", "code": code, "timed_out": True}
    if phase == "done" and code != 0 and accept is not None and accept(code):
        return {"kind": "exit", "code": code, "timed_out": False}
    if phase == "done" and code != 143:
        return {"kind": "exit", "code": code, "timed_out": False}
    # 沒到時限就被 TERM、被收掉、死在半路：重掛一次。
    retries = proc.get("retries", 0)
    if retries >= 1:
        return {"kind": "twice"}
    for leftover in ("state.json", stdout):
        try:
            os.unlink(os.path.join(job, leftover))
        except OSError:
            pass
    proc = dict(proc, retries=retries + 1)
    if held:                                             # 拔列的信剛寄：等列不見了下一輪才掛
        try:
            write_json(os.path.join(job, PROC_JSON), dict(proc, remount=True))
        except Failed as error:
            return {"kind": "write", "msg": error.msg}
        return None
    try:
        mount(job, name, target(), proc, box, daemon, **args)
    except Failed as error:
        return {"kind": "launch", "msg": "cannot send the re-add letter: %s %s" % (error.code, error.msg)}
    return None
