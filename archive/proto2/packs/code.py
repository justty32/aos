"""code 工具包 — 看 Python 骨架、搜尋、檢查，並在修改前後存檔與比較。"""
import ast
import difflib
import json
import os
import shutil
import subprocess
import sys

PROMPT = ("改 Python 前用 code_outline 看骨架、code_search 找位置；改之前 code_checkpoint 存檔，"
          "改壞用 code_undo。大檔用 edit（old 要剛好一次）不要整份 write，超過一分鐘的指令用 run_long。")


TOOLS = [
    {"name": "code_outline",
     "description": "看類別、函式、方法名與行號，不讀全文。",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string"}},
         "required": ["path"]}},
    {"name": "code_search",
     "description": "找原樣文字，列出檔名、行號與前後幾行。",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string"},
         "path": {"type": "string", "description": "預設 ."},
         "context": {"type": "integer", "description": "前後幾行，預設 2"},
         "limit": {"type": "integer", "description": "預設 20，上限 50"}},
         "required": ["query"]}},
    {"name": "code_check",
     "description": "檢查 Python 語法。",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string"}},
         "required": ["path"]}},
    {"name": "code_checkpoint",
     "description": "改前存檔，回存檔編號。",
     "parameters": {"type": "object", "properties": {
         "paths": {"type": "array", "items": {"type": "string"}}},
         "required": ["paths"]}},
    {"name": "code_diff",
     "description": "比較目前檔案與最近一次存檔的差異。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "code_undo",
     "description": "還原最近一次存檔；當時不存在的檔案會被刪除。",
     "parameters": {"type": "object", "properties": {}}},
]


SKIP_DIRS = {".git", ".aos-agent", ".aos-undo", "__pycache__"}


def _result(text, limit=4000, suggestion="縮小 path 或查找範圍再試一次。", forced=False,
            total_text=None):
    """把文字停在完整一行；被截時把原因和下一步一起說清楚。"""
    whole = text if total_text is None else total_text
    clipped = len(text) > limit
    shown = text
    if clipped:
        shown = text[:limit]
        end = shown.rfind("\n")
        if end >= 0:
            shown = shown[:end]
    out = {"text": shown}
    if clipped or forced:
        out.update({"truncated": True, "total_chars": len(whole),
                    "shown_chars": len(shown), "suggestion": suggestion})
    return out


def _project(ctx, path):
    """第一版缺 Ctx.project_path，所以包內自己把路徑關在世界裡。
    工作室成員家裡的 `team/` 是指向共用區的 symlink，realpath 會跑到自己世界外面，所以共用區也算裡面。"""
    world = os.path.realpath(ctx.world)
    raw = path if os.path.isabs(path) else os.path.join(world, path)
    target = os.path.realpath(raw)
    roots = [world]
    try:                                # 這包也會被單獨載入測試，那時旁邊沒有 aos_agent
        from aos_agent import team_root_of
    except ImportError:
        team_root_of = None
    team_root = team_root_of(ctx.world) if team_root_of else None
    if team_root:
        roots.append(os.path.realpath(os.path.join(team_root, "team")))
    if not any(os.path.commonpath((root, target)) == root for root in roots):
        raise ValueError("路徑跑到專案資料夾外面了：%s" % path)
    return target


def _relative(ctx, path):
    return os.path.relpath(path, os.path.realpath(ctx.world)).replace(os.sep, "/")


def _undo_root(ctx):
    """第一版缺 Ctx.undo_dir，所以包內固定使用 home/.aos-undo。"""
    return os.path.join(ctx.home, ".aos-undo")


class _Outline(ast.NodeVisitor):
    def __init__(self):
        self.items = []
        self.depth = 0
        self.scopes = []

    def _add(self, kind, node):
        self.items.append((self.depth, kind, node.name, node.lineno))

    def visit_ClassDef(self, node):
        self._add("class", node)
        self.depth += 1
        self.scopes.append("class")
        self.generic_visit(node)
        self.scopes.pop()
        self.depth -= 1

    def _visit_function(self, node):
        self._add("method" if self.scopes and self.scopes[-1] == "class" else "function", node)
        self.depth += 1
        self.scopes.append("function")
        self.generic_visit(node)
        self.scopes.pop()
        self.depth -= 1

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function


