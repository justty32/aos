"""daemon.md §2 的非同步入口：讀目標、開控制 pipe、交出孩子；登記、go、收屍的時機歸 daemon。

前置檢查、環境、stderr 與 exit 照 inst（共用 aos_exec_run._execute_inst）；孩子自己一個 pgid、
同一 session。`launcher` 決定 fd 0／1 怎麼接：預設兩條控制 pipe，daemon 的池式孩子改用
aos_daemon_pools._launch（只留 fd 0、fd 1 接 /dev/null）。
"""
import contextlib
import io
import json
import os
import subprocess

import aos_inst
from aos_directives import Context, DirectiveError, Document, resolve_located
from aos_exec_run import DEFAULT_DIR_TARGET, _execute_inst, _finish


class SpawnError(Exception):
    """daemon 的 Usage 或 SpawnFailed；尚未交出孩子，不登記。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code, self.msg = code, msg


class Spawned:
    """daemon 擁有的孩子與 exit 檔收尾；控制 pipe 由呼叫者關閉。"""

    def __init__(self, process, exit_path="", exit_append=False):
        self.process = process
        self.exit_path, self.exit_append = exit_path, exit_append

    def finish(self, code=None):
        """收屍後呼叫；省略 code 時將 Popen 的負訊號碼轉為 128+N。"""
        if code is None:
            code = self.process.poll()
            if code is None:
                raise SpawnError("SpawnFailed", "孩子尚未退出，不能寫 exit")
            code = code if code >= 0 else 128 - code
        return _finish(code, self.exit_path, None, self.exit_append)


def spawn_target(xxx, dir_target=DEFAULT_DIR_TARGET, launcher=None):
    """daemon.md §2：讀目標、開控制 pipe，回孩子；登記與 go 由 daemon 做。

    與同步執行共用 inst 的前置檢查、環境、stderr 及 exit；孩子使用獨立 pgid、同一
    session。Popen 起不來（包括普通執行的 126／127）都丟 SpawnFailed，不登記假 pid。
    `launcher` 省略＝`_spawn_control`（fd 0／1 兩條 pipe）；每次都重讀目標。
    """
    launcher = launcher or _spawn_control
    p = os.path.abspath(xxx)
    if os.path.isdir(p):
        target, base = os.path.join(p, dir_target), p
        if not os.path.isfile(target):
            raise SpawnError("SpawnFailed", "資料夾 %s 裡沒有 %s" % (p, dir_target))
    elif p.endswith(".json"):
        target, base = p, os.path.dirname(p)
    else:
        if not os.path.exists(p):
            raise SpawnError("SpawnFailed", "找不到 %s" % xxx)
        return launcher([p], os.path.dirname(p), dict(os.environ), None, None, None, 0, "")
    inst = _load_control_inst(target, base)
    diagnostic = io.StringIO()
    try:
        with contextlib.redirect_stderr(diagnostic):
            result = _execute_inst(inst, 0, launcher=launcher)
    except ValueError as e:
        raise SpawnError("SpawnFailed", "FieldTypeMismatch: 無法執行 inst：%s" % e)
    if not isinstance(result, Spawned):
        raise SpawnError("SpawnFailed", diagnostic.getvalue().strip())
    return result


def _load_control_inst(target, base):
    """只讀一份快照，檢查頂層顯式串流，再以原文件位置解 inst。"""
    try:
        with open(target, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise SpawnError("SpawnFailed", "ReadFailed: %s" % e)
    except UnicodeError as e:
        raise SpawnError("SpawnFailed", "JsonSyntax: %s" % e)
    try:
        obj = json.loads(raw)
    except ValueError as e:
        raise SpawnError("SpawnFailed", "JsonSyntax: %s" % e)
    try:
        top = resolve_located(obj, Context(Document(target, obj), base_dir=base), [])
        if isinstance(top.value, dict) and any(key in top.value for key in ("stdin", "stdout")):
            raise SpawnError("Usage", "daemon 孩子的 stdin／stdout 由控制 pipe 接管，不可寫在 inst")
        # load_obj 會丟掉原文件與 subtree 位置；指回已在記憶體的文件，保留 $ref:"" 語意。
        reference = {"$ref": ""}
        if top.position:
            reference["$at"] = "/" + "/".join(str(x).replace("~", "~0").replace("/", "~1")
                                               for x in top.position)
        ctx = Context(top.ctx.doc, base_dir=base, env=top.ctx.env)
        return aos_inst._load(reference if top.position else top.value, ctx, base)
    except (aos_inst.InstError, DirectiveError) as e:
        raise SpawnError("SpawnFailed", str(e))


def _spawn_control(argv, cwd, env, fin, fout, ferr, timeout_ms, exit_path,
                   on_spawn=None, exit_append=False, *unused):
    """Popen 自己開的四個 pipe 端都是 CLOEXEC；只 dup 子端到 fd 0／1。"""
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, process_group=0, close_fds=True,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=ferr,
                             bufsize=0)
    except (OSError, ValueError) as e:
        raise SpawnError("SpawnFailed", "無法啟動子程式：%s" % e)
    os.set_blocking(p.stdin.fileno(), False)
    os.set_blocking(p.stdout.fileno(), False)
    return Spawned(p, exit_path, exit_append)

