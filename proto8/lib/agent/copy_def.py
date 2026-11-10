"""copy_def - 把一份定義（範本、kernel）抄到別處時，改寫「指進 proto8」的路徑：env／anchor／absolute／relative 四種寫法（templates/copy-out 與 agents new 共用）。

使用者 11-10 午：「使用者自己準備。要用相對位置、絕對位置、環境變數指定都可」「兩台各自設一次...不要限制只設一次」——
寫出來的檔只放寫法，不放解出來的值；每次用到才由讀它的程式解（aos-exec／aos-json／aos-directive 的指示詞，N-45）。
四種寫法（MODE）：
  env       {"$env": "AOS_PROTO8", "$path": "/<proto8 底下的相對路徑>"}；每台設一次 AOS_PROTO8＝這台 proto8 的絕對路徑（預設）。
  anchor    經 DEST/.aos-proto8 的相對路徑（錨點捷徑由呼叫的人建；copy-out 建、--relink 重指）。
  absolute  這台 proto8 的絕對路徑（兩台要放同一位置）。
  relative  從那個檔的資料夾到 proto8 的相對路徑（兩台要同樣的相對擺法）。
改的地方（範本裡每個相對路徑照「它在範本原位」解開：落在範本裡＝照舊；落在 proto8 裡＝照 MODE 改；都不是＝照舊、帶 .. 的提醒一行）：
  - 任一 JSON 檔（*.json，與 JSON 形的 _entry）裡的字串值：相對、指得到東西的才算（從那個檔的資料夾算；tools.*.path、單子 argv、
    _memory.json 的 base、kernel.json 的 exec 與 endpoints 都是這種）。JSON key 不動。
  - {"$env": "AOS_CD", "$path": 相對}（AOS_CD＝定義的根）：env／absolute 換成整格新值，anchor／relative 只換 $path。別的指示詞整格不動。
  - 相對捷徑：anchor／relative／absolute 照寫法重寫捷徑；env（捷徑放不了環境變數）：_entry 捷徑換成等價的 JSON 單子
    {"argv": ["aos-exec", {"$env": "AOS_PROTO8", "$path": …}]}；指到檔的換成那份檔的複本（快照，之後 repo 改了不跟著變）；
    指到資料夾的退回 absolute——後兩種各提醒一行、列在 notes。
不讀環境變數、不碰 AOS_PROTO8 的值：寫的是寫法。PROTO＝本檔 realpath 往上兩層（lib/agent → proto8）。
"""
import json
import os
import shutil

MODES = ("env", "anchor", "absolute", "relative")
ENV = "AOS_PROTO8"
ANCHOR = ".aos-proto8"
PROTO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


class CopyFail(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code


def inside(path, root):
    return os.path.commonpath([path, root]) == root


def is_proto8(d):
    """d 是不是一份 proto8 資料夾（認 templates/copy-out 與 py/aos_flags.py；捷徑照跟）。"""
    return os.path.isfile(os.path.join(d, "templates", "copy-out")) and os.path.isfile(os.path.join(d, "py", "aos_flags.py"))


def env_value(sub):
    return {"$env": ENV} if sub == "." else {"$env": ENV, "$path": "/" + sub}


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise CopyFail("TemplateBad", "cannot read %s as JSON: %s" % (path, e))


def save(path, value):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(value, ensure_ascii=False) + "\n")
        os.replace(tmp, path)                            # N-05：先寫暫存再改名
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise CopyFail("WriteFailed", "cannot write %s: %s" % (path, e))


