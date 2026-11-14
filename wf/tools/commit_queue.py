#!/usr/bin/env python3
"""commit_queue — 多條線共用一個工作樹時的 commit 排隊：申請者自己拿鎖當場做，在 repo 外的快取樹組 commit（HEAD＋這次的檔＋共用索引檔操作＋index_gen 生成物），CAS 推進 main，再補回共用 index 與工作樹。

  commit-request submit --line L [--files F…] [--rm F…] --msg-file M [--op JSON]… [--ops-file J]
                        [--dry-run] [--keep-claim] [--wait S] [--repo R] [--cache C]
  commit-request claim   --line L F…            開工時宣告「這些檔我在改」；被別條線 claim 著就失敗
  commit-request release --line L (F…|--all)    放掉自己的 claim；--force F… 不分是誰（頂層用）
  commit-request claims                         列出所有 claim
  commit-request doctor [--repair]              鎖、未完成的日誌、claim、共用 index 裡 staged 的、三份共用檔在工作樹的差異；--repair 照日誌補完

共用索引檔不收整檔，只收操作（--op 給 JSON，可重複；--ops-file 給 JSON 陣列）：
  {"op": "day_upsert", "date": "2026-11-14", "name": "x", "link": "x.md", "summary": "…"}   日索引表，以連結 link 認列，有就換、沒有加表尾；那天還沒有日索引就用範本開一份
  {"op": "month_bump", "date": "2026-11-14", "segment": "…"}   月索引那天的列：摘要（以；切段）沒有完全相同的這段才「份數加一、尾加；segment」；沒有那天的列就照日期插入
  {"op": "month_set", "date": "2026-11-14", "count": 10}   月索引那天的列：份數直接設成 count（非負整數；份數＝那天日索引的列數），摘要不動；已經是這個數就什麼都不改；沒有那天的列＝套不上
  {"op": "log_upsert", "key": "- **open｜主題", "text": "整行"}   wf/SESSION-LOG.md「## 最新進度」段，行首等於 key 的那行換掉，沒有就加段尾
  {"op": "log_delete", "key": "- **open｜主題"}                  刪那一行
路徑：--files／--rm 的相對路徑從 repo 根算（不管 cwd）；--msg-file、--ops-file 從 cwd 算。
結果：stderr 給人看，stdout 最後一行 JSON {"status": DONE|BLOCKED|FAILED, "code", "commit", "files", "generated", "warnings", "hint"}。
exit：0 DONE、1 內部錯誤、2 BLOCKED、3 申請不合格、4 生成器失敗、5 忙碌（等鎖逾時）、6 repo 狀態異常。
設計與測試：proto8/thinking/2026-11/14/commit-queue-1114.md。純標準庫；不改訊息、不開分支、不 push、不刪共用工作樹裡的非生成檔。
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
PROG = "commit-request"
REF = "refs/heads/main"
GEN_PREFIX = "wf/knowledge/code-map/"
GEN_NAME = "_index.json"
LOG_SECTION = "## 最新進度"
SESSION_LOG = "wf/SESSION-LOG.md"
SHARED_RE = re.compile(r"proto8/thinking/\d{4}-\d\d/(\d\d/)?README\.md")
STALE_MIN = 120          # claim 超過這麼多分鐘，擋下時標 stale
DAY_TEMPLATE = """# proto8 討論紀錄：{date}

