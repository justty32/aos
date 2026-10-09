"""Skill 索引、經 llmcall 選擇與任務掛載。"""
import argparse
import fcntl
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from aos7_fs import N, OK, Unknown, append_jsonl, edit_json, fact, now, write_json

TOP = Path(__file__).resolve().parents[2]
DEFAULT_BUDGET = "budget/llm"
SYSTEM = "你是 skill 選擇器。從清單挑一個最適合題目的 skill，只回它的 name，不要其他字；都不適合回 none。"


def unquote(text):
    text = text.strip()
    while len(text) >= 2 and text[0] in "\"'`" and text[-1] == text[0]:
        text = text[1:-1].strip()
    return text


def build(node):
    """只掃描，不寫檔；符號連結照目錄跟進去。"""
    directory = Path(node) / "skills"
    if not Path(node).is_dir() or not directory.is_dir():
        raise ValueError("node 不存在或沒有 skills/ 目錄")
    skills, rejected = {}, {}
    for entry in sorted(directory.iterdir()):
        if entry.name.startswith(".") or not entry.is_dir():
            continue
        try:
            rows = (entry / "SKILL.md").read_text(encoding="utf-8").splitlines()
            if not rows or rows[0] != "---":
                raise ValueError("缺少開頭 frontmatter ---")
            if "---" not in rows[1:]:
                raise ValueError("缺少收尾 ---")
            fields = {}
            for row in rows[1:rows.index("---", 1)]:
                if not row.strip():
                    continue
                if ":" not in row or row[:1].isspace():
                    raise ValueError("frontmatter 須為 key: value 單行")
                key, value = row.split(":", 1)
                fields[key.strip()] = unquote(value)
            name, description = fields.get("name", ""), fields.get("description", "")
            if not name or not description:
                raise ValueError("name、description 都須非空")
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name) or name != entry.name:
                raise ValueError("name 不合法或不等於目錄名")
            if description in ("|", ">", "|-", ">-", "|+", ">+") or len(description) > 1024 or "\n" in description or "\r" in description:
                raise ValueError("description 超過 1024 字元或含換行")
            skills[name] = {"description": description, "path": f"skills/{name}/SKILL.md",
                            "scripts": (entry / "scripts").is_dir()}
        except (OSError, UnicodeError, ValueError) as e:
            rejected[entry.name] = "SKILL.md 不合：" + str(e).replace("\n", " ")
    must = {}
    state, obj = fact(directory / "must.json")
    if state != N:
        if state != OK or not isinstance(obj, dict):
            rejected["must.json"] = "讀不到或不是任務類型物件"
        else:
            errors = []
            for task, names in obj.items():
                names = [names] if isinstance(names, str) else names
                if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                    errors.append(f"{task} 的名字格式不合")
                    continue
                unknown = [n for n in names if n not in skills]
                if unknown:
                    errors.append("不認得：" + "、".join(unknown))
                else:
                    must[task] = obj[task]
            if errors:
                rejected["must.json"] = "；".join(errors)
    return {"v": 1, "skills": skills, "lines": [f"- {n}: {v['description']}" for n, v in skills.items()],
            "must": must, "rejected": rejected}


