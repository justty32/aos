"""jobs 工具包 — 把長工作放進自己的世界，做完寄信回來。"""
import datetime
import json
import os
import re
import shlex


PROMPT = ("長工作：run_long 會把要跑很久的 shell 指令放進另一個世界，另開一個鐘，"
          "最多跑一小時，做完會寄信到 inbox/jobs/。叫完不要等；這一格先回一句已經開跑就結束，"
          "下一格看到新信後用信箱工具讀結果。jobs_list 看所有長工作，job_peek 看輸出尾端，"
          "job_cancel 取消還在跑的工作。")

TOOLS = [
    {"name": "run_long",
     "description": "另開一個鐘跑長時間 shell 指令。當場回 job 名稱，不等它做完；最多跑一小時，做完會寄信。",
     "parameters": {"type": "object", "properties": {
         "command": {"type": "string", "description": "要跑的 shell 指令，會原樣存進 cmd.sh"},
         "name": {"type": "string", "description": "可選的 job 名稱，只能用英數字、底線、減號"}},
         "required": ["command"]}},
    {"name": "jobs_list",
     "description": "列出所有長工作：名稱、狀態、退出碼、跑了幾秒與指令。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "job_peek",
     "description": "看一個長工作的 stdout 與 stderr 最後幾行，預設各 20 行。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string", "description": "job 名稱"},
         "lines": {"type": "integer", "minimum": 1,
                   "description": "要看最後幾行，預設 20"}},
         "required": ["name"]}},
    {"name": "job_cancel",
     "description": "取消一個還在跑的長工作，並把它標成 cancelled。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string", "description": "job 名稱"}},
         "required": ["name"]}},
]


