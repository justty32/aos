"""cpu.md §2、§3、§6 的家、JSON-RPC 信封與可重做檔案操作。

exec cpu、daemon、kernel 共用這一層；不決定工作如何執行。
"""
import copy
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import select
import stat
import sys
import tempfile
import time

from aos_directives import Context, DirectiveError, Document, parse_options, resolve_located


class HomeError(Exception):
    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code, self.msg = code, msg


class RequestExists(HomeError):
    def __init__(self, name):
        super().__init__("AlreadyExists", "request 已存在：%s" % name)


@dataclass
class Envelope:
    name: str
    id: object = None
    notify: bool = False
    method: str | None = None
    params: object = None
    error: dict | None = None


def result_response(id, result):
    return {"jsonrpc": "2.0", "id": id, "result": result}


def error_response(id, code, message, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


def params_error(id, msg, position, code="FieldTypeMismatch"):
    return error_response(id, -32602, msg, {"code": code, "position": position})


def validate_name(name):
    if (not isinstance(name, str) or not name.endswith(".json") or
            "/" in name or "\0" in name):
        raise HomeError("FieldTypeMismatch", "request 名稱必須是單一 .json 檔名")
    return name


def _constant(value):
    raise ValueError("JSON 不接受 %s" % value)


def _loads(raw):
    return json.loads(raw, parse_constant=_constant)


def _valid_id(value):
    return (value is None or isinstance(value, str) or
            (type(value) in (int, float) and
             (not isinstance(value, float) or math.isfinite(value))))


def read_request(path):
    """讀一份檔並分三類；壞信封的 error 是可直接寫出的完整回音。"""
    path = Path(path)
    env = Envelope(validate_name(path.name))
    try:
        obj = _loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        env.error = error_response(None, -32700, "不是合法 JSON：%s" % exc)
        return env
    except OSError as exc:
        raise HomeError("ReadFailed", "讀不到 %s：%s" % (path, exc)) from exc
    if isinstance(obj, dict) and _valid_id(obj.get("id")):
        env.id = obj.get("id")
    if (not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0" or
            not isinstance(obj.get("method"), str) or not _valid_id(obj.get("id"))):
        env.error = error_response(env.id, -32600, "不是合法 JSON-RPC 2.0 request")
        return env
    env.notify = "id" not in obj
    env.method, env.params = obj["method"], obj.get("params")
    return env


def read_json(path):
    try:
        return _loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise HomeError("ReadFailed", "讀不到 JSON %s：%s" % (path, exc)) from exc


def _write_temp(path, obj, indent=None):
    """暫存檔與目的檔同資料夾、名字帶檔名與 pid（再加亂數，不會撞）；失敗也不留下半份。"""
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".%s.%d." % (path.name, os.getpid()),
                                         suffix=".tmp", dir=path.parent, delete=False) as out:
            temp = out.name
            json.dump(obj, out, ensure_ascii=False, allow_nan=False, indent=indent)
            out.write("\n")
        return temp
    except BaseException:
        if temp is not None:
            Path(temp).unlink(missing_ok=True)
        raise


def write_json(path, obj, indent=None):
    """整份原子重寫；indent 給人會手改的檔用（例如 agent 的 info.json 用 2）。"""
    path = Path(path)
    temp = None
    try:
        temp = _write_temp(path, obj, indent)
        os.replace(temp, path)
    except (OSError, ValueError, TypeError) as exc:
        raise HomeError("WriteFailed", "寫不進 %s：%s" % (path, exc)) from exc
    finally:
        if temp is not None:
            Path(temp).unlink(missing_ok=True)


def post_request(home, name, obj):
    """只在不存在時放單；不建立別人的家或佇列。"""
    path = Path(home) / "requests" / validate_name(name)
    temp = None
    try:
        temp = _write_temp(path, obj)
        os.link(temp, path)
    except FileExistsError as exc:
        raise RequestExists(name) from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HomeError("WriteFailed", "放不進 %s：%s" % (path, exc)) from exc
    finally:
        if temp is not None:
            Path(temp).unlink(missing_ok=True)
    return name


def ensure_queue(home):
    try:
        for name in ("requests", "responses"):
            (Path(home) / name).mkdir(exist_ok=True)
    except OSError as exc:
        raise HomeError("WriteFailed", "建不起佇列：%s" % exc) from exc


