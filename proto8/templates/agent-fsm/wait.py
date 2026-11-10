# wait.py - wait 格：寄請求、逐拍收 llm kernel 回信；未寄且 request.json 不在時回 think 重建，另記思考成本觀測。
# loop 照跑、不卡著等：每拍一下就退，ctl 的 pause／stop 每拍都看得到。
#   think/pending.txt 不在＝還沒寄：aos-post init think/reply（沒有才建）、aos-llm send --reply-to think/reply < request.json，
#     request.json 不在＝退 11 回 think，從 history＋定義重組；在才寄、信件名稱寫進 pending.txt、退 10（下一拍再來看）。
#   在＝已寄：aos-llm recv think/reply <名>：沒到（10）＝退 10；到了（0）＝那則 assistant 接進 history.jsonl、刪 pending.txt、退 0（→ act）；
#     kernel 回錯（1）＝刪 pending.txt、aos-llm 的 stderr 原樣、這格再多寫自己一行 BrainFailed、退 1（P-20 停下等人；人重跑＝沒 pending、request.json 還在→重寄＝重試）。
#   寄之前看 request.json 的 endpoint 跟現在的 llm.json（interfaces.json 宣告的定義檔疊這隻的 stack 同相對路徑檔，疊法同 brain.py）
#     對不對得上：對不上＝退 11 回 think 重組（11-05 edge-agent：代號寫錯停下、人 aos-agent llm set／改或刪 llm.json 再起，
#     原本照舊的 request.json 重寄、又是同一個錯，要人手動把 stage.txt 寫成 think）。llm.json 讀不懂＝當 {}（brain 重組時會報 CfgBad）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝回信接進 history（→ act）；10＝還沒回（→ wait）；11＝請求不在或腦設定改過、回 think 重組請求。
# 不看 queue：思考中來的信等答完回 idle 再收（使用者 11-04「等答完回 idle 再收」）。沒有自己的逾時（kernel 的 timeout_ms／priority.deadline 守）。
#   等太久只提醒（11-10 坑-74 選項 A）：寄出（pending.txt 的 mtime）滿 10 分鐘印一行 warning、之後每滿 10 分鐘再一行，照樣退 10 繼續等；
#   印到第幾個 10 分鐘記在 think/wait_warned.txt（一個整數；寄新信與收掉回信時刪），每拍是新行程也不重複印。
# 錯：stderr 一行「agent-fsm: error: 代號 原因」、退 1——StackMissing、BrainFailed（kernel 回錯）、
#   SendFailed（aos-llm send 退非 0；它自己的 stderr 原樣在上面，例 LlmKernelMissing）、ReplyBad、PostFailed、WriteFailed。下層的 stderr 一律不攔（stdio-unify R10）。
# --help 印英文用法；Ctrl-C 退 130。
import json, os, signal, subprocess, sys, time
from pathlib import Path

_import_paths = [str(Path(__file__).resolve().parent)]
for _parent in Path(__file__).resolve().parents:
    for _layer, _module in (("py", "aos_flags.py"), ("lib", "agent/agent_files.py")):
        _root = _parent / _layer
        if (_root / _module).is_file() and str(_root) not in _import_paths:
            _import_paths.append(str(_root))
sys.path[:0] = _import_paths
try:
    import aos_flags  # noqa: E402
    from observed import append as append_observed  # noqa: E402
    if (Path(__file__).resolve().parent / "agent_files.py").is_file():
        from agent_files import declared_files  # noqa: E402
    else:
        from agent.agent_files import declared_files  # noqa: E402
except ModuleNotFoundError as _error:
    if _error.name not in ("aos_flags", "tool_io", "agent_files", "agent", "agent.agent_files", "observed", "observed_children"):
        raise
    print("agent-fsm: error: ModuleMissing required Python module %s is unavailable" % _error.name,
          file=sys.stderr)
    sys.exit(1)
finally:
    for _path in _import_paths:
        sys.path.remove(_path)


HELP = """\
usage: wait.py   (a cell of templates/agent-fsm; run by its fsm.json under aos-fsm, needs $AOS_STACK)
The wait cell: send $AOS_STACK/think/request.json to the llm kernel (aos-llm send), then on
each later run look for the reply (aos-llm recv). Exit 0 = reply appended to history (go act);
10 = not yet; 11 = no pending request and request.json is missing, or brain settings changed;
go back to think to rebuild. A pending request is received even without request.json.
Waiting never times out here: after every full 10 minutes without a reply (counted from
think/pending.txt) one warning line goes to stderr, and the cell keeps waiting.
Append think letter, endpoint, model, usage and elapsed_ms to observed.jsonl (best effort).
On error: one line "agent-fsm: error: CODE reason" on stderr, exit 1.
"""
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）

NOT_YET = 10                                     # aos-llm recv：回信還沒到
WARN_EVERY_S = 600                               # 等回信每滿 10 分鐘提醒一次（坑-74）
REBUILD = 11                                     # 請求不在或腦設定對不上：回 think 重組


def die(code, reason):
    aos_flags.die("agent-fsm", code, reason)


def write_atomic(path, text):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05：先寫暫存再改名
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        die("WriteFailed", "cannot write %s: %s" % (path, e))


def read_obj(path):
    """一層 JSON 物件；不在、讀不懂、不是物件＝{}。"""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def run(argv, **kw):
    try:
        return subprocess.run(argv, stdout=subprocess.PIPE, text=True, **kw)   # stderr 不吞：下層自己說原因
    except OSError as e:
        die("SendFailed", "%s cannot start (must be on PATH): %s" % (argv[0], e))


try:
    opts, rest = aos_flags.parse(sys.argv[1:], {}, help=HELP)