class Rewriter:
    """src＝原定義（realpath）；out＝已整份抄好、要改的資料夾；final＝它最後的位置（算相對用；同 out 或 out 之後要改名成的）。
    warn＝收一句英文提醒的函式。run() 回改了幾個路徑；notes＝退路提醒（捷徑換複本、退 absolute）。"""

    def __init__(self, src, out, final, mode, warn=lambda s: None, proto=PROTO):
        if mode not in MODES:
            raise CopyFail("ArgumentsBad", "proto8 mode must be one of %s (got %r)" % (", ".join(MODES), mode))
        self.src, self.out, self.final = os.path.realpath(src), os.path.abspath(out), os.path.abspath(final)
        self.mode, self.warn, self.proto = mode, warn, proto
        self.count, self.notes = 0, []

    def _target(self, src_dir, rel):
        """rel 從範本裡 src_dir 解開 → proto8 底下的相對路徑；範本裡、不是相對、指不到＝None。"""
        if not isinstance(rel, str) or not rel or os.path.isabs(rel) or rel.startswith("#"):
            return None
        full = os.path.normpath(os.path.join(src_dir, rel))
        if inside(full, self.src):
            return None
        if not inside(full, self.proto) or not os.path.lexists(full):
            if rel.startswith("../") and not inside(full, self.proto):
                self.warn("%s in %s points outside the repo; left as is" % (rel, src_dir))
            return None
        return os.path.relpath(full, self.proto)

    def _here(self, src_dir):
        return os.path.join(self.final, os.path.relpath(src_dir, self.src))

    def _write(self, sub, here):
        """proto8 底下的 sub、寫在 final 裡 here 資料夾的那個檔 → 新值。"""
        self.count += 1
        if self.mode == "env":
            return env_value(sub)
        if self.mode == "absolute":
            return os.path.normpath(os.path.join(self.proto, sub))
        if self.mode == "relative":
            return os.path.relpath(os.path.join(self.proto, sub), os.path.realpath(here))   # 還不在的部分照字面
        return os.path.relpath(os.path.join(self.final, ANCHOR, sub), here)

    def value(self, src_dir, rel):
        sub = self._target(src_dir, rel)
        return None if sub is None else self._write(sub, self._here(src_dir))

    def json_value(self, src_dir, v):
        """JSON 值 → (新值, 改了沒)。"""
        if isinstance(v, str):
            new = self.value(src_dir, v)
            return (v, False) if new is None else (new, True)
        if isinstance(v, list):
            pairs = [self.json_value(src_dir, x) for x in v]
            return [p[0] for p in pairs], any(p[1] for p in pairs)
        if not isinstance(v, dict):
            return v, False
        if "$ref" in v or "$env" in v:                   # 指示詞：只認 AOS_CD 那種，其他整格不動
            if v.get("$env") == "AOS_CD" and "$ref" not in v and isinstance(v.get("$path"), str):
                sub = self._target(self.src, v["$path"])
                if sub is not None:
                    new = self._write(sub, self.final)
                    if isinstance(new, str) and self.mode in ("anchor", "relative"):
                        return dict(v, **{"$path": new}), True
                    return new, True
            return v, False
        changed, out = False, {}
        for k, x in v.items():
            out[k], c = self.json_value(src_dir, x)
            changed = changed or c
        return out, changed

    def _link(self, src_dir, name, out_path):
        target = os.readlink(os.path.join(src_dir, name))
        sub = self._target(src_dir, target)
        if sub is None:
            return
        full = os.path.join(self.proto, sub)
        rel_name = os.path.relpath(out_path, self.out)
        try:
            os.remove(out_path)
            if self.mode != "env":
                os.symlink(self._write(sub, self._here(src_dir)), out_path)
            elif name == "_entry":
                self.count += 1
                save(out_path, {"argv": ["aos-exec", env_value(sub)]})
            elif os.path.isfile(full):
                shutil.copyfile(full, out_path)
                self.notes.append("%s is a copy of %s (a symlink cannot hold %s)" % (rel_name, full, ENV))
            else:
                self.count += 1
                os.symlink(full, out_path)
                self.notes.append("%s -> %s is an absolute symlink (a symlink cannot hold %s)" % (rel_name, full, ENV))
        except OSError as e:
            raise CopyFail("WriteFailed", "cannot rewrite %s: %s" % (out_path, e))

    def run(self):
        for directory, dirs, files in os.walk(self.src):
            links = [d for d in dirs if os.path.islink(os.path.join(directory, d))]   # 指到資料夾的捷徑：不往下走、當捷徑改
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git") and d not in links]
            rel_dir = os.path.relpath(directory, self.src)
            for name in files + links:
                s = os.path.join(directory, name)
                out_path = os.path.normpath(os.path.join(self.out, rel_dir, name))
                if os.path.islink(s):
                    self._link(directory, name, out_path)
                    continue
                if not (name.endswith(".json") or name == "_entry"):
                    continue
                try:
                    with open(s, "rb") as f:
                        head = f.read(1)
                except OSError as e:
                    raise CopyFail("TemplateBad", "cannot read %s: %s" % (s, e))
                if name == "_entry" and head not in (b"[", b"{"):
                    continue                             # 程式形的 _entry 不動
                new, changed = self.json_value(directory, load(s))
                if changed:
                    save(out_path, new)
        for n in self.notes:
            self.warn(n)
        return self.count


def needs(mode, dest, proto=PROTO):
    """抄完印的那一行：這份需要本機備好什麼（英文）。"""
    if mode == "env":
        now = os.environ.get(ENV)
        return "needs %s set to this machine's proto8 folder (now: %s; this repo: %s)" % (ENV, now if now else "unset", proto)
    if mode == "absolute":
        return "needs proto8 at %s on every machine" % proto
    if mode == "relative":
        return "needs proto8 at the same place relative to %s (now: %s)" % (dest, os.path.relpath(proto, os.path.realpath(dest)))
    return "needs %s pointing at this machine's proto8 folder (copy-out --relink after a move)" % os.path.join(dest, ANCHOR)
