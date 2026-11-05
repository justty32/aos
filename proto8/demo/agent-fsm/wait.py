# wait.py - wait 格：把 think 寫好的 $AOS_STACK/think/request.json 寄給 llm kernel、之後一拍一拍看回信到了沒（thinking 2026-11-04 think-as-function 03 § 1）。
# loop 照跑、不卡著等：每拍一下就退，ctl 的 pause／stop 每拍都看得到。
#   think/pending.txt 不在＝還沒寄：aos-post init think/reply（沒有才建）、aos-llm send --reply-to think/reply < request.json，
#     信件名稱寫進 pending.txt、退 10（下一拍再來看）。
#   在＝已寄：aos-llm recv think/reply <名>：沒到（10）＝退 10；到了（0）＝那則 assistant 接進 history.jsonl、刪 pending.txt、退 0（→ act）；
#     kernel 回錯（1）＝刪 pending.txt、aos-llm 的 stderr 原樣、退 1（P-20 停下等人；人重跑＝沒 pending、request.json 還在→重寄＝重試）。
#   寄之前看 request.json 的 endpoint 跟現在的 llm.json（範本那份 AOS_CD/llm.json 疊這隻的 $AOS_STACK/llm.json，疊法同 brain.py）
#     對不對得上：對不上＝退 11 回 think 重組（11-05 edge-agent：代號寫錯停下、人 aos-agent llm set／改或刪 llm.json 再起，
#     原本照舊的 request.json 重寄、又是同一個錯，要人手動把 stage.txt 寫成 think）。llm.json 讀不懂＝當 {}（brain 重組時會報 CfgBad）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝回信接進 history（→ act）；10＝還沒回（→ wait）；11＝腦設定改過、回 think 重組請求。
# 不看 queue：思考中來的信等答完回 idle 再收（使用者 11-04「等答完回 idle 再收」）。沒有自己的逾時（kernel 的 timeout_ms／priority.deadline 守）。
# 錯：stderr 一行「agent-fsm: 代號 原因」、退 1——StackMissing、RequestMissing（沒 pending 也沒 request.json：人改了 stack）、
#   SendFailed（aos-llm send 退非 0；它自己的 stderr 原樣在上面，例 LlmKernelMissing）、ReplyBad、PostFailed、WriteFailed。kernel 回的錯（aos-llm recv 退 1）原樣轉。
import json, os, subprocess, sys

NOT_YET = 10                                     # aos-llm recv：回信還沒到
REBUILD = 11                                     # 腦設定跟 request.json 對不上：回 think 重組


def die(code, reason):
    print("agent-fsm: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


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


stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "AOS_STACK is not set")
think = os.path.join(stack, "think")
request, pending, box = (os.path.join(think, n) for n in ("request.json", "pending.txt", "reply"))
history_path = os.path.join(stack, "history.jsonl")

try:
    with open(pending, encoding="utf-8") as f:
        name = f.read().strip()
except FileNotFoundError:
    name = None
except OSError as e:
    die("WriteFailed", "cannot read %s: %s" % (pending, e))

if not name:                                     # 還沒寄
    if not os.path.isfile(request):
        die("RequestMissing", "neither %s nor pending.txt exists (stack edited? write think into stage.txt and start again)" % request)
    cfg = read_obj(os.path.join(os.environ.get("AOS_CD") or ".", "llm.json"))
    cfg.update(read_obj(os.path.join(stack, "llm.json")))
    body = read_obj(request)
    if cfg.get("endpoint") != body.get("endpoint"):
        sys.exit(REBUILD)                        # 腦設定改過（多半是上次 kernel 回錯、人改了代號再起）：brain 重組再寄
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        r = run(["aos-post", "init", box])
        if r.returncode != 0:
            die("PostFailed", "aos-post init %s exited %d" % (box, r.returncode))
    with open(request, encoding="utf-8") as f:
        r = run(["aos-llm", "send", "--reply-to", box], stdin=f)
    name = r.stdout.strip()
    if r.returncode != 0 or not name:
        die("SendFailed", "aos-llm send exited %d" % r.returncode)
    write_atomic(pending, name + "\n")
    sys.exit(NOT_YET)

r = run(["aos-llm", "recv", box, name], stdin=subprocess.DEVNULL)
if r.returncode == NOT_YET:
    sys.exit(NOT_YET)
try:                                             # 回信收掉了（或 kernel 回錯）：這封了結，之後停下的話人重跑＝重寄
    os.remove(pending)
except FileNotFoundError:
    pass
if r.returncode != 0:                            # kernel 回錯：aos-llm 已在 stderr 說了
    sys.exit(1)
try:
    message = json.loads(r.stdout)
except ValueError as e:
    die("ReplyBad", "aos-llm recv did not print JSON: %s" % e)
if not isinstance(message, dict) or message.get("role") != "assistant":
    die("ReplyBad", "message in the reply is not an assistant message: %s" % r.stdout.strip()[:200])
try:
    with open(history_path, "a", encoding="utf-8") as f:   # 一次寫一整行，只附加（P-41）
        f.write(json.dumps(message, ensure_ascii=False) + "\n")
except OSError as e:
    die("WriteFailed", "cannot append to history.jsonl: %s" % e)
sys.exit(0)
