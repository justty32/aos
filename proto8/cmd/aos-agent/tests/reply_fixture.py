"""reply_fixture - 回答配對測試的共用零件（reply-match-1114）：假 aos-post、假 daemon 表、模擬寫的一方（新身體／舊身體，fsm 形／eca 形），不跑真 agent。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "lib")]
import aos_ws  # noqa: E402

AGENT_BIN = PROTO / "cmd" / "aos-agent" / "bin" / "aos-agent"
BASE_COMMIT = "158816ad0eaebf2776a87cbf58b9bf9c7db6fce1"   # reply-match 施工前的 main（暫存樹 git archive 的那個）

# 假 aos-post：只做 aos_ws.put 用到的 init、send --ordered（信＝<box>/new/<12 位序號>.q/letter.json）；序號跳過各格已有的、用 mkdir 搶，兩人同寄也不撞。
FAKE_POST = r'''#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
if a[0] == "init":
    for s in ("tmp", "new", "cur", "archive"):
        os.makedirs(os.path.join(a[1], s), exist_ok=True)
    sys.exit(0)
if a[:2] == ["send", "--ordered"]:
    box, body = a[2], sys.stdin.read()
    n = 1
    while True:
        name = "%012d.q" % n
        if any(os.path.lexists(os.path.join(box, s, name)) for s in ("new", "cur", "archive")):
            n += 1
            continue
        try:
            os.mkdir(os.path.join(box, "tmp", name))
            break
        except FileExistsError:
            n += 1
    with open(os.path.join(box, "tmp", name, "letter.json"), "w") as f:
        f.write(body)
    os.rename(os.path.join(box, "tmp", name), os.path.join(box, "new", name))
    print(name)
    sys.exit(0)
sys.stderr.write("aos-post: error: ArgumentsBad fake aos-post: %r\n" % a)
sys.exit(2)
'''


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


class Daemon:
    """一個假 daemon 資料夾：procs_state.json 的表、每隻一個 stack（queue、state.json），加上放假 aos-post 的 bin/。"""

    def __init__(self, test, names=("kid",)):
        self.root = Path(tempfile.mkdtemp(prefix="reply-match-"))
        test.addCleanup(shutil.rmtree, self.root, True)
        self.dir = self.root / "daemon"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "aos-post").write_text(FAKE_POST)
        (self.bin / "aos-post").chmod(0o755)
        self.rows = {}
        for n in names:
            self.add(n)

    def add(self, name):
        stack = self.dir / "procs" / name
        for s in ("tmp", "new", "cur", "archive"):
            (stack / "queue" / s).mkdir(parents=True, exist_ok=True)
        (stack / "state.json").write_text('{"phase":"running"}')
        self.rows[name] = {"phase": "running", "stack": "procs/" + name, "def": str(self.root / ("def-" + name))}
        self.save()
        return stack

    def save(self):
        (self.dir / "procs_state.json").write_text(json.dumps({"procs": self.rows}))

    def stack(self, name="kid"):
        return self.dir / "procs" / name

    def env(self, **extra):
        return clean_env(PATH="%s:%s" % (self.bin, os.environ["PATH"]), **extra)

    def agent(self, *argv, input=None, bin=AGENT_BIN, timeout=60):
        """跑 aos-agent -d <假 daemon> argv…；回 CompletedProcess。"""
        return subprocess.run([sys.executable, str(bin), "-d", str(self.dir), *argv], input=input, capture_output=True,
                              text=True, env=self.env(), cwd=str(self.root), timeout=timeout,
                              stdin=None if input is not None else subprocess.DEVNULL)

    def start(self, *argv, input=None, bin=AGENT_BIN):
        """背景跑 aos-agent（兩人同問用）；回 Popen。"""
        p = subprocess.Popen([sys.executable, str(bin), "-d", str(self.dir), *argv], stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env(), cwd=str(self.root))
        if input is not None:
            p.stdin.write(input)
            p.stdin.close()
        return p


def append(stack, *rows):
    with open(os.path.join(stack, "history.jsonl"), "a", encoding="utf-8") as f:
        for m in rows:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


class Body:
    """模擬寫的一方（新身體照 03 §1 的寫法；舊身體＝現行，沒有 aos 鍵、沒有 letters.json）。
    shape＝"fsm"：一次收一封，中間有一則帶 tool_calls 的 assistant 與 tool 列；"eca"：把 queue 裡的信全部收成一批、一則回答。
    gather_s＝收信前等多久（讓多封信湊成一批）；think_s＝收完到回答之間等多久；
    drop＝(信名, 內容) → None 或 "bad"／"blocked"（收信時就丟）；fail＝內容 → True 時交出去後失敗（記 failed、不答）；
    answer＝[內容…] → 回答文字；before_answer／after＝(stack) → 寫回答之前／之後叫（模擬 summarize、history rm）。"""

    def __init__(self, test, stack, *, upgraded=True, shape="fsm", gather_s=0.0, think_s=0.2, drop=None, fail=None, answer=None,
                 before_answer=None, after=None):
        self.stack, self.upgraded, self.shape = str(stack), upgraded, shape
        self.before_answer, self.after = before_answer or (lambda s: None), after or (lambda s: None)
        self.gather_s, self.think_s = gather_s, think_s
        self.drop, self.fail = drop or (lambda n, t: None), fail or (lambda t: False)
        self.answer = answer or (lambda texts: "re: " + " | ".join(texts))
        self.stop = threading.Event()
        self.t = threading.Thread(target=self.run, daemon=True)
        self.t.start()
        test.addCleanup(self.t.join, 10)
        test.addCleanup(self.stop.set)

    def q(self, stage):
        return os.path.join(self.stack, "queue", stage)

    def run(self):
        while not self.stop.is_set():
            names = aos_ws.names(self.stack, "new")
            if not names:
                time.sleep(0.05)
                continue
            if self.gather_s:
                time.sleep(self.gather_s)
                names = aos_ws.names(self.stack, "new")
            if self.shape == "fsm":
                names = names[:1]
            self.turn(names)

    def turn(self, names):
        good, texts = [], []
        for n in names:
            os.rename(os.path.join(self.q("new"), n), os.path.join(self.q("cur"), n))
            with open(os.path.join(self.q("cur"), n, "letter.json"), encoding="utf-8") as f:
                body = json.load(f)
            why = self.drop(n, body.get("content"))
            if why:
                if self.upgraded:
                    aos_ws.letters_drop(self.stack, [n], why)
            else:
                good.append(n)
                texts.append(body.get("content"))
                if self.upgraded:
                    aos_ws.letters_take(self.stack, [n])
                    append(self.stack, aos_ws.mark_letter(body, n))
                else:
                    append(self.stack, body)
            os.rename(os.path.join(self.q("cur"), n), os.path.join(self.q("archive"), n))   # done
        if not good:
            return
        if self.shape == "fsm":
            append(self.stack, {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "math", "arguments": "{}"}}]},
                   {"role": "tool", "tool_call_id": "c1", "content": "2"})
        time.sleep(self.think_s)
        if any(self.fail(t) for t in texts):
            if self.upgraded:
                aos_ws.letters_drop(self.stack, good, "failed")
            return
        self.before_answer(self.stack)
        m = {"role": "assistant", "content": self.answer(texts)}
        if self.upgraded:
            append(self.stack, aos_ws.mark_answer(m, aos_ws.letters_pending(self.stack)))
            aos_ws.letters_answered(self.stack)
        else:
            append(self.stack, m)
        self.after(self.stack)


def base_tree(test, *paths):
    """施工前（BASE_COMMIT）的 proto8 那幾個資料夾抄到暫存夾、回 proto8 的路徑；拿不到 repo 就 skip。
    repo 位置：$REPLY_MATCH_REPO，不然從這個檔往上找 .git。只讀 repo（git archive）。"""
    repo = os.environ.get("REPLY_MATCH_REPO")
    if not repo:
        p = Path(__file__).resolve()
        repo = next((str(d) for d in p.parents if (d / ".git").exists()), None)
    if not repo:
        test.skipTest("no git repo to read the pre-change files from (set REPLY_MATCH_REPO)")
    have = subprocess.run(["git", "-C", repo, "cat-file", "-e", BASE_COMMIT], capture_output=True)
    if have.returncode != 0:
        test.skipTest("commit %s not in %s" % (BASE_COMMIT, repo))
    out = Path(tempfile.mkdtemp(prefix="reply-match-base-"))
    test.addCleanup(shutil.rmtree, out, True)
    arch = subprocess.run(["git", "-C", repo, "archive", BASE_COMMIT] + ["proto8/" + p for p in paths], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(out)], input=arch.stdout, check=True)
    return out / "proto8"
