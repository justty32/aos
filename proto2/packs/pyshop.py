"""pyshop 工具包 — Python 小程式工作室的家當：看資產、生骨架、跑標準檢查。"""
import os
import re
import subprocess

PROMPT = ("接到 Python 小程式的活：先 scaffold 生骨架再改，改完一定 run_checks（語法＋測試＋冒煙）。"
          "常用 snippets 與檢查腳本都在 team/assets，用 asset_list／asset_get 看。")

TOOLS = [
    {"name": "asset_list",
     "description": "列出 team/assets 底下所有資產與一句說明。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "asset_get",
     "description": "看一個資產檔的內容。",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "assets 底下的相對路徑"}},
         "required": ["path"]}},
    {"name": "scaffold",
     "description": "用 snippets 在專案目錄生出主程式、測試與 README；已存在的不蓋。",
     "parameters": {"type": "object", "properties": {
         "order_id": {"type": "string", "description": "單號"},
         "name": {"type": "string", "description": "程式名，不含 .py"},
         "kind": {"type": "string", "description": "目前只有 cli"}},
         "required": ["order_id", "name"]}},
    {"name": "run_checks",
     "description": "在專案目錄跑標準檢查；給 main 就多跑一次 CLI 冒煙。",
     "parameters": {"type": "object", "properties": {
         "order_id": {"type": "string", "description": "單號"},
         "main": {"type": "string", "description": "主程式檔名，例如 todo.py"}},
         "required": ["order_id"]}},
]

ID_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
NAME_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SKIP_DIRS = {"__pycache__", ".git"}
STEP_TIMEOUT = 60
TAIL = 1500


def _fail(text):
    return {"ok": False, "error": text}


def _team_dir(ctx):
    """工作室共用區 <根>/team；不在工作室裡就丟 ValueError。"""
    try:                                # 這包也會被單獨載入測試，那時旁邊不一定有 aos_agent
        from aos_agent import team_root_of
    except ImportError:
        team_root_of = None
    root = team_root_of(ctx.world) if team_root_of else None
    if not root:
        raise ValueError("你不在一個有 team/team.json 的工作室裡，沒有 team/ 可以用")
    return os.path.join(root, "team")


def _assets_dir(ctx):
    assets = os.path.join(_team_dir(ctx), "assets")
    if not os.path.isdir(assets):
        raise ValueError("找不到 team/assets；請主線把 presets/studio/assets 複製過來")
    return assets


def _project_dir(ctx, order_id, make=False):
    if not isinstance(order_id, str) or not ID_OK.match(order_id):
        raise ValueError("單號只能用英數字、底線、點與減號：%r" % (order_id,))
    path = os.path.join(_team_dir(ctx), "projects", order_id)
    if make:
        os.makedirs(path, exist_ok=True)
    elif not os.path.isdir(path):
        raise ValueError("還沒有這張單的專案目錄：team/projects/%s（先 scaffold）" % order_id)
    return path


def _inside(root, path):
    """把路徑關在 root 裡；跑到外面（含 ../ 與 symlink）就丟 ValueError。"""
    if not isinstance(path, str) or not path or os.path.isabs(path):
        raise ValueError("路徑要是 assets 底下的相對路徑：%r" % (path,))
    target = os.path.realpath(os.path.join(root, path))
    real_root = os.path.realpath(root)
    if os.path.commonpath((real_root, target)) != real_root:
        raise ValueError("路徑跑到 assets 外面了：%s" % path)
    return target


