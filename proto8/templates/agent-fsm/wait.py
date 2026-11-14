# wait.py - wait 格：寄請求、逐拍收 llm kernel 回信；未寄且 request.json 不在時回 think 重建，另記思考成本觀測。
# loop 照跑、不卡著等：每拍一下就退，ctl 的 pause／stop 每拍都看得到。
#   think/pending.txt 不在＝還沒寄：aos-post init think/reply（沒有才建）、aos-llm send --reply-to think/reply < request.json，
#     request.json 不在＝退 11 回 think，從 history＋定義重組；在才寄、信件名稱寫進 pending.txt、退 10（下一拍再來看）。
#   在＝已寄：think/reply 缺 tmp／new／cur 任一＝先 aos-post init（11-10 TS：clone 後空的 reply 夾不在 git，recv 會 MailboxMissing）；
#     aos-llm recv --quiet think/reply <名>：沒到（10）＝退 10；到了（0）＝那則 assistant 接進 history.jsonl、刪 pending.txt、退 0（→ act）；
#     kernel 回錯（1）＝刪 pending.txt、aos-llm 的 stderr 原樣、這格再多寫自己一行 BrainFailed、退 1（P-20 停下等人；人重跑＝沒 pending、request.json 還在→重寄＝重試）。
#   寄之前看 request.json 的 endpoint 與調整鍵跟現在的 llm.json（model 對 endpoint、調整鍵對 request 同名鍵，llm_settings.py）（interfaces.json 宣告的定義檔疊這隻的 stack 同相對路徑檔，疊法同 brain.py）
#     對不對得上：對不上＝退 11 回 think 重組（11-05 edge-agent：代號寫錯停下、人 aos-agent llm set／改或刪 llm.json 再起，
#     原本照舊的 request.json 重寄、又是同一個錯，要人手動把 stage.txt 寫成 think）。llm.json 讀不懂＝當 {}（brain 重組時會報 CfgBad）。
#   寄之前也看 request.json 是不是從現在的 history 組的（11-10 TS，I2 L01：git reset／clone 後，這台舊的 request.json 會擺在新的 history 旁邊）：
#     messages 最後一則跟 history.jsonl 最後一則（都 JSON 正規化：sort_keys）不一樣＝退 11 回 think 重組、不寄；history 空、request 沒 messages＝不比。
#     history.jsonl 比 request.json 新（mtime）也算（11-10 晚 self-family：aos-agent history／self_history 改了中間幾行、最後一則沒變）。
#     已寄出的不追：回信照收、接在改過的 history 後面（那封是照舊的 history 答的；使用者「風險自己擔」）。
# 信不見了（11-10 TS，I3 C2）：recv 回 10、而 $AOS_LLM_KERNEL（解法同 aos-llm：相對＝從 $AOS_DAEMON 算，沒有＝cwd）解得到資料夾時，
#   看 <kernel>/requests/{new,cur}/<名>（只讀不寫）；兩處都沒有＝再 recv 一次（kernel 先寄回信才刪 cur，這次不會誤判）；
#   還是 10＝刪 pending.txt、印一行 warning、退 10（下一拍 request.json 在就重寄，不在就退 11 回 think 重組）。
#   AOS_LLM_KERNEL 沒設或解不到資料夾＝不判斷、照舊等。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝回信接進 history（→ act）；10＝還沒回（→ wait）；11＝請求不在、腦設定改過或請求比 history 舊，回 think 重組請求。
# 不看 queue：思考中來的信等答完回 idle 再收（使用者 11-04「等答完回 idle 再收」）。沒有自己的逾時（kernel 的 timeout_ms／priority.deadline 守）。
#   等太久只提醒（11-10 坑-74 選項 A）：寄出（pending.txt 的 mtime）滿 10 分鐘印一行 warning（說信在 kernel 的哪一格，11-10 晚 B10）、之後每滿 10 分鐘再一行，照樣退 10 繼續等；
#   印到第幾個 10 分鐘記在 think/wait_warned.txt（一個整數；寄新信與收掉回信時刪），每拍是新行程也不重複印。
#   平常每拍帶 recv --quiet（不印「為什麼還沒回」那行，免得每 300 ms 一行刷屏，I3 C1）；只有要印 10 分鐘提醒的那一拍不帶，
#   讓 aos-llm 自己把原因印在這格那行前面（不讀它的 stderr）。
# 失敗後冷卻（two-machines 06，使用者 11-10 裁「失敗後冷卻」）：BrainFailed、SendFailed（send 退非 0）是外面服務的錯，
#   先用 lib/agent/cooldown.py 記一筆 $AOS_STACK/cooldown.json（30 秒起、加倍到 30 分鐘；dropped 一直是 0——重寄同一份請求、不掉信）；
#   寫不成只 warning 一行、不改原本的結果。寄之前（沒 pending、request.json 在、endpoint 對得上）冷卻中＝不寄、退 10 留在 wait；
#   冷卻到了（due）或沒有＝照寄。好的回信接進 history 之後刪 cooldown.json（刪不掉＝warning）。ReplyBad、WriteFailed 等不寫冷卻。
#   BrainFailed（kernel 收了、回了錯＝端點本身壞）：照舊退 1；開了 auto_restart 的列：退 1 → daemon 重起 → 在 wait 冷卻裡活過 3 秒，
#     不會被三次判停；沒開的照舊停著等人。
#   SendFailed（11-10 TS，I3 C4；使用者「如果llms那邊我沒開aos daemon，那就是我自己的問題，但我也希望他不要搞壞」）：
#     記冷卻、印一行 warning（不是 error）、退 10 留在 wait，冷卻到了再寄——有沒有 --auto-restart 都不會停。
#     **改了 P-20 在這個情況的行為：kernel 不在＝等它來，不停下。** 記冷卻時 kernel 資料夾解不到，reason 尾巴多寫
#     「(llm kernel folder not found)」；之後冷卻中而 AOS_LLM_KERNEL 已解得到資料夾＝當作到了、立刻寄（I3 C3：不用等滿 30 分鐘）。
#     kernel 資料夾在、send 還是失敗（例 body 壞）＝照冷卻間隔重試，不每拍刷屏。
#   11-14：正要寄時 AOS_LLM_KERNEL 沒設或去空白後為空＝先 brain_failed，再 LlmKernelMissing 退 1、不記冷卻，request.json 留著；環境不會自己補上，要重掛。
# 錯：stderr 一行「agent-fsm: error: 代號 原因」、退 1——StackMissing、BrainFailed（kernel 回錯）、
#   LlmKernelMissing（寄之前 AOS_LLM_KERNEL 沒設或空白）、SendFailed（aos-llm 起不來、或 send 退 0 卻沒印信件名稱）、ReplyBad、PostFailed、WriteFailed。下層的 stderr 一律不攔（stdio-unify R10）。
# hook（lib/agent/hooks.py，圖紙 thinking/2026-11/10/self-family/hook）：BrainFailed、SendFailed（send 退非 0、或退 0 沒印信名）、ReplyBad
#   照原本行為退出／記冷卻之前觸發 brain_failed（name＝代號、reason＝這格那行的原因）；hook 停下＝HookFailed／HooksBad 退 1（冷卻不記）。
# --help 印英文用法；Ctrl-C 退 130。
# on_clock（11-11 thinking/2026-11/11/clock-hook）：這格一開頭先 hooks.clock_tick（經 cell_common.clock_tick）——時鐘走到了的 on_clock hook 才跑（handler 預設什麼都不做、history 不多東西）；沒有這種 hook＝只讀清單。
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
    if (Path(__file__).resolve().parent / "cooldown.py").is_file():
        import cooldown  # noqa: E402
    else:
        from agent import cooldown  # noqa: E402
    if (Path(__file__).resolve().parent / "hooks.py").is_file():
        import hooks  # noqa: E402
    else:
        from agent import hooks  # noqa: E402