# 放進每個 job 的第三行。只用標準函式庫，直接寫結果與父的 inbox/jobs/。
FINISH_CODE = (
    "import datetime,json,os,sys;"
    "job=os.path.abspath(sys.argv[1]);exit_code=int(sys.argv[2]);"
    "meta=json.load(open(os.path.join(job,'meta.json'),encoding='utf-8'));"
    "out_path=os.path.join(job,'stdout.log');err_path=os.path.join(job,'stderr.log');"
    "out=open(out_path,encoding='utf-8',errors='replace').read() if os.path.isfile(out_path) else '';"
    "err=open(err_path,encoding='utf-8',errors='replace').read() if os.path.isfile(err_path) else '';"
    "ended=datetime.datetime.now();started=datetime.datetime.fromisoformat(meta['started']);"
    "seconds=max(0,int((ended-started).total_seconds()));"
    "result={'name':meta['name'],'command':meta['command'],'exit':exit_code,'seconds':seconds,"
    "'started':meta['started'],'ended':ended.isoformat(timespec='seconds'),"
    "'stdout_bytes':os.path.getsize(out_path) if os.path.isfile(out_path) else 0,"
    "'stdout_tail':out[-2000:],'stderr_bytes':os.path.getsize(err_path) if os.path.isfile(err_path) else 0,"
    "'stderr_tail':err[-2000:]};"
    "f=open(os.path.join(job,'result.json'),'w',encoding='utf-8');"
    "json.dump(result,f,ensure_ascii=False,indent=2);f.write('\\n');f.close();"
    "first=('job %s 被 3600 秒逾時砍掉了（exit 124），跑了 %d 秒。' % (meta['name'],seconds) "
    "if exit_code==124 else 'job %s 做完了：exit %d，跑了 %d 秒。' % (meta['name'],exit_code,seconds));"
    "content=first+'\\nstdout 最後幾行：\\n'+out[-2000:]+"
    "'\\n完整輸出在 jobs/%s/stdout.log，要看用 sh 或 job_peek。' % meta['name'];"
    "box=os.path.join(meta['parent_home'],'inbox','jobs');os.makedirs(box,exist_ok=True);"
    "stamp=ended.strftime('%Y%m%d-%H%M%S-%f')+'.json';"
    "mail={'from':'jobs','time':ended.isoformat(timespec='seconds'),'content':content};"
    "f=open(os.path.join(box,stamp),'w',encoding='utf-8');"
    "json.dump(mail,f,ensure_ascii=False,indent=2);f.write('\\n');f.close()"
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


def _short(text, size=160):
    text = str(text)
    return text if len(text) <= size else text[:size - 1] + "…"


def _run_long(args, ctx):
    if not os.environ.get("AOS_DAEMON_DIR"):
        return {"ok": False, "error": "沒設 AOS_DAEMON_DIR，不能替長工作另開鐘"}
    command = args.get("command")
    if not isinstance(command, str) or not command:
        return {"ok": False, "error": "command 要是一句非空的 shell 指令"}
    name = args.get("name")
    if name is None or name == "":
        name = _now().strftime("%Y%m%d-%H%M%S-%f")
    job = _job_dir(ctx, name)
    if job is None:
        return {"ok": False, "error": "name 只能用英數字、底線、減號"}
    if os.path.exists(job):
        return {"ok": False, "error": "這個 job 名稱已經有人用了：%s" % name}

    os.makedirs(os.path.join(job, ".aos"))
    with open(os.path.join(job, "cmd.sh"), "w", encoding="utf-8") as f:
        f.write(command)
    started = _now().isoformat(timespec="seconds")
    ctx.write_json(os.path.join(job, "meta.json"), {
        "name": name, "parent_home": ctx.home, "command": command, "started": started,
    })
    inst = "\n".join([
        "[ -e result.json ] && exit 0",
        "timeout 3600 sh cmd.sh > stdout.log 2> stderr.log",
        "python3 -c %s . \"$?\"" % shlex.quote(FINISH_CODE),
        "aos-daemon unregister . --no-wait",
    ]) + "\n"
    with open(os.path.join(job, ".aos", "inst"), "w", encoding="utf-8") as f:
        f.write(inst)

    ok, message = ctx.register_clock(job, no_wait=True)
    if not ok:
        return {"ok": False, "error": "job 建好了，但另開鐘失敗：%s" % message,
                "name": name, "path": os.path.relpath(job, ctx.home)}
    return {"ok": True, "name": name, "path": os.path.relpath(job, ctx.home)}


def _jobs_list(ctx):
    rows = []
    root = _jobs_dir(ctx)
    if not os.path.isdir(root):
        return rows
    for name in sorted(os.listdir(root)):
        job = os.path.join(root, name)
        if not os.path.isdir(job):
            continue
        meta = ctx.read_json(os.path.join(job, "meta.json"), {}) or {}
        result_path = os.path.join(job, "result.json")
        result = ctx.read_json(result_path, {}) if os.path.isfile(result_path) else {}
        result = result if isinstance(result, dict) else {}
        if result.get("cancelled"):
            state = "cancelled"
        elif os.path.isfile(result_path):
            state = "done"
        else:
            state = "running"
        seconds = result.get("seconds")
        if seconds is None and meta.get("started"):
            seconds = _elapsed(meta["started"])
        rows.append({"name": name, "state": state, "exit": result.get("exit"),
                     "seconds": seconds or 0, "command": _short(meta.get("command") or "")})
    return rows


def _job_peek(args, ctx):
    name = args.get("name")
    job = _job_dir(ctx, name)
    if job is None:
        return {"error": "name 只能用英數字、底線、減號"}
    if not os.path.isdir(job):
        return {"error": "找不到這個 job：%s" % name}
    lines = args.get("lines", 20)
    if not isinstance(lines, int) or isinstance(lines, bool) or lines < 1:
        return {"error": "lines 要是大於 0 的整數"}
    return {"name": name, "lines": lines,
            "stdout": _tail(os.path.join(job, "stdout.log"), lines),
            "stderr": _tail(os.path.join(job, "stderr.log"), lines)}


def _job_cancel(args, ctx):
    name = args.get("name")
    job = _job_dir(ctx, name)
    if job is None:
        return {"ok": False, "error": "name 只能用英數字、底線、減號"}
    if not os.path.isdir(job):
        return {"ok": False, "error": "找不到這個 job：%s" % name}
    ok, message = ctx.unregister_clock(job)
    if not ok:
        return {"ok": False, "error": "收鐘失敗，job 還沒有取消：%s" % message}
    meta = ctx.read_json(os.path.join(job, "meta.json"), {}) or {}
    started = meta.get("started") or _now().isoformat(timespec="seconds")
    result = {"name": name, "command": meta.get("command") or "", "exit": None,
              "cancelled": True, "seconds": _elapsed(started), "started": started,
              "ended": _now().isoformat(timespec="seconds")}
    ctx.write_json(os.path.join(job, "result.json"), result)
    return {"ok": True, "name": name, "state": "cancelled"}


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
