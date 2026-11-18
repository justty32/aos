"""aos_sweep 清道夫本體：一輪（封存、保留期、封存總量、行程）與 purge 的流程、鎖、找列、報告；檔案細節在 aos_sweep_files、行程在 aos_sweep_proc；aos-sweeper 與 aos-daemon-ctl sweep 共用。
只管 D 自己這台（使用者 11-10「每個daemon要掛就自己掛，只管自己」）：讀 D 的 procs_state 表，不往子 daemon 底下走；子 daemon 那一列本身的 stderr 是 D 表上的一列，照封。
封存＝copytruncate（daemon 用 O_APPEND 開 stderr，截成 0 後從 0 接著寫；改名不行，子行程的 fd 會一直寫進舊 inode）。
封存檔放該列 stack 的 <stderr 去副檔名>_archives/<UTC>.<副檔名>.gz；只認自己寫的檔名樣式，別的檔不碰。
同一台同時只有一個清道夫：D/.sweeper.lock 的 flock（點開頭＝不進 image）；拿不到＝Busy。
單一檔出錯＝提醒行、往下一個（掛在 aos-loop 底下退非 0 會讓那支 loop 整支結束）；只有表讀不了回 table 欄給呼叫者判。"""
import datetime
import fcntl
import json
import os
import re
import time

import aos_flags
import daemon_ctl as dc
import aos_sweep_proc
from aos_sweep_files import archive_dir, archive_one, count_bad, expire, own_files, purge_dir, releasing

LOCK = ".sweeper.lock"
MIN_BYTES = 1 << 20          # 1 MiB 以上才封（草稿代定 4）：小的留著讓人 cat 看最近的錯
RETENTION_DAYS = 7           # aos-sweeper 的預設保留期（使用者 11-10「默認七天」）


class Busy(Exception):
    """D/.sweeper.lock 被另一個清道夫拿著。"""


def parse_retention(text):
    """--retention-days：正整數，或 none＝永不自動刪；0 不收（照字面是「立刻全刪」，那是 sweep --purge 的事）。"""
    if text == "none":
        return None
    if not re.fullmatch(r"[0-9]+", text or "") or int(text) <= 0:
        raise ValueError("--retention-days takes a positive whole number of days, or none (never delete automatically); to delete all archives now use aos-daemon-ctl sweep --purge")
    return int(text)


class Report:
    """一輪的結果；warning 同時印到 stderr（P-21：一行一則）。"""

    def __init__(self, prog, d, dry_run, now):
        self.prog = prog
        self.data = {"at": datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                     "daemon": d, "dry_run": dry_run, "table": "ok", "archived": [], "expired": [], "purged": [],
                     "archives": {"files": 0, "bytes": 0}, "bad_files": 0,
                     "processes": {"checked": False, "note": None, "orphans": [], "zombies": []}, "warnings": []}

    def warn(self, sentence):
        self.data["warnings"].append(sentence)
        aos_flags.warn(self.prog, sentence)


class Lock:
    """D/.sweeper.lock 的 flock；wait_s 秒內拿不到＝Busy。dry_run 時檔不在就不建（--dry-run 不動任何檔），照樣不加鎖往下看。"""

    def __init__(self, d, wait_s, dry_run):
        self.fd = None
        path = os.path.join(d, LOCK)
        try:
            if dry_run:
                self.fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
            else:
                self.fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o644)
        except FileNotFoundError:
            return
        end = time.monotonic() + wait_s
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                if time.monotonic() >= end:
                    os.close(self.fd)
                    raise Busy("another sweeper is working on %s (it holds %s)" % (d, path)) from None
                time.sleep(0.1)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def targets(d):
    """（表, [(名字, stack)…], stderr 檔名, procs_loop 檔名）。stack 是 D 自己的列跳過（那份 stderr 歸 D 的上一層）；兩列同 stack 只算一次。"""
    st = dc.state(d)
    names = dc.names_of(d)
    seen, out = {os.path.realpath(d)}, []
    for name, row in sorted(st["procs"].items()):
        stack = row.get("stack") if isinstance(row, dict) else None
        if not isinstance(stack, str) or not stack:
            continue
        real = os.path.realpath(stack)
        if real in seen:
            continue
        seen.add(real)
        out.append((name, stack))
    return st, out, names["procs_stderr"], names["procs_loop"]