except aos_flags.Error as e:
    die(e.code, e)
if rest:
    die("ArgumentsBad", "unexpected argument %s (usage: wait.py)" % rest[0])

stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "AOS_STACK is not set")
think = os.path.join(stack, "think")
request, pending, box = (os.path.join(think, n) for n in ("request.json", "pending.txt", "reply"))
history_path = os.path.join(stack, "history.jsonl")
sent_path = os.path.join(think, "sent.json")
warned_path = os.path.join(think, "wait_warned.txt")


def forget_warned():
    try:
        os.remove(warned_path)
    except FileNotFoundError:
        pass
    except OSError as e:
        aos_flags.warn("agent-fsm", "cannot remove %s: %s" % (warned_path, e))


def warn_if_slow(letter):
    """Warn once per full 10 minutes since the letter was sent; never fails the cell."""
    try:
        waited_s = time.time() - os.stat(pending).st_mtime
    except OSError:
        return
    step = int(waited_s // WARN_EVERY_S)
    if step < 1:
        return
    try:
        with open(warned_path, encoding="utf-8") as f:
            done = int(f.read().strip() or "0")
    except (OSError, ValueError):
        done = 0
    if step <= done:
        return
    tmp = os.path.join(think, ".wait_warned.txt.%d.tmp" % os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("%d\n" % step)
        os.replace(tmp, warned_path)
    except OSError:
        return                                   # 記不下來就不提醒，免得每拍都印
    aos_flags.warn("agent-fsm", "no reply from the brain for %d minutes to letter %s (llm kernel: %s); still waiting"
                   % (waited_s // 60, letter, os.environ.get("AOS_LLM_KERNEL") or "AOS_LLM_KERNEL not set"))

try:
    with open(pending, encoding="utf-8") as f:
        name = f.read().strip()
except FileNotFoundError:
    name = None
except OSError as e:
    die("WriteFailed", "cannot read %s: %s" % (pending, e))

try:
    files = declared_files(os.environ.get("AOS_CD") or ".")
except ValueError as e:
    die("InterfaceBad", str(e))
if not name:                                     # 還沒寄
    if not os.path.isfile(request):
        sys.exit(REBUILD)                        # image 不存可重建的請求；有 pending 時仍先收原回信，不能重寄
    cfg = read_obj(os.path.join(os.environ.get("AOS_CD") or ".", files["llm"])) if "llm" in files else {}
    if "llm" in files:
        cfg.update(read_obj(os.path.join(stack, files["llm"])))
    body = read_obj(request)
    if cfg.get("endpoint") != body.get("endpoint"):
        sys.exit(REBUILD)                        # 腦設定改過（多半是上次 kernel 回錯、人改了代號再起）：brain 重組再寄
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        r = run(["aos-post", "init", box])
        if r.returncode != 0:
            die("PostFailed", "aos-post init %s exited %d" % (box, r.returncode))
    try:
        with open(sent_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"started_ns": time.time_ns(), "endpoint": body.get("endpoint")}) + "\n")
    except OSError as e:
        aos_flags.warn("agent-fsm", "cannot write think timing: %s" % e)
    with open(request, encoding="utf-8") as f:
        r = run(["aos-llm", "send", "--reply-to", box], stdin=f)
    name = r.stdout.strip()
    if r.returncode != 0 or not name:
        die("SendFailed", "aos-llm send exited %d" % r.returncode)
    forget_warned()                              # 新的一封：提醒從頭算
    write_atomic(pending, name + "\n")
    sys.exit(NOT_YET)

r = run(["aos-llm", "recv", "--full", box, name], stdin=subprocess.DEVNULL)
if r.returncode == NOT_YET:
    warn_if_slow(name)
    sys.exit(NOT_YET)
try:                                             # 回信收掉了（或 kernel 回錯）：這封了結，之後停下的話人重跑＝重寄
    os.remove(pending)
except FileNotFoundError:
    pass
forget_warned()
received_ns = time.time_ns()
elapsed_ms = None
sent_endpoint = None
try:
    with open(sent_path, encoding="utf-8") as f:
        sent = json.load(f)
        sent_endpoint = sent.get("endpoint")
        started_ns = sent["started_ns"]
        if not isinstance(started_ns, int) or isinstance(started_ns, bool):
            raise ValueError("started_ns must be an integer")
        elapsed_ms = max(0, (received_ns - started_ns) / 1_000_000)
except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
    aos_flags.warn("agent-fsm", "cannot read think timing: %s" % e)


def observe(reply):
    append_observed(stack, {"kind": "think",
                            "letter": name,
                            "endpoint": reply.get("endpoint", sent_endpoint),
                            "model": reply.get("model"), "usage": reply.get("usage"),
                            "elapsed_ms": elapsed_ms})


if r.returncode != 0:                            # kernel 回錯：aos-llm 已在 stderr 說了，這格只多寫自己一行
    observe({})
    die("BrainFailed", "aos-llm recv exited %d (its reason is above)" % r.returncode)
try:
    reply = json.loads(r.stdout)
    message = reply.get("message") if isinstance(reply, dict) else None
except ValueError as e:
    die("ReplyBad", "aos-llm recv did not print JSON: %s" % e)
if not isinstance(message, dict) or message.get("role") != "assistant":
    die("ReplyBad", "message in the reply is not an assistant message: %s" % r.stdout.strip()[:200])
observe(reply)
try:
    with open(history_path, "a", encoding="utf-8") as f:   # 一次寫一整行，只附加（P-41）
        f.write(json.dumps(message, ensure_ascii=False) + "\n")
except OSError as e:
    die("WriteFailed", "cannot append to history.jsonl: %s" % e)
sys.exit(0)