def _outline(args, ctx):
    path = _project(ctx, args.get("path") or "")
    if not os.path.isfile(path):
        return {"error": "找不到 Python 檔：%s" % (args.get("path") or "")}
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=_relative(ctx, path))
    visitor = _Outline()
    visitor.visit(tree)
    lines = ["%s%s %s（第 %d 行）" % ("  " * depth, kind, item, lineno)
             for depth, kind, item, lineno in visitor.items]
    all_text = "\n".join(lines) if lines else "沒有類別、函式或方法"
    shown = "\n".join(lines[:200]) if lines else all_text
    return _result(shown, forced=len(lines) > 200, total_text=all_text,
                   suggestion="骨架超過 200 項；改看更小的檔案。")


def _search_files(path):
    if os.path.isfile(path):
        return [path]
    found = []
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            found.append(os.path.join(root, name))
    return found


def _search(args, ctx):
    query = args.get("query") or ""
    if not query:
        return {"error": "query 不能是空的"}
    path = _project(ctx, args.get("path") or ".")
    if not os.path.exists(path):
        return {"error": "找不到搜尋路徑：%s" % (args.get("path") or ".")}
    try:
        context = max(0, int(args.get("context", 2)))
        limit = min(50, max(1, int(args.get("limit", 20))))
    except (TypeError, ValueError):
        return {"error": "context 和 limit 要填整數"}
    hits = []
    for filename in _search_files(path):
        try:
            with open(filename, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, UnicodeError):
            continue
        for index, line in enumerate(lines):
            if query in line:
                first = max(0, index - context)
                last = min(len(lines), index + context + 1)
                block = ["%s:%d" % (_relative(ctx, filename), index + 1)]
                for pos in range(first, last):
                    mark = ">" if pos == index else " "
                    block.append("%s %d| %s" % (mark, pos + 1, lines[pos]))
                hits.append("\n".join(block))
    if not hits:
        return {"text": "找不到：%s" % query, "matches": 0}
    all_text = "\n\n".join(hits)
    shown = "\n\n".join(hits[:limit])
    out = _result(shown, forced=len(hits) > limit, total_text=all_text,
                  suggestion="結果還有更多；縮小 path、query 或 context 再找。")
    out["matches"] = len(hits)
    out["shown_matches"] = min(limit, len(hits))
    return out


def _check(args, ctx):
    path = _project(ctx, args.get("path") or "")
    if not os.path.isfile(path):
        return {"error": "找不到 Python 檔：%s" % (args.get("path") or "")}
    done = subprocess.run([sys.executable, "-m", "py_compile", path], cwd=ctx.world,
                          capture_output=True, text=True)
    if done.returncode == 0:
        return {"ok": True}
    message = (done.stderr or done.stdout or "語法檢查失敗").strip()
    message = message.replace(path, _relative(ctx, path))
    out = _result(message, limit=2000, suggestion="錯誤太長；先看第一個語法錯誤。")
    out["ok"] = False
    return out


def _next_checkpoint(root):
    nums = [int(name) for name in os.listdir(root) if name.isdigit()] if os.path.isdir(root) else []
    return max(nums, default=0) + 1


