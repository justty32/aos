#!/usr/bin/env python3
"""test_ffi.py：用 Python 標準庫 ctypes 載 lib/libinst.so、呼叫 aos_inst_exec（和兩步的 start／wait），證明 C FFI 用得起來。

    python3 tests/test_ffi.py lib/libinst.so
"""
import ctypes
import os
import signal
import sys
import tempfile


class Input(ctypes.Structure):
    """對應 aos.h 的 aos_inst_input_t（欄位順序、型別要一模一樣）。沒設的欄位都是零＝預設值。"""
    _fields_ = [("argv", ctypes.POINTER(ctypes.c_char_p)), ("cwd", ctypes.c_char_p),
                ("envs", ctypes.POINTER(ctypes.c_char_p)),
                ("paths", ctypes.c_char_p * 3), ("appends", ctypes.c_bool * 3), ("merge", ctypes.c_bool),
                ("timeout_ms", ctypes.c_ulonglong), ("grace_ms", ctypes.c_ulonglong),
                ("inherits", ctypes.c_bool * 3), ("new_session", ctypes.c_bool)]


class Result(ctypes.Structure):
    """對應 aos.h 的 aos_inst_result_t。"""
    _fields_ = [("code", ctypes.c_int), ("signal", ctypes.c_int), ("timed_out", ctypes.c_bool),
                ("pid", ctypes.c_long), ("ms", ctypes.c_ulonglong)]


class Proc(ctypes.Structure):
    """對應 aos.h 的 aos_inst_proc_t。呼叫者只讀 pid。"""
    _fields_ = [("pid", ctypes.c_long), ("pidfd", ctypes.c_int), ("t0_ms", ctypes.c_ulonglong),
                ("deadline_ms", ctypes.c_ulonglong), ("grace_ms", ctypes.c_ulonglong), ("group", ctypes.c_bool)]


def strings(items):
    """Python 字串 list → NULL 結尾的 char* 陣列；None 照樣傳 NULL。"""
    if items is None:
        return None
    return (ctypes.c_char_p * (len(items) + 1))(*[s.encode() for s in items], None)


def load(path):
    lib = ctypes.CDLL(path)
    lib.aos_inst_exec.restype = ctypes.c_int
    lib.aos_inst_exec.argtypes = [ctypes.POINTER(Input), ctypes.POINTER(Result)]
    lib.aos_inst_start.restype = ctypes.c_int
    lib.aos_inst_start.argtypes = [ctypes.POINTER(Input), ctypes.POINTER(Proc)]
    lib.aos_inst_wait.restype = ctypes.c_int
    lib.aos_inst_wait.argtypes = [ctypes.POINTER(Proc), ctypes.POINTER(Result)]
    lib.aos_inst_strerror.restype = ctypes.c_char_p
    lib.aos_inst_strerror.argtypes = [ctypes.c_int]
    return lib


def run(lib, argv, cwd, stdout=None, envs=None, timeout_ms=0):
    """跑一次。路徑都要是絕對路徑（lib 的規矩）。"""
    argv_c, envs_c = strings(argv), strings(envs)  # 留著參照，免得呼叫途中被回收
    inp = Input(argv=argv_c, cwd=cwd.encode(), envs=envs_c, timeout_ms=timeout_ms)
    inp.paths[1] = stdout.encode() if stdout else None
    r = Result()
    rc = lib.aos_inst_exec(ctypes.byref(inp), ctypes.byref(r))
    return rc, r


