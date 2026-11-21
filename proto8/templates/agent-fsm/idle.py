# idle.py [--prompt FILE] - idle 格（收信）：$AOS_STACK/queue/ 的信全部收進 $AOS_STACK/history.jsonl，接進去就收掉（aos-post done）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝收到至少一封好信、或丟了 goal 提醒（→ think）；10＝沒信（表上接住＝停著等，改成字串 next＝收工）。
# 一次收全部、照處理順序（有序在前照名字＝寄的順序、無序在後照名字；同 aos_ws.letter_key）；cur/ 有上次認領了還沒接完的先接（P-12）。
# 壞信（body 不是 {"role": "user", "content": 非空字串}）：aos-post done 丟掉、$AOS_STACK/mailbox_warning.txt 覆寫一行（N-16；同 aos-eca-turn）。
# 回答配對（thinking/2026-11/14/reply-match-1114/03 §1）：好信照序 aos_ws.letters_take（加進 $AOS_STACK/letters.json 的 pending）→ history 的 user 列帶
#   "aos": {"letter": 信名}（信裡自帶的 aos 鍵蓋掉）→ done；壞信、被 before_queue 擋的信在 done 之前記進 dropped（reason bad／blocked）。goal 提醒不經 queue、不帶 aos。
# --prompt FILE＝開場白（相對路徑從範本資料夾＝AOS_CD 算）：history 空、queue 也沒好信時投一次進 queue 再收；沒給＝沒有開場白。
# hook（圖紙 thinking/2026-11/10/self-family/hook；經 py/aos/agentlib/agent_hooks.py 的遙控器 H，11-20 hook 介面第 2 刀）：好信接進 history 之前
#   before_queue（H.take_letter：可改 content；攔下＝aos-post done 丟掉、不進 history、不算好信、mailbox_warning.txt 寫一行是哪個 hook 丟的），
#   接進去並 done 之後 after_queue。hook 停下（HookFailed／HooksBad）時還沒 done 的信留在 cur/、下次重跑再接（P-12）。
# 錯：stderr 一行「agent-fsm: error: 代號 原因」、退 1、history 不接（P-20）。aos-post 的 stderr 不攔、原樣透出（stdio-unify R10）。--help 印英文用法；Ctrl-C 退 130。設計：proto8/thinking/2026-11/04/loop-fsm-agent/01-設計.md § 3。
# on_clock（11-11 thinking/2026-11/11/clock-hook）：這格建好 queue 之後、收信之前先 H.clock_tick()——時鐘走到了的 on_clock hook 才跑（handler 預設什麼都不做、history 不多東西）；沒有這種 hook＝只讀清單。
# goal（11-11 thinking/2026-11/11/goal/02，使用者「當agent自己停下來時(在沒有新user prompt的情況下，自己不再呼叫工具)，自動丟goal給他」）：
#   收不到信（信優先）、history 最後一則是沒有 tool_calls 的 assistant（或 history 還空：外面先 set 的 goal 當開場題目，11-11 稍後使用者「也丟，當開場題目」）、
#   $AOS_STACK/goal.json 是 active＝把一則 user「[aos] goal: …」直接接進 history、退 0 去 think（不走 queue、不觸發 before_queue／after_queue）。
#   上次提醒之後腦叫過 goal 以外的工具（只看 history：goal_state.progressed；do_task 摺過也算得到）＝計數先歸零；連續到上限那次丟
#   「[aos] goal: reminder limit N reached; goal paused …」、goal 改 paused（之後不丟）。先寫 goal.json 再接 history（寫不成＝warning、不丟）。
#   自己暫停後來了訊息、答完又停下＝只讀 history 最後 262144 bytes，找到 goal 呼叫且未碰到提醒或 summary 才加一次 paused 提示；
#   不改 goal.json、不自動 resume；外面或 aos 設的暫停不提示。goal.json 壞了＝安靜當沒有（每 300 ms 一拍，不洗 log；aos-agent goal get 報 GoalBad）。讀寫走 py/aos/agentlib/goal_state.py。
# /compact bypasses queue hooks, batches one summary request after ordinary letters, and resumes an existing request without taking mail.
# 可摺的不到 compact.MIN_ROWS 則（例：剛壓完又來一封）＝使用者 11-20「當成正常做完」：不問腦、不摺，先回一則 compact.SKIP 的回答
#   （照 compact done 的形狀，answer_to＋aos.compact＋aos.skipped），信記成答完；不寫 mailbox_warning、不記 dropped。
#   回答寫在這批普通信之前（批開頭先看 cur/ 有沒有 /compact），這批的普通信才不會被它擋在後面沒人答。
# before_compact（11-21 線 top-1121-compact4，規矩在 compact.py）：夠摺時、清工具輸出與加要求之前發；攔下（退 10）＝照「compact not needed」的樣子
#   回一則「compact blocked by hook H: …」（多 aos.blocked）、信記成答完；hook 給了 summary＝加要求列後當場摺（compact.fold，那裡發 after_compact），不叫腦。
import json, os, re, signal, subprocess, sys
from pathlib import Path

