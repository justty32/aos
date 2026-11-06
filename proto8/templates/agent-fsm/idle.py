# idle.py [--prompt FILE] - idle 格（收信）：$AOS_STACK/queue/ 的信全部收進 $AOS_STACK/history.jsonl，接進去就收掉（aos-post done）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝收到至少一封好信（→ think）；10＝沒信（表上接住＝停著等，改成字串 next＝收工）。
# 一次收全部、照處理順序（有序在前照名字＝寄的順序、無序在後照名字；同 aos_ws.letter_key）；cur/ 有上次認領了還沒接完的先接（P-12）。
# 壞信（body 不是 {"role": "user", "content": 非空字串}）：aos-post done 丟掉、$AOS_STACK/mailbox_warning.txt 覆寫一行（N-16；同 aos-eca-turn）。
# --prompt FILE＝開場白（相對路徑從範本資料夾＝AOS_CD 算）：history 空、queue 也沒好信時投一次進 queue 再收；沒給＝沒有開場白。
# 錯：stderr 一行「agent-fsm: error: 代號 原因」、退 1、history 不接（P-20）。aos-post 的 stderr 不攔、原樣透出（stdio-unify R10）。--help 印英文用法；Ctrl-C 退 130。設計：proto8/thinking/2026-11/04/loop-fsm-agent/01-設計.md § 3。
import json, os, re, shutil, signal, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "py"))   # py/aos_flags.py（錯誤行、提醒行的共用介面）
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(shutil.which("aos-tools") or "/")), "..", "..", "..", "py"))   # 複製出 repo 的：從 PATH 上 aos-tools 的真位置找 proto8/py
import aos_flags  # noqa: E402

HELP = """\
usage: idle.py [--prompt FILE]   (a cell of templates/agent-fsm; run by its fsm.json under aos-fsm, needs $AOS_STACK)
The idle cell: take every letter in $AOS_STACK/queue/ into $AOS_STACK/history.jsonl.
Exit 0 = took at least one good letter (go think); 10 = no letter.
--prompt FILE: an opening message put into the queue once while history is empty.
On error: one line "agent-fsm: error: CODE reason" on stderr, exit 1.
"""
if "--help" in sys.argv[1:]:                    # --help：英文說明印 stdout、退 0（stdio-unify R3）
    sys.stdout.write(HELP)
    sys.exit(0)
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）

NOT_FOUND = 10                                   # aos-post take-all 沒信可收
ORDERED = re.compile(r"^[0-9]{12}\.")            # 有序信的名字：<12 位序號>.<尾名>（N-16）


def die(code, reason):
    aos_flags.die("agent-fsm", code, reason)


def flags(argv, known):
    """--名 值 這種旗標；回 {名: 值}。不認得、少了值＝ArgumentsBad。"""
    out, i = {}, 0
    while i < len(argv):
        if argv[i] not in known or i + 1 >= len(argv) or not argv[i + 1]:
            die("ArgumentsBad", "cannot parse %s (usage: idle.py [--prompt FILE])" % argv[i])
        out[argv[i]] = argv[i + 1]
        i += 2
    return out


def here(path):
    """相對路徑從範本資料夾（AOS_CD；沒設＝cwd）算。"""
    return os.path.join(os.environ.get("AOS_CD") or ".", path)


opts = flags(sys.argv[1:], ("--prompt",))
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


def write_atomic(path, text):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05：先寫暫存再改名
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        die("WriteFailed", "cannot write %s: %s" % (path, e))


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
            write_atomic(os.path.join(stack, "mailbox_warning.txt"), "letter %s rejected: %s\n" % (sig, why.replace("\n", " ")))
            continue
        try:
            with open(history_path, "a", encoding="utf-8") as f:     # 一次寫一整行，只附加（P-41）
                f.write(json.dumps({"role": "user", "content": body["content"]}, ensure_ascii=False) + "\n")
        except OSError as e:
            die("WriteFailed", "cannot append to history.jsonl: %s" % e)
        post(["done", box, sig])                 # 接進 history 就算收到（使用者 11-04「接進對話紀錄就收」）
        good += 1
    return good


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
if take() or (opening() and take()):
    sys.exit(0)
sys.exit(10)
