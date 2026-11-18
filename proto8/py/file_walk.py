"""file_walk - grep 與 glob 共用的走樹：隱藏名、.gitignore（問 git）、資料夾捷徑不跟進、只把一般檔當檔、掃描預算與計數；另含兩支共用的檔名樣式（* ? [..] **）。

設計與裁定：thinking 2026-11-11 new-tools 01（G1 兩支、G2 純 Python、G3「預設跳過，問 git」）。不是工具（沒有 _entry），是 lib 頂層的共用模組（同 tool_io；給 lib/base 的 grep、glob 用，不 import 工具）。
走法：深度優先、每層照名字排；資料夾先吐自己再進去。. 開頭的名字預設不進不吐（hidden=True 或樣式明寫那段才算）；在 git 工作樹裡時 .git 與 git 說擋掉的都跳過。
捷徑：連到資料夾的吐成 dir 但不進（免得繞圈、免得拉進整個 /）；連到檔的照吐、路徑是捷徑自己的；壞掉的不吐不計。fifo、socket、裝置吐成 other（呼叫者不讀，免得卡住）。
預算：MAX_SECONDS 秒或 MAX_ENTRIES 個名字先到先停（stopped 記停在哪）；測試直接改這兩個模組常數或傳參數，不靠環境變數。
"""
import os, re, shutil, stat, subprocess, time

MAX_SECONDS, MAX_ENTRIES = 20.0, 20000


class PatternError(Exception):
    """樣式壞了（例 [ 沒關）；原因是英文。"""


def _segment(seg):
    """一段（不含 /）的 * ? [..] → 正規式；[ 沒關＝PatternError。"""
    out, i = [], 0
    while i < len(seg):
        c = seg[i]
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = i + 1
            if j < len(seg) and seg[j] in "!^":
                j += 1
            if j < len(seg) and seg[j] == "]":
                j += 1
            while j < len(seg) and seg[j] != "]":
                j += 1
            if j >= len(seg):
                raise PatternError("unclosed [ in %r" % seg)
            body = seg[i + 1:j]
            neg = body[:1] in ("!", "^")
            body = body[1:] if neg else body
            out.append("[" + ("^" if neg else "") + body.replace("\\", "\\\\") + "]")
            i = j
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


class Pattern:
    """檔名樣式：* 一層內任意、? 一字、[abc]、** 任意層（含零層）；不含 / 的樣式＝比對任何一層的名字。"""

    def __init__(self, text):
        if text.startswith("/"):
            raise PatternError("the pattern is relative to path; put the folder in path instead")
        segs = [s for s in text.split("/") if s not in ("", ".")]
        if not segs:
            raise PatternError("the pattern is empty")
        if len(segs) == 1 and segs[0] != "**":
            segs = ["**"] + segs                   # *.py＝任何深度的 .py
        body = "".join("(?:[^/]+/)*" if s == "**" else _segment(s) + "/" for s in segs)
        try:
            self._re = re.compile("^" + body + "$", re.S)
        except re.error as e:
            raise PatternError("%s in %r" % (e, text)) from None
        self._dots = [re.compile("^" + _segment(s) + "$", re.S) for s in segs if s.startswith(".")]

    def match(self, rel):
        """rel＝從起點算、以 / 分隔的相對路徑。"""
        return bool(self._re.match(rel + "/"))

    def names(self, name):
        """name 是 . 開頭時，樣式有沒有明寫那段（明指＝不受 hidden 擋）。"""
        return any(d.match(name) for d in self._dots)


def git_ignored(root, warn):
    """root 在 git 工作樹裡＝回 git 說擋掉的相對路徑集合（資料夾不帶 /）；不在＝None；git 不在或失敗＝warn 一行、回 None。"""
    git = shutil.which("git")
    if git is None:
        warn("git is not on PATH; .gitignore is not applied")
        return None
    try:
        r = subprocess.run([git, "-C", root, "rev-parse", "--is-inside-work-tree"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=MAX_SECONDS)
        if r.returncode != 0 or r.stdout.strip() != b"true":
            return None                            # 不在 git 工作樹裡（git 的原因不讀，不讀下層 stderr）
        r = subprocess.run([git, "-C", root, "ls-files", "-z", "-o", "-i", "--exclude-standard", "--directory"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=MAX_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as e:
        warn("git failed (%s); .gitignore is not applied" % (e.strerror if isinstance(e, OSError) and e.strerror else e))
        return None
    if r.returncode != 0:
        warn("git ls-files exited %d; .gitignore is not applied" % r.returncode)
        return None
    return {p.decode("utf-8", "surrogateescape").rstrip("/") for p in r.stdout.split(b"\0") if p}


class Walk:
    """走一棵樹：for rel, full, kind in Walk(root)；kind＝file／dir／other。走完看 unreadable、stopped、entries。"""

    def __init__(self, root, *, hidden=False, gitignore=True, pattern=None, warn=None, max_seconds=None, max_entries=None):
        self.root, self.hidden, self.pattern = root, hidden, pattern
        self.max_seconds = MAX_SECONDS if max_seconds is None else max_seconds
        self.max_entries = MAX_ENTRIES if max_entries is None else max_entries
        self.unreadable, self.entries, self.stopped = 0, 0, None
        self.ignored = git_ignored(root, warn or (lambda s: None)) if gitignore else None
        self._t0 = time.monotonic()

    def _skip_name(self, name):
        named = self.pattern is not None and self.pattern.names(name)
        if self.ignored is not None and name == ".git" and not named:
            return True                            # git 自己的資料，不算工作樹裡的檔
        return name.startswith(".") and not self.hidden and not named

    def _over(self):
        if self.entries > self.max_entries:
            self.stopped = "%d entries" % self.max_entries
        elif time.monotonic() - self._t0 > self.max_seconds:
            self.stopped = "%g s" % self.max_seconds
        return self.stopped is not None

    def _list(self, full):
        try:
            with os.scandir(full) as it:
                return iter(sorted(it, key=lambda e: e.name))
        except OSError:
            self.unreadable += 1
            return iter(())

    def __iter__(self):
        stack = [("", self._list(self.root))]      # 每層（rel, 還沒看的名字）；遇到資料夾馬上進去＝照路徑排
        while stack:
            prel, items = stack[-1]
            e = next(items, None)
            if e is None:
                stack.pop()
                continue
            self.entries += 1
            if self._over():
                return
            if self._skip_name(e.name):
                continue
            rel = prel + "/" + e.name if prel else e.name
            if self.ignored is not None and rel in self.ignored:
                continue
            try:
                if e.is_symlink():
                    st = os.stat(e.path)           # 跟過去看是什麼；壞掉的捷徑跳過不計
                    kind = "dir" if stat.S_ISDIR(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else "other"
                    sub = None                     # 連到資料夾的不進
                elif e.is_dir(follow_symlinks=False):
                    kind, sub = "dir", e.path
                else:
                    kind, sub = ("file" if stat.S_ISREG(e.stat(follow_symlinks=False).st_mode) else "other"), None
            except OSError:
                continue
            yield rel, e.path, kind
            if sub is not None:
                stack.append((rel, self._list(sub)))
            if self._over():
                return
