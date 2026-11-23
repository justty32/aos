#!/usr/bin/env python3
"""stack_commit — 11-23 起退場：stack 不再跟著 git 搬（使用者「直接變成.stack，然後把它git ignore，就這樣。換機那一套就不用了。」），留著等使用者決定刪不刪。原本是換機工具 stack-commit 的本體：離站（leave）確認 _stack 的 daemon 已停、llm kernel 沒有 _stack 還沒回的信，只挑該帶走的檔經 commit-request 交一個 commit；到站（arrive）檢查能不能安全起樹與殼裡的 AOS_HOME／AOS_DAEMON／AOS_LLM_KERNEL。

  stack-commit leave  [--leave-dirty] [--ignore-llm] [--secret-ok F]… [--dry-run] [--line L] [--wait S] [--repo R] [--cache C]
  stack-commit arrive [--no-clean] [--dry-run] [--repo R]
  stack-commit status [--repo R]

_stack＝repo 根的 _stack/（寫死，跟 commit_queue.py 的 STACK_COMMIT_PREFIX 同一個）；根 .gitignore 忽略它，該帶走哪些照
proto8/py/aos/apps/agent/stack.gitignore 的規則挑（`git ls-files -o --exclude-from=那份 -- _stack`，不看根 .gitignore）。規劃與理由：
proto8/thinking/2026-11/22/工作區與stack-1122/02-規劃.md 線 4、邊緣狀況 1～5、9、14、15、18～23。

leave（離開這台；先 aos-daemon-ctl -d <repo>/_stack shutdown）：
  1. 對 _stack 底下每個資料夾試拿 daemon 用的那把 flock（daemon.cpp check_running 鎖的是 stack 資料夾本身）；有一個拿不到＝還有 daemon 在跑，拒絕。
     _stack 本身那把一直握到結束，leave 跑到一半沒有 daemon 起得來。
  2. _stack 以外還沒交件的髒檔（git status）印出來；要加 --leave-dirty 才繼續（那些檔不會跟著換台）。
  3. $AOS_LLM_KERNEL/requests/{new,cur} 裡寄件人（sender）或回信箱（reply_to）在 _stack 底下的信＝還沒回，印出來、拒絕；--ignore-llm 才繼續。
     沒設 AOS_LLM_KERNEL 就跳過並印一行。只讀那邊的信箱，不收信、不刪信。相對路徑從 $AOS_DAEMON 算，沒有就從 cwd（同 aos-llm）。
  4. 清單＝跟 HEAD 比：新檔（照 stack.gitignore 挑的沒追蹤檔）、內容或權限變了的追蹤檔、不見的追蹤檔（走 --rm）。沒東西＝NothingToCommit，退 0。
  5. 掃金鑰樣式（wf/public/tools/scan 的 key 規則：sk-、ghp_…、github_pat_、xox?-、AKIA、私鑰標頭、Bearer），命中就停、印檔名與行號（不印內容）；
     看過確定沒事的檔用 --secret-ok 檔 放行（可重複）。
  6. commit-request submit --stack-commit 交一個 commit（訊息寫機器名與時間，英文），不 push；--dry-run 照樣做前五步、交給 commit-request --dry-run。
arrive（到了這台；git pull 前後各跑一次——git 會默默蓋掉被忽略的檔，pull 前跑才抓得到「這台離站後又跑過」）：
  1. 同 leave 第 1 步：有 daemon 握著 _stack 就拒絕。
  2. _stack 跟 HEAD 不一樣（同 leave 第 4 步的清單不空）＝這台上次離開後又跑過、或沒做 leave：印出來、拒絕，讓人決定留哪一邊。
  3. 清掉上次留在這台的執行期檔（stack.gitignore 擋的沒追蹤檔：鎖、socket、endpoints.json、cooldown.json、think/request.json、tmp/ 的半封信…）；
     留著 .session_home、claude/ 與只給人看的紀錄（live.jsonl、transcripts/、stderr.txt、*.bad-* …，見 KEEP_*）。--no-clean 不清；--dry-run 只列。
  4. 上次 pull（ORIG_HEAD..HEAD）動到 proto8/py、proto8/cpp 就提醒先跑 install.py。
  5. 查這個殼（只看、不改、只印這幾個名字與路徑）：AOS_HOME 是不是這個 repo 的 proto8、AOS_DAEMON 解開是不是 _stack、AOS_LLM_KERNEL 有設且
     aos-daemon-ctl -d 它 ping 得到、AOS_KERNEL 有設的話那一站（它的上一層）ping 得到、沒設就印「沒有權限站」；殼裡帶著 AOS_STACK 也提醒。
     git 設定 pull.rebase、rebase.autoStash、merge.autoStash 開著也提醒。這些對不上只印、不停（llm kernel 沒開時 agent 只是一直等）。
  6. 印起樹那一行，不代跑。
status：唯讀、不清；試一下鎖就放（不握著），印 daemon 有沒有在跑、_stack 跟 HEAD 差哪些檔（只在這台、還沒交的那些；git clean -fdx 會刪掉的就是它們）。

結果：stderr 給人看（stack-commit: …），stdout 最後一行 JSON {"status": DONE|REFUSED|FAILED, "code", …}。
exit：0 完成（含沒東西可交）、1 內部錯誤、2 被檢查擋下（什麼都沒做）、3 參數或 repo 不對、4 commit-request 沒交成（它的 JSON 在 "commit_request"）。
純標準庫；不 push、不改殼、不寫 _stack 以外的檔（arrive 第 3 步只刪 _stack 裡上面說的執行期檔）。
"""
import argparse
import datetime
import fcntl
import fnmatch
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
PROG = "stack-commit"
STACK = "_stack"                                         # repo 根相對；跟 commit_queue.STACK_COMMIT_PREFIX 一致
STACK_RULES = "proto8/py/aos/apps/agent/stack.gitignore"
ROOT_DEF = "wf/tree/root"
DEFAULT_LINE = "stack-commit"
EXIT = {"DONE": 0, "internal": 1, "refused": 2, "invalid": 3, "commit": 4}
SHOW = 20                                                # 清單最多印幾行