← [{month}](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
"""
EXIT = {"DONE": 0, "internal": 1, "BLOCKED": 2, "invalid": 3, "generator": 4, "busy": 5, "repo": 6}


class Stop(Exception):
    """結束這次處理：status、code、exit、訊息、附帶欄位。"""

    def __init__(self, status, code, exit_code, msg, **extra):
        super().__init__(msg)
        self.status, self.code, self.exit_code, self.msg, self.extra = status, code, exit_code, msg, extra


def say(msg):
    print(f"{PROG}: {msg}", file=sys.stderr)


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def is_generated(path):
    return os.path.basename(path) == GEN_NAME or path.startswith(GEN_PREFIX)


# ---------------------------------------------------------------- git

class Git:
    """兩種環境：shared＝共用工作樹與共用 index；cache＝同一個 .git，但工作樹與 index 是快取的。"""

    def __init__(self, repo, cache):
        self.repo, self.cache = repo, cache
        self.gitdir = os.path.join(repo, ".git")
        self.tree = os.path.join(cache, "tree")
        self.index = os.path.join(cache, "index")
        base = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env_shared = dict(base)
        self.env_cache = dict(base, GIT_DIR=self.gitdir, GIT_WORK_TREE=self.tree, GIT_INDEX_FILE=self.index)

    def run(self, args, where="shared", data=None, check=True):
        env = self.env_shared if where == "shared" else self.env_cache
        cwd = self.repo if where == "shared" else self.tree
        p = subprocess.run(["git"] + args, cwd=cwd, env=env, input=data, capture_output=True)
        if check and p.returncode != 0:
            raise Stop("FAILED", "GitFailed", EXIT["internal"],
                       f"git {' '.join(args[:3])}…: {p.stderr.decode(errors='replace').strip()}")
        return p

    def out(self, args, where="shared", data=None):
        return self.run(args, where, data).stdout.decode()

    def tree_entries(self, commit, paths):
        """{path: (mode, sha)}，只含 commit 裡有的。"""
        if not paths:
            return {}
        res = {}
        raw = self.run(["ls-tree", "-z", "--full-tree", commit, "--"] + list(paths)).stdout.decode()
        for rec in raw.split("\0"):
            if not rec:
                continue
            meta, path = rec.split("\t", 1)
            mode, typ, sha = meta.split()
            if typ == "blob":
                res[path] = (mode, sha)
        return res

    def blob_of_file(self, full, path, write):
        """工作樹檔 → (mode, sha)。符號連結照 git 的收法。"""
        if os.path.islink(full):
            data, mode = os.readlink(full).encode(), "120000"
            args = ["hash-object", "--stdin", "--no-filters"]
        else:
            with open(full, "rb") as f:
                data = f.read()
            mode = "100755" if os.access(full, os.X_OK) else "100644"
            args = ["hash-object", "--stdin", "--path", path]
        if write:
            args.insert(1, "-w")
        return mode, self.out(args, data=data).strip()

    def cat(self, sha):
        return self.run(["cat-file", "blob", sha]).stdout


# ---------------------------------------------------------------- 共用索引檔的操作（全部冪等）

def day_path(date):
    return f"proto8/thinking/{date[:7]}/{date[8:10]}/README.md"


def month_path(date):
    return f"proto8/thinking/{date[:7]}/README.md"


def check_op(op):
    kind = op.get("op")
    need = {"day_upsert": ("date", "name", "link", "summary"), "month_bump": ("date", "segment"), "month_set": ("date",),
            "log_upsert": ("key", "text"), "log_delete": ("key",)}
    if kind not in need:
        raise Stop("FAILED", "OpBad", EXIT["invalid"], f"unknown op {kind!r} (day_upsert, month_bump, month_set, log_upsert, log_delete)")
    if kind == "month_set" and (isinstance(op.get("count"), bool) or not isinstance(op.get("count"), int) or op["count"] < 0):
        raise Stop("FAILED", "OpBad", EXIT["invalid"], "month_set: count must be a non-negative integer")
    for k in need[kind]:
        if not isinstance(op.get(k), str) or not op[k].strip():
            raise Stop("FAILED", "OpBad", EXIT["invalid"], f"{kind}: {k} missing or empty")
    if "date" in op and not re.fullmatch(r"\d{4}-\d\d-\d\d", op["date"]):
        raise Stop("FAILED", "OpBad", EXIT["invalid"], f"{kind}: date must be YYYY-MM-DD")
    for k in ("name", "link", "summary", "segment"):
        if k in op and ("|" in op[k] or "\n" in op[k]):
            raise Stop("FAILED", "OpBad", EXIT["invalid"], f"{kind}: {k} must not contain '|' or a newline (use ｜)")
    for k in ("key", "text"):
        if k in op and "\n" in op[k]:
            raise Stop("FAILED", "OpBad", EXIT["invalid"], f"{kind}: {k} must be one line")
    if kind == "log_upsert" and not op["text"].startswith(op["key"]):
        raise Stop("FAILED", "OpBad", EXIT["invalid"], "log_upsert: text must start with key")
    return kind


def op_target(op):
    return SESSION_LOG if op["op"].startswith("log_") else (day_path(op["date"]) if op["op"] == "day_upsert" else month_path(op["date"]))


def apply_op(text, op):
    """text → (新 text, 警告或 None)。套不上丟 ValueError。"""
    lines = text.split("\n")
    kind = op["op"]
    if kind == "day_upsert":
        new = f"| [{op['name']}]({op['link']}) | {op['summary']} |"
        rows = [i for i, ln in enumerate(lines) if ln.startswith("|")]
        if not rows:
            raise ValueError("no table in day index")
        pat = re.compile(r"^\| \[[^\]]*\]\(" + re.escape(op["link"]) + r"\) \|")
        hit = [i for i in rows if pat.match(lines[i])]
        if len(hit) > 1:
            raise ValueError(f"{len(hit)} rows link to {op['link']}")
        if hit:
            lines[hit[0]] = new
        else:
            lines.insert(rows[-1] + 1, new)
        return "\n".join(lines), None
    if kind == "month_bump":
        date, seg = op["date"], op["segment"]
        key = f"| [{date}]({date[8:10]}/README.md) |"
        pat = re.compile(r"^\| \[(\d{4}-\d\d-\d\d)\]\(\d\d/README\.md\) \|")
        rows = [(i, pat.match(ln).group(1)) for i, ln in enumerate(lines) if pat.match(ln)]
        hit = [i for i, d in rows if d == date]
        if len(hit) > 1:
            raise ValueError(f"{len(hit)} rows for {date}")
        if hit:
            cells = lines[hit[0]].strip()[1:-1].split("|", 2)
            if len(cells) != 3:
                raise ValueError(f"row for {date} is not 3 cells")
            count, summary = cells[1].strip(), cells[2].strip()
            if seg.strip() in [x.strip() for x in summary.split("；")]:
                return text, None
            if not count.isdigit():
                raise ValueError(f"count of {date} is not a number: {count!r}")
            lines[hit[0]] = f"{key} {int(count) + 1} | {summary}；{seg} |"
        else:
            if not rows:
                raise ValueError("no day rows in month index")
            after = [i for i, d in rows if d < date]
            at = (after[-1] + 1) if after else rows[0][0]
            lines.insert(at, f"{key} 1 | {seg} |")
        return "\n".join(lines), None
    if kind == "month_set":
        date = op["date"]
        key = f"| [{date}]({date[8:10]}/README.md) |"
        hit = [i for i, ln in enumerate(lines) if ln.startswith(key)]
        if len(hit) != 1:
            raise ValueError(f"{len(hit)} rows for {date} in month index (month_set needs exactly one)")
        cells = lines[hit[0]].strip()[1:-1].split("|", 2)
        if len(cells) != 3:
            raise ValueError(f"row for {date} is not 3 cells")
        if cells[1].strip() == str(op["count"]):
            return text, None
        lines[hit[0]] = f"{key} {op['count']} | {cells[2].strip()} |"
        return "\n".join(lines), None
    # log_upsert / log_delete
    try:
        start = lines.index(LOG_SECTION)
    except ValueError:
        raise ValueError(f"no '{LOG_SECTION}' section in {SESSION_LOG}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    hit = [i for i in range(start + 1, end) if lines[i].startswith(op["key"])]
    if len(hit) > 1:
        raise ValueError(f"{len(hit)} lines start with {op['key']!r}")
    if kind == "log_delete":
        if not hit:
            return text, f"log_delete: no line starts with {op['key']!r}"
        del lines[hit[0]]
        return "\n".join(lines), None
    if hit:
        lines[hit[0]] = op["text"]
    else:
        bullets = [i for i in range(start + 1, end) if lines[i].startswith("- **")]
        at = (bullets[-1] + 1) if bullets else start + 1
        lines.insert(at, op["text"])
    return "\n".join(lines), None


def apply_ops(text, ops):
    warns = []
    for op in ops:
        text, w = apply_op(text, op)
        if w:
            warns.append(w)
    return text, warns


# ---------------------------------------------------------------- 快取夾：鎖、claim、日誌

def default_cache(repo):
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "aos-commit-queue", hashlib.sha1(repo.encode()).hexdigest()[:10])


class Lock:
    def __init__(self, cache, line, wait):
        self.path = os.path.join(cache, "lock")
        self.holder = os.path.join(cache, "holder.json")
        self.line, self.wait, self.fd = line, wait, None

    def __enter__(self):
        self.fd = open(self.path, "a+")
        deadline = time.time() + self.wait
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    who = read_json(self.holder, {})
                    raise Stop("FAILED", "Busy", EXIT["busy"], f"queue busy for {self.wait}s; holder {who}",
                               holder=who, hint="retry later")
                time.sleep(0.2)
        write_json(self.holder, {"line": self.line, "pid": os.getpid(), "since": now()})
        return self

    def __exit__(self, *a):
        try:
            write_json(self.holder, {})
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            self.fd.close()


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, obj):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def write_file(full, data, mode="100644"):
    """先寫暫存再改名；mode 照 git。"""
    os.makedirs(os.path.dirname(full), exist_ok=True)
    tmp = f"{full}.cq-tmp.{os.getpid()}"
    if mode == "120000":
        os.symlink(data.decode(), tmp)
    else:
        with open(tmp, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o755 if mode == "100755" else 0o644)
    os.replace(tmp, full)


def test_hook(stage):
    """只給測試用：CQ_TEST_DIE_AT=<stage> 在那一刻硬退；CQ_TEST_RUN_AT=<stage> 在那一刻跑 CQ_TEST_CMD。"""
    if os.environ.get("CQ_TEST_RUN_AT") == stage and os.environ.get("CQ_TEST_CMD"):
        subprocess.run(["bash", "-c", os.environ["CQ_TEST_CMD"]], check=False)
    if os.environ.get("CQ_TEST_DIE_AT") == stage:
        os._exit(9)


# ---------------------------------------------------------------- 處理

class Queue:
    def __init__(self, repo, cache):
        self.repo = os.path.realpath(repo)
        self.cache = os.path.realpath(cache or default_cache(self.repo))
        os.makedirs(self.cache, exist_ok=True)
        if self.cache == self.repo or self.cache.startswith(self.repo + os.sep):
            raise Stop("FAILED", "CacheBad", EXIT["invalid"], "cache folder must be outside the repo")
        self.git = Git(self.repo, self.cache)
        self.journal = os.path.join(self.cache, "journal.json")
        self.claims_path = os.path.join(self.cache, "claims.json")
        self.warnings = []

    # -- 共用
    def claims(self):
        return read_json(self.claims_path, {})

    def head(self):
        g = self.git
        sym = g.run(["symbolic-ref", "-q", "HEAD"], check=False).stdout.decode().strip()
        if sym != REF:
            raise Stop("FAILED", "RepoState", EXIT["repo"], f"HEAD is {sym or 'detached'}, not {REF}")
        for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "BISECT_LOG"):
            if os.path.exists(os.path.join(g.gitdir, marker)):
                raise Stop("FAILED", "RepoState", EXIT["repo"], f"{marker} present: finish or abort it first")
        return g.out(["rev-parse", REF]).strip()

    def norm(self, p):
        """相對路徑一律從 repo 根算（不管 cwd 在哪，例如 wf/temp/<線>）；連結本身不解開。"""
        ab = p if os.path.isabs(p) else os.path.join(self.repo, p)
        full = os.path.join(os.path.realpath(os.path.dirname(ab)), os.path.basename(ab))
        if not full.startswith(self.repo + os.sep):
            raise Stop("FAILED", "PathBad", EXIT["invalid"], f"{p}: outside the repo")
        rel = os.path.relpath(full, self.repo)
        if rel.startswith(".git" + os.sep) or rel == ".git":
            raise Stop("FAILED", "PathBad", EXIT["invalid"], f"{p}: inside .git")
        return rel

    # -- 補回（共用工作樹先、共用 index 後）：日誌在就照日誌做；可重複
    def finish(self, j):
        g = self.git
        entries = j["entries"]
        paths = list(entries)
        cur_main = g.out(["rev-parse", REF]).strip()
        if cur_main != j["new"]:
            # main 已經又往前了：只補 main 上跟 NEW 一樣的那些路徑，其餘交給後來那個 commit
            now_ent = g.tree_entries(cur_main, paths)
            paths = [p for p in paths if (now_ent.get(p) and list(now_ent[p])) == entries[p] or
                     (entries[p] is None and p not in now_ent)]
            self.warnings.append(f"main is already past {j['new'][:10]}; finished only the paths it still has")
        # 1) 共用工作樹
        for path in paths:
            if path not in j["generated"] and path not in j["shared"]:
                continue                       # 申請者自己的檔：工作樹本來就是這份
            full = os.path.join(self.repo, path)
            ent = entries[path]
            if path in j["generated"]:
                if ent is None:
                    if os.path.lexists(full):
                        os.remove(full)        # 生成器刪掉的生成物，工作樹跟著刪
                elif not (os.path.lexists(full) and list(g.blob_of_file(full, path, False)) == ent):
                    write_file(full, g.cat(ent[1]), ent[0])
                continue
            old = j["shared_old"].get(path)
            cur = list(g.blob_of_file(full, path, False)) if os.path.exists(full) else None
            if cur == ent:
                continue
            if cur is None or (old and cur == list(old)):
                write_file(full, g.cat(ent[1]), ent[0])
                continue
            # 工作樹這份有別人沒 commit 的字：三方合併（工作樹、OLD、NEW），衝突就退回「在工作樹那份上重套 ops」
            tmpd = os.path.join(self.cache, "merge")
            os.makedirs(tmpd, exist_ok=True)
            fo, fn = os.path.join(tmpd, "old"), os.path.join(tmpd, "new")
            with open(fo, "wb") as f:
                f.write(g.cat(old[1]) if old else b"")
            with open(fn, "wb") as f:
                f.write(g.cat(ent[1]))
            m = subprocess.run(["git", "merge-file", "-p", full, fo, fn], env=g.env_shared, capture_output=True)
            try:
                if m.returncode == 0:
                    text = m.stdout.decode("utf-8")
                else:
                    with open(full, encoding="utf-8") as f:
                        text = f.read()
                text2, _ = apply_ops(text, j["shared"][path])
                write_file(full, text2.encode(), cur[0])
                self.warnings.append(f"{path}: working copy had uncommitted edits by someone; kept them and merged this commit in"
                                     + ("" if m.returncode == 0 else " (re-applied the ops; 3-way merge had conflicts)"))
            except ValueError as e:
                self.warnings.append(f"{path}: could not bring this commit into the working copy ({e}); left it as is")
        # 2) 共用 .git/index：一次寫完，再 refresh 填回 stat
        if paths:
            lines = [f"0 {'0' * 40}\t{p}" if entries[p] is None else f"{entries[p][0]} {entries[p][1]}\t{p}" for p in paths]
            for _ in range(50):
                p = g.run(["update-index", "-z", "--index-info"], data=("\0".join(lines) + "\0").encode(), check=False)
                if p.returncode == 0:
                    break
                if b"index.lock" not in p.stderr:
                    raise Stop("FAILED", "GitFailed", EXIT["internal"], f"update-index: {p.stderr.decode().strip()}")
                time.sleep(0.2)
            else:
                self.warnings.append("shared .git/index is locked by someone else; run `commit-request doctor --repair` later")
                return False
            # 填回 stat；不能帶路徑——`update-index <路徑>` 會把工作樹內容 stage 進去（工作樹上別人的字就被 stage 了）
            g.run(["update-index", "-q", "--refresh"], check=False)
        return True

    def repair(self):
        j = read_json(self.journal, None)
        if not j:
            return None
        if self.git.run(["merge-base", "--is-ancestor", j["new"], REF], check=False).returncode != 0:
            os.remove(self.journal)            # 死在 update-ref 成功之前：什麼都沒落地
            return None
        self.after_ref(j)
        if self.finish(j):
            os.remove(self.journal)
            self.warnings.append(f"finished an earlier interrupted commit {j['new'][:10]} ({j['line']})")
        return j["new"]

    def after_ref(self, j):
        """update-ref 成功後馬上做、可重複：放 claim、寫 log.jsonl。"""
        if j.get("released"):
            return
        cl = self.claims()
        if not j.get("keep_claim"):
            for f in j["own"]:
                if cl.get(f, {}).get("line") == j["line"]:
                    del cl[f]
            write_json(self.claims_path, cl)
        with open(os.path.join(self.cache, "log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now(), "line": j["line"], "commit": j["new"], "paths": sorted(j["entries"])},
                               ensure_ascii=False) + "\n")
        j["released"] = True
        write_json(self.journal, j)

    # -- 快取樹
    def align(self, old):
        g = self.git
        assert os.path.realpath(g.tree) != self.repo
        os.makedirs(g.tree, exist_ok=True)
        if not os.path.exists(g.index):
            g.run(["read-tree", old], "cache")
            g.run(["checkout-index", "-a", "-f"], "cache")
        else:
            g.run(["read-tree", "--reset", "-u", old], "cache")
        g.run(["update-index", "-q", "--refresh"], "cache", check=False)
        dirty = [p for p in g.out(["diff-files", "--name-only", "-z"], "cache").split("\0") if p]
        if dirty:
            g.run(["checkout-index", "-f", "-z", "--stdin"], "cache", data="\0".join(dirty).encode())
        g.run(["clean", "-fdxq"], "cache")

    # -- 申請
    def submit(self, a, ops):
        g = self.git
        msg_file = os.path.abspath(a.msg_file)
        if not os.path.isfile(msg_file) or not open(msg_file, "rb").read().strip():
            raise Stop("FAILED", "MessageBad", EXIT["invalid"], f"{a.msg_file}: missing or empty")
        files = [self.norm(p) for p in a.files]
        rms = [self.norm(p) for p in a.rm]
        if len(set(files + rms)) != len(files + rms):
            raise Stop("FAILED", "PathBad", EXIT["invalid"], "a path is listed twice")
        if not files and not rms and not ops:
            raise Stop("FAILED", "EmptyRequest", EXIT["invalid"], "nothing to commit (give --files, --rm or --op)")
        for op in ops:
            check_op(op)
        targets = {}
        for op in ops:
            targets.setdefault(op_target(op), []).append(op)
        bad = []
        for p in files:
            full = os.path.join(self.repo, p)
            if not os.path.lexists(full):
                bad.append(f"{p}: does not exist (to delete it use --rm)")
            elif os.path.isdir(full) and not os.path.islink(full):
                bad.append(f"{p}: is a folder; list files one by one")
            elif is_generated(p):
                bad.append(f"{p}: generated file; the queue regenerates it")
            elif p == SESSION_LOG or SHARED_RE.fullmatch(p):
                bad.append(f"{p}: shared index file; send --op instead of the file")
        if bad:
            raise Stop("FAILED", "RequestBad", EXIT["invalid"], "; ".join(bad))
        # 等鎖之前先拍一次快照：等鎖期間又被改，就擋下（交出的是半成品）
        pre = {p: g.blob_of_file(os.path.join(self.repo, p), p, True) for p in files}
        with Lock(self.cache, a.line, a.wait):
            self.repair()
            for attempt in range(3):
                old = self.head()
                res = self.build(a, files, rms, targets, old, msg_file, pre)
                if a.dry_run or res.get("status") != "RETRY":
                    return res
                self.warnings.append(f"main moved during processing (attempt {attempt + 1}); redone on the new HEAD")
            raise Stop("FAILED", "MainMoving", EXIT["repo"], "main kept moving; 3 attempts failed")

    def held_by_others(self, line, paths):
        cl = self.claims()
        out = {}
        for p in paths:
            c = cl.get(p)
            if c and c["line"] != line:
                age = None
                try:
                    age = int((datetime.datetime.now().astimezone() - datetime.datetime.fromisoformat(c["at"])).total_seconds() // 60)
                except (ValueError, TypeError):
                    pass
                out[p] = dict(c, minutes=age, stale=bool(age is not None and age >= STALE_MIN))
        return out

    @staticmethod
    def held_msg(held):
        return "; ".join(f"{p} is claimed by {c['line']} since {c['at']} ({c['minutes']} min"
                         + (", stale: the top level may `release --force`" if c["stale"] else "") + ")"
                         for p, c in held.items())

    def build(self, a, files, rms, targets, old, msg_file, pre):
        g = self.git
        head = g.tree_entries(old, files + rms + list(targets))
        # 驗：改動、刪除、忽略、claim
        bad = []
        for p in rms:
            if p not in head:
                bad.append(f"{p}: --rm but not in HEAD")
            elif os.path.lexists(os.path.join(self.repo, p)):
                bad.append(f"{p}: --rm but still in the working tree (delete it yourself first)")
        if bad:
            raise Stop("FAILED", "RequestBad", EXIT["invalid"], "; ".join(bad))
        new_files = [p for p in files if p not in head]
        if new_files:
            ign = g.run(["check-ignore", "--stdin", "-z"], data="\0".join(new_files).encode(), check=False).stdout.decode()
            ign = [p for p in ign.split("\0") if p]
            if ign:
                raise Stop("FAILED", "RequestBad", EXIT["invalid"], f"ignored by .gitignore: {ign}")
        snap = {p: g.blob_of_file(os.path.join(self.repo, p), p, True) for p in files}
        moved = [p for p in files if snap[p] != pre[p]]
        if moved:
            raise Stop("BLOCKED", "ChangedWhileWaiting", EXIT["BLOCKED"], f"changed while waiting for the queue: {moved}",
                       files=moved, hint="finish editing, then submit again")
        same = [p for p in files if head.get(p) == snap[p]]
        if same:
            if len(same) == len(files) and not rms and not targets and \
                    g.out(["log", "-1", "--format=%B", old]).strip() == open(msg_file, encoding="utf-8", errors="replace").read().strip():
                self.warnings.append(f"already committed at {old[:10]} (same files and message); nothing done")
                return {"status": "DONE", "code": "AlreadyCommitted", "commit": old, "files": files, "generated": []}
            raise Stop("BLOCKED", "Unchanged", EXIT["BLOCKED"], f"no change against HEAD: {same}", files=same,
                       hint="drop them from --files")
        held = self.held_by_others(a.line, files + rms)
        if held:
            raise Stop("BLOCKED", "Claimed", EXIT["BLOCKED"], self.held_msg(held), files=sorted(held), holder=held,
                       hint="ask that line (aos mail) to submit or release first; do not commit over it")
        claims = self.claims()
        unclaimed = [p for p in files + rms if p not in claims]
        if unclaimed:
            self.warnings.append(f"not claimed: {unclaimed}")

        # 組：快取樹＝OLD＋清單檔＋共用檔操作
        self.align(old)
        info = []
        for p in files:
            mode, sha = snap[p]
            write_file(os.path.join(g.tree, p), g.cat(sha), mode)
            info.append(f"{mode} {sha}\t{p}")
        for p in rms:
            full = os.path.join(g.tree, p)
            if os.path.lexists(full):
                os.remove(full)
            info.append(f"0 {'0' * 40}\t{p}")
        shared_old = {}
        for path, ops in targets.items():
            if path in head:
                shared_old[path] = head[path]
                text, mode = g.cat(head[path][1]).decode("utf-8"), head[path][0]
            elif path.endswith("/README.md") and path.count("/") == 4:      # 新的一天：用範本開日索引
                date = targets[path][0]["date"]
                text, mode = DAY_TEMPLATE.format(date=date, month=date[:7]), "100644"
            else:
                raise Stop("FAILED", "OpBad", EXIT["invalid"], f"{path} not in HEAD")
            try:
                text2, w = apply_ops(text, ops)
            except ValueError as e:
                raise Stop("BLOCKED", "OpFailed", EXIT["BLOCKED"], f"{path}: {e}", files=[path])
            self.warnings += w
            if path in head and text2 == text:
                continue
            sha = g.out(["hash-object", "-w", "--stdin", "--path", path], data=text2.encode()).strip()
            write_file(os.path.join(g.tree, path), text2.encode(), mode)
            info.append(f"{mode} {sha}\t{path}")
        if info:
            g.run(["update-index", "--index-info"], "cache", data=("\n".join(info) + "\n").encode())

        # 生成物：用快取樹裡那支 index_gen（＝HEAD＋本次的版本）
        gen = subprocess.run([sys.executable, os.path.join(g.tree, "wf/tools/index_gen.py"), "--root", g.tree, "--apply", "--quiet"],
                             cwd=g.tree, env=g.env_cache, capture_output=True)
        if gen.returncode != 0:
            raise Stop("FAILED", "GeneratorFailed", EXIT["generator"], gen.stderr.decode(errors="replace").strip(),
                       hint="fix the header lines it names, then submit again; nothing was committed")
        st = g.out(["status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames"], "cache")
        generated, outside = [], []
        for rec in [r for r in st.split("\0") if r]:
            code, path = rec[:2], rec[3:]
            if code[1] == " ":          # 只看工作樹 vs 快取 index（第一欄是本次放進去的）
                continue
            (generated if is_generated(path) else outside).append(path)
        if outside:
            raise Stop("FAILED", "GeneratorOutside", EXIT["generator"], f"index_gen changed non-generated files: {outside}")
        gen_info = []
        for path in generated:
            full = os.path.join(g.tree, path)
            if os.path.lexists(full):
                mode, sha = g.blob_of_file(full, path, True)
                gen_info.append(f"{mode} {sha}\t{path}")
            else:
                gen_info.append(f"0 {'0' * 40}\t{path}")
        if gen_info:
            g.run(["update-index", "--index-info"], "cache", data=("\n".join(gen_info) + "\n").encode())
        test_hook("before_commit_tree")
        tree = g.out(["write-tree"], "cache").strip()
        if tree == g.out(["rev-parse", old + "^{tree}"]).strip():
            raise Stop("BLOCKED", "NothingToCommit", EXIT["BLOCKED"], "the result equals HEAD")
        new = g.out(["commit-tree", tree, "-p", old, "-F", msg_file], "cache").strip()
        # 這次真正變了哪些路徑：以 diff-tree 為準
        entries = {}
        raw = g.out(["diff-tree", "-r", "-z", "--no-renames", "--no-commit-id", old, new]).split("\0")
        for i in range(0, len(raw) - 1, 2):
            meta, path = raw[i], raw[i + 1]
            if not meta:
                break
            _, nmode, _, nsha, status = meta[1:].split()
            entries[path] = None if status == "D" else [nmode, nsha]
        gen_paths = sorted(p for p in entries if is_generated(p))
        result = {"status": "DONE", "code": "Committed", "commit": new,
                  "files": sorted(p for p in entries if not is_generated(p)), "generated": gen_paths}
        if a.dry_run:
            say("dry run, nothing committed:\n" + g.out(["diff", "--stat", old, new]))
            result.update(code="DryRun", commit=None, would_be=new)
            return result

        test_hook("before_update_ref")
        j = {"line": a.line, "old": old, "new": new, "entries": entries, "generated": gen_paths,
             "shared": {p: targets[p] for p in targets if p in entries},
             "shared_old": {p: shared_old.get(p) for p in targets if p in entries},
             "own": files + rms, "keep_claim": a.keep_claim, "at": now()}
        write_json(self.journal, j)
        p = g.run(["update-ref", "-m", f"commit-queue {a.line}", REF, new, old], check=False)
        if p.returncode != 0:
            os.remove(self.journal)
            return {"status": "RETRY"}
        self.after_ref(j)
        test_hook("after_update_ref")
        if self.finish(j):
            os.remove(self.journal)
        for f in files:
            full = os.path.join(self.repo, f)
            if os.path.lexists(full) and g.blob_of_file(full, f, False) != tuple(snap[f]):
                self.warnings.append(f"{f}: changed again after it was taken for the commit")
        say(f"committed {new[:10]} for {a.line}: {len(result['files'])} files + {len(gen_paths)} generated")
        return result

    # -- claim
    def claim(self, line, paths, wait):
        rel = [self.norm(p) for p in paths]
        with Lock(self.cache, line, wait):
            held = self.held_by_others(line, rel)
            if held:
                raise Stop("BLOCKED", "Claimed", EXIT["BLOCKED"], self.held_msg(held),
                           files=sorted(held), holder=held, hint="mail that line to coordinate; nothing was claimed")
            cl = self.claims()
            for p in rel:
                cl[p] = {"line": line, "at": now()}
            write_json(self.claims_path, cl)
        return {"status": "DONE", "code": "Claimed", "files": rel}

    def release(self, line, paths, all_, force, wait):
        with Lock(self.cache, line or "release", wait):
            cl = self.claims()
            if all_:
                rel = [p for p, c in cl.items() if c["line"] == line]
            else:
                rel = [self.norm(p) for p in paths]
            done, skipped = [], []
            for p in rel:
                if p in cl and (force or cl[p]["line"] == line):
                    del cl[p]
                    done.append(p)
                elif p in cl:
                    skipped.append(f"{p} ({cl[p]['line']})")
            write_json(self.claims_path, cl)
        if skipped:
            self.warnings.append(f"claimed by other lines, not released: {skipped}")
        return {"status": "DONE", "code": "Released", "files": done}

    def doctor(self, repair, wait):
        g = self.git
        rep = {"cache": self.cache, "holder": read_json(os.path.join(self.cache, "holder.json"), {}),
               "journal": read_json(self.journal, None), "claims": self.claims()}
        rep["staged_in_shared_index"] = [p for p in g.out(["diff", "--cached", "--name-only", "-z", REF]).split("\0") if p]
        shared = [SESSION_LOG] + [p for p in g.out(["ls-files", "-z", "--", "proto8/thinking/*/README.md",
                                                     "proto8/thinking/*/*/README.md"]).split("\0") if p]
        rep["shared_files_dirty"] = [p for p in g.out(["diff", "--name-only", "-z", REF, "--"] + shared).split("\0") if p]
        if repair:
            with Lock(self.cache, "doctor", wait):
                rep["repaired"] = self.repair()
        return {"status": "DONE", "code": "Doctor", "report": rep}


def main(argv):
    ap = argparse.ArgumentParser(prog=PROG, description="commit 排隊（見檔頭）")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(HERE)))
    ap.add_argument("--cache")
    ap.add_argument("--wait", type=float, default=120)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--line", required=True)
    s.add_argument("--files", nargs="*", default=[])
    s.add_argument("--rm", nargs="*", default=[])
    s.add_argument("--msg-file", required=True)
    s.add_argument("--op", action="append", default=[])
    s.add_argument("--ops-file")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--keep-claim", action="store_true")
    c = sub.add_parser("claim")
    c.add_argument("--line", required=True)
    c.add_argument("paths", nargs="+")
    r = sub.add_parser("release")
    r.add_argument("--line")
    r.add_argument("--all", action="store_true")
    r.add_argument("--force", action="store_true")
    r.add_argument("paths", nargs="*")
    sub.add_parser("claims")
    d = sub.add_parser("doctor")
    d.add_argument("--repair", action="store_true")
    for sp in (s, c, r, d):       # 讓 --wait/--repo/--cache 也能寫在子指令後面
        sp.add_argument("--repo", dest="repo_", default=None)
        sp.add_argument("--cache", dest="cache_", default=None)
        sp.add_argument("--wait", dest="wait_", type=float, default=None)
    a = ap.parse_args(argv)
    repo = getattr(a, "repo_", None) or a.repo
    cache = getattr(a, "cache_", None) or a.cache
    wait = getattr(a, "wait_", None) or a.wait
    a.wait = wait
    q = None
    try:
        q = Queue(repo, cache)
        if a.cmd == "submit":
            ops = []
            for o in a.op:
                ops.append(json.loads(o))
            if a.ops_file:
                with open(a.ops_file, encoding="utf-8") as f:
                    more = json.load(f)
                ops += more if isinstance(more, list) else [more]
            res = q.submit(a, ops)
        elif a.cmd == "claim":
            res = q.claim(a.line, a.paths, wait)
        elif a.cmd == "release":
            if not a.line and not a.force:
                raise Stop("FAILED", "ArgumentsBad", EXIT["invalid"], "give --line (or --force)")
            res = q.release(a.line, a.paths, a.all, a.force, wait)
        elif a.cmd == "claims":
            res = {"status": "DONE", "code": "Claims", "claims": q.claims()}
        else:
            res = q.doctor(a.repair, wait)
        code = 0
    except Stop as e:
        say(f"{e.status} {e.code}: {e.msg}")
        res = dict({"status": e.status, "code": e.code, "error": e.msg}, **e.extra)
        code = e.exit_code
    except json.JSONDecodeError as e:
        say(f"FAILED OpBad: --op/--ops-file is not JSON: {e}")
        res, code = {"status": "FAILED", "code": "OpBad", "error": str(e)}, EXIT["invalid"]
    if q and q.warnings:
        for w in q.warnings:
            say("warning: " + w)
        res["warnings"] = q.warnings
    print(json.dumps(res, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