except (ModuleNotFoundError, ImportError) as _error:
    if _error.name not in ("aos_flags", "tool_io", "agent_files", "agent", "agent.agent_files", "observed", "observed_children",
                           "cooldown", "agent.cooldown", "hooks", "agent.hooks"):
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
10 = not yet; 11 = no pending request and request.json is missing, brain settings changed,
or request.json was built from an older history (its last message is not the last line of
history.jsonl, or history.jsonl is newer than it); go back to think to rebuild. A pending request is received even without
request.json; a missing think/reply mailbox is created first (aos-post init).
Waiting never times out here: after every full 10 minutes without a reply (counted from
think/pending.txt) one warning line goes to stderr, and the cell keeps waiting. Other ticks
call aos-llm recv --quiet; the warning tick does not, so aos-llm prints why there is no reply.
Lost letter: when aos-llm recv says "not yet" and $AOS_LLM_KERNEL resolves to a folder
(relative to $AOS_DAEMON, else the current folder) but the letter is in neither
requests/new/ nor requests/cur/ there, the cell receives once more; still nothing = it
forgets the letter (deletes think/pending.txt), prints one warning and sends again next tick.
Append think letter, endpoint, model, usage and elapsed_ms to observed.jsonl (best effort).
Cooldown after a failure of the outside service, recorded in $AOS_STACK/cooldown.json
(30 s, then 1, 2, 4, 8, 15, 30 minutes, then every 30 minutes):
  SendFailed (aos-llm send exited nonzero, e.g. the llm kernel folder is missing): one
    warning line, exit 10 and stay in wait; the agent does not stop. This changes P-20 for
    this case: no llm kernel yet = wait for it, do not stop.
  BrainFailed (the kernel replied with an error): exit 1 as before.
  LlmKernelMissing (AOS_LLM_KERNEL unset or blank before sending): run brain_failed, exit 1
    without cooldown, keep request.json; add the agent again with the variable.