_import_paths = [str(Path(__file__).resolve().parent)]
if os.environ.get("AOS_HOME"):  # 家外的格只經 AOS_HOME 找 lib（路徑規則一：不往上找旁邊的夾、不猜）
    _import_paths.append(os.path.join(os.environ["AOS_HOME"], "lib"))
sys.path[:0] = _import_paths
try:
    from aos import flags as aos_flags  # noqa: E402
    from aos import ws as aos_ws  # noqa: E402  （回答配對：letters_take／letters_drop／mark_letter）
    from aos.agentlib import agent_hooks  # noqa: E402
    from aos.agentlib import goal_state  # noqa: E402
except (ModuleNotFoundError, ImportError) as _error:
    if _error.name not in ("aos", "aos.agentlib"):
        raise
    if not os.environ.get("AOS_HOME"):
        print("agent-fsm: error: HomeMissing AOS_HOME is not set (it names the proto8 folder that holds lib)",
              file=sys.stderr)
        sys.exit(1)
    print("agent-fsm: error: ModuleMissing required Python module %s is unavailable" % _error.name,
          file=sys.stderr)
    sys.exit(1)
finally:
    for _path in _import_paths:
        sys.path.remove(_path)

HELP = """\
usage: idle.py [--prompt FILE]   (a cell of templates/agent-fsm; run by its fsm.json under aos-fsm, needs $AOS_STACK)
The idle cell: take every letter in $AOS_STACK/queue/ into $AOS_STACK/history.jsonl.
Exit 0 = took at least one good letter (go think); 10 = no letter.
Goal: with no letter, when the last message is an answer without tool_calls (or history is
still empty) and $AOS_STACK/goal.json is active, one user message "[aos] goal: ..." goes into
history (exit 0). After an agent pauses its own goal and answers a later message, idle adds
one paused note asking it to decide whether to resume; the goal stays unchanged.
--prompt FILE: an opening message put into the queue once while history is empty.
Hooks (hooks.json declared in interfaces.json): before_queue runs before a good letter goes
into history (it may change content, or drop the letter: done, not in history, one line in
mailbox_warning.txt); after_queue runs after it went in. A failing hook = HookFailed, exit 1.
/compact bypasses queue hooks and requests a summary after taking the entire batch. With
fewer than four foldable messages there is no brain call and nothing is folded: the /compact
letters get one answer "compact not needed: ..." (before the ordinary letters of the batch).
Otherwise before_compact runs first: exit 10 = the letters get one answer "compact blocked by
hook H: ..." and nothing is folded; a hook that gives a summary = folded at once, no brain call.
While a summary is already requested, take no mail and return to think.
On error: one line "agent-fsm: error: CODE reason" on stderr, exit 1.
"""
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）

NOT_FOUND = 10                                   # aos-post take-all 沒信可收
ORDERED = re.compile(r"^[0-9]{12}\.")            # 有序信的名字：<12 位序號>.<尾名>（N-16）


