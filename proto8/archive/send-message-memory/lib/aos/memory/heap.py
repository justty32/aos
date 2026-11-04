# heap.py - 記憶庫（heap）的讀寫：分六類、每類一份索引、一筆一個 .md；memory 工具與 brain.py 共用
# 位置：$AOS_HEAP（沒設＝$AOS_WS/.heap/）。放哪由叫的人決定（像 stack，C-67）：兩隻 agent 指同一個＝共用，各指各的＝私有。
#
#   $AOS_HEAP/
#     index.json          頂層索引（wf-table/1）：有東西的類各一列——類名、一句說明、幾筆、指向 <類>/index.json
#     <類>/index.json     這類的索引（wf-table/1）：一筆一列——id、標題、標籤、摘要、建立／更新時間、狀態、檔案
#     <類>/<NNN>.md       一筆的全文（第一行 # 標題）
#     archive/<類>/       forget 掉的筆搬來這裡（不刪；索引那列 status=forgotten）
#     .flock              寫入時 flock（並行寫不互蓋）
import datetime, fcntl, json, os, re

KINDS = {   # 類名＝資料夾名（複數，C-54）：一句說明
    "prefs": "使用者偏好：怎麼做事、喜歡什麼、不要什麼",
    "facts": "事實：專案、環境、人、東西在哪",
    "outcomes": "做過的事的結論",
    "gotchas": "踩過的坑與解法",
    "snippets": "檔案、片段、指令",
    "skills": "可重用的做法：步驟、prompt",
}
COLUMNS = ["id", "title", "tags", "summary", "created", "updated", "status", "path", "reason"]
TITLE_MAX, TEXT_MAX = 80, 4000


class HeapBad(Exception):
    """記憶庫本身壞了（索引不是 JSON、建不了資料夾）——不是模型的錯，工具要退 1。"""


def where():
    return os.environ.get("AOS_HEAP") or os.path.join(os.environ.get("AOS_WS", "."), ".heap")


def now():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def _write(path, text):                      # N-05：先寫 . 開頭的暫存檔再改名
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _table(columns, rows):                     # wf-table/1；不是從 md 抽出來的，source 留空
    return {"contract": "wf-table/1", "source": "", "extracted": now()[:10],
            "columns": columns, "link_columns": ["path"], "rows": rows}