While that cooldown runs, a request about to be sent is held back (exit 10, stay in wait);
once it is due the same request is sent again. A SendFailed cooldown recorded while the
kernel folder was missing counts as due as soon as $AOS_LLM_KERNEL resolves to a folder.
A good reply deletes cooldown.json.
Hooks: brain_failed runs on LlmKernelMissing, BrainFailed, SendFailed and ReplyBad before the cell goes on as
above (name = that code, reason = this cell's reason). A failing hook = HookFailed, exit 1.
On error: one line "agent-fsm: error: CODE reason" on stderr, exit 1 (including LlmKernelMissing).
"""
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）

NOT_YET = 10                                     # aos-llm recv：回信還沒到
WARN_EVERY_S = 600                               # 等回信每滿 10 分鐘提醒一次（坑-74）
REBUILD = 11                                     # 請求不在或腦設定對不上：回 think 重組


def die(code, reason):
    aos_flags.die("agent-fsm", code, reason)


sys.dont_write_bytecode = True                   # 定義資料夾不留 __pycache__（P-15）
from atomic_file import write_atomic  # noqa: E402  （範本資料夾在 sys.path 最前面）
import cell_common  # noqa: E402


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
cell_common.clock_tick(hooks, stack, lambda line: aos_flags.warn("agent-fsm", line), die)   # 11-11 on_clock：每格開頭看一次時鐘，到了才起 handler
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


def brain_failed(code, reason):
    """問腦沒成：先跑 brain_failed hook（match 比代號）；hook 停下＝這格的錯、退 1。之後呼叫的人照原本行為。"""
    try:
        hooks.fire("brain_failed", {"name": code, "reason": reason}, os.environ.get("AOS_CD") or ".", stack,
                   warn=lambda line: aos_flags.warn("agent-fsm", line))
    except (hooks.HookFailed, hooks.HooksBad) as e:
        die(type(e).__name__, str(e))


def record_failure(code, reason):
    """外面服務的錯：記一筆冷卻（dropped 0）；寫不成只提醒，呼叫的人照舊 die。"""
    try:
        cooldown.fail(stack, code, reason)
    except OSError as e:
        aos_flags.warn("agent-fsm", "cannot write %s: %s" % (cooldown.path(stack), e))


def slow_step():
    """這一拍要不要印 10 分鐘提醒：要＝回第幾個 10 分鐘（整數），不要＝None。只看、不記。"""
    try:
        waited_s = time.time() - os.stat(pending).st_mtime
    except OSError:
        return None
    step = int(waited_s // WARN_EVERY_S)
    if step < 1:
        return None
    try:
        with open(warned_path, encoding="utf-8") as f:
            done = int(f.read().strip() or "0")
    except (OSError, ValueError):
        done = 0
    return step if step > done else None


def warn_slow(letter, step):
    """Warn once per full 10 minutes since the letter was sent; never fails the cell."""
    tmp = os.path.join(think, ".wait_warned.txt.%d.tmp" % os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("%d\n" % step)
        os.replace(tmp, warned_path)
    except OSError:
        return                                   # 記不下來就不提醒，免得每拍都印
    try:
        waited_s = time.time() - os.stat(pending).st_mtime
    except OSError:
        waited_s = step * WARN_EVERY_S
    aos_flags.warn("agent-fsm", "no reply from the brain for %d minutes to letter %s: %s; still waiting"
                   % (waited_s // 60, letter, slow_reason(letter)))


def slow_reason(letter):
    """10 分鐘提醒的原因（11-10 晚 two-machines B10）：信在 kernel 的哪一格。kernel 沒在跑由 aos-llm recv 那行說。"""
    k = os.environ.get("AOS_LLM_KERNEL")
    if not k:
        return "AOS_LLM_KERNEL is not set, so this cell cannot tell where the letter is"
    kernel = kernel_dir()
    if kernel is None:
        return "AOS_LLM_KERNEL (%s) is not a folder" % k
    kernel = os.path.abspath(kernel)
    if os.path.exists(os.path.join(kernel, "requests", "new", letter)):
        return ("it is still queued at the llm kernel %s and not started yet (the kernel is not running, all slots are busy, "
                "or a budget with spent: wait is used up)" % kernel)
    if os.path.exists(os.path.join(kernel, "requests", "cur", letter)):
        return "the llm kernel %s is running it; the brain call itself is slow (see %s)" % (
            kernel, os.path.join(kernel, "requests", "cur", letter, "stderr.txt"))
    return "the letter is no longer at the llm kernel %s; the reply may be on its way" % kernel


def kernel_dir():
    """$AOS_LLM_KERNEL 解成資料夾（同 aos-llm：相對＝從 $AOS_DAEMON 算，沒有＝cwd）；沒設或不是資料夾＝None。"""
    k = os.environ.get("AOS_LLM_KERNEL")
    if not k:
        return None
    d = os.environ.get("AOS_DAEMON")
    if not os.path.isabs(k) and d:
        k = os.path.join(d, k)
    return k if os.path.isdir(k) else None


KERNEL_GONE = "(llm kernel folder not found)"    # SendFailed 時 kernel 資料夾解不到：記進冷卻的 reason，之後看它在不在


def stale_request(body):
    """request.json 是不是從比較舊的 history 組的：messages 最後一則≠history.jsonl 最後一則（JSON 正規化後比）。
    history 空或讀不懂、request 沒 messages＝不比（False）。"""
    messages = body.get("request", {}).get("messages") if isinstance(body.get("request"), dict) else None
    if not isinstance(messages, list) or not messages:
        return False
    last = None
    try:
        with open(history_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = line
    except OSError:
        return False
    if last is None:
        return False
    try:
        last = json.loads(last)
    except ValueError:
        return False                             # history 壞了交給 brain 報 HistoryBad
    norm = lambda m: json.dumps(m, sort_keys=True, ensure_ascii=False)
    if norm(messages[-1]) != norm(last):
        return True
    try:                                         # 最後一則一樣、但 history 在請求之後被改過（aos-agent history 改了中間幾行；11-10 晚 self-family）
        return os.stat(history_path).st_mtime_ns > os.stat(request).st_mtime_ns
    except OSError:
        return False


def recv(quiet=True):
    return run(["aos-llm", "recv", "--full"] + (["--quiet"] if quiet else []) + [box, name], stdin=subprocess.DEVNULL)


def ensure_box():
    """回信箱缺 tmp／new／cur 任一＝aos-post init（沒有才建）。"""
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        r = run(["aos-post", "init", box])
        if r.returncode != 0:
            die("PostFailed", "aos-post init %s exited %d" % (box, r.returncode))


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
    sys.dont_write_bytecode = True               # 定義資料夾不留 __pycache__（P-15）
    import llm_settings  # noqa: E402  （範本資料夾在 sys.path 最前面）
    try:
        model, tuning = llm_settings.body_fields(cfg)
    except ValueError:
        sys.exit(REBUILD)                        # 設定壞了：交給 brain 報 CfgBad
    sent_req = body.get("request") if isinstance(body.get("request"), dict) else {}
    if model != body.get("endpoint") or tuning != {k: sent_req[k] for k in llm_settings.TUNING if k in sent_req}:
        sys.exit(REBUILD)                        # 腦設定改過（多半是上次 kernel 回錯、人改了代號再起）：brain 重組再寄
    if stale_request(body):
        sys.exit(REBUILD)                        # 請求比 history 舊（reset／clone 後留下的）：brain 重組再寄
    if not os.environ.get("AOS_LLM_KERNEL", "").strip():
        reason = ('AOS_LLM_KERNEL is not set, so this agent has no brain; add it again with the variable, e.g. subagent add '
                  'envs {"AOS_LLM_KERNEL": "<llm kernel stack>"} or aos-agent ctl add --envs AOS_LLM_KERNEL=<stack>, '
                  "or set it in the daemon's .env")
        brain_failed("LlmKernelMissing", reason)
        die("LlmKernelMissing", reason)
    phase, rec = cooldown.state(stack)
    if phase == "cooling" and not (rec.get("code") == "SendFailed" and KERNEL_GONE in str(rec.get("reason"))
                                   and kernel_dir()):
        sys.exit(NOT_YET)                        # 冷卻中：不寄、留在 wait；到了（due）或 kernel 剛出現才重寄同一份
    ensure_box()
    try:
        with open(sent_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"started_ns": time.time_ns(), "endpoint": body.get("endpoint")}) + "\n")
    except OSError as e:
        aos_flags.warn("agent-fsm", "cannot write think timing: %s" % e)
    with open(request, encoding="utf-8") as f:
        r = run(["aos-llm", "send", "--reply-to", box], stdin=f)
    name = r.stdout.strip()
    if r.returncode != 0:                        # kernel 不在等：記冷卻、warning、留在 wait（不停下，改了 P-20 這一處）
        gone = kernel_dir() is None
        reason = "aos-llm send exited %d" % r.returncode + (" " + KERNEL_GONE if gone else "")
        brain_failed("SendFailed", reason)
        record_failure("SendFailed", reason)
        aos_flags.warn("agent-fsm", "aos-llm send exited %d (its reason is above); the request stays and is sent again "
                       "%s" % (r.returncode, "once AOS_LLM_KERNEL is a folder or the cooldown ends" if gone
                               else "when the cooldown ends"))
        sys.exit(NOT_YET)
    if not name:
        brain_failed("SendFailed", "aos-llm send exited 0 but printed no letter name")
        die("SendFailed", "aos-llm send exited 0 but printed no letter name")
    forget_warned()                              # 新的一封：提醒從頭算
    write_atomic(pending, name + "\n", die)
    sys.exit(NOT_YET)

ensure_box()                                     # clone 後空的 think/reply 不在 git：recv 前補（TG 實跑抓到的 MailboxMissing）
step = slow_step()
r = recv(quiet=step is None)                     # 要提醒的那一拍不帶 --quiet：aos-llm 自己印原因
if r.returncode == NOT_YET:
    kernel = kernel_dir()
    if kernel and not any(os.path.exists(os.path.join(kernel, "requests", q, name)) for q in ("new", "cur")):
        r = recv()                               # kernel 先寄回信才刪 cur：再收一次就分得出「剛答完」
        if r.returncode == NOT_YET:
            try:
                os.remove(pending)
            except FileNotFoundError:
                pass
            except OSError as e:
                die("WriteFailed", "cannot remove %s: %s" % (pending, e))
            forget_warned()
            aos_flags.warn("agent-fsm", "the letter %s is no longer queued at the llm kernel %s; sending the request again"
                           % (name, kernel))
            sys.exit(NOT_YET)
    if r.returncode == NOT_YET:
        if step is not None:
            warn_slow(name, step)
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
    brain_failed("BrainFailed", "aos-llm recv exited %d (its reason is above)" % r.returncode)
    record_failure("BrainFailed", "aos-llm recv exited %d" % r.returncode)
    die("BrainFailed", "aos-llm recv exited %d (its reason is above)" % r.returncode)
try:
    reply = json.loads(r.stdout)
    message = reply.get("message") if isinstance(reply, dict) else None
except ValueError as e:
    brain_failed("ReplyBad", "aos-llm recv did not print JSON: %s" % e)
    die("ReplyBad", "aos-llm recv did not print JSON: %s" % e)
if not isinstance(message, dict) or message.get("role") != "assistant":
    brain_failed("ReplyBad", "message in the reply is not an assistant message: %s" % r.stdout.strip()[:200])
    die("ReplyBad", "message in the reply is not an assistant message: %s" % r.stdout.strip()[:200])
observe(reply)
try:
    with open(history_path, "a", encoding="utf-8") as f:   # 一次寫一整行，只附加（P-41）
        f.write(json.dumps(message, ensure_ascii=False) + "\n")
except OSError as e:
    die("WriteFailed", "cannot append to history.jsonl: %s" % e)
try:                                             # 好的回信：冷卻歸零
    cooldown.clear(stack)
except OSError as e:
    aos_flags.warn("agent-fsm", "cannot remove %s: %s" % (cooldown.path(stack), e))
sys.exit(0)