def read_state(home, default=None):
    path = Path(home) / "state.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return copy.deepcopy({"current": None, "runs": 0} if default is None else default)
    except (OSError, UnicodeError) as exc:
        raise HomeError("ReadFailed", "讀不到 state：%s" % exc) from exc
    try:
        state = _loads(raw)
        if not isinstance(state, dict):
            raise ValueError("state 必須是物件")
        return state
    except (ValueError, UnicodeError) as exc:
        raise HomeError("ReadFailed", "state 不是合法 JSON 物件：%s" % exc) from exc


def write_state(home, state):
    write_json(Path(home) / "state.json", state)


def reconcile_actions(current, request_exists, response_exists):
    """cpu.md §6.2 五列表的純判定；動作順序也是持久化順序。"""
    if current is None or not request_exists:
        return ()
    if response_exists or current.get("notify", False):
        return ("delete_request",)
    return ("interrupt", "delete_request")


def reconcile(home, current):
    if current is None:
        return
    home = Path(home)
    name = validate_name(current["name"])
    req, response = home / "requests" / name, home / "responses" / name
    for action in reconcile_actions(current, req.exists(), response.exists()):
        if action == "interrupt":
            write_json(response, error_response(current.get("id"), -32000,
                       "上一任主人中斷，執行結果不明", {"code": "Interrupted"}))
        else:
            req.unlink(missing_ok=True)


def list_requests(home):
    return sorted(p.name for p in (Path(home) / "requests").iterdir()
                  if p.is_file() and p.name.endswith(".json") and
                  not p.name.startswith(("ack-", "stop-")))


def scan_controls(home, on_stop):
    """處理控制前綴；ack 先刪回音再刪原單，stop 只叫旗標 callback。"""
    home = Path(home)
    paths = sorted(p for p in (home / "requests").iterdir()
                   if p.is_file() and p.name.endswith(".json") and
                   p.name.startswith(("ack-", "stop-")))
    for path in paths:
        env = read_request(path)
        response = env.error
        expected = "ack" if path.name.startswith("ack-") else "stop"
        if response is None:
            if env.method != expected or not env.notify:
                response = error_response(env.id, -32600, "控制前綴必須對應同名 notification")
            elif expected == "ack":
                try:
                    if not isinstance(env.params, dict):
                        raise HomeError("FieldTypeMismatch", "ack.params 必須是物件")
                    name = validate_name(env.params.get("name"))
                except HomeError as exc:
                    response = params_error(env.id, exc.msg, ["params", "name"])
                else:
                    (home / "responses" / name).unlink(missing_ok=True)
            else:
                on_stop()
        if response is not None and not env.notify:
            write_json(home / "responses" / path.name, response)
        path.unlink(missing_ok=True)


def load_info(home, kind):
    """展開 info 指示詞（中心是家，禁 $opt），驗共同身分與輪詢欄位。"""
    home = Path(home).absolute()
    path = home / "info.json"
    try:
        obj = read_json(path)
    except HomeError as exc:
        raise HomeError("NotAHome", exc.msg) from exc

    def expand(value, ctx, position):
        loc = resolve_located(value, ctx, position)
        value = parse_options(loc.value, loc.position, {})[1]
        if isinstance(value, dict):
            return {k: expand(v, loc.ctx, loc.position + [k]) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v, loc.ctx, loc.position + [str(i)]) for i, v in enumerate(value)]
        return value

    try:
        obj = expand(obj, Context(Document(str(path), obj), base_dir=str(home)), [])
    except DirectiveError as exc:
        raise HomeError(exc.code, exc.msg) from exc
    mi = obj.get("_metainfo") if isinstance(obj, dict) else None
    if (not isinstance(mi, dict) or mi.get("_type") != kind or
            type(mi.get("_version")) is not int or mi["_version"] != 1):
        raise HomeError("NotAHome", "info 的身分必須是 %s 第 1 版" % kind)
    for name, default, minimum in (("poll_ms", 20, 1), ("timeout_ms", 0, 0)):
        value = obj.setdefault(name, default)
        if type(value) is not int or value < minimum:
            raise HomeError("FieldTypeMismatch", "%s 必須是至少 %d 的整數" % (name, minimum))
    return obj