class Heap:
    def __init__(self, root=None):
        self.root = root or where()

    # ---- 讀 ----
    def rows(self, kind):
        p = os.path.join(self.root, kind, "index.json")
        try:
            with open(p, encoding="utf-8") as f:
                t = json.load(f)
        except FileNotFoundError:
            return []
        except ValueError as e:
            raise HeapBad("%s 不是 JSON：%s" % (p, e))
        if not isinstance(t, dict) or not isinstance(t.get("rows"), list):
            raise HeapBad("%s 沒有 rows" % p)
        return [dict({c: "" for c in COLUMNS}, **r) for r in t["rows"] if isinstance(r, dict)]

    def active(self, kinds=None):
        out = []
        for k in kinds or KINDS:
            out += [dict(r, kind=k) for r in self.rows(k) if r["status"] == "active"]
        return out

    def text(self, row):
        try:
            with open(os.path.join(self.root, row["kind"], row["path"]), encoding="utf-8") as f:
                body = f.read()
        except OSError:
            return ""
        return re.sub(r"\A# [^\n]*\n\n?", "", body)          # 第一行是 # 標題，拿掉

    def find(self, id_):
        m = re.fullmatch(r"([a-z]+)/(\d{3,})", id_ or "")
        if not m or m.group(1) not in KINDS:
            return None
        for r in self.rows(m.group(1)):
            if r["id"] == id_:
                return dict(r, kind=m.group(1))
        return None

    # ---- 寫（一律持鎖）----
    def _lock(self):
        try:
            os.makedirs(self.root, exist_ok=True)
            f = open(os.path.join(self.root, ".flock"), "a")
        except OSError as e:
            raise HeapBad("記憶庫 %s 建不了：%s" % (self.root, e))
        fcntl.flock(f, fcntl.LOCK_EX)
        return f

    def _save_rows(self, kind, rows):
        os.makedirs(os.path.join(self.root, kind), exist_ok=True)
        clean = [{c: r.get(c, "") for c in COLUMNS} for r in rows]
        _write(os.path.join(self.root, kind, "index.json"),
               json.dumps(_table(COLUMNS, clean), ensure_ascii=False, indent=1) + "\n")
        top = [{"kind": k, "desc": d, "counter_active": str(len([r for r in (clean if k == kind else self.rows(k))
                                                         if r["status"] == "active"])),
                "path": k + "/index.json"} for k, d in KINDS.items()
               if os.path.exists(os.path.join(self.root, k, "index.json"))]    # 頂層只指已經有的下一層
        _write(os.path.join(self.root, "index.json"),
               json.dumps(_table(["kind", "desc", "counter_active", "path"], top), ensure_ascii=False, indent=1) + "\n")

    def save(self, kind, title, text, tags=()):
        """同一類裡同標題（不分大小寫）＝更新那一筆；回 (id, 舊全文或 None)。"""
        with self._lock():
            rows = self.rows(kind)
            at = now()
            old = next((r for r in rows if r["status"] == "active" and r["title"].lower() == title.lower()), None)
            if old:
                prev = self.text(dict(old, kind=kind))
                old.update(title=title, updated=at, summary=_summary(text),
                           tags=", ".join(_tags(old["tags"].split(",")) + [t for t in tags if t not in old["tags"]]))
                row = old
            else:
                prev = None
                n = 1 + max([int(r["id"].split("/")[1]) for r in rows] or [0])
                row = {"id": "%s/%03d" % (kind, n), "title": title, "tags": ", ".join(tags),
                       "summary": _summary(text), "created": at, "updated": at, "status": "active",
                       "path": "%03d.md" % n, "reason": ""}
                rows.append(row)
            os.makedirs(os.path.join(self.root, kind), exist_ok=True)
            _write(os.path.join(self.root, kind, row["path"]), "# %s\n\n%s\n" % (title, text.rstrip("\n")))
            self._save_rows(kind, rows)
            return row["id"], prev

    def forget(self, id_, reason=""):
        """搬到 archive/<類>/，索引那列標 forgotten；回那一列（找不到回 None）。"""
        kind = id_.split("/")[0] if "/" in (id_ or "") else ""
        if kind not in KINDS:
            return None
        with self._lock():
            rows = self.rows(kind)
            row = next((r for r in rows if r["id"] == id_ and r["status"] == "active"), None)
            if not row:
                return None
            dst = os.path.join(self.root, "archive", kind)
            os.makedirs(dst, exist_ok=True)
            try:
                os.replace(os.path.join(self.root, kind, row["path"]), os.path.join(dst, row["path"]))
            except FileNotFoundError:
                pass
            row.update(status="forgotten", path="../archive/%s/%s" % (kind, row["path"]),
                       updated=now(), reason=reason)
            self._save_rows(kind, rows)
            return dict(row, kind=kind)

    # ---- 找 ----
    def search(self, query="", kinds=None, limit=5, skip=()):
        """關鍵字：英數一個字一個詞、中文兩字一詞；標題命中 3 分、標籤 2 分、內文 1 分。query 空＝最近更新的。"""
        rows = [r for r in self.active(kinds) if r["id"] not in skip]
        q = _tokens(query)
        if not q:
            return sorted(rows, key=lambda r: r["updated"], reverse=True)[:limit]
        scored = []
        for r in rows:
            title, tags, body = _tokens(r["title"]), _tokens(r["tags"]), _tokens(self.text(r))
            s = sum(3 * (t in title) + 2 * (t in tags) + (t in body) for t in q)
            if s:
                scored.append((s, r["updated"], r))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [r for _, _, r in scored[:limit]]

    def counts(self):
        return {k: len([r for r in self.rows(k) if r["status"] == "active"]) for k in KINDS}

    # ---- 每題開頭自動附上（brain.py 用）----
    def context(self, question, pref_budget=1500, hit_budget=2400, hits=5):
        """回一段放進 system 的文字；記憶庫是空的回空字串。偏好全附（到上限），其他類照題目找最像的幾筆。"""
        counts = self.counts()
        total = sum(counts.values())
        if not total:
            return ""
        lines = ["## 記憶庫（每題開頭自動附上；共 %d 筆：%s）" % (
            total, "、".join("%s %d" % (k, n) for k, n in counts.items() if n))]
        shown, used = set(), 0
        prefs = self.search("", ["prefs"], limit=100)
        if prefs:
            lines.append("### 使用者偏好（全部）")
            for r in prefs:
                item = _item(r, self.text(r), 400)
                if used + len(item) > pref_budget:
                    lines.append("（偏好太多，後面沒附；用 memory 的 search 找）")
                    break
                lines.append(item)
                shown.add(r["id"])
                used += len(item)
        found = self.search(question, [k for k in KINDS if k != "prefs"], limit=hits, skip=shown)
        if found:
            lines.append("### 跟這題可能有關的")
            used = 0
            for r in found:
                item = _item(r, self.text(r), 600)
                if used + len(item) > hit_budget:
                    break
                lines.append(item)
                used += len(item)
        lines.append("（這裡只附一部分；不夠就用 memory 工具 op=search 找、op=read 讀全文。記憶可能過時：跟使用者現在說的衝突時以現在說的為準，並更新記憶。）")
        return "\n".join(lines)


def _item(r, text, cut):
    body = " ".join(text.split())
    if len(body) > cut:
        body = body[:cut] + "…（截斷，op=read 看全文）"
    tags = "［%s］" % r["tags"] if r["tags"] else ""
    return "- [%s] %s%s（更新 %s）：%s" % (r["id"], r["title"], tags, r["updated"][:10], body)


def _summary(text):
    return " ".join(text.split())[:100]


def _tags(tags):
    return [t.strip() for t in tags if isinstance(t, str) and t.strip()]


def _tokens(s):
    s = (s or "").lower()
    out = set(re.findall(r"[a-z0-9_]+", s))
    for run in re.findall(r"[㐀-鿿豈-﫿]+", s):
        out |= {run} if len(run) == 1 else {run[i:i + 2] for i in range(len(run) - 1)}
    return out