# 金鑰樣式：抄自 wf/public/tools/scan/scan.py 的 key 規則（home 路徑、email 在 stack 裡本來就有，不掃）
SECRET_RULES = [
    ("key-openai", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("key-github", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("key-slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("key-aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("key-private", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer", re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{20,}")),
]

# arrive 清執行期檔時留著的（stack.gitignore 也擋它們，但不是「會讀錯的執行期狀態」）：
KEEP_PARTS = {".session_home", "claude", "transcripts", "stderr_archives", "observed"}   # 路徑裡任何一段是這些
KEEP_NAMES = {"live.jsonl", "turns.jsonl", "aos-mcp-logs.jsonl", "mailbox_warning.txt", "stderr.txt",
              "sweeper_report.json", "stop_cause.json", "observed.jsonl"}
KEEP_GLOBS = ("counter_*.txt", "*.bad-*")

GIT_DANGER = ("while _stack is tracked, do not run git stash, git reset --hard, git checkout -- ., git clean -fdx, "
              "git pull --autostash or git pull --rebase in this repo: they roll the stack back or delete what is not committed yet "
              "(git clean -fdx deletes every _stack file that is not in a commit)")


class Stop(Exception):
    def __init__(self, status, code, exit_code, msg, **extra):
        super().__init__(msg)
        self.status, self.code, self.exit_code, self.msg, self.extra = status, code, exit_code, msg, extra


def say(msg):
    print(f"{PROG}: {msg}", file=sys.stderr)


def show_list(head, items, fmt=str):
    say(f"{head} ({len(items)}):")
    for x in items[:SHOW]:
        print(f"  {fmt(x)}", file=sys.stderr)
    if len(items) > SHOW:
        print(f"  ... and {len(items) - SHOW} more", file=sys.stderr)


class Repo:
    def __init__(self, path):
        top = os.path.realpath(path)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        p = subprocess.run(["git", "-C", top, "rev-parse", "--show-toplevel"], env=self.env, capture_output=True)
        if p.returncode != 0:
            raise Stop("FAILED", "RepoBad", EXIT["invalid"], f"{path}: not a git repo")
        self.top = os.path.realpath(p.stdout.decode().strip())
        self.stack = os.path.join(self.top, STACK)
        self.rules = os.path.join(self.top, STACK_RULES)
        if not os.path.isfile(self.rules):
            raise Stop("FAILED", "RulesMissing", EXIT["invalid"], f"{STACK_RULES} not found in {self.top}")

    def run(self, args, data=None, check=True):
        p = subprocess.run(["git"] + args, cwd=self.top, env=self.env, input=data, capture_output=True)
        if check and p.returncode != 0:
            raise Stop("FAILED", "GitFailed", EXIT["internal"], f"git {' '.join(args[:3])}: {p.stderr.decode(errors='replace').strip()}")
        return p

    def zlist(self, args):
        return [x for x in self.run(args).stdout.decode().split("\0") if x]

    # -- _stack 跟 HEAD 差什麼
    def changes(self):
        """(新增或改過的檔, 不見的檔, 其中新檔的集合)；都是 repo 根相對路徑、排好序。"""
        head = {}
        for rec in self.zlist(["ls-tree", "-r", "-z", "--full-tree", "HEAD", "--", STACK]):
            meta, path = rec.split("\t", 1)
            mode, typ, sha = meta.split()
            if typ == "blob":
                head[path] = (mode, sha)
        rules = f"--exclude-from={self.rules}"
        untracked = set(self.zlist(["ls-files", "-o", "-z", rules, "--", STACK]))
        cached = set(self.zlist(["ls-files", "-c", "-z", "--", STACK]))
        cached_ignored = set(self.zlist(["ls-files", "-c", "-i", "-z", rules, "--", STACK]))
        cand = set(head) | untracked | (cached - cached_ignored)
        files, rms, regular = [], [], []
        for p in cand:
            full = os.path.join(self.top, p)
            if not os.path.lexists(full) or (os.path.isdir(full) and not os.path.islink(full)):
                if p in head:
                    rms.append(p)
                continue
            if p not in head:
                files.append(p)
            elif os.path.islink(full) or "\n" in p:
                if self.blob(full, p) != head[p]:
                    files.append(p)
            else:
                regular.append(p)
        if regular:                                      # 一次算完：git hash-object --stdin-paths（照 .gitattributes，同 commit_queue）
            shas = self.run(["hash-object", "--stdin-paths"], data=("\n".join(regular) + "\n").encode()).stdout.decode().split()
            for p, sha in zip(regular, shas):
                mode = "100755" if os.access(os.path.join(self.top, p), os.X_OK) else "100644"
                if (mode, sha) != head[p]:
                    files.append(p)
        return sorted(files), sorted(rms), {p for p in files if p not in head}

    def blob(self, full, path):
        if os.path.islink(full):
            sha = self.run(["hash-object", "--stdin", "--no-filters"], data=os.readlink(full).encode()).stdout.decode().strip()
            return ("120000", sha)
        with open(full, "rb") as f:
            data = f.read()
        sha = self.run(["hash-object", "--stdin", "--path", path], data=data).stdout.decode().strip()
        return ("100755" if os.access(full, os.X_OK) else "100644", sha)

    def runtime_files(self):
        """stack.gitignore 擋的沒追蹤檔裡，arrive 要清的那些（KEEP_* 以外）。"""
        out = []
        for p in self.zlist(["ls-files", "-o", "-i", "-z", f"--exclude-from={self.rules}", "--", STACK]):
            parts = p.split("/")
            name = parts[-1]
            if any(x in KEEP_PARTS for x in parts[1:]) or name in KEEP_NAMES or any(fnmatch.fnmatchcase(name, g) for g in KEEP_GLOBS):
                continue
            out.append(p)
        return sorted(out)


# ---------------------------------------------------------------- 鎖

def lock_stack(stack, hold):
    """對 stack 底下每個資料夾試拿 flock。回 (握著的 _stack fd 或 None, 拿不到的資料夾)。hold＝False 時全部馬上放。"""
    fd_root, busy = None, []
    for d, dirs, _ in os.walk(stack):
        dirs.sort()
        try:
            fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            busy.append(d)
            os.close(fd)
            continue
        if d == stack and hold:
            fd_root = fd                                 # 一直握到行程結束：這段時間 daemon 起不來（DaemonExists）
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    return fd_root, busy


def need_stopped(repo):
    fd, busy = lock_stack(repo.stack, hold=True)
    if busy:
        rel = [os.path.relpath(b, repo.top) for b in busy]
        raise Stop("REFUSED", "DaemonRunning", EXIT["refused"],
                   f"a daemon still holds {', '.join(rel[:5])}" + (" ..." if len(rel) > 5 else ""),
                   busy=rel, hint=f"stop the tree first: aos-daemon-ctl -d {repo.stack} shutdown (and wait until it returns), then run this again")
    return fd


# ---------------------------------------------------------------- 環境

def resolve_kernel(value):
    """AOS_LLM_KERNEL／AOS_KERNEL 的解法同 aos-llm：絕對照用；相對從 $AOS_DAEMON 算，沒有就從 cwd。"""
    v = os.path.expanduser(value)
    if not os.path.isabs(v):
        base = os.environ.get("AOS_DAEMON") or os.getcwd()
        v = os.path.join(os.path.expanduser(base), v)
    return os.path.realpath(v)


def inside(path, root):
    if not isinstance(path, str) or not path:
        return False
    rp = os.path.realpath(path)
    return rp == root or rp.startswith(root + os.sep)


def llm_letters(repo):
    """(kernel 路徑或 None, [(new|cur, 信名, 說明)])：寄件人或回信箱在 _stack 底下、還在 llm kernel 信箱裡的信。"""
    v = os.environ.get("AOS_LLM_KERNEL")
    if not v:
        return None, []
    k = resolve_kernel(v)
    stack = os.path.realpath(repo.stack)
    hits = []
    for sub in ("new", "cur"):
        box = os.path.join(k, "requests", sub)
        try:
            names = sorted(os.listdir(box))
        except OSError:
            continue
        for name in names:
            full = os.path.join(box, name)
            lj = os.path.join(full, "letter.json") if os.path.isdir(full) else full
            try:
                with open(lj, encoding="utf-8") as f:
                    letter = json.load(f)
                if not isinstance(letter, dict):
                    raise ValueError("not an object")
            except (OSError, ValueError) as e:
                hits.append((sub, name, f"unreadable ({e.__class__.__name__}); counted as possibly from _stack"))
                continue
            who = letter.get("sender")
            if inside(who, stack) or inside(letter.get("reply_to"), stack):
                hits.append((sub, name, "from " + (os.path.relpath(os.path.realpath(who), repo.top) if inside(who, stack) else "reply_to in _stack")))
    return k, hits


def ping(stack_dir):
    """(True/False/None, 一句話)：aos-daemon-ctl -d DIR ping；沒有這個指令就退回試 flock（只看有沒有 daemon 握著）。"""
    if not os.path.isdir(stack_dir):
        return False, "folder does not exist"
    ctl = shutil.which("aos-daemon-ctl")
    if ctl:
        try:
            p = subprocess.run([ctl, "-d", stack_dir, "ping"], capture_output=True, timeout=20)
        except subprocess.TimeoutExpired:
            return False, "ping timed out"
        if p.returncode == 0:
            return True, (p.stdout.decode(errors="replace").strip().splitlines() or ["answered"])[-1]
        err = (p.stderr.decode(errors="replace").strip().splitlines() or [f"exit {p.returncode}"])[-1]
        return False, err
    fd = None
    try:
        fd = os.open(stack_dir, os.O_RDONLY | os.O_DIRECTORY)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False, "no daemon holds it (aos-daemon-ctl not on PATH, checked the lock only)"
    except BlockingIOError:
        return True, "a daemon holds it (aos-daemon-ctl not on PATH, not pinged)"
    except OSError as e:
        return None, str(e)
    finally:
        if fd is not None:
            os.close(fd)


def check_env(repo, notes):
    """arrive 第 5 步：只看、只印這幾個變數的名字與路徑。notes 收一句一句的提醒。"""
    want_home = os.path.join(repo.top, "proto8")
    h = os.environ.get("AOS_HOME")
    if not h:
        notes.append(f"AOS_HOME is not set (export AOS_HOME={want_home} once per machine, then source $AOS_HOME/env.sh)")
    else:
        if os.path.realpath(os.path.expanduser(h)) != os.path.realpath(want_home):
            notes.append(f"AOS_HOME is {h}, not this repo's proto8 ({want_home})")
        if not os.path.exists(os.path.join(os.path.expanduser(h), "bin", "aos-exec")):
            notes.append(f"{h}/bin/aos-exec is missing: run python3 {h}/install.py")
    if os.environ.get("AOS_STACK"):
        notes.append("this shell has AOS_STACK set (an agent's shell?): start the tree from a plain shell; "
                     "exports in ~/.zshrc or ~/.bashrc belong inside the [[ -z $AOS_STACK ]] check")
    d = os.environ.get("AOS_DAEMON")
    if not d:
        notes.append(f"AOS_DAEMON is not set: aos-daemon-ctl without -d looks for ./.stack, not _stack (export AOS_DAEMON={repo.stack})")
    elif os.path.realpath(os.path.expanduser(d)) != os.path.realpath(repo.stack):
        notes.append(f"AOS_DAEMON is {d}, not {repo.stack}")
    else:
        say(f"AOS_DAEMON = {d} (this repo's _stack)")
    k = os.environ.get("AOS_LLM_KERNEL")
    if not k:
        notes.append("AOS_LLM_KERNEL is not set: agent-fsm agents stop at their first brain call (LlmKernelMissing); "
                     "start this machine's llm kernel and export AOS_LLM_KERNEL to its stack")
    else:
        kp = resolve_kernel(k)
        ok, why = ping(kp)
        if ok:
            say(f"AOS_LLM_KERNEL = {k}: {why}")
        else:
            notes.append(f"AOS_LLM_KERNEL = {k}: the llm kernel there does not answer ({why}); agents that ask the brain will wait until it runs")
    s = os.environ.get("AOS_KERNEL")
    if not s:
        say("AOS_KERNEL is not set: no permission station (letters and ctl go straight to the daemon)")
    else:
        sp = os.path.dirname(resolve_kernel(s))
        ok, why = ping(sp)
        if ok:
            say(f"AOS_KERNEL = {s}: the station's daemon {sp}: {why}")
        else:
            notes.append(f"AOS_KERNEL = {s}: the station's daemon {sp} does not answer ({why}); with AOS_KERNEL set and no station, "
                         "every mailbox_send, mailbox_peek, clock_register and self_* call fails after 3 s (KernelFailed); "
                         "start the station or unset AOS_KERNEL, then start the tree again")


def check_git_config(repo, notes):
    def get(key):
        p = repo.run(["config", "--get", key], check=False)
        return p.stdout.decode().strip().lower() if p.returncode == 0 else ""
    if get("pull.rebase") not in ("", "false"):
        notes.append("git config pull.rebase is on: with a running _stack every git pull refuses (tracked stack files are always modified); "
                     "set it to false in this repo")
    for key in ("rebase.autostash", "merge.autostash"):
        if get(key) == "true":
            notes.append(f"git config {key} is true: a pull would stash and put back the running stack's files; set it to false in this repo")


def check_install(repo, notes):
    p = repo.run(["rev-parse", "-q", "--verify", "ORIG_HEAD"], check=False)
    orig = p.stdout.decode().strip()
    head = repo.run(["rev-parse", "HEAD"]).stdout.decode().strip()
    if orig and orig != head and repo.run(["merge-base", "--is-ancestor", orig, head], check=False).returncode == 0:
        changed = repo.zlist(["diff", "--name-only", "-z", orig, head, "--", "proto8/py", "proto8/cpp"])
        if changed:
            notes.append(f"the commits since ORIG_HEAD ({orig[:10]}) change {len(changed)} files under proto8/py or proto8/cpp: "
                         f"run python3 {repo.top}/proto8/install.py before starting the tree")
            return
        say(f"the commits since ORIG_HEAD ({orig[:10]}) do not touch proto8/py or proto8/cpp")
        return
    say("if the last pull changed proto8/py or proto8/cpp, run python3 proto8/install.py before starting the tree")


# ---------------------------------------------------------------- 三個動作

def scan_secrets(repo, files, ok):
    hits = []
    for p in files:
        if p in ok:
            continue
        full = os.path.join(repo.top, p)
        if os.path.islink(full):
            continue
        try:
            with open(full, "rb") as f:
                text = f.read().decode("utf-8", errors="replace")
        except OSError as e:
            raise Stop("FAILED", "ReadFailed", EXIT["internal"], f"{p}: {e}")
        for n, line in enumerate(text.split("\n"), 1):
            for rule, rx in SECRET_RULES:
                if rx.search(line):
                    hits.append((p, n, rule))
    return hits


def leave(a, repo):
    if not os.path.isdir(repo.stack):
        raise Stop("FAILED", "StackMissing", EXIT["invalid"], f"{repo.stack} does not exist")
    lock = need_stopped(repo)
    say(f"no daemon holds {STACK} (held its lock until this run ends)")
    warnings = []
    # 2. _stack 以外的髒檔
    dirty = []
    for rec in repo.zlist(["status", "--porcelain=v1", "-z", "--untracked-files=normal", "--no-renames"]):
        path = rec[3:]
        if path != STACK and not path.startswith(STACK + "/"):
            dirty.append(rec)
    if dirty:
        show_list("files outside _stack not committed yet (they do not move to the other machine)", dirty)
        if not a.leave_dirty:
            raise Stop("REFUSED", "DirtyOutside", EXIT["refused"], f"{len(dirty)} uncommitted files outside {STACK}",
                       hint="submit them with commit-request first, or add --leave-dirty to go on without them")
        warnings.append(f"left {len(dirty)} uncommitted files outside {STACK} (--leave-dirty)")
    # 3. llm kernel 那邊還沒回的信
    k, letters = llm_letters(repo)
    if k is None:
        say("AOS_LLM_KERNEL is not set: skipped the check for unanswered brain letters")
    elif letters:
        show_list(f"letters from {STACK} still in the llm kernel {k}/requests", letters, lambda x: f"{x[0]}/{x[1]}: {x[2]}")
        if not a.ignore_llm:
            raise Stop("REFUSED", "LlmLetters", EXIT["refused"], f"{len(letters)} brain letters from {STACK} not answered yet",
                       hint="let the llm kernel answer them (keep it running, check again), or add --ignore-llm: "
                            "an answer that comes after this commit makes _stack dirty again")
        warnings.append(f"{len(letters)} brain letters from {STACK} not answered yet (--ignore-llm)")
    else:
        say(f"no letters from {STACK} waiting in the llm kernel {k}")
    # 4. 清單
    files, rms, new = repo.changes()
    if not files and not rms:
        say(f"nothing to commit: {STACK} matches HEAD")
        return {"status": "DONE", "code": "NothingToCommit", "commit": None, "files": [], "rm": [], "warnings": warnings}
    say(f"{STACK}: {len(new)} new, {len(files) - len(new)} changed, {len(rms)} removed")
    # 5. 金鑰樣式
    ok = {os.path.relpath(os.path.realpath(os.path.join(repo.top, p)), repo.top) for p in a.secret_ok}
    hits = scan_secrets(repo, files, ok)
    if hits:
        show_list("secret-like text (file:line: rule; the text is not shown)", hits, lambda x: f"{x[0]}:{x[1]}: {x[2]}")
        raise Stop("REFUSED", "SecretFound", EXIT["refused"], f"{len(hits)} secret-like hits in {len({h[0] for h in hits})} files",
                   files=sorted({h[0] for h in hits}),
                   hint="look at each file; if it is fine, run again with --secret-ok FILE for it; nothing was committed")
    # 6. 交件
    host = socket.gethostname()
    at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    msg = (f"stack-commit leave: {STACK} from {host} at {at}\n\n"
           f"{len(new)} new, {len(files) - len(new)} changed, {len(rms)} removed; picked by {STACK_RULES}, "
           f"after the daemon on {STACK} was shut down. Not pushed.\n")
    with tempfile.NamedTemporaryFile("w", prefix="stack-commit-msg-", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(msg)
        msg_file = f.name
    base = [sys.executable, os.path.join(HERE, "commit_queue.py"), "--repo", repo.top]
    if a.cache:
        base += ["--cache", a.cache]
    base += ["--wait", str(a.wait)]
    cmd = base + ["submit", "--line", a.line, "--stack-commit", "--msg-file", msg_file]
    if files:
        cmd += ["--files"] + files
    if rms:
        cmd += ["--rm"] + rms
    if a.dry_run:
        cmd.append("--dry-run")
    try:
        # 先 claim（別條線 claim 著 _stack 的檔就擋下）；交成了 commit-request 自己放，dry run 與失敗時這裡放
        c = subprocess.run(base + ["claim", "--line", a.line] + files + rms, capture_output=True)
        if c.returncode != 0:
            sys.stderr.write(c.stderr.decode(errors="replace"))
            raise Stop("FAILED", "CommitFailed", EXIT["commit"], f"commit-request claim exit {c.returncode}",
                       hint="another line claims a _stack file; ask it to release, nothing was committed")
        p = subprocess.run(cmd, capture_output=True)
        if a.dry_run or p.returncode != 0:
            subprocess.run(base + ["release", "--line", a.line] + files + rms, capture_output=True)
    finally:
        os.remove(msg_file)
    sys.stderr.write(p.stderr.decode(errors="replace"))
    out = p.stdout.decode(errors="replace").strip().splitlines()
    try:
        res = json.loads(out[-1]) if out else {}
    except ValueError:
        res = {"raw": out[-1]}
    if lock is not None:
        os.close(lock)
    if p.returncode != 0:
        raise Stop("FAILED", "CommitFailed", EXIT["commit"], f"commit-request exit {p.returncode}: {res.get('code')} {res.get('error', '')}".strip(),
                   commit_request=res)
    if a.dry_run:
        say("dry run: nothing committed")
    else:
        say(f"committed {str(res.get('commit'))[:10]}; not pushed: push it yourself when you mean to (it holds the agents' conversations and letters)")
    say(GIT_DANGER)
    return {"status": "DONE", "code": "DryRun" if a.dry_run else "Committed", "commit": res.get("commit"),
            "files": files, "rm": rms, "warnings": warnings + res.get("warnings", []), "commit_request": res}


def arrive(a, repo):
    notes = []
    cleaned = []
    if not os.path.isdir(repo.stack):
        say(f"{STACK} does not exist here yet (nothing pulled, or no leave was ever committed)")
        lock = None
    else:
        lock = need_stopped(repo)
        say(f"no daemon holds {STACK}")
        files, rms, new = repo.changes()
        if files or rms:
            items = [("new " if p in new else "changed ") + p for p in files] + ["removed " + p for p in rms]
            show_list(f"{STACK} differs from HEAD", items)
            raise Stop("REFUSED", "StackDirty", EXIT["refused"],
                       f"{STACK} has {len(files) + len(rms)} changes not in HEAD: it ran on this machine after its last leave, or the leave was not done",
                       hint="decide which side to keep: this machine's (run stack-commit leave here and sort out the other side) "
                            "or HEAD's (put those files back or away by hand); this tool does not choose")
        say(f"{STACK} matches HEAD")
        junk = repo.runtime_files()
        if not junk:
            say("no runtime files left from an earlier run here")
        elif a.no_clean or a.dry_run:
            show_list("runtime files from an earlier run here" + (" (not removed: --no-clean)" if a.no_clean else " (dry run: would remove)"), junk)
        else:
            stack = os.path.realpath(repo.stack)
            for p in junk:
                full = os.path.join(repo.top, p)
                if not inside(os.path.dirname(full), stack):
                    continue
                try:
                    os.remove(full)
                    cleaned.append(p)
                except OSError as e:
                    notes.append(f"could not remove {p}: {e}")
            show_list("removed runtime files from an earlier run here", cleaned)
    check_install(repo, notes)
    check_env(repo, notes)
    check_git_config(repo, notes)
    if not os.path.isdir(os.path.join(repo.top, ROOT_DEF)):
        notes.append(f"{ROOT_DEF} is not in this repo yet")
    for n in notes:
        say("check: " + n)
    if notes:
        say("see the move manual (wf/workflows/dev-env) for the shell setup")
    say(GIT_DANGER)
    start = f"cd {repo.top} && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK aos-exec --stack {STACK} {ROOT_DEF}"
    say("start the tree yourself (not run here):")
    print(f"  {start}", file=sys.stderr)
    if lock is not None:
        os.close(lock)
    return {"status": "DONE", "code": "DryRun" if a.dry_run else "Arrived", "removed": cleaned, "notes": notes, "start": start}


def status(a, repo):
    if not os.path.isdir(repo.stack):
        say(f"{STACK} does not exist")
        return {"status": "DONE", "code": "Status", "running": False, "files": [], "rm": []}
    _, busy = lock_stack(repo.stack, hold=False)
    say("a daemon is running on _stack" if busy else "no daemon holds _stack")
    files, rms, new = repo.changes()
    if files or rms:
        items = [("new " if p in new else "changed ") + p for p in files] + ["removed " + p for p in rms]
        show_list(f"{STACK} differs from HEAD: these exist only on this machine (git clean -fdx, git stash, git reset --hard would lose them)", items)
    else:
        say(f"{STACK} matches HEAD")
    return {"status": "DONE", "code": "Status", "running": bool(busy), "files": files, "rm": rms}


def main(argv):
    ap = argparse.ArgumentParser(prog=PROG, description="move _stack between machines: leave (commit what should travel) and arrive (check before starting); see the file header")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lv = sub.add_parser("leave", help="after shutdown: commit the _stack files that should travel (not pushed)")
    lv.add_argument("--leave-dirty", action="store_true", help="go on although files outside _stack are not committed")
    lv.add_argument("--ignore-llm", action="store_true", help="go on although the llm kernel still holds letters from _stack")
    lv.add_argument("--secret-ok", action="append", default=[], metavar="FILE", help="a file you checked: skip the secret scan for it (repeatable)")
    lv.add_argument("--dry-run", action="store_true", help="do every check and pass --dry-run to commit-request")
    lv.add_argument("--line", default=DEFAULT_LINE, help=f"line name for commit-request (default {DEFAULT_LINE})")
    lv.add_argument("--wait", type=float, default=120, help="seconds to wait for the commit queue")
    lv.add_argument("--cache", help="commit-request cache folder (tests)")
    ar = sub.add_parser("arrive", help="before and after git pull, before starting the tree: check and clean")
    ar.add_argument("--no-clean", action="store_true", help="do not remove runtime files left from an earlier run here")
    ar.add_argument("--dry-run", action="store_true", help="only list the runtime files that would be removed")
    sub.add_parser("status", help="read only: is a daemon running, what in _stack is not committed")
    for sp in (lv, ar, sub.choices["status"]):
        sp.add_argument("--repo", default=os.path.dirname(os.path.dirname(HERE)), help="the repo (default: the one this tool is in)")
    a = ap.parse_args(argv)
    try:
        repo = Repo(a.repo)
        res = {"leave": leave, "arrive": arrive, "status": status}[a.cmd](a, repo)
        code = 0
    except Stop as e:
        say(f"error: {e.code} {e.msg}")
        if e.extra.get("hint"):
            say("hint: " + e.extra["hint"])
        res = dict({"status": e.status, "code": e.code, "error": e.msg}, **e.extra)
        code = e.exit_code
    print(json.dumps(res, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
