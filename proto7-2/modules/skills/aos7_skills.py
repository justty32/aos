"""Skill 索引、經 llmcall 選擇與任務掛載。"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from aos7_fs import N, OK, U, Unknown, edit_json, fact, locked, now, write_json

TOP = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(TOP / "packs/budget")]
import aos7_budget

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
        raise ValueError(f"找不到 {directory}/ 資料夾。給一個裡面有 skills/ 的資料夾，例：aos7-skills index ~/my-node")
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
            phrases = {}
            for key in ("triggers", "not_for"):
                items = [s.strip() for s in re.split("[、,，]", fields.get(key, "")) if s.strip()]
                if len(items) > 32 or any(len(s) > 64 for s in items):
                    raise ValueError("triggers／not_for 每項 ≤64 字、最多 32 項")
                phrases[key] = items
            skills[name] = {**phrases, "description": description, "path": f"skills/{name}/SKILL.md",
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
    if result["rejected"]:
        details = "；".join(f"{name}（{reason}）" for name, reason in result["rejected"].items())
        error(f"有 {len(result['rejected'])} 本不收：{details}。改好那幾本的 SKILL.md 再跑 index，其他已照寫")
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


def keyword_guess(question, skills):
    """關鍵字重疊最多的那本；一個字都沒對上回 none。本機挑選與練習用的 AI 共用。"""
    scores = [(len(words(question) & words(n + " " + v["description"])), n) for n, v in skills.items()]
    score, guess = min(scores, key=lambda x: (-x[0], x[1])) if scores else (0, "none")
    return guess if score else "none"


def hit(phrase, question):
    if re.search(r"[A-Za-z0-9]", phrase):
        return bool(re.search(r"(?<![A-Za-z0-9])" + re.escape(phrase) + r"(?![A-Za-z0-9])", question, re.I))
    return phrase in question


def local_pick(question, skills):
    """觸發詞優先；舊書至少重疊兩詞，平手不猜。"""
    triggered, fallback, excluded = [], [], []
    qw = words(question)
    for name, book in skills.items():
        blocked = [p for p in book.get("not_for", []) if hit(p, question)]
        if blocked:
            excluded.append(name + " 不適用（" + "、".join(blocked) + "）")
            continue
        phrases = book.get("triggers", [])
        if phrases:
            matches = list(dict.fromkeys(p for p in phrases if hit(p, question)))
            if matches:
                triggered.append((len(matches), name, "觸發詞：" + "、".join(matches)))
        else:
            score = len(qw & words(book["description"])) + len(qw & words(name.replace("-", " ")))
            fallback.append((score, name, f"簡介重疊 {score} 詞"))
    scores = triggered or fallback
    score = max((s[0] for s in scores), default=0)
    winners = [s for s in scores if s[0] == score]
    enough = score >= (1 if triggered else 2)
    tie = enough and len(winners) > 1
    answer = winners[0][1] if enough and not tie else "none"
    why = ("平手：" + "、".join(s[1] for s in winners) if tie else winners[0][2]) if enough else "沒有觸發詞命中，簡介重疊不到 2 詞"
    if excluded:
        why += "；" + "；".join(excluded)
    return dict(answer=answer, score=score, why=why, tie=tie)


NONE = "目錄裡沒有一本合這個題目。換個說法再挑，或跑 index 看有哪幾本"
LLMCALL_SAYS = {  # llmcall 沒留 stderr 時的備用句
    1: "llmcall 做不到，沒有交付。用 aos7-llmcall status 看原因後再挑",
    2: "llmcall 的參數不合。給有效的預留與期限，例：--reserve 20000 --deadline 600",
    3: "不確定：llmcall 沒有確定結果，證據留在 llmcall/。照原樣再跑一次會接續",
}


def show(node, result, answer, log):
    """印挑到的路徑或 none；回 (退出碼, stderr 那句)。"""
    if answer == "none":
        print("none", flush=True)
        return 1, NONE
    log["picked"] = answer
    print((node / result["skills"][answer]["path"]).absolute())
    return 0, None


def ask_ai(node, args, result, log):
    """經 llmcall 問一次 AI；回 (退出碼, stderr 那句)。llmcall 的 1／2／3 與它那句照傳。"""
    lines = "\n".join(result["lines"])
    log["call"] = "pick-" + hashlib.sha256((args.question + "\n" + lines + "\n" + args.model).encode()).hexdigest()[:16]
    if args.reserve <= 0 or args.deadline <= 0:
        raise ValueError("--reserve、--deadline 要正數。例：--reserve 20000 --deadline 600")
    state, grant = fact(node / args.budget / "grant.json")
    if state == U:
        raise Unknown(grant)
    if state != OK or not isinstance(grant, dict) or not isinstance(grant.get("holder"), str) or not grant["holder"]:
        raise ValueError('grant 讀不到或缺 holder。給可讀的 grant.json 與非空 holder，例："holder": "skills"')
    prompt = f"清單：\n{lines}\n\n題目：{args.question}"
    if grant.get("gateway") == "llm.fake":
        request = {"fake": {"mode": "ok", "usage": (len(SYSTEM) + len(prompt)) // 3 + 1,
                            "text": keyword_guess(args.question, result["skills"])}}
    elif grant.get("gateway") == "llm.litellm":
        request = {"litellm": {"model": args.model, "messages": [
            {"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}}
    else:
        raise ValueError('不支援的 gateway。給 llm.fake 或 llm.litellm，例："gateway": "llm.fake"')
    bud = aos7_budget.Bud(node / args.budget)
    if not aos7_budget.ledger_running(bud):          # 只讀試鎖，不在帳夾裡建檔
        return 1, aos7_budget.not_running(bud)
    path = node / "skills" / ".pick" / f'{log["call"]}.{os.getpid()}.json'   # 同題並行各用各的，不互刪
    write_json(str(path), request)
    try:                                              # llmcall 會把請求抄進自己的證據夾，這份用完即刪
        proc = subprocess.run([sys.executable, str(TOP / "packs/llmcall/bin/aos7-llmcall"), "call", args.budget,
                               "--holder", grant["holder"], "--call", log["call"], "--logical", "skills/pick",
                               "--request", str(path), "--reserve", str(args.reserve), "--deadline", str(args.deadline)],
                              cwd=node, capture_output=True, text=True)
    finally:
        path.unlink(missing_ok=True)
    said = [line for line in proc.stderr.splitlines() if line.strip()]
    said = said[-1].strip().removeprefix("aos7-llmcall: ") if said else None
    if proc.returncode not in (0, 4):
        rc = proc.returncode if proc.returncode in LLMCALL_SAYS else 3
        return rc, (said if rc == proc.returncode else None) or LLMCALL_SAYS[rc]
    receipt = json.loads(proc.stdout.strip().splitlines()[-1])
    log.update(answer=receipt["text"], used=receipt["used"])
    if not isinstance(log["answer"], str):
        raise TypeError("回條 text 不是字串")
    try:
        answer = parse_answer(log["answer"], result["skills"])
        rc, message = show(node, result, answer, log)
    except ValueError as e:
        rc, message = 1, str(e) + "。跑 index 看有哪些名字，換個說法再挑"
    if proc.returncode == 4:                          # 已交付、帳沒清：照用，轉述 llmcall 那句（挑不到也要提醒）
        unsettled = said or "已交付但帳沒清。用 aos7-llmcall status 看證據並對帳"
        message = message + "。另外：" + unsettled if message else unsettled
    return rc, message


def keep_last(path, obj, n=50):
    """log.jsonl 加一行、只留最近 n 行（持 log.jsonl.lock，寫暫存再換名；並行不丟行）。"""
    with locked(str(path)):
        rows = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
        tmp.write_text("\n".join(rows[-(n - 1):] + [json.dumps(obj, ensure_ascii=False)]) + "\n", encoding="utf-8")
        os.replace(tmp, path)


def pick(node, args):
    start = time.monotonic()
    log = dict(at=now(), via="llmcall", call=None, q=args.question, answer=None, picked=None, used=None, rc=2, score=0, why="尚未挑選")
    message = None
    try:
        result = build(node)
        local = local_pick(args.question, result["skills"])
        log.update(score=local["score"], why=local["why"])
        has_ledger = args.budget is not None or (node / DEFAULT_BUDGET).exists()
        explicit = re.search(r"(?<!不)(?<!別)(?<!不要)用\s*(技能|skill)(?![A-Za-z])|(?<![A-Za-z])use\s+(a\s+)?skills?(?![A-Za-z])",
                             args.question, re.I)        # 明說用技能；「不要用技能」「cause skill」不算
        if not (has_ledger and (local["tie"] or explicit)):
            # 本機路徑不讀 grant、不碰帳；call 仍按題目＋目錄取，供重試統計辨認。
            log["call"] = "local-" + hashlib.sha256(
                (args.question + "\n" + "\n".join(result["lines"])).encode()).hexdigest()[:16]
            log.update(via="local", answer=local["answer"])
            log["rc"], message = show(node, result, log["answer"], log)
        else:
            log["why"] = ("平手，問 AI；" if local["tie"] else "題目明說用技能，問 AI；") + log["why"]
            args.budget = args.budget or DEFAULT_BUDGET
            log["rc"], message = ask_ai(node, args, result, log)
    except (OSError, Unknown, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        log["rc"] = 3
        message = f"不確定：挑選沒能確認（{e}），證據留在 llmcall/。照原樣再跑一次會接續"
    except ValueError as e:                           # 你給的不對：不記錄、什麼都沒動
        log["rc"], message = 2, str(e)
    finally:
        log["elapsed"] = round(time.monotonic() - start, 3)
        if log["rc"] != 2 and (node / "skills").is_dir():
            try:
                keep_last(node / "skills/.pick/log.jsonl", log)
            except (OSError, UnicodeError) as e:
                log["rc"] = 3
                message = f"不確定：挑選記錄沒寫完（{e}）。照原樣再跑一次會接續"
        if message:
            error(message)
    return log["rc"]


def mount(node, skill, task):
    result = build(node)
    if skill not in result["skills"]:
        raise ValueError("skill 不在索引。給 index 列出的名字，例：aos7-skills mount ~/my-node alpha work")
    root = next((p for p in (node, *node.parents) if (p / ".aosd").is_dir()), None)
    if root is None:
        raise ValueError("找不到空間根（.aosd）。給上層有 .aosd/ 的 node，例：aos7-skills mount ~/space/node alpha work")
    try:
        relative = (node / "skills" / skill).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        raise ValueError("skill 在空間外，掛不進去。給空間內的 skill 資料夾，例：~/space/node/skills/alpha；外面的請直接讀 SKILL.md") from None
    def update(obj):
        if not isinstance(obj, dict) or not isinstance(obj.get("tasks"), list) or not all(
                isinstance(t, dict) for t in obj["tasks"]):
            raise Unknown("tasks.json 讀不到或格式不合")
        item = next((t for t in obj["tasks"] if t.get("name") == task), None)
        if item is None:
            raise ValueError("找不到該 task。給 tasks.json 裡的任務名，例：aos7-skills mount ~/my-node alpha work")
        if "mounts" in item and not isinstance(item["mounts"], dict):
            raise Unknown("tasks.json 的 mounts 格式不合")
        item.setdefault("mounts", {})["skill-" + skill] = relative
        return obj
    edit_json(str(node / ".aos/tasks.json"), update)
    print("skill-" + skill)
    return 0


def error(message):
    print("aos7-skills: " + " ".join(str(message).splitlines()), file=sys.stderr)


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        error(message.rstrip("。.") + "。用法看 aos7-skills --help")
        self.exit(2)


def main(argv=None):
    ap = ArgumentParser(
        prog="aos7-skills", description="給 AI 挑工具說明書（skill）：index 抄目錄、pick 挑一本、mount 借給任務。",
        epilog="<node> 就是一個裝著 skills/ 子資料夾的資料夾。第一次跑：index 再 pick，不必開帳。")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{index,pick,mount}")
    helps = {
        "index": ("把書名和一句簡介抄成目錄，stdout 一本一行", "退出碼與契約見 ADVANCED.md"),
        "pick": ("照題目挑一本，印 SKILL.md 路徑；挑不到印 none", "沒帳就用本機關鍵字挑；有帳且平手或明說用技能才問 AI。退出碼與契約見 ADVANCED.md"),
        "mount": ("把一本 skill 掛給 aos 空間裡的任務", "退出碼與契約見 ADVANCED.md"),
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
        error(f"不確定：{e}。修好那個檔或等別人寫完，再照原樣跑一次")
        return 3
