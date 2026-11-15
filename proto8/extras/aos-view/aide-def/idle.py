# idle.py [--prompt FILE] - idle 格（收信）：$AOS_STACK/queue/ 的信全部收進 $AOS_STACK/history.jsonl，接進去就收掉（aos-post done）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝收到至少一封好信、或丟了 goal 提醒（→ think）；10＝沒信（表上接住＝停著等，改成字串 next＝收工）。
# 一次收全部、照處理順序（有序在前照名字＝寄的順序、無序在後照名字；同 aos_ws.letter_key）；cur/ 有上次認領了還沒接完的先接（P-12）。
# 壞信（body 不是 {"role": "user", "content": 非空字串}）：aos-post done 丟掉、$AOS_STACK/mailbox_warning.txt 覆寫一行（N-16；同 aos-eca-turn）。
# --prompt FILE＝開場白（相對路徑從範本資料夾＝AOS_CD 算）：history 空、queue 也沒好信時投一次進 queue 再收；沒給＝沒有開場白。
# hook（lib/agent/hooks.py，圖紙 thinking/2026-11/10/self-family/hook）：好信接進 history 之前 before_queue（可改 content；攔下＝aos-post done 丟掉、
#   不進 history、不算好信、mailbox_warning.txt 寫一行是哪個 hook 丟的），接進去並 done 之後 after_queue。hook 停下（HookFailed／HooksBad）時
#   還沒 done 的信留在 cur/、下次重跑再接（P-12）。
# 錯：stderr 一行「agent-fsm: error: 代號 原因」、退 1、history 不接（P-20）。aos-post 的 stderr 不攔、原樣透出（stdio-unify R10）。--help 印英文用法；Ctrl-C 退 130。設計：proto8/thinking/2026-11/04/loop-fsm-agent/01-設計.md § 3。
# on_clock（11-11 thinking/2026-11/11/clock-hook）：這格建好 queue 之後、收信之前先 hooks.clock_tick（經 cell_common.clock_tick）——時鐘走到了的 on_clock hook 才跑（handler 預設什麼都不做、history 不多東西）；沒有這種 hook＝只讀清單。
# goal（11-11 thinking/2026-11/11/goal/02，使用者「當agent自己停下來時(在沒有新user prompt的情況下，自己不再呼叫工具)，自動丟goal給他」）：
#   收不到信（信優先）、history 最後一則是沒有 tool_calls 的 assistant（或 history 還空：外面先 set 的 goal 當開場題目，11-11 稍後使用者「也丟，當開場題目」）、
#   $AOS_STACK/goal.json 是 active＝把一則 user「[aos] goal: …」直接接進 history、退 0 去 think（不走 queue、不觸發 before_queue／after_queue）。
#   上次提醒之後腦叫過 goal 以外的工具（只看 history：goal_state.progressed；do_task 摺過也算得到）＝計數先歸零；連續到上限那次丟
#   「[aos] goal: reminder limit N reached; goal paused …」、goal 改 paused（之後不丟）。先寫 goal.json 再接 history（寫不成＝warning、不丟）。
#   goal.json 壞了＝安靜當沒有（每 300 ms 一拍，不洗 log；aos-agent goal get 報 GoalBad）。讀寫走 lib/agent/goal_state.py。
import json, os, re, signal, subprocess, sys
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
    if (Path(__file__).resolve().parent / "hooks.py").is_file():
        import hooks  # noqa: E402
    else:
        from agent import hooks  # noqa: E402
    if (Path(__file__).resolve().parent / "goal_state.py").is_file():
        import goal_state  # noqa: E402
    else:
        from agent import goal_state  # noqa: E402
except (ModuleNotFoundError, ImportError) as _error:
    if _error.name not in ("aos_flags", "tool_io", "agent_files", "agent", "agent.agent_files", "hooks", "agent.hooks",
                           "goal_state", "agent.goal_state"):
        raise
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
history (exit 0).
--prompt FILE: an opening message put into the queue once while history is empty.
Hooks (hooks.json declared in interfaces.json): before_queue runs before a good letter goes
into history (it may change content, or drop the letter: done, not in history, one line in
mailbox_warning.txt); after_queue runs after it went in. A failing hook = HookFailed, exit 1.
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
    if names("new"):
        post(["take-all", box], ok=(0, NOT_FOUND))
    good = 0
    for sig in names("cur"):
        body, why = body_of(sig)
        if body is None:                         # 壞信一律丟，不通知寄信人（N-16）
            post(["done", box, sig])
            write_atomic(os.path.join(stack, "mailbox_warning.txt"), "letter %s rejected: %s\n" % (sig, why.replace("\n", " ")), die)
            continue
        content = body["content"]
        r = fire("before_queue", {"letter": sig, "content": content})
        if r["blocked"]:                         # hook 丟掉這封：收掉、不進 history、不算好信
            post(["done", box, sig])
            write_atomic(os.path.join(stack, "mailbox_warning.txt"), "letter %s dropped by hook %s\n" % (sig, r["hook"]), die)
            continue
        content = r["data"]["content"]
        try:
            with open(history_path, "a", encoding="utf-8") as f:     # 一次寫一整行，只附加（P-41）
                f.write(json.dumps({"role": "user", "content": content}, ensure_ascii=False) + "\n")
        except OSError as e:
            die("WriteFailed", "cannot append to history.jsonl: %s" % e)
        post(["done", box, sig])                 # 接進 history 就算收到（使用者 11-04「接進對話紀錄就收」）
        good += 1
        fire("after_queue", {"letter": sig, "content": content})
    return good


def fire(event, data):
    """跑 hook；hook 停下＝這格的錯（HookFailed／HooksBad）、退 1。"""
    try:
        return hooks.fire(event, data, os.environ.get("AOS_CD") or ".", stack,
                          warn=lambda line: aos_flags.warn("agent-fsm", line))
    except (hooks.HookFailed, hooks.HooksBad) as e:
        die(type(e).__name__, str(e))


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
cell_common.clock_tick(hooks, stack, lambda line: aos_flags.warn("agent-fsm", line), die)   # 11-11 on_clock：idle 在建好 queue 之後看時鐘（第一次就跑的 handler 可能往 queue 寄信），到了才起 handler
def goal_turn():
    """沒信時：腦停下來了、goal active＝接一則 [aos] goal: 進 history，回 True（去 think）。"""
    if not os.path.isfile(goal_state.path(stack)):  # 先只看檔在不在：沒 goal 的 agent 每拍不讀 history
        return False
    try:
        rec = goal_state.read(stack)
    except goal_state.GoalBad:
        return False
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