def die(code, reason):
    aos_flags.die("agent-fsm", code, reason)


def here(path):
    """相對路徑從範本資料夾（AOS_CD；沒設＝cwd）算。"""
    return os.path.join(os.environ.get("AOS_CD") or ".", path)


try:
    values, rest = aos_flags.parse(sys.argv[1:], {}, multi={'--prompt': '--prompt'}, help=HELP)
except aos_flags.Error as e:
    die(e.code, e)
if rest:
    die("ArgumentsBad", "unexpected argument %s (usage: idle.py [--prompt FILE])" % rest[0])
# 收齊重複值再取最後一個：任一次空值都照舊報錯，不讓後面的值蓋掉錯誤。
for flag, items in values.items():
    if any(not value for value in items):
        die("ArgumentsBad", "%s needs a non-empty value (usage: idle.py [--prompt FILE])" % flag)
opts = {flag: items[-1] for flag, items in values.items()}
prompt = here(opts["--prompt"]) if "--prompt" in opts else None
if prompt and not os.path.isfile(prompt):
    die("PromptMissing", "prompt file not found: %s" % prompt)
stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "AOS_STACK is not set")
box = os.path.join(stack, "queue")
history_path = os.path.join(stack, "history.jsonl")
H = agent_hooks.open(os.environ.get("AOS_CD") or ".", stack, fail=die,   # hook 遙控器：停下（HookFailed／HooksBad）＝die、退 1
                     warn=lambda line: aos_flags.warn("agent-fsm", line))


def post(args, stdin_text="", ok=(0,)):
    """叫 aos-post；回 (結束碼, stdout)。stderr 不攔：aos-post 自己的話原樣透出（R10）。碼不在 ok 裡＝PostFailed（ok=None＝不檢查）。"""
    try:
        r = subprocess.run(["aos-post"] + args, input=stdin_text, stdout=subprocess.PIPE, text=True)
    except OSError as e:
        die("PostFailed", "aos-post cannot start (must be on PATH): %s" % e)
    if ok is not None and r.returncode not in ok:
        die("PostFailed", "aos-post %s exited %d" % (args[0], r.returncode))
    return r.returncode, r.stdout


def names(stage):
    """queue 某一格的信件名稱（. 開頭的不算，N-05），照處理順序排。"""
    try:
        found = [n for n in os.listdir(os.path.join(box, stage)) if not n.startswith(".")]
    except (FileNotFoundError, NotADirectoryError):
        return []
    return sorted(found, key=lambda n: (0 if ORDERED.match(n) else 1, n))


def history_empty():
    try:
        with open(history_path, encoding="utf-8") as f:
            return not any(line.strip() for line in f)
    except FileNotFoundError:
        return True
    except OSError as e:
        die("HistoryBad", "cannot read history.jsonl: %s" % e)


sys.dont_write_bytecode = True                   # 定義資料夾不留 __pycache__（P-15）
from atomic_file import write_atomic  # noqa: E402  （範本資料夾在 sys.path 最前面）
import cell_common  # noqa: E402


def body_of(sig):
    """好信回 (body, None)；壞信回 (None, 原因)。"""
    code, out = post(["see", box, sig], ok=None)
    if code != 0:
        return None, "aos-post see exited %d" % code
    try:
        body = json.loads(out).get("body")
    except (ValueError, AttributeError):
        return None, "aos-post see did not print a JSON object"
    if not (isinstance(body, dict) and body.get("role") == "user" and isinstance(body.get("content"), str)
            and body["content"].strip()):
        return None, "body must be {\"role\": \"user\", \"content\": non-empty string}"
    return body, None