def index(node):
    result = build(node)
    directory = Path(node) / "skills"
    write_json(str(directory / "index.json"), result)
    if (directory / "must.json").exists():
        rows = ["| 任務類型 | 必用 skill | SKILL.md |", "| --- | --- | --- |"]
        for task, names in result["must"].items():
            names = [names] if isinstance(names, str) else names
            rows.append(f"| {task} | {', '.join(names)} | " +
                        ", ".join(f"skills/{n}/SKILL.md" for n in names) + " |")
        (directory / "MUST.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    else:
        (directory / "MUST.md").unlink(missing_ok=True)
    for line in result["lines"]:
        print(line)
    for name, reason in result["rejected"].items():
        error(f"拒收 {name}：{reason}")
    return int(bool(result["rejected"]))


def parse_answer(text, names):
    """先解外層引號，再取首行首詞；索引外明確拒絕。"""
    text = unquote(text)
    answer = unquote(text.splitlines()[0].split()[0]).lower() if text else ""
    if answer != "none" and answer not in names:
        raise ValueError(f"模型回了索引外的 {answer}")
    return answer


def words(text):
    return set(re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", text.lower()))


def ledger_alive(lock, wait=2.0):
    """帳任務常駐時持有 ledger.lock；剛起的給它 wait 秒拿鎖。"""
    end = time.monotonic() + wait
    while True:
        with open(lock, "a") as lk:
            try:
                fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.1)


def keyword_guess(question, skills):
    """關鍵字重疊最多的那本；一個字都沒對上回 none。本機挑選與假 AI 共用。"""
    scores = [(len(words(question) & words(n + " " + v["description"])), n) for n, v in skills.items()]
    score, guess = min(scores, key=lambda x: (-x[0], x[1])) if scores else (0, "none")
    return guess if score else "none"


def show(node, result, answer, log):
    if answer == "none":
        print("none")
        return
    log.update(picked=answer, rc=0)
    print((node / result["skills"][answer]["path"]).absolute())


def pick(node, args):
    start = time.monotonic()
    log = dict(at=now(), via="llmcall", call=None, q=args.question, answer=None, picked=None, used=None, rc=2)
    try:
        result = build(node)
        if args.budget is None and not (node / DEFAULT_BUDGET).exists():
            # 沒開帳就走本機挑選：不問 AI、不記帳；第一次跑走這條。call 仍按題目＋目錄取，供重試統計辨認。
            log["call"] = "local-" + hashlib.sha256(
                (args.question + "\n" + "\n".join(result["lines"])).encode()).hexdigest()[:16]
            log.update(via="local", answer=keyword_guess(args.question, result["skills"]), rc=1)
            error("本機挑選（關鍵字比對，沒問 AI、不記帳）；要讓 AI 挑，見 README「進階：讓 AI 挑」")
            show(node, result, log["answer"], log)
            return log["rc"]
        args.budget = args.budget or DEFAULT_BUDGET
        lines = "\n".join(result["lines"])
        log["call"] = "pick-" + hashlib.sha256(
            (args.question + "\n" + lines + "\n" + args.model).encode()).hexdigest()[:16]
        state, grant = fact(node / args.budget / "grant.json")
        if state != OK or not isinstance(grant, dict) or not isinstance(grant.get("holder"), str) or not grant["holder"]:
            raise ValueError("grant 讀不到或缺 holder")
        prompt = f"清單：\n{lines}\n\n題目：{args.question}"
        if grant.get("gateway") == "llm.fake":
            request = {"fake": {"mode": "ok", "usage": (len(SYSTEM) + len(prompt)) // 3 + 1,
                                "text": keyword_guess(args.question, result["skills"])}}
        elif grant.get("gateway") == "llm.litellm":
            request = {"litellm": {"model": args.model, "messages": [
                {"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}}
        else:
            raise ValueError("不支援的 gateway")
        if not ledger_alive(node / args.budget / "ledger.lock"):
            log["rc"] = 3
            raise ValueError("帳任務沒在跑：先在 node 裡起 aos7-budget ledger " + args.budget)
        path = node / "skills" / ".pick" / (log["call"] + ".json")
        write_json(str(path), request)
        proc = subprocess.run(["python3", str(TOP / "packs/llmcall/bin/aos7-llmcall"), "call", args.budget,
                               "--holder", grant["holder"], "--call", log["call"], "--logical", "skills/pick",
                               "--request", str(path), "--reserve", str(args.reserve), "--deadline", str(args.deadline)],
                              cwd=node, capture_output=True, text=True)
        log["rc"] = 3
        last = proc.stdout.strip().splitlines()[-1:] or [""]
        if proc.returncode not in (0, 4):
            print(proc.stderr + last[0], file=sys.stderr)
            error(f"llmcall 沒交付（退出碼 {proc.returncode}）")
        else:
            if proc.returncode == 4:
                error("已交付但帳未清（usage 未知或超出預留），見 aos7-llmcall status")
            receipt = json.loads(last[0])
            log.update(answer=receipt["text"], used=receipt["used"], rc=1)
            show(node, result, parse_answer(log["answer"], result["skills"]), log)
    except ValueError as e:
        error(str(e))
    except (OSError, Unknown, KeyError, IndexError, TypeError) as e:
        log["rc"] = 3
        error(str(e))
    finally:
        log["elapsed"] = round(time.monotonic() - start, 3)
        if (node / "skills").is_dir():
            append_jsonl(str(node / "skills/.pick/log.jsonl"), log)
    return log["rc"]


def mount(node, skill, task):
    result = build(node)
    if skill not in result["skills"]:
        raise ValueError("skill 不在索引")
    root = next((p for p in (node, *node.parents) if (p / ".aosd").is_dir()), None)
    if root is None:
        raise ValueError("找不到空間根（.aosd）")
    try:
        relative = (node / "skills" / skill).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        raise ValueError("skill 在空間外，掛不進去；請直接讀 SKILL.md") from None
    def update(obj):
        if not isinstance(obj, dict) or not isinstance(obj.get("tasks"), list) or not all(
                isinstance(t, dict) for t in obj["tasks"]):
            raise Unknown("tasks.json 讀不到或格式不合")
        item = next((t for t in obj["tasks"] if t.get("name") == task), None)
        if item is None:
            raise ValueError("找不到該 task")
        if "mounts" in item and not isinstance(item["mounts"], dict):
            raise Unknown("tasks.json 的 mounts 格式不合")
        item.setdefault("mounts", {})["skill-" + skill] = relative
        return obj
    edit_json(str(node / ".aos/tasks.json"), update)
    print("skill-" + skill)
    return 0


def error(message):
    print("aos7-skills: " + message, file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="aos7-skills", description="給 AI 挑工具說明書（skill）：index 抄目錄、pick 挑一本、mount 借給任務。",
        epilog="<node> 就是一個裝著 skills/ 子資料夾的資料夾。第一次跑：index 再 pick，不必開帳。")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{index,pick,mount}")
    helps = {
        "index": ("把 <node>/skills/*/SKILL.md 的名字＋一句簡介抄成目錄（stdout 一本一行）",
                  "退出碼：0 全收、1 有拒收（stderr 說原因）、2 沒有 skills/。"),
        "pick": ("照題目挑一本，印那本 SKILL.md 的路徑；挑不到印 none",
                 "預設：node 沒有 budget/llm/ 就本機關鍵字挑選（不問 AI、不記帳）；"
                 "有 budget/llm/（或給了 --budget）就經 llmcall 問 AI 並記帳，要先開帳、起帳任務。"
                 "退出碼：0 挑到、1 none、2 設定不對、3 帳任務沒在跑或 llmcall 沒交付。"),
        "mount": ("把一本 skill 掛到 .aos/tasks.json 某個任務的 mnt/skill-<名>（進階，要在 aos 空間裡）",
                  "退出碼：0 已掛、2 找不到空間根／skill／任務、3 tasks.json 讀不到。"),
    }
    for cmd, (short, more) in helps.items():
        p = sub.add_parser(cmd, help=short, description=short + "。", epilog=more)
        p.add_argument("node", help="node 資料夾（裡面要有 skills/）")
        if cmd == "pick":
            p.add_argument("question", help="題目，一句話說你要做什麼")
            p.add_argument("--budget", default=None, help="進階：帳的資料夾（相對 node），預設 budget/llm；有它才問 AI")
            p.add_argument("--model", default="chatgpt-gpt-6-sol-high", help="進階：問真 AI 時的模型")
            p.add_argument("--reserve", type=int, default=20000, help="進階：每次預留的 token 數")
            p.add_argument("--deadline", type=float, default=600, help="進階：llmcall 最長等幾秒")
        if cmd == "mount":
            p.add_argument("skill", help="skill 名字（index 印的那個）")
            p.add_argument("task", help=".aos/tasks.json 裡的任務名")
    args = ap.parse_args(argv)
    node = Path(args.node).absolute()
    try:
        if args.cmd == "pick":
            return pick(node, args)
        return index(node) if args.cmd == "index" else mount(node, args.skill, args.task)
    except ValueError as e:
        error(str(e))
        return 2
    except (OSError, Unknown) as e:
        error(str(e))
        return 3