def _note(path):
    """一句說明：程式與腳本取開頭的註解，md 取第一個有字的行。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            head = [f.readline() for _ in range(4)]
    except OSError:
        return ""
    for line in head:
        text = (line or "").strip()
        if not text or text.startswith("#!"):
            continue
        text = text.lstrip("#").strip()
        text = text.replace("<!--", "").replace("-->", "").strip()
        if text:
            return text[:70]
    return ""


def _asset_list(args, ctx):
    root = _assets_dir(ctx)
    rows = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            path = os.path.join(folder, name)
            rows.append({"path": os.path.relpath(path, root).replace(os.sep, "/"),
                         "note": _note(path)})
    return {"ok": True, "dir": "team/assets", "count": len(rows), "assets": rows}


def _asset_get(args, ctx):
    root = _assets_dir(ctx)
    shown = args.get("path") or ""
    path = _inside(root, shown)
    if not os.path.isfile(path):
        return _fail("assets 裡沒有這個檔：%s（先用 asset_list 看）" % shown)
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    short = ctx.truncate(text)
    out = {"ok": True, "path": shown.replace(os.sep, "/"), "text": short}
    if short != text:
        out["truncated"] = True
    return out


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _drop_snippet_header(text, title):
    """把 snippet 開頭那句「這是 snippet，複製後改名」換成這支程式自己的抬頭。"""
    lines = text.splitlines(True)
    if lines and "snippet" in lines[0] and lines[0].lstrip().startswith(("#", "<!--")):
        lines = lines[1:]
    return title + "".join(lines)


def _merge(cli_text, store_text):
    """把 json_store 的本體合進 cli 骨架，生出單獨一支可以跑的程式。"""
    parts = store_text.split("# SNIPPET-BODY", 1)
    body = parts[1].split("\n", 1)[1] if len(parts) > 1 else store_text
    out = []
    for line in cli_text.splitlines(True):
        if "SNIPPET-MERGE: json_store" in line:
            out.append(body.strip("\n") + "\n")
        else:
            out.append(line)
    return "".join(out)


def _scaffold(args, ctx):
    assets = _assets_dir(ctx)
    kind = args.get("kind") or "cli"
    if kind != "cli":
        return _fail("目前只會生 cli；kind 給了 %r" % (kind,))
    name = args.get("name") or ""
    if not NAME_OK.match(name):
        return _fail("程式名要像 Python 模組：英文字母或底線開頭，只用英數字與底線（%r）" % (name,))
    order_id = args.get("order_id") or ""
    project = _project_dir(ctx, order_id, make=True)

    snippets = os.path.join(assets, "snippets")
    for need in ("cli_argparse.py", "json_store.py", "test_template.py", "readme_template.md"):
        if not os.path.isfile(os.path.join(snippets, need)):
            return _fail("assets/snippets 少了 %s" % need)

    program = _merge(_read(os.path.join(snippets, "cli_argparse.py")),
                     _read(os.path.join(snippets, "json_store.py")))
    program = _drop_snippet_header(program, "# %s.py — 單號 %s 的主程式（scaffold 生的骨架，直接改）\n"
                                   % (name, order_id))
    test = _read(os.path.join(snippets, "test_template.py"))
    test = test.replace('MODULE = "cli_argparse"', 'MODULE = "%s"' % name)
    test = _drop_snippet_header(test, "# test_%s.py — 單號 %s 的測試（scaffold 生的骨架，直接加測試）\n"
                                % (name, order_id))
    readme = _read(os.path.join(snippets, "readme_template.md"))
    readme = readme.replace("{{NAME}}", name).replace("{{ORDER}}", order_id)
    readme = _drop_snippet_header(readme, "")

    created, skipped = [], []
    for filename, text in (("%s.py" % name, program),
                           ("test_%s.py" % name, test),
                           ("README.md", readme)):
        path = os.path.join(project, filename)
        if os.path.exists(path):
            skipped.append(filename)
            continue
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
        created.append(filename)
    return {"ok": True, "order": order_id, "name": name, "kind": kind,
            "dir": "team/projects/%s" % order_id, "created": created, "skipped": skipped,
            "next": "改 %s.py，補 test_%s.py，改完叫 run_checks" % (name, name)}


def _tail(*chunks):
    parts = []
    for chunk in chunks:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8", "replace")
        parts.append(chunk or "")
    return "".join(parts)[-TAIL:]


def _step(name, command, cwd):
    """跑一支檢查腳本；逾時算沒過，輸出只留最後 1500 字。"""
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                              timeout=STEP_TIMEOUT)
    except subprocess.TimeoutExpired as e:
        return {"name": name, "exit": None,
                "tail": _tail(e.stdout, e.stderr, "\n跑超過 %d 秒被停掉了" % STEP_TIMEOUT)}
    except OSError as e:
        return {"name": name, "exit": None, "tail": str(e)}
    return {"name": name, "exit": done.returncode, "tail": _tail(done.stdout, done.stderr)}


def _run_checks(args, ctx):
    assets = _assets_dir(ctx)
    project = _project_dir(ctx, args.get("order_id") or "")
    tests_sh = os.path.join(assets, "checks", "run_tests.sh")
    if not os.path.isfile(tests_sh):
        return _fail("assets/checks/run_tests.sh 不在")
    steps = [_step("run_tests", ["bash", tests_sh, "."], project)]
    main = args.get("main")
    if main:
        if not isinstance(main, str) or "/" in main or main in ("", ".", ".."):
            return _fail("main 要是專案目錄裡的檔名，例如 todo.py（%r）" % (main,))
        if not os.path.isfile(os.path.join(project, main)):
            return _fail("專案目錄裡沒有 %s" % main)
        smoke_sh = os.path.join(assets, "checks", "smoke_cli.sh")
        if not os.path.isfile(smoke_sh):
            return _fail("assets/checks/smoke_cli.sh 不在")
        steps.append(_step("smoke_cli", ["bash", smoke_sh, main], project))
    return {"ok": all(step["exit"] == 0 for step in steps),
            "order": args.get("order_id"), "dir": "team/projects/%s" % (args.get("order_id"),),
            "steps": steps}


def run(name, args, ctx):
    handlers = {"asset_list": _asset_list, "asset_get": _asset_get,
                "scaffold": _scaffold, "run_checks": _run_checks}
    handler = handlers.get(name)
    if handler is None:
        return _fail("pyshop 沒有這個工具：%s" % name)
    try:
        return handler(args if isinstance(args, dict) else {}, ctx)
    except (OSError, ValueError) as error:
        return _fail(str(error))