def take():
    """這一批＝cur/ 全部（上次認領了還沒接完的）＋ new/ 全部（aos-post take-all）；照處理順序。回接進 history 的封數。"""
    import compact
    if compact.state(stack).get("phase") == "asked":
        history = cell_common.read_history(history_path, die)
        if compact.asking(stack, history):
            return 1
    if names("new"):
        post(["take-all", box], ok=(0, NOT_FOUND))
    short = [name for name, _ in compact.waiting_letters(box, "cur")]
    if short:                                    # 太短就先答，寫在這批普通信之前（普通信是待答信，不算可摺，數字不受它們影響）
        count = compact.foldable(stack, cell_common.read_history(history_path, die), aos_ws)
        if count < compact.MIN_ROWS:
            answer_short(compact, short, count)
    good = 0
    compact_letters = []
    compact_extra = ""
    for sig in names("cur"):
        body, why = body_of(sig)
        if body is None:                         # 壞信一律丟，不通知寄信人（N-16）
            drop(sig, "bad")
            post(["done", box, sig])
            write_atomic(os.path.join(stack, "mailbox_warning.txt"), "letter %s rejected: %s\n" % (sig, why.replace("\n", " ")), die)
            continue
        content = body["content"]
        is_c, extra = compact.is_compact(content)
        if is_c:
            compact_letters.append(sig)
            if len(compact_letters) == 1:
                compact_extra = extra
            continue
        content = H.take_letter(box, sig, content)
        if content is None:                      # hook 丟掉這封：已收掉（記 dropped、done、mailbox_warning），不進 history、不算好信
            continue
        try:                                    # 回答配對：先記 pending、再接 history（帶 aos.letter）、最後 done（讀的一方照這個方向查）
            aos_ws.letters_take(stack, [sig])
        except OSError as e:
            die("WriteFailed", "cannot write %s: %s" % (os.path.join(stack, aos_ws.LETTERS), e))
        row = aos_ws.mark_letter({"role": "user", "content": content}, sig)
        try:
            with open(history_path, "a", encoding="utf-8") as f:     # 一次寫一整行，只附加（P-41）
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as e:
            die("WriteFailed", "cannot append to history.jsonl: %s" % e)
        post(["done", box, sig])                 # 接進 history 就算收到（使用者 11-04「接進對話紀錄就收」）
        good += 1
        H.fire("after_queue", {"letter": sig, "content": content})
    if compact_letters:
        history = cell_common.read_history(history_path, die)
        count = compact.foldable(stack, history, aos_ws)
        if count < compact.MIN_ROWS:             # 批開頭沒認出來的（照理不會有）：一樣當成做完
            answer_short(compact, compact_letters, count)
            return good
        warn = lambda line: aos_flags.warn("agent-fsm", line)   # noqa: E731
        plan = compact.before(stack, compact_letters, compact_extra, count, die, warn)   # before_compact（compact 第 4 刀）
        if plan["blocked"]:                      # 攔下：回一則 blocked、信記成答完，不清不摺
            answer_short(compact, compact_letters, count,
                         lambda: compact.blocked(stack, history_path, compact_letters, plan, aos_ws, die))
            return good
        try:
            aos_ws.letters_take(stack, compact_letters)
        except OSError as e:
            die("WriteFailed", "cannot take compact letters: %s" % e)
        given = compact.ask(stack, history_path, compact_letters, compact_extra, aos_ws, die,   # 先清舊的工具輸出再加要求（compact 第 1 刀）
                            warn=warn, plan=plan)
        for sig in compact_letters:
            post(["done", box, sig])
        if given is not None:                    # hook 給了摘要：當場摺，不叫腦（摺不成＝compact.give_up 照舊）
            compact.fold(stack, history_path, {"role": "assistant", "content": given}, aos_ws, warn, die)
        return good + 1
    return good


def answer_short(compact, sigs, count, write=None):
    """可摺的不到門檻：回一則「compact not needed」（compact.skip）、收信、記成答完（回答配對：pending → history → done → 清 pending）。
    write＝換成別的回答（before_compact 攔下時的 compact.blocked），其餘一樣。"""
    if write:
        write()
    else:
        compact.skip(stack, history_path, sigs, count, aos_ws, die)
    for sig in sigs:
        post(["done", box, sig])
    try:
        aos_ws.letters_answered(stack, sigs)
    except OSError as e:
        aos_flags.warn("agent-fsm", "cannot write %s: %s" % (os.path.join(stack, aos_ws.LETTERS), e))


