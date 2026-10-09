"""記憶整理包：舊段先封存再換摘要，open 項與最近 N 則留原文。"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

TOP = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(TOP / "lib"), str(TOP / "modules/tools")]
from aos7_fs import append_jsonl, now, read_json, sweep_tmp, test_point, write_json
from aos7_taskside import task_env, wait_tock

DEFAULT = dict(files=["wf/SESSION-LOG.md", "notes/journal.jsonl"], max_bytes=16384,
               keep_recent=10, on_stage_change=True, stage_similarity=0.2, summary_max_chars=1200, llm=None, events=False)
LLM_DEFAULT = dict(budget="budget/llm", holder="compact", reserve=4000, gateway="fake",
                   model="chatgpt-gpt-6-sol-high", deadline=600, patience=5)
PROMPT = ("這是一個 agent 的工作紀錄。請將舊紀錄濃縮成一段繁體中文摘要，≤{n} 字。"
          "保留決定、數字、檔名與未解問題；不要列已在 open 項裡的事。只輸出摘要本文。")


class Failure(Exception):
    """帶退出碼的輸入或交付失敗。"""
    def __init__(self, message, code=2, hint=None):
        super().__init__(message)
        self.code = code
        self.hint = hint


def load(path, default):
    try:
        return json.loads(read_text(path))
    except FileNotFoundError:
        return default
    except (ValueError, UnicodeError) as e:
        if path.name != "compact.json":  # 自己寫的 state／pending 壞了：做到哪裡不確定，證據留著。
            raise Failure(f"compact/{path.name} 讀不懂（{e}），做到哪裡不確定，檔案原樣留著", 3,
                          hint=f"先看 compact/{path.name}；修好或移走後再跑一次") from e
        raise Failure(f"{path.name} 不是有效 JSON：{e}", hint='請修正 JSON；例：compact.json 可先用 {}') from e


def file_path(node, rel):
    """只接受 node 內的 md／jsonl 記憶檔，避免設定跨出邊界。"""
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
        raise Failure("記憶檔必須是相對 node 的路徑", hint='請給 node 內相對路徑；例：notes/journal.jsonl')
    path = (node / rel).resolve()
    if not path.is_relative_to(node) or path == node or path.suffix not in (".md", ".jsonl"):
        raise Failure("記憶檔須在 node 內，副檔名為 .md 或 .jsonl", hint='請給 node 內 md／jsonl 路徑；例：notes/journal.jsonl')
    if path.is_relative_to(node / "compact"):
        raise Failure("compact/ 是工作資料，不能作為記憶檔", hint='請指定工作資料以外的記憶檔；例：notes/journal.jsonl')
    return path


def config(node):
    obj = load(node / "compact.json", {})
    if not isinstance(obj, dict):
        raise Failure("compact.json 須是物件", hint='請給 JSON 物件；例：{}')
    cfg = dict(DEFAULT, **obj)
    if not isinstance(cfg["files"], list):
        raise Failure("files 須是陣列", hint='請給路徑陣列；例："files": ["notes/journal.jsonl"]')
    for rel in cfg["files"]:
        file_path(node, rel)
    if len(set(cfg["files"])) != len(cfg["files"]):
        raise Failure("files 不能重複", hint='請每個路徑只列一次；例："files": ["notes/journal.jsonl"]')
    for key in ("max_bytes", "keep_recent", "summary_max_chars"):
        if type(cfg[key]) is not int or cfg[key] < (1 if key == "summary_max_chars" else 0):
            raise Failure(f"{key} 須是合法非負整數", hint='請給整數，summary_max_chars 至少 1；例："keep_recent": 10')
    if type(cfg["events"]) is not bool:
        raise Failure("events 須是布林值", hint='請給 true 或 false；例：compact.json 的 "events": false')
    if type(cfg["on_stage_change"]) is not bool:
        raise Failure("on_stage_change 須是布林值", hint='請給布林值；例："on_stage_change": true')
    if type(cfg["stage_similarity"]) not in (int, float) or not 0 <= cfg["stage_similarity"] <= 1:
        raise Failure("stage_similarity 須是 0～1 的數值", hint='請給 0～1 數值；例："stage_similarity": 0.2')
    if cfg["llm"] is not None:
        if not isinstance(cfg["llm"], dict):
            raise Failure("llm 須是物件或 null", hint='請給設定物件或 null；例："llm": null')
        llm = cfg["llm"] = dict(LLM_DEFAULT, **cfg["llm"])
        for key in ("budget", "holder", "model"):
            if not isinstance(llm[key], str) or not llm[key]:
                raise Failure(f"llm.{key} 須是非空字串", hint='請給非空字串；例："holder": "compact"')
        if llm["gateway"] not in ("fake", "litellm"):
            raise Failure("llm.gateway 須是 fake 或 litellm", hint='請給 fake 或 litellm；例："gateway": "fake"')
        for key in ("reserve", "patience"):
            if type(llm[key]) is not int or llm[key] < 0:
                raise Failure(f"llm.{key} 須是非負整數", hint='請給非負整數；例："reserve": 4000')
        if type(llm["deadline"]) not in (int, float) or not 0 < llm["deadline"] <= 86400:
            raise Failure("llm.deadline 須介於 0 與 86400 秒之間", hint='請給 0 到 86400 之間的秒數；例："deadline": 600')
    return cfg


def has_open(value):
    """JSON 字串值中的未完成標記也算 open，包括巢狀值。"""
    if isinstance(value, str):
        return "- [ ]" in value
    if isinstance(value, dict):
        return any(has_open(v) for v in value.values())
    return isinstance(value, list) and any(has_open(v) for v in value)


def physical_lines(text):
    """只按 LF 切實體行，CRLF 與 Unicode 字元原樣留下。"""
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])


def records(text, suffix):
    """回骨架／則的片段；則有索引、原文、open 與可摘要標記。"""
    parts, idx = [], 0
    for line in physical_lines(text):
        if suffix == ".md" and line[:1].isspace() and line.strip() and parts and parts[-1]["index"] is not None:
            parts[-1]["text"] += line
            continue
        record = bool(line.strip()) if suffix == ".jsonl" else line.startswith(("- ", "* "))
        opened, valid = False, True
        if record and suffix == ".md":
            opened = line.startswith(("- [ ]", "* [ ]"))
        elif record:
            try:
                value = json.loads(line)
                opened = (isinstance(value, dict) and
                          (value.get("open") is True or value.get("status") == "open")) or has_open(value)
            except ValueError:
                valid = False  # 壞行算則，但摘要時不把它弄丟。
        parts.append(dict(text=line, index=idx if record else None, open=opened, valid=valid))
        idx += int(record)
    return parts


def read_text(path):
    """不轉換換行，保證 open 原文與整檔雜湊都是原始 bytes。"""
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def flat(text):
    return " ".join(text.split())


def local_summary(old, limit):
    return ("本機摘要：" + "；".join(flat(p["text"])[:60] for p in old))[:limit]


def stage_text(node, cfg):
    rel = next((f for f in cfg["files"] if f.endswith(".md")), None)
    if rel is None or not file_path(node, rel).exists():
        return ""
    active, lines = False, []
    for line in physical_lines(read_text(file_path(node, rel))):
        if line.startswith("## "):
            if active:
                break
            active = True
        elif active:
            lines.append(line)
    return "".join(p["text"] for p in records("".join(lines), ".md") if p["index"] is not None)


def active_indices(text):
    """現役段（第一個 `## ` 到下一個 `## `）裡的則索引：進行中的工作，不摘要（D6 的段落證據也靠它保持原文）。"""
    out, active = set(), False
    for part in records(text, ".md"):
        if part["index"] is None and part["text"].startswith("## "):
            if active:
                break
            active = True
        elif active and part["index"] is not None:
            out.add(part["index"])
    return out


def stage_count(node, cfg):
    return sum(p["index"] is not None for p in records(stage_text(node, cfg), ".md"))


def stage_jaccard(previous, current):
    def bigrams(text):
        text = "".join(text.lower().split())
        return {text[i:i + 2] for i in range(len(text) - 1)}
    a, b = bigrams(previous), bigrams(current)
    return len(a & b) / len(a | b) if a | b else 1.0


def observe_stage(node, cfg, state):
    state = dict(state)
    text = stage_text(node, cfg)
    last, ended = state.get("stage_last", ""), state.get("stage_ended", False)
    if text:
        if ended and last and cfg["on_stage_change"]:
            similarity = stage_jaccard(last, text)
            if similarity < cfg["stage_similarity"]:
                state["stage_due"] = True
                state["stage_evidence"] = dict(ended=True, similarity=similarity, threshold=cfg["stage_similarity"])
        state.update(stage_last=text, stage_ended=False)
    else:
        state.update(stage_last=last, stage_ended=bool(last))
    state.setdefault("stage_due", False)
    return state


def stage_reason(evidence):
    return (f'段落切換（上一段已清空，新段相似度 {evidence["similarity"]:.2f} '
            f'< {evidence["threshold"]:g}）')


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".compact-tmp")
    with tmp.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def cleanup(work, p):
    for name in ("pending.json", f'req-{p["job"]}.json', f'result-{p["job"]}.json'):
        (work / name).unlink(missing_ok=True)


def log_once(work, entry):
    log = work / "log.jsonl"
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                old = json.loads(line)
                if old.get("job") == entry["job"] and old.get("status") == entry.get("status"):
                    return
            except (ValueError, AttributeError):
                pass
    append_jsonl(str(log), entry)


def summarize(node, work, p):
    old = [r for r in records(p["original"], Path(p["file"]).suffix) if r["index"] in p["indices"]]
    text = local_summary(old, p["summary_max_chars"])
    llm = p["llm"]
    if llm is None:
        return text
    req, result = work / f'req-{p["job"]}.json', work / f'result-{p["job"]}.json'
    if not req.exists():
        raw = "".join(r["text"] for r in old)
        request = {"fake": dict(mode="ok", usage=len(raw) // 2 + 50, text=text)} if llm["gateway"] == "fake" else \
            {"litellm": dict(model=llm["model"], messages=[
                dict(role="system", content=PROMPT.format(n=p["summary_max_chars"])),
                dict(role="user", content=f"以下是共 {len(old)} 則舊紀錄：\n" + raw)])}
        write_json(str(req), request)
    if llm["gateway"] == "litellm":
        if not (TOP / "packs/llmcall/aos7_llmcall_litellm.py").is_file():
            raise Failure("摘要沒拿到：現行 llmcall 尚未提供 litellm 傳輸", 3, hint='pending 留著，照原樣再跑一次會接續')
    argv = [sys.executable, str(TOP / "packs/llmcall/bin/aos7-llmcall"), "call", llm["budget"],
            "--holder", llm["holder"], "--call", p["call_id"], "--logical", "compact/" + p["file"],
            "--request", str(req), "--reserve", str(llm["reserve"]), "--deadline", str(llm["deadline"]),
            "--patience", str(llm["patience"]), "--out", str(result)]
    reply = subprocess.run(argv, cwd=node, capture_output=True, text=True)
    if reply.returncode:
        raise Failure("摘要沒拿到：llmcall 退出 " + str(reply.returncode), 3, hint='pending 留著，照原樣再跑一次會接續')
    receipt = read_json(str(result), {})
    text = receipt.get("text") if isinstance(receipt, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise Failure("摘要沒拿到：回條沒有非空 text", 3, hint='pending 留著，照原樣再跑一次會接續')
    if len(text) > p["summary_max_chars"] * 1.5:
        p["truncated"] = True
        text = text[:p["summary_max_chars"]]
    return text


def resume(node, work, p, cfg=None):
    """固定原內容與摘要證據；追加接回，改寫放棄，完成後可選發布事件。"""
    cfg = config(node) if cfg is None else cfg
    path = file_path(node, p["file"])
    if p["kind"] == "compact.done" and "summary" not in p:
        p["summary"] = summarize(node, work, p)
        write_json(str(work / "pending.json"), p)
        test_point("compact-after-summary")
    if p["kind"] == "compact.forget":
        test_point("compact-after-summary")  # forget 跳過摘要後也可注入同一故障點。
    parts = records(p["original"], path.suffix)
    selected = set(p["indices"])
    marker = ""
    if p["kind"] == "compact.done":
        summary = flat(p["summary"])
        marker = (json.dumps(dict(compact="summary", job=p["job"], count=len(selected), text=summary, ref="ref://compact/" + p["job"]), ensure_ascii=False)
                  if path.suffix == ".jsonl" else f'- （摘要 {p["job"]}，{len(selected)} 則）{summary}（原文 ref://compact/{p["job"]}）') + "\n"
    new, inserted = [], False
    for part in parts:
        if part["index"] in selected:
            if not inserted:
                new.append(marker)
                inserted = True
        else:
            new.append(part["text"])  # open、最近 N 則與骨架留原位，一字不改。
    base = "".join(new)
    with (work / "write.lock").open("a") as writer:
        fcntl.flock(writer, fcntl.LOCK_EX)
        current = read_text(path)
        replaced = (not current.startswith(p["original"]) and p.get("new_len") is not None and len(current) >= p["new_len"]
                    and p.get("new_sha") == digest(current[:p["new_len"]]))
        if not replaced:
            if digest(current) == p["sha256"]:
                target = base
            elif current.startswith(p["original"]):
                target = base + current[len(p["original"]):]
            else:
                log_once(work, dict(job=p["job"], file=p["file"], status="abandoned", at=now(), why="記憶檔被改寫"))
                cleanup(work, p)
                print(f'{p["file"]}：原文已被改寫，放棄上次整理，留待重新規劃')
                return dict(job=p["job"], file=p["file"], status="abandoned")
            p["new_sha"] = digest(target)
            p["new_len"] = len(target)
            p["after_bytes"] = len(target.encode("utf-8"))
            write_json(str(work / "pending.json"), p)
        archive = work / "archive" / (p["job"] + ("-forget" if p["kind"] == "compact.forget" else "") + path.suffix)
        if not archive.exists():
            atomic_text(archive, "".join(r["text"] for r in parts if r["index"] in selected))
        test_point("compact-after-archive")
        if not replaced:
            atomic_text(path, target)
            test_point("compact-after-replace")
    entry = dict(job=p["job"], file=p["file"], before_bytes=len(p["original"].encode("utf-8")),
                 after_bytes=p["after_bytes"], count=len(selected), open=sum(r["open"] for r in parts),
                 trigger=p["trigger"], at=p["at"])
    entry["ref"] = "ref://compact/" + archive.stem
    for key in ("evidence", "truncated"):
        if key in p:
            entry[key] = p[key]
    log_once(work, entry)
    cleanup(work, p)
    if cfg["events"]:
        why = None
        try:
            ev = subprocess.run([sys.executable, str(TOP / "modules/events/aos7-events"), "pub",
                                 "--events", str(node / "events"), "--node", node.name, "--kind", p["kind"],
                                 "--event-id", "compact/" + p["job"],
                                 "--payload", json.dumps(entry, ensure_ascii=False)], capture_output=True, text=True)
            if ev.returncode:
                try:
                    why = json.loads(ev.stdout.strip().splitlines()[-1]).get("why")
                except (ValueError, AttributeError, IndexError):
                    pass
                why = why or flat(ev.stdout + " " + ev.stderr)[:500] or f"pub 退出 {ev.returncode}"
        except Exception as error:
            why = f"{type(error).__name__}: {flat(str(error))}"
        if why is not None:
            try:  # 事件是可選通知：連這行記不下也不讓整理算失敗。
                append_jsonl(str(work / "log.jsonl"), dict(job=p["job"], file=p["file"],
                             status="event_failed", why=why, at=now()))
            except OSError:
                pass
        entry["event"] = "failed" if why is not None else "ok"
    human_result(p, entry, archive, parts, current if replaced else target)
    return entry


def human_result(p, entry, archive, parts, target):
    before = sum(r["index"] is not None for r in parts)
    after = sum(r["index"] is not None for r in records(target, archive.suffix))
    if p["trigger"] == "stage_change" and "evidence" in p:
        print("原因：" + stage_reason(p["evidence"]))
    action = "摘掉" if p["kind"] == "compact.done" else "忘掉"
    print(f'{p["file"]}：{before} 則 → {after} 則（{action} {entry["count"]}、open {entry["open"]} '
          f'{"全留" if p["kind"] == "compact.done" else "依指定範圍"}），'
          f'{entry["before_bytes"]} → {entry["after_bytes"]} bytes，原文在 compact/archive/{archive.name}'
          + (f'（原因：{trigger_reason(p["trigger"], p.get("max_bytes"))}）' if p["trigger"] in ("max_bytes", "force") else ""))


def trigger_reason(trigger, max_bytes):
    """dry-run 計畫行與實跑結果行共用同一句原因。"""
    return {"max_bytes": f'大小超過 {max_bytes}', "force": "強制整理（--force）", "stage_change": "段落切換"}[trigger]


def human_plan(plan, cfg):
    if not plan["count"]:
        print(f'{plan["file"]}：不需要整理')
        return
    reason = trigger_reason(plan["trigger"], cfg["max_bytes"])
    if plan["trigger"] == "stage_change":
        reason = stage_reason(plan["evidence"])
    print(f'{plan["file"]}：{plan["records"]} 則，open {plan["open"]}，會摘掉 {plan["count"]} 則（原因：{reason}）')


def pending(work, rel, text, indices, trigger, cfg, kind="compact.done", forget_range=None, evidence=None):
    sha = digest(text)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    job = "c" + stamp + "-" + hashlib.sha256((rel + sha + str(indices)).encode()).hexdigest()[:8]
    p = dict(job=job, file=rel, sha256=sha, original=text, indices=indices, new_sha=None, call_id=job,
             trigger=trigger, kind=kind, at=now(), llm=cfg["llm"], summary_max_chars=cfg["summary_max_chars"],
             max_bytes=cfg["max_bytes"])
    if evidence is not None:
        p["evidence"] = evidence
    if forget_range is not None:
        p.update({"from": forget_range[0], "to": forget_range[1]})
    write_json(str(work / "pending.json"), p)
    test_point("compact-after-pending")
    return p


def save_state(work, previous, current):
    """預設假值與缺欄位等價；只寫真正改變的段落狀態。"""
    def normalized(state):
        state = dict(state)
        for key, default in (("stage_last", ""), ("stage_ended", False), ("stage_due", False)):
            if state.get(key, default) == default:
                state.pop(key, None)
        return state
    if normalized(previous) != normalized(current):
        write_json(str(work / "state.json"), current)
        return dict(current)
    return previous


def once(node, cfg, dry=False, force=False):
    work, entries = node / "compact", []
    saved = load(work / "state.json", {})
    state = observe_stage(node, cfg, saved)
    changed = state["stage_due"]
    evidence = state.get("stage_evidence")
    if not dry:
        saved = save_state(work, saved, state)
    if not dry and (work / "pending.json").exists():
        # 舊 pending 只算它自己那一輪；接完後照樣重評同一檔，新觸發（stage_due）不被它吃掉。
        entries.append(resume(node, work, load(work / "pending.json", None), cfg))
    first = len(entries)
    for rel in cfg["files"]:
        path = file_path(node, rel)
        if not path.exists():
            continue
        text = read_text(path)
        rec = [r for r in records(text, path.suffix) if r["index"] is not None]
        old = rec[:max(0, len(rec) - cfg["keep_recent"])]
        live = active_indices(text) if rel == next((f for f in cfg["files"] if f.endswith(".md")), None) else set()
        indices = [r["index"] for r in old if not r["open"] and r["valid"] and r["index"] not in live]
        trigger = "force" if force else "stage_change" if changed else "max_bytes" if len(text.encode("utf-8")) > cfg["max_bytes"] else "不需要"
        plan = dict(file=rel, records=len(rec), open=sum(r["open"] for r in rec),
                    count=len(indices) if trigger != "不需要" and len(indices) >= 2 else 0, trigger=trigger)
        if changed and evidence is not None:
            plan["evidence"] = evidence
        if not plan["count"]:
            plan["trigger"] = "不需要"
        if dry or not plan["count"]:
            human_plan(plan, cfg)
            entries.append(plan)
        else:
            entries.append(resume(node, work, pending(work, rel, text, indices, trigger, cfg, evidence=evidence if changed else None), cfg))
    if not dry:
        state["stage_due"] = changed and any(e.get("status") == "abandoned" for e in entries[first:])
        if not state["stage_due"]:
            state.pop("stage_evidence", None)
        saved = save_state(work, saved, state)
    return dict(ok=True, dry_run=dry, files=entries)


def forget(node, cfg, args):
    work = node / "compact"
    if not args.dry_run and (work / "pending.json").exists():
        p = load(work / "pending.json", None)
        result = resume(node, work, p, cfg)
        if p["kind"] == "compact.forget" and p["file"] == args.file and [p.get("from"), p.get("to")] == [args.start, args.end]:
            return dict(ok=True, forgotten=result)
        raise Failure("已先接完上次沒做完的整理，檔已變，這次沒忘掉任何則", 1, hint="先用 --dry-run 重看再指定範圍")
    path = file_path(node, args.file)
    if not path.is_file():
        raise Failure("forget 的檔案不存在", hint='請給存在的記憶檔；例：--file notes/journal.jsonl')
    text = read_text(path)
    rec = [r for r in records(text, path.suffix) if r["index"] is not None]
    if not 1 <= args.start <= args.end <= len(rec):
        raise Failure("forget 範圍不合（1 起算，含頭尾）", hint='請給檔案內 1 起算且含頭尾的範圍；例：--from 1 --to 1')
    chosen = rec[args.start - 1:args.end]
    if any(r["open"] for r in chosen) and not args.include_open:
        raise Failure("範圍含 open 項；明確給 --include-open 才能忘掉", hint='請確認要忘掉未完成項再明確加旗標；例：--from 1 --to 1 --include-open')
    if args.dry_run:
        print(f"{args.file}：會忘掉 {len(chosen)} 則，open {sum(r['open'] for r in chosen)}")
        return dict(ok=True, dry_run=True, previews=[r["text"][:80] for r in chosen])
    p = pending(work, args.file, text, [r["index"] for r in chosen], "forget", cfg, "compact.forget", [args.start, args.end])
    return dict(ok=True, forgotten=resume(node, work, p, cfg))


class Parser(argparse.ArgumentParser):
    def error(self, message):
        for en, zh in (("the following arguments are required:", "少了必要參數"), ("unrecognized arguments:", "看不懂的參數"),
                       ("invalid choice:", "沒有這個子命令"), ("expected one argument", "後面少了值"),
                       ("invalid int value:", "要給整數，收到"), ("choose from", "可用")):
            message = message.replace(en, zh)
        example = ("aos7-compact forget <node> --file notes/journal.jsonl --from 1 --to 1 --dry-run"
                   if self.prog.endswith(" forget") else "aos7-compact now <node> --dry-run")
        raise Failure(f"參數不對（{message}）", hint=f"例：{example}，<node> 是工作資料夾路徑；完整用法看 --help")


def main(argv=None):
    """命令列入口；最後一行固定 JSON，watch 每回合鎖住自己的 node。"""
    ap = Parser(prog="aos7-compact", description="把 node（一個工作資料夾）裡太長的記憶檔整理成摘要；原文先存進 <node>/compact/archive/，未完成（open）與最近 10 則留下。",
                epilog="第一次用：now <node> --dry-run 看計畫，再 now <node> 實際整理。記憶檔超過 16384 bytes 才會整理（門檻與常駐 watch 見 ADVANCED.md）。")
    commands = ap.add_subparsers(dest="command", required=True, parser_class=Parser, metavar="{now,forget}")
    a = commands.add_parser("now", help="現在檢查一次，需要就整理", description="檢查一次 node 的記憶檔；需要時（例如檔超過 16384 bytes）才整理。")
    a.add_argument("node", help="node：一個工作資料夾的路徑")
    a.add_argument("--dry-run", action="store_true", help="只印計畫，不寫任何檔")
    a.add_argument("--force", action="store_true", help="不管檔大小，強制整理")
    a = commands.add_parser("forget", help="人手刪掉指定的幾則（原文仍存進 archive）", description="刪掉某個記憶檔的第 A 到 B 則（1 起算、含頭尾）；原文另存 archive。")
    a.add_argument("node", help="node：一個工作資料夾的路徑")
    a.add_argument("--file", required=True, help="記憶檔，相對 node 的路徑，例如 notes/journal.jsonl")
    a.add_argument("--from", dest="start", type=int, required=True, metavar="A", help="第幾則開始（1 起算）")
    a.add_argument("--to", dest="end", type=int, required=True, metavar="B", help="到第幾則（含）")
    a.add_argument("--dry-run", action="store_true", help="只印會刪哪幾則（每則前 80 字），不寫")
    a.add_argument("--include-open", action="store_true", help="now 永遠不摘 open（未完成）項；forget 是你親手刪，範圍含 open 項時要加這個表示確定")
    a = commands.add_parser("watch", description="進階：讓 aos 每回合自動跑一次 now（aos keep 任務，設法見 ADVANCED.md）。手動試用請改用 now。")
    a.add_argument("--rounds", type=int, default=0, metavar="N", help="跑 N 回合就停；不給就一直跑")
    try:
        args = ap.parse_args(argv)
        try:
            me = task_env() if args.command == "watch" else None
        except (KeyError, ValueError) as e:
            raise Failure("watch 需要完整 keep 任務環境", hint='請用完整 aos keep 任務環境；手動例：aos7-compact now <node>') from e
        node = Path(me["node"] if me else args.node).resolve()
        if not node.is_dir():
            raise Failure("node 資料夾不存在", hint='請給存在的 node 資料夾；例：aos7-compact now ./node --dry-run')
        if me and args.rounds < 0:
            raise Failure("rounds 須是非負整數", hint="請給非負整數；例：watch --rounds 1")
        cfg = config(node)
        def run(recover_only=False):
            dry = getattr(args, "dry_run", False)
            if dry:
                lock = node / "compact/lock"
                if lock.exists():
                    with lock.open("rb") as lk:
                        try:
                            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            raise Failure("同一 node 已有 compact 在做，這次沒動任何檔", 3, hint="等它做完再跑一次") from None
                        return forget(node, cfg, args) if args.command == "forget" else once(node, cfg, True, args.force)
                return forget(node, cfg, args) if args.command == "forget" else once(node, cfg, True, args.force)
            work = node / "compact"
            work.mkdir(exist_ok=True)
            with (work / "lock").open("a") as lk:
                try:
                    fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise Failure("同一 node 已有 compact 在做，這次沒動任何檔", 3, hint="等它做完再跑一次") from None
                sweep_tmp(str(work))
                sweep_tmp(str(work / "archive"))
                rels = cfg["files"] + ([args.file] if args.command == "forget" else [])
                if (work / "pending.json").exists():
                    rels.append(load(work / "pending.json", {})["file"])
                for directory in {file_path(node, rel).parent for rel in rels} | {work / "archive"}:
                    for tmp in directory.glob(".*.compact-tmp"):
                        tmp.unlink()
                if recover_only:
                    return resume(node, work, load(work / "pending.json", None), cfg)
                return forget(node, cfg, args) if args.command == "forget" else once(node, cfg, force=getattr(args, "force", False))
        result = None
        if me:
            if (node / "compact/pending.json").exists():
                run(recover_only=True)
            last, rounds = 0, 0
            while not args.rounds or rounds < args.rounds:
                last = wait_tock(me["task"], last)
                cfg = config(node)
                result = run()
                rounds += 1
            result["rounds"] = rounds
        else:
            result = run()
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        code = error.code if isinstance(error, Failure) else 3
        print(json.dumps(dict(ok=False, error=str(error)), ensure_ascii=False))
        if isinstance(error, Failure):
            fact = flat(str(error))
            if code == 3:
                fact = "不確定：" + fact
            hint = error.hint or ("照原樣再跑一次會接續" if code == 3 else "依上述原因修正後再跑；例：aos7-compact now <node> --dry-run")
        else:
            fact = (f"不確定：{type(error).__name__}: {flat(str(error))}，做到哪裡不確定，"
                    "已寫的 pending／archive 留著")
            hint = "照原樣再跑一次會接續"
        print(f"aos7-compact: {fact}。{hint}", file=sys.stderr)
        return code


if __name__ == "__main__":
    sys.exit(main())