def main():
    lib = load(sys.argv[1] if len(sys.argv) > 1 else "lib/libinst.so")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.txt")
        env = os.path.join(tmp, "env.txt")
        rc, r = run(lib, ["sh", "-c", "echo hi; exit 3"], tmp, stdout=out)
        assert rc == 0 and r.code == 3 and r.signal == 0 and not r.timed_out, (rc, r.code)
        assert open(out).read() == "hi\n"

        os.environ["AOS_FFI_KEEP"] = "keep"
        rc, r = run(lib, ["sh", "-c", "echo $X $AOS_FFI_KEEP"], tmp, stdout=env)  # envs NULL＝沿用
        assert rc == 0 and open(env).read() == "keep\n"
        # envs＝完整環境；要在呼叫者的上面改一點就自己組
        full = ["%s=%s" % kv for kv in {**os.environ, "X": "from-python"}.items()]
        rc, r = run(lib, ["sh", "-c", "echo $X $AOS_FFI_KEEP"], tmp, stdout=env, envs=full)
        assert rc == 0 and open(env).read() == "from-python keep\n"
        rc, r = run(lib, ["sh", "-c", "echo $X $AOS_FFI_KEEP"], tmp, stdout=env, envs=["X=only", "PATH=/usr/bin:/bin"])
        assert rc == 0 and open(env).read() == "only\n"

        rc, r = run(lib, ["sh"], tmp, stdout="relative.txt")
        assert lib.aos_inst_strerror(rc) == b"PathNotAbsolute", rc

        bindir = os.path.join(tmp, "bin")  # 找程式用 envs 的 PATH
        os.mkdir(bindir)
        with open(os.path.join(bindir, "aos-hello"), "w") as f:
            f.write("#!/bin/sh\nexit 9\n")
        os.chmod(os.path.join(bindir, "aos-hello"), 0o755)
        rc, r = run(lib, ["aos-hello"], tmp, envs=["PATH=" + bindir])
        assert rc == 0 and r.code == 9, (rc, r.code)

        rc, r = run(lib, ["sleep", "5"], tmp, timeout_ms=100)
        assert rc == 0 and r.timed_out and r.signal == 9, (r.timed_out, r.signal)

        rc, r = run(lib, ["no-such-program-aos-xyz"], tmp)
        assert lib.aos_inst_strerror(rc) == b"CommandNotFound", rc

        # 兩步：start 拿到 pid、自己送訊號、wait 收結果
        argv_c = strings(["sleep", "5"])
        inp, p, r = Input(argv=argv_c, cwd=tmp.encode()), Proc(), Result()
        assert lib.aos_inst_start(ctypes.byref(inp), ctypes.byref(p)) == 0
        assert p.pid > 0
        os.kill(p.pid, signal.SIGTERM)
        assert lib.aos_inst_wait(ctypes.byref(p), ctypes.byref(r)) == 0
        assert r.pid == p.pid and r.signal == signal.SIGTERM and r.code == 128 + signal.SIGTERM, (r.signal, r.code)

        # new_session：子程式自成一個行程群組
        inp = Input(argv=argv_c, cwd=tmp.encode(), new_session=True)
        assert lib.aos_inst_start(ctypes.byref(inp), ctypes.byref(p)) == 0
        assert os.getpgid(p.pid) == p.pid, (os.getpgid(p.pid), p.pid)
        os.killpg(p.pid, signal.SIGKILL)
        assert lib.aos_inst_wait(ctypes.byref(p), ctypes.byref(r)) == 0 and r.signal == signal.SIGKILL

        # inherits[1]：stdout 接呼叫者自己的 fd 1（先把 fd 1 換成檔）
        inh = os.path.join(tmp, "inherit.txt")
        echo_c = strings(["sh", "-c", "echo inherited"])
        inp = Input(argv=echo_c, cwd=tmp.encode())
        inp.inherits[1] = True
        sys.stdout.flush()
        saved = os.dup(1)
        fd = os.open(inh, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        os.dup2(fd, 1)
        os.close(fd)
        try:
            rc = lib.aos_inst_exec(ctypes.byref(inp), ctypes.byref(r))
        finally:
            os.dup2(saved, 1)
            os.close(saved)
        assert rc == 0 and open(inh).read() == "inherited\n", (rc, open(inh).read())
    print("test_ffi：全部通過")


if __name__ == "__main__":
    main()
