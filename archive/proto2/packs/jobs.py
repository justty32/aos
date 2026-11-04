"""jobs 工具包 — 把長工作放進自己的世界，共用層收結果。"""
import datetime
import os
import re
import shlex

PROMPT = "run_long 最多跑一小時，叫完系統會睡到結果回來。"

TOOLS = [
    {"name": "run_long", "description": "另開一個鐘跑長時間 shell 指令，最多一小時。",
     "parameters": {"type": "object", "properties": {
         "command": {"type": "string"}, "name": {"type": "string"}},
         "required": ["command"]}},
    {"name": "jobs_list", "description": "列出所有長工作。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "job_peek", "description": "看一個長工作的輸出尾端。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string"}, "lines": {"type": "integer"}},
         "required": ["name"]}},
    {"name": "job_cancel", "description": "取消一個還在跑的長工作。",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}},
                    "required": ["name"]}},
]

FINISH_CODE = (
    "import datetime,json,os,sys;"
    "job=os.path.abspath(sys.argv[1]);code=int(sys.argv[2]);rid=sys.argv[3];"
    "meta=json.load(open(os.path.join(job,'meta.json'),encoding='utf-8'));"
    "outp=os.path.join(job,'stdout.log');errp=os.path.join(job,'stderr.log');"
    "out=open(outp,encoding='utf-8',errors='replace').read() if os.path.isfile(outp) else '';"
    "err=open(errp,encoding='utf-8',errors='replace').read() if os.path.isfile(errp) else '';"
    "ended=datetime.datetime.now();started=datetime.datetime.fromisoformat(meta['started']);"
    "result={'name':meta['name'],'command':meta['command'],'exit':code,"
    "'seconds':max(0,int((ended-started).total_seconds())),'started':meta['started'],"
    "'ended':ended.isoformat(timespec='seconds'),'stdout_tail':out[-2000:],'stderr_tail':err[-2000:]};"
    "result.update({'error':'長工作逾時了。','kind_of_error':'timeout'} if code==124 else "
    "({'error':'長工作失敗了，exit %d。'%code,'kind_of_error':'llm'} if code else {}));"
    "folder=os.path.join(job,'results');os.makedirs(folder,exist_ok=True);"
    "tmp=os.path.join(folder,rid+'.tmp');dst=os.path.join(folder,rid);"
    "f=open(tmp,'w',encoding='utf-8');json.dump(result,f,ensure_ascii=False);f.close();os.replace(tmp,dst)"
)


def _jobs_dir(ctx):
    return os.path.join(ctx.home, "jobs")


