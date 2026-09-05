"""跑一筆指令，寫 .aos/ticks/<N>/insts/ 與 results/。欄位照 WRITER-BRIEF 4.3。"""
import base64
import os
import signal
import subprocess

from . import fsutil, status

DEFAULT_TIMEOUT_MS = 60000


def _argv_item(x):
    if isinstance(x, dict) and "b64" in x:
        return base64.b64decode(x["b64"])
    return str(x)


def build_env(land, tick, series_id, frame, tmpdir, inst, extra=None):
    inherit = inst.get("env_inherit", True)
    env = dict(os.environ) if inherit else {}
    path_list = land.load_config().get("path") or []
    if path_list:
        env["PATH"] = os.pathsep.join(path_list)
    elif not inherit:
        env["PATH"] = "/usr/bin:/bin"
    env["AOS_LAND"] = land.root
    env["AOS_TICK"] = str(tick)
    env["AOS_SERIES"] = series_id
    env["AOS_FRAME"] = frame
    env["AOS_TMP"] = tmpdir
    if os.environ.get("AOS_HOME"):
        env["AOS_HOME"] = os.environ["AOS_HOME"]
    for k, v in (inst.get("env") or {}).items():
        env[str(k)] = str(v)
    for k, v in (extra or {}).items():
        env[str(k)] = str(v)
    return env


def run_inst(land, tick, inst, series_id, timeout_ms=None, extra_env=None):
    """跑一筆指令。回傳執行結果物件（傳輸層）。"""
    inst_id = inst.get("id") or fsutil.new_id()
    inst = dict(inst, id=inst_id, format_version=inst.get("format_version", 1))
    fsutil.write_json(land.inst_file(tick, inst_id), inst)

    tmpdir = land.tick_tmp(tick, inst_id)
    fsutil.ensure_dir(tmpdir)
    frame = land.frame(series_id)
    fsutil.ensure_dir(frame)

    out_path = land.resolve(inst["stdout"]) if inst.get("stdout") else land.result_stdout(tick, inst_id)
    err_path = land.resolve(inst["stderr"]) if inst.get("stderr") else land.result_stderr(tick, inst_id)
    fsutil.ensure_dir(os.path.dirname(out_path))
    fsutil.ensure_dir(os.path.dirname(err_path))

    # timeout_ms 只能比 run 給的更短
    ceiling = timeout_ms if timeout_ms is not None else int(
        land.load_config().get("inst_timeout_ms", DEFAULT_TIMEOUT_MS))
    want = inst.get("timeout_ms")
    eff = min(ceiling, int(want)) if want is not None else ceiling

    result = {
        "format_version": 1,
        "id": inst_id,
        "started_at": fsutil.now_iso(),
        "ended_at": None,
        "exit_code": None,
        "signal": None,
        "timed_out": False,
        "spawn_error": None,
        "stdout": out_path,
        "stderr": err_path,
    }

    argv = [_argv_item(x) for x in inst["argv"]]
    env = build_env(land, tick, series_id, frame, tmpdir, inst, extra_env)
    cwd = land.resolve(inst["cwd"]) if inst.get("cwd") else land.root
    stdin_path = land.resolve(inst["stdin"]) if inst.get("stdin") else os.devnull

    fin = fout = ferr = None
    try:
        fin = open(stdin_path, "rb")
        fout = open(out_path, "wb")
        ferr = open(err_path, "wb")
        p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=fin, stdout=fout,
                             stderr=ferr, start_new_session=True)
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as e:
        result["spawn_error"] = "%s: %s" % (type(e).__name__, e)
        result["ended_at"] = fsutil.now_iso()
        for f in (fin, fout, ferr):
            if f:
                f.close()
        fsutil.write_json(land.result_file(tick, inst_id), result)
        return result

    try:
        p.wait(timeout=eff / 1000.0)
    except subprocess.TimeoutExpired:
        result["timed_out"] = True
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            p.kill()
        p.wait()
    finally:
        for f in (fin, fout, ferr):
            if f:
                f.close()

    rc = p.returncode
    if rc is not None and rc < 0:
        result["signal"] = -rc
        result["exit_code"] = None
    else:
        result["exit_code"] = rc
    result["ended_at"] = fsutil.now_iso()
    fsutil.write_json(land.result_file(tick, inst_id), result)
    _rm_tmp(tmpdir)
    return result


def _rm_tmp(tmpdir):
    """暫存器壽命的暫存目錄，指令跑完就刪。"""
    for root, dirs, files in os.walk(tmpdir, topdown=False):
        for f in files:
            try:
                os.unlink(os.path.join(root, f))
            except OSError:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass


def transport_ok(result):
    """傳輸層：跑沒跑起來（I-04 第一頻道）。"""
    if result.get("spawn_error"):
        return False, status.SPAWN_ERROR, result["spawn_error"]
    if result.get("timed_out"):
        return False, status.TIMEOUT, "指令逾時被殺"
    if result.get("signal") is not None:
        return False, status.KILLED, "被訊號 %s 殺掉" % result["signal"]
    return True, None, None


def semantic_ok(land, step, result):
    """語意層：做成沒做成（I-04 第二頻道）。看 expect 檔與 .status.json。"""
    expect = step.get("expect")
    if not expect:
        # 沒宣告檔才看結束碼（WRITER-BRIEF 4.2〔主編補〕）
        rc = result.get("exit_code")
        if rc == 0:
            return True, None, None
        return False, "exit_code", "沒有 `expect`，結束碼是 %s" % rc
    path = land.resolve(expect)
    state, st = status.triple(path)
    if state == status.OK:
        return True, None, None
    if state == status.FAILED:
        return False, st.get("reason", "failed"), st.get("message", "")
    return False, "no_expect_file", "說好要產出 %s，但檔不在" % path