def _checkpoint(args, ctx):
    paths = args.get("paths")
    if not isinstance(paths, list) or not paths:
        return {"error": "paths 要放至少一個檔案路徑"}
    root = _undo_root(ctx)
    number = _next_checkpoint(root)
    destination = os.path.join(root, str(number))
    os.makedirs(destination)
    entries = []
    total = 0
    for given in paths:
        if not isinstance(given, str) or not given:
            shutil.rmtree(destination)
            return {"error": "paths 裡每一項都要是檔案路徑"}
        source = _project(ctx, given)
        relative = _relative(ctx, source)
        existed = os.path.isfile(source)
        chars = 0
        if existed:
            with open(source, encoding="utf-8") as f:
                chars = len(f.read())
            backup = os.path.join(destination, relative)
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.copy2(source, backup)
        elif os.path.exists(source):
            shutil.rmtree(destination)
            return {"error": "checkpoint 只收檔案，不收資料夾：%s" % given}
        entries.append({"path": relative, "existed": existed, "chars": chars})
        total += chars
    with open(os.path.join(destination, "checkpoint.json"), "w", encoding="utf-8") as f:
        json.dump({"number": number, "files": entries}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    names = [entry["path"] + ("" if entry["existed"] else "（原本不存在）")
             for entry in entries]
    text = "checkpoint %d\n%s" % (number, "\n".join(names))
    out = _result(text, limit=1000, suggestion="檔名太多；分成幾次 checkpoint。")
    out.update({"checkpoint": number, "files": len(entries), "chars": total})
    return out


def _latest(ctx):
    root = _undo_root(ctx)
    nums = [int(name) for name in os.listdir(root) if name.isdigit()] if os.path.isdir(root) else []
    if not nums:
        return None, None
    number = max(nums)
    directory = os.path.join(root, str(number))
    try:
        with open(os.path.join(directory, "checkpoint.json"), encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        return number, None
    return directory, manifest


def _read_lines(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines(keepends=True)


def _diff(args, ctx):
    directory, manifest = _latest(ctx)
    if directory is None:
        return {"error": "還沒有 checkpoint；修改前先用 code_checkpoint"}
    if manifest is None:
        return {"error": "最近的 checkpoint 讀不到"}
    chunks = []
    summaries = []
    for entry in manifest.get("files", []):
        relative = entry["path"]
        current = _project(ctx, relative)
        before_path = os.path.join(directory, relative)
        before = _read_lines(before_path) if entry.get("existed") else []
        after = _read_lines(current)
        if before == after:
            continue
        diff = list(difflib.unified_diff(before, after, fromfile="a/" + relative,
                                         tofile="b/" + relative, lineterm=""))
        added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        summaries.append("%s：+%d -%d" % (relative, added, removed))
        chunks.append("\n".join(line.rstrip("\n") for line in diff))
    if not chunks:
        return {"text": "no changes"}
    text = "有變的檔案：\n%s\n\n%s" % ("\n".join(summaries), "\n\n".join(chunks))
    out = _result(text, suggestion="差異太長；縮小下一次 checkpoint 的 paths。")
    out["changed_files"] = len(chunks)
    return out


def _undo(args, ctx):
    directory, manifest = _latest(ctx)
    if directory is None:
        return {"error": "還沒有 checkpoint；沒有東西可以還原"}
    if manifest is None:
        return {"error": "最近的 checkpoint 讀不到"}
    restored = []
    removed = []
    for entry in manifest.get("files", []):
        relative = entry["path"]
        target = _project(ctx, relative)
        if entry.get("existed"):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(os.path.join(directory, relative), target)
            restored.append(relative)
        elif os.path.isfile(target):
            os.remove(target)
            removed.append(relative)
    lines = (["還原：" + name for name in restored] + ["移除：" + name for name in removed])
    out = _result("\n".join(lines) or "沒有檔案要還原", limit=1000,
                  suggestion="檔名太多；查看最近 checkpoint 的 checkpoint.json。")
    out.update({"restored": restored, "removed": removed})
    return out


def run(name, args, ctx):
    try:
        if name == "code_outline":
            return _outline(args, ctx)
        if name == "code_search":
            return _search(args, ctx)
        if name == "code_check":
            return _check(args, ctx)
        if name == "code_checkpoint":
            return _checkpoint(args, ctx)
        if name == "code_diff":
            return _diff(args, ctx)
        if name == "code_undo":
            return _undo(args, ctx)
        return {"error": "code 沒有這個工具：%s" % name}
    except (OSError, SyntaxError, ValueError) as error:
        return {"error": str(error)}