def link_json(path, obj):
    """出貨箱用的一般目的路徑：同目錄暫存後 link，存在時不覆蓋。"""
    path, temp = Path(path), None
    try:
        temp = _write_temp(path, obj)
        os.link(temp, path)
    except FileExistsError as exc:
        raise RequestExists(path.name) from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HomeError("WriteFailed", "放不進 %s：%s" % (path, exc)) from exc
    finally:
        if temp is not None:
            Path(temp).unlink(missing_ok=True)


SOURCE_CWD = "目前資料夾"


def resolve_target(value=None, env_var=None, env=None):
    """三支指令共用的「家」找法：--target → 環境變數 → 目前資料夾；回（絕對路徑, 來源）。"""
    env = os.environ if env is None else env
    if value:
        return Path(os.path.abspath(os.path.expanduser(value))), "--target"
    if env_var and env.get(env_var):
        return Path(os.path.abspath(os.path.expanduser(env[env_var]))), env_var
    return Path(os.path.abspath(".")), SOURCE_CWD


def target_note(label, path, source, env_var=None):
    """錯誤訊息尾巴：講清楚這次用的是哪個家、從哪來的。"""
    if source == SOURCE_CWD:
        source = "目前資料夾（沒給 --target%s）" % ("、也沒設 " + env_var if env_var else "")
    return "（%s＝%s，取自 %s）" % (label, path, source)


# ---- 門鈴（09-24 tick-gap；cpu.md §6.5）----
# cpu 家裡的 `wake` 是一個具名管道（FIFO）。cpu 閒著時不是單純睡 poll_ms，而是「睡 poll_ms 或有人按門鈴」；
# 放單的人（kernel 派工）放好單之後往裡面寫一個位元組，cpu 馬上醒來列 requests/。只是提早說一聲：
# 按不到（cpu 沒在跑、FIFO 不在、管道滿了）一律當沒事，cpu 照舊每 poll_ms 看一次。
WAKE = "wake"
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class Doorbell:
    """cpu 那一側：建（或沿用）FIFO，開讀端＋一個自己的寫端（沒有別的寫端時 select 才不會一直回 EOF）。"""

    def __init__(self, home):
        self.fds = None
        path = os.path.join(home, WAKE)
        try:
            try:
                os.mkfifo(path, 0o600)
            except FileExistsError:
                pass
            flags = os.O_NONBLOCK | os.O_CLOEXEC | _NOFOLLOW
            rfd = os.open(path, os.O_RDONLY | flags)
            try:
                if not stat.S_ISFIFO(os.fstat(rfd).st_mode):
                    raise OSError("%s 不是 FIFO" % path)
                wfd = os.open(path, os.O_WRONLY | flags)
            except OSError:
                os.close(rfd)
                raise
            self.fds = (rfd, wfd)
        except OSError as exc:
            sys.stderr.write("aos-cpu: NoDoorbell: 門鈴用不了，只靠輪詢：%s\n" % exc)

    def wait(self, seconds, also=None):
        """睡 seconds 秒或門鈴響；響了就把管道讀乾淨（幾聲都算一聲）。also：另一個可讀就醒的 fd（cpu 的控制 pipe，stop 不用等滿）。"""
        watch = ([] if self.fds is None else [self.fds[0]]) + ([] if also is None else [also])
        if not watch:
            time.sleep(seconds)
            return
        try:
            ready, _, _ = select.select(watch, [], [], seconds)
        except (OSError, ValueError):
            time.sleep(seconds)
            return
        if self.fds is not None and self.fds[0] in ready:
            try:
                while os.read(self.fds[0], 4096):
                    pass
            except OSError:
                pass

    def close(self):
        if self.fds is not None:
            for fd in self.fds:
                os.close(fd)
            self.fds = None


def ring(home):
    """放單的人那一側：往 cpu 家的門鈴寫一個位元組；回有沒有按到。
    沒有讀端（cpu 沒在跑，ENXIO）、不在、不是 FIFO、管道滿（EAGAIN，反正已經有人按過）都當沒事。"""
    try:
        fd = os.open(os.path.join(home, WAKE), os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC | _NOFOLLOW)
    except OSError:
        return False
    try:
        if not stat.S_ISFIFO(os.fstat(fd).st_mode):
            return False
        os.write(fd, b"\n")
        return True
    except OSError:
        return False
    finally:
        os.close(fd)
