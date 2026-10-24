# common.py - self-improve 三格（run.py、judge.py、improve.py）共用：工作區與 stack 的佈局、版本、預算、跑一次函數
#
# 工作區（$AOS_WS，使用者交辦的）：goal.txt、target/ 或 target.json（原版，永遠不動）、judge/（判準）、budget.json（選填）、out/（成果）
# stack（$AOS_STACK，執行中的）：started_at.txt、current.txt（現在輪到哪一版）、versions/vNNN/（每一版一個資料夾，拍下來就不再改）
import datetime, hashlib, json, os, shutil, signal, subprocess, sys, tempfile

BUDGET = {"rounds": 5, "elapsed_ms": 30 * 60 * 1000, "tokens": 500000}      # budget.json 沒寫的照這個
TAIL = 4000                                                               # stdout、stderr 各留最後幾個字


def die(code, reason):
    print("self-improve: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def tail(text):
    return text if len(text) <= TAIL else "…（前面截掉 %d 字）\n" % (len(text) - TAIL) + text[-TAIL:]


ws = os.environ.get("AOS_WS")
stack = os.environ.get("AOS_STACK")
if not ws or not os.path.isdir(ws):
    die("WsMissing", "沒設定 AOS_WS 或不是資料夾")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
ws, stack = os.path.realpath(ws), os.path.realpath(stack)
VERSIONS = os.path.join(stack, "versions")


def write(path, text):
    """N-05：先寫 . 開頭的暫存檔再改名。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def read(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return default


def read_json(path, default=None):
    text = read(path)
    if text is None:
        return default
    try:
        return json.loads(text)
    except ValueError as e:
        die("StackBad", "%s 不是 JSON：%s" % (path, e))


def target_name(folder):
    """函數在 folder 裡叫什麼：target（資料夾程式）或 target.json（單檔）。"""
    return next((n for n in ("target", "target.json") if os.path.lexists(os.path.join(folder, n))), None)


def copy_target(src_folder, dst_folder):
    """把 src_folder 裡的函數複製到 dst_folder（符號連結照原樣複製，不跟過去）；回複本的路徑，沒有函數回 None。"""
    name = target_name(src_folder)
    if name is None:
        return None
    src, dst = os.path.join(src_folder, name), os.path.join(dst_folder, name)
    os.makedirs(dst_folder, exist_ok=True)
    if os.path.isdir(src) and not os.path.islink(src):
        shutil.copytree(src, dst, symlinks=True)
    else:
        shutil.copy2(src, dst, follow_symlinks=False)
    return dst


def tree_hash(folder):
    """函數內容的指紋（檔名＋內容），拿來認出「改回跟某一版一樣」。"""
    h = hashlib.sha256()
    name = target_name(folder)
    if name is None:
        return "none"
    root = os.path.join(folder, name)
    paths = [root] if not os.path.isdir(root) else sorted(
        os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs)
    for p in paths:
        h.update(os.path.relpath(p, folder).encode() + b"\0")
        if os.path.islink(p):
            h.update(b"link:" + os.readlink(p).encode())
        else:
            with open(p, "rb") as f:
                h.update(f.read())
        h.update(b"\0")
    return h.hexdigest()[:16]


def versions():
    """拍好的各版（vNNN、有 version.json 的，由舊到新）；改進到一半斷掉的那個資料夾不算。"""
    if not os.path.isdir(VERSIONS):
        return []
    return sorted(v for v in os.listdir(VERSIONS)
                  if v.startswith("v") and v[1:].isdigit() and os.path.exists(os.path.join(VERSIONS, v, "version.json")))


def verdict(v):
    return read_json(os.path.join(VERSIONS, v, "verdict.json"))


def best():
    """判過的版本裡分數最高的；同分取最早的（保守：沒變好就從原本那版重來，out/best/ 也不會換成同分的新寫法）。沒有判過的回 None。"""
    judged = [(verdict(v), v) for v in versions()]
    judged = [(-d["score"], v) for d, v in judged if d]
    return min(judged)[1] if judged else None


def budget():
    b = dict(BUDGET)
    got = read_json(os.path.join(ws, "budget.json"), {})
    if not isinstance(got, dict):
        die("BudgetBad", "budget.json 要是 JSON 物件")
    for k, v in got.items():
        if k in b:
            if type(v) is not int or v < 0:
                die("BudgetBad", "budget.json 的 %s 要是非負整數" % k)
            b[k] = v
    return b


def used():
    """用掉多少：rounds＝改進了幾輪（含失敗中斷的）、elapsed_ms＝從第一次跑到現在、tokens＝改進者問腦的 usage 加總。"""
    started = read(os.path.join(stack, "started_at.txt"))
    elapsed = 0
    if started:
        t0 = datetime.datetime.fromisoformat(started.strip())
        elapsed = int((datetime.datetime.now(datetime.timezone.utc) - t0).total_seconds() * 1000)
    tokens = 0
    for d, _, fs in os.walk(stack):
        if "usage.jsonl" in fs:
            for line in read(os.path.join(d, "usage.jsonl"), "").splitlines():
                try:
                    tokens += int(json.loads(line)["usage"].get("total_tokens") or 0)
                except (ValueError, KeyError, TypeError, AttributeError):
                    pass
    failed = len(os.listdir(os.path.join(stack, "failed"))) if os.path.isdir(os.path.join(stack, "failed")) else 0
    return {"rounds": max(len(versions()) - 1, 0) + failed, "elapsed_ms": elapsed, "tokens": tokens}


def sandbox():
    """工作區有 sandbox.json＝函數一律關進 aos-sandbox 跑（proto8/sandbox）；沒有＝照舊不關。回設定檔路徑或 None。"""
    path = os.path.join(ws, "sandbox.json")
    return path if os.path.exists(path) else None


def run_target(version_dir, argv_tail, stdin="", timeout_ms=10000, extra_env=None, exec_target=None):
    """在 version_dir 裡那份函數的暫時複本上跑一次（函數改到自己的檔也不影響拍下來的那版），回結果 dict。
    exec_target 沒給＝跑函數本身；給了＝跑那個目標（判準的 check），函數複本的路徑放在環境變數 IMPROVE_TARGET。"""
    with tempfile.TemporaryDirectory(prefix="self-improve.") as tmp:
        copy = copy_target(version_dir, tmp)
        run_ws = os.path.join(tmp, "ws")
        os.mkdir(run_ws)
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}   # 函數拿到乾淨的 aos 環境
        env.update(extra_env or {})
        if exec_target:
            env["IMPROVE_TARGET"] = copy or os.path.join(tmp, "target")
        argv = ["aos-exec", "--ws", run_ws, "--", exec_target or copy or os.path.join(tmp, "target")] + argv_tail
        box = sandbox()
        if box and not exec_target:                  # 10-24 沙箱接線：只關函數本身；檢查程式就是判準，不關
            argv = ["aos-sandbox", box] + argv
            env["IMPROVE_RUN"] = tmp                 # 設定檔用 {"$env": "IMPROVE_RUN"} 指這次的暫時資料夾（複本＋工作區）
        t0 = datetime.datetime.now()
        try:
            p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=env, start_new_session=True)
        except OSError as e:
            die("LaunchFailed", "aos-exec 起不來：%s" % e)
        timed_out = False
        try:
            out, err = p.communicate(stdin.encode(), timeout=timeout_ms / 1000)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(p.pid, signal.SIGKILL)
            out, err = p.communicate()
        ms = int((datetime.datetime.now() - t0).total_seconds() * 1000)
    dec = lambda b: b.decode("utf-8", "replace")
    return {"code": p.returncode, "timed_out": timed_out, "stdout": dec(out), "stderr": tail(dec(err)), "elapsed_ms": ms}


def criteria():
    """判準：("cases", [例子...]) 或 ("check", 檢查程式的路徑)。judge/cases.json 優先；兩個都沒有＝JudgeMissing。"""
    judge = os.path.join(ws, "judge")
    path = os.path.join(judge, "cases.json")
    if os.path.exists(path):
        cases = read_json(path)
        if not isinstance(cases, list) or not cases:
            die("JudgeBad", "judge/cases.json 要是非空的陣列")
        for i, c in enumerate(cases, 1):
            ok = (isinstance(c, dict) and isinstance(c.get("stdout"), str)
                  and isinstance(c.get("args", []), list) and all(isinstance(a, str) for a in c.get("args", []))
                  and isinstance(c.get("stdin", ""), str) and type(c.get("code", 0)) is int
                  and type(c.get("hidden", False)) is bool and type(c.get("timeout_ms", 1)) is int)
            if not ok:
                die("JudgeBad", "judge/cases.json 第 %d 組不對（要 {stdout, args?, stdin?, code?, hidden?, timeout_ms?}）" % i)
        return "cases", cases
    for name in ("check", "check.json"):
        if os.path.lexists(os.path.join(judge, name)):
            return "check", os.path.join(judge, name)
    die("JudgeMissing", "工作區沒有 judge/cases.json 也沒有 judge/check")