def drop(sig, reason):
    """這封不會進 history：在 done 之前記進 letters.json 的 dropped（ask 立刻報 LetterDropped）；寫不成只 warning（ask 最壞等到逾時）。"""
    try:
        aos_ws.letters_drop(stack, [sig], reason)
    except OSError as e:
        aos_flags.warn("agent-fsm", "cannot write %s: %s" % (os.path.join(stack, aos_ws.LETTERS), e))


def opening():
    """history 空、給了 --prompt、內容非空＝把開場白當一則 user 投進 queue（有序）。回 True＝投了。"""
    if not prompt or not history_empty():
        return False
    try:
        with open(prompt, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        die("PromptMissing", "prompt file not found: %s" % prompt)
    except OSError as e:
        die("PromptBad", "cannot read %s: %s" % (prompt, e))
    text = text[:-1] if text.endswith("\n") else text          # 結尾一個換行不算
    if not text.strip():
        return False
    post(["send", "--ordered", box], json.dumps({"role": "user", "content": text}, ensure_ascii=False))
    return True


if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
    post(["init", box])                          # 先建好，aos-agent say／listen 認得（同 aos-eca-turn）
H.clock_tick()                                   # 11-11 on_clock：idle 在建好 queue 之後看時鐘（第一次就跑的 handler 可能往 queue 寄信），到了才起 handler
def history_tail():
    """只讀最後 262144 bytes；截斷的首行丟掉，壞 JSON／編碼回 None（不猜）。"""
    try:
        with open(history_path, "rb") as f:
            offset = max(0, f.seek(0, os.SEEK_END) - 262144)
            f.seek(offset)
            data = f.read(262144)
    except FileNotFoundError:
        return []
    except OSError as e:
        die("HistoryBad", "cannot read history.jsonl: %s" % e)
    if offset:
        data = data.partition(b"\n")[2]
    try:
        return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    except (ValueError, UnicodeError):
        return None


def goal_turn():
    """沒信時：active 丟一般提醒；自己暫停後有新訊息且又停下，丟一次 paused 提示。"""
    if not os.path.isfile(goal_state.path(stack)):  # 先只看檔在不在：沒 goal 的 agent 每拍不讀 history
        return False
    try:
        rec = goal_state.read(stack)
    except goal_state.GoalBad:
        return False
    if rec is not None and rec["status"] == "paused" and rec.get("updated_by") == "agent":
        tail = history_tail()
        if tail is None or not goal_state.paused_due(rec, tail):
            return False
        try:
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"role": "user", "content": goal_state.paused_note(rec)}, ensure_ascii=False) + "\n")
        except OSError as e:
            die("WriteFailed", "cannot append to history.jsonl: %s" % e)
        return True
    if rec is None or rec["status"] != "active":
        return False
    history = []
    try:
        with open(history_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        history.append(json.loads(line))
                    except ValueError:
                        return False             # history 壞了不是這裡的事（think／act 會報 HistoryBad）
    except FileNotFoundError:
        pass                                     # 還沒有 history＝空（開場）
    except OSError as e:
        die("HistoryBad", "cannot read history.jsonl: %s" % e)
    if not goal_state.due(history):              # 腦停下來了，或 history 還空（外面先 set 的 goal 當開場題目）
        return False
    text, rec = goal_state.plan(rec, goal_state.progressed(history))
    try:
        goal_state.write(stack, rec)
    except OSError as e:
        aos_flags.warn("agent-fsm", "cannot write %s: %s; no goal reminder this time" % (goal_state.path(stack), e))
        return False
    try:
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"role": "user", "content": text}, ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot append to history.jsonl: %s" % e)
    return True


if take() or (opening() and take()) or goal_turn():
    sys.exit(0)
sys.exit(10)
