"""gate_lib - kernel_gate 工具與它兩支 hook 共用：站在哪、跑一輪、留著的信怎麼列、通知怎麼寄。純標準庫。"""
import json, os, subprocess, sys

HOOK = "kernel_gate"                    # agent 身上那支 on_clock hook 的名字；它的小格就是站的 stack
HERE = os.path.dirname(os.path.realpath(__file__))
KERNEL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "aos", "kernel")    # lib/aos/kernel（框架站）
STEP_S = 30
OFF_MSG = "the station was switched off before anyone decided"


class Failed(Exception):
    def __init__(self, code, why):
        super().__init__("%s %s" % (code, why))
        self.code, self.why = code, why


def cell_of(stack):
    return os.path.join(stack, "hooks", HOOK)


def run(argv, text=None, env=None):
    """回 (退出碼, stdout, stderr)；起不來或逾時丟 Failed。"""
    try:
        p = subprocess.run(argv, input=text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           timeout=STEP_S, env=env)
    except OSError as e:
        raise Failed("LaunchFailed", "cannot run %s (put it on PATH with proto8/install.sh): %s" % (argv[0], e)) from None
    except subprocess.TimeoutExpired:
        raise Failed("CommandFailed", "%s took over %d s" % (" ".join(argv[:2]), STEP_S)) from None
    return p.returncode, p.stdout, p.stderr


def handler_ref(name):
    """這包裡一支程式的路徑：在 $AOS_HOME 底下就寫成指示詞（整棵樹搬家後照通），否則絕對路徑。"""
    path = os.path.join(HERE, name)
    home = os.environ.get("AOS_HOME")
    if home:
        rel = os.path.relpath(path, os.path.realpath(home))
        if not rel.startswith(".."):
            return {"$env": "AOS_HOME", "$path": "/" + rel}
    return path


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, value):
    tmp = os.path.join(os.path.dirname(path), ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(value, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except OSError as e:
        raise Failed("WriteFailed", "cannot write %s: %s" % (path, e)) from None


def round_once(cell):
    """叫框架站做一輪（AOS_STACK＝站的 stack）。回 (退出碼, 它的 stderr)；stderr 也原樣放到自己的 stderr。"""
    code, _, err = run(["aos-exec", "--stack", cell, KERNEL, os.path.join(cell, "kernel.json")])
    sys.stderr.write(err)
    return code, err


def refusal(err, name):
    """站的 stderr 裡有沒有「這封被拒」那一行；有就回「代號 原因」。"""
    mark = "kernel: warning: letter %s refused: " % name
    for line in err.splitlines():
        if line.startswith(mark):
            return line[len(mark):]
    return None


def held(cell):
    """留著的信：[(信名, 列, 信)]；信讀不到的略過。body 被站的 before_verdict 改過就用改過的那份。"""
    window = read_json(os.path.join(cell, "hold.json"), {})
    rows = window.get("held") if isinstance(window, dict) else None
    found = []
    for row in rows if isinstance(rows, list) else []:
        name = row.get("letter") if isinstance(row, dict) else None
        if not isinstance(name, str):
            continue
        letter = read_json(os.path.join(cell, "requests", "cur", name, "letter.json"))
        if not isinstance(letter, dict):
            continue
        changed = os.path.join(cell, "bodies", name + ".json")
        if os.path.exists(changed):
            letter["body"] = read_json(changed, letter.get("body"))
        found.append((name, row, letter))
    return found


def is_request_key(key):
    return key.startswith("procs_") or key in ("queue_wait_ms", "ping")


def lines(name, row, letter, now_ms):
    """一封留著的信：機器讀到的事實各一行，寄件人自己多寫的鍵原樣一行。"""
    body = letter.get("body")
    request = {k: v for k, v in body.items() if is_request_key(k) and k != "queue_wait_ms"} if isinstance(body, dict) else body
    extra = {k: v for k, v in body.items() if not is_request_key(k)} if isinstance(body, dict) else {}
    wait = body.get("queue_wait_ms") if isinstance(body, dict) else None
    deadline = "none (it stays held until you decide)"
    if isinstance(wait, int) and not isinstance(wait, bool) and wait > 0:
        left = None
        try:
            import datetime
            sent = datetime.datetime.fromisoformat(str(letter.get("sent_at")).replace("Z", "+00:00"))
            left = int((sent.timestamp() * 1000 + wait - now_ms) / 1000)
        except (ValueError, TypeError, OverflowError):
            pass
        deadline = ("the sender waits %d more seconds, then the station refuses it for you" % max(left, 0)
                    if left is not None else "queue_wait_ms %d" % wait)
    return ["- letter %s" % name,
            "    from: %s" % letter.get("sender"),
            "    request: %s" % json.dumps(request, ensure_ascii=False),
            "    deadline: %s" % deadline,
            "    other keys the sender wrote (nobody checked them): %s" % (json.dumps(extra, ensure_ascii=False) if extra else "(none)")]


def notice(rows, now_ms):
    n = len(rows)
    out = ["[aos] kernel_hold: %d request%s held at your kernel station and wait%s for your decision."
           % (n, "" if n == 1 else "s", "s" if n == 1 else "")]
    for name, row, letter in rows:
        out += lines(name, row, letter, now_ms)
    out.append('Decide each one: kernel_gate {"op": "pass", "letter": "<letter>"} or kernel_gate {"op": "refuse", '
               '"letter": "<letter>", "reason": "<one line for the sender>"}. The station forwards what you pass.')
    return "\n".join(out)


def decide(cell, name, verdict, reason=None):
    folder = os.path.join(cell, "decisions")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as e:
        raise Failed("WriteFailed", "cannot create %s: %s" % (folder, e)) from None
    said = {"verdict": verdict}
    if verdict == "refuse":
        said["error"] = {"code": "HoldRefused", "msg": reason}
    write_json(os.path.join(folder, name + ".json"), said)