def _places(d, rows):
    """（標籤, stack）：表上各列＋表外的預設小格；realpath 去重。保留期、purge、封存總量都看這些。"""
    seen, out = set(), []
    for label, stack in list(rows) + [("procs/" + os.path.basename(c), c) for c in aos_sweep_proc.cells(d)]:
        real = os.path.realpath(stack)
        if real not in seen:
            seen.add(real)
            out.append((label, stack))
    return out


def sweep(d, prog, min_bytes=MIN_BYTES, retention_days=None, stop_grace_s=aos_sweep_proc.STOP_GRACE_S,
          dry_run=False, wait_s=0.0, now=None):
    """跑一輪：封存 → 刪過期（retention_days＝None 不刪）→ 封存總量 → .bad- 數量 → 行程。回報告 dict；拿不到鎖丟 Busy。"""
    d = os.path.realpath(d)
    now = time.time() if now is None else now
    rep = Report(prog, d, dry_run, now)
    lock = Lock(d, wait_s, dry_run)
    try:
        try:
            st, rows, err_name, loop_name = targets(d)
        except dc.Fail as e:
            rep.data["table"] = "%s %s" % (e.code, e)
            rep.warn("cannot read the daemon table at %s (%s); nothing done this round" % (d, e))
            return rep.data
        for name, stack in rows:
            archive_one(rep, name, stack, err_name, min_bytes, dry_run, now)
        places = _places(d, rows)
        for label, stack in places:
            adir = archive_dir(stack, err_name)[0]
            if retention_days is not None:
                expire(rep, label, adir, retention_days, dry_run, now)
            for _, b, _t in own_files(adir):
                rep.data["archives"]["files"] += 1
                rep.data["archives"]["bytes"] += b
        rep.data["bad_files"] = count_bad(d) + sum(count_bad(s) for _, s in places)
        for label, stack in [("daemon", d)] + places:   # 11-10（open-14）：放鎖殘骸
            releasing(rep, label, stack, dry_run, now)
        aos_sweep_proc.check(rep, d, st, loop_name, stop_grace_s, dry_run, now)
        return rep.data
    finally:
        lock.close()


def purge(d, prog, dry_run=False, wait_s=30.0, now=None):
    """刪這台所有封存（表上各列＋預設小格），不管保留期；不封存、不碰 stderr、不碰行程。回報告 dict；拿不到鎖丟 Busy。"""
    d = os.path.realpath(d)
    now = time.time() if now is None else now
    rep = Report(prog, d, dry_run, now)
    lock = Lock(d, wait_s, dry_run)
    try:
        try:
            _st, rows, err_name, _loop = targets(d)
        except dc.Fail as e:
            rep.data["table"] = "%s %s" % (e.code, e)
            rep.warn("cannot read the daemon table at %s (%s); nothing purged" % (d, e))
            return rep.data
        for label, stack in _places(d, rows):
            purge_dir(rep, label, archive_dir(stack, err_name)[0], dry_run)
        return rep.data
    finally:
        lock.close()


def lines(data):
    """報告的人看版（stdout，一事一行）。"""
    dry = data["dry_run"]

    def verb(word, past):
        return "would " + word if dry else past
    out = []
    for a in data["archived"]:
        out.append("%s: %s %s (%d bytes) to %s" % (a["name"], verb("archive", "archived"), a["file"], a["bytes"], a["archive"]))
    for a in data["expired"]:
        out.append("%s: %s %d expired archive(s) (%d bytes) in %s" % (a["name"], verb("delete", "deleted"), a["files"], a["bytes"], a["dir"]))
    for a in data.get("releasing", []):
        out.append("%s: %s leftover lock folder %s" % (a["name"], verb("remove", "removed"), a["dir"]))
    for a in data["purged"]:
        out.append("%s: %s %d file(s) (%d bytes) in %s" % (a["name"], verb("purge", "purged"), a["files"], a["bytes"], a["dir"]))
    if not data["purged"]:
        out.append("archives: %d file(s), %d bytes" % (data["archives"]["files"], data["archives"]["bytes"]))
        out.append("bad files: %d" % data["bad_files"])
        p = data["processes"]
        if p["note"]:
            out.append("processes: %s" % p["note"])
        for o in p["orphans"]:
            out.append("%s: pid %s: %s" % (o["cell"], o["pid"], o["action"]))
        for z in p["zombies"]:
            out.append("zombie: pid %d (%s), parent %d" % (z["pid"], z["comm"], z["ppid"]))
    return out


def write_report(path, data):
    """先寫同夾暫存再改名（讀的人不會讀到半份）。"""
    tmp = os.path.join(os.path.dirname(path) or ".", ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=1) + "\n")
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