def _job_dir(ctx, name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        return None
    return os.path.join(_jobs_dir(ctx), name)


def _now():
    return datetime.datetime.now()


def _elapsed(started):
    return max(0, int((_now() - datetime.datetime.fromisoformat(started)).total_seconds()))


def _tail(path, lines):
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as f:
        return "\n".join(f.read().splitlines()[-lines:])


def _run_long(args, ctx):
    if not os.environ.get("AOS_DAEMON_DIR"):
        ctx.reply("長工作沒有鐘，無法開跑。", error=True)
        return {"ok": False, "error": "沒有 daemon 鐘"}
    command = args.get("command")
    if not isinstance(command, str) or not command:
        return {"ok": False, "error": "command 要是一句非空的 shell 指令"}
    name = args.get("name") or _now().strftime("%Y%m%d-%H%M%S-%f")
    job = _job_dir(ctx, name)
    if job is None:
        return {"ok": False, "error": "name 只能用英數字、底線、減號"}
    if os.path.exists(job):
        return {"ok": False, "error": "這個 job 名稱已經有人用了：%s" % name}
    os.makedirs(os.path.join(job, ".aos"))
    os.makedirs(os.path.join(job, "requests"))
    os.makedirs(os.path.join(job, "results"))
    with open(os.path.join(job, "cmd.sh"), "w", encoding="utf-8") as f:
        f.write(command)
    started = _now().isoformat(timespec="seconds")
    ctx.write_json(os.path.join(job, "meta.json"), {
        "name": name, "command": command, "started": started,
    })
    request = ctx.send("jobs", {"name": name, "command": command}, target=job,
                       timeout_s=3600)
    meta = ctx.read_json(os.path.join(job, "meta.json"), {})
    meta["request"] = request
    ctx.write_json(os.path.join(job, "meta.json"), meta)
    inst = "\n".join([
        "timeout 3600 sh cmd.sh > stdout.log 2> stderr.log",
        "python3 -c %s . \"$?\" %s.json" % (shlex.quote(FINISH_CODE), shlex.quote(request)),
        "aos-daemon unregister . --no-wait",
    ]) + "\n"
    with open(os.path.join(job, ".aos", "inst"), "w", encoding="utf-8") as f:
        f.write(inst)
    ok, message = ctx.register_clock(job, no_wait=True)
    if not ok:
        ctx.cancel(request)
        ctx.reply("長工作的鐘開不起來。", error=True)
        return {"ok": False, "error": message, "name": name}
    ctx.sleep_until("jobs", request)
    return {"ok": True, "name": name, "id": request,
            "path": os.path.relpath(job, ctx.home)}


def _jobs_list(ctx):
    rows = []
    root = _jobs_dir(ctx)
    if not os.path.isdir(root):
        return rows
    pending = {item.get("id") for item in ctx.pending()}
    for name in sorted(os.listdir(root)):
        job = os.path.join(root, name)
        meta = ctx.read_json(os.path.join(job, "meta.json"), {}) or {}
        if not isinstance(meta, dict):
            continue
        request = meta.get("request")
        result = ctx.read_json(os.path.join(ctx.home, "side", "jobs", str(request) + ".json"), {})
        if request in pending:
            state = "running"
        elif isinstance(result, dict) and result.get("kind_of_error") == "cancelled":
            state = "cancelled"
        elif isinstance(result, dict) and result:
            state = "error" if result.get("error") else "done"
        else:
            state = "unknown"
        rows.append({"name": name, "state": state, "exit": result.get("exit"),
                     "seconds": result.get("seconds", _elapsed(meta["started"])),
                     "command": str(meta.get("command") or "")[:160]})
    return rows


def _job_peek(args, ctx):
    job = _job_dir(ctx, args.get("name"))
    if job is None or not os.path.isdir(job):
        return {"error": "找不到這個 job"}
    lines = args.get("lines", 20)
    if not isinstance(lines, int) or isinstance(lines, bool) or lines < 1:
        return {"error": "lines 要是大於 0 的整數"}
    return {"name": args.get("name"), "lines": lines,
            "stdout": _tail(os.path.join(job, "stdout.log"), lines),
            "stderr": _tail(os.path.join(job, "stderr.log"), lines)}


def _job_cancel(args, ctx):
    job = _job_dir(ctx, args.get("name"))
    if job is None or not os.path.isdir(job):
        return {"ok": False, "error": "找不到這個 job"}
    meta = ctx.read_json(os.path.join(job, "meta.json"), {}) or {}
    ok, message = ctx.unregister_clock(job)
    if not ok:
        return {"ok": False, "error": "收鐘失敗：%s" % message}
    request = meta.get("request")
    if request:
        ctx.cancel(request)
    return {"ok": True, "name": args.get("name"), "state": "cancelled"}


def on_result(ctx, kind, request, result):
    name = result.get("name") or request
    if result.get("error"):
        return None
    return "長工作 %s 做完了：exit %s，跑了 %s 秒。" % (
        name, result.get("exit"), result.get("seconds"))


def run(name, args, ctx):
    if name == "run_long":
        return _run_long(args, ctx)
    if name == "jobs_list":
        return _jobs_list(ctx)
    if name == "job_peek":
        return _job_peek(args, ctx)
    if name == "job_cancel":
        return _job_cancel(args, ctx)
    return {"error": "jobs 沒有這個工具：%s" % name}
