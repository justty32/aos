# aos_eca/slash.py - ⑭ slash 指令（/clear、/compact、/status、/usage、/exit、/goal）在 aos 這層怎麼做。
import fcntl
import json
import os
import re
import subprocess
import time

import aos_flags

from .common import Fail, cli_ask, cli_base, cli_cell, cli_hook, must_post
from .history import append_history, history_rows, note_sum
from .hook import fire
from .handoff import Handoff


# ---- ⑭ slash 指令（11-12 thinking eca-slash；使用者「aos-say/listen我希望也能支援這些」「chat也要」）----
# 實測（claude 2.1.322、codex 0.167.1）：claude -p 認 /compact（同一個 id 壓縮、result 空）、/clear（回新 id，但 --resume 的 aos 不記）、
# /usage（印額度）；/status、/exit 回「isn't available in this environment」。codex exec 一個都不認（當成一般題目給模型）。
# 所以：一批只有一封、內容（去頭尾空白）剛好是下面其中一個＝aos 這層做（CLI 原生認得的才交給它），回答一則 [aos] slash: …；
# 其他（多封一批、後面還帶字）照一般題目交出去。
# /goal（11-12 晚，使用者「eca還有一個slash command我很常用：/goal」「包括/goal clear」）只有它放寬成「以 /goal 開頭」（後面帶目標或 clear 等）；
# 實測 claude -p 認 /goal（`/goal 條件`＝設了就照跑一輪、`/goal clear`、`/goal` 查看；目標只活在那一次 claude -p 裡，下一次查看＝No goal set），
# codex exec 不認（當成題目），codex 畫面認 `/goal [<objective>|clear|edit|pause|resume]`。

SLASH = ("/clear", "/compact", "/status", "/usage", "/exit")
GOAL = "/goal"

# codex 畫面已有 goal 時再 /goal 新目標，會跳「Replace goal?」選單（11-12 實拍 0.167.2：標題「Replace goal?」、「New objective: …」、
# 「› 1. Replace current goal  Set the new objective and start it now」「2. Cancel  Keep the current goal」「enter select · esc back」，
# 預設停在 1，Enter＝選它）。使用者「幫我處理，要自動說選yes」：只認這一個選單，而且游標停在 1. Replace current goal 才按 Enter。
REPLACE_WAIT = 5                                          # 秒：打進 /goal 之後等這個選單出現多久


def goal_replace_prompt(screen):
    """畫面字（capture-pane）最後 30 行是不是 codex 的「Replace goal?」選單：'yes'＝是、游標在 1. Replace current goal、也有 2. Cancel；
    'other'＝有那個標題、但選單長得不一樣（不亂按）；None＝沒有。選單畫在畫面中間，同一行左邊可能還有別的字，所以不錨行首。"""
    tail = "\n".join((screen or "").splitlines()[-30:])
    if "Replace goal?" not in tail:
        return None
    if re.search(r"›\s*1\.\s*Replace current goal\b", tail) and re.search(r"\b2\.\s*Cancel\b", tail):
        return "yes"
    return "other"


def confirm_goal_replace(cell):
    """打進 codex 畫面的 /goal 之後：最多等 REPLACE_WAIT 秒看有沒有「Replace goal?」選單；認得＝按 Enter（選 1. Replace current goal）。
    回接在 [aos] slash 那則後面的一句（沒有選單＝空字串）。"""
    def screen():
        return cell.tmux("capture-pane", "-p", "-t", cli_base.TMUX_SESSION).stdout
    deadline, seen = time.time() + REPLACE_WAIT, None
    while time.time() < deadline:
        seen = goal_replace_prompt(screen())
        if seen:
            break
        time.sleep(0.3)
    if seen is None:
        return ""
    if seen == "other":
        return "; codex asked something about replacing the goal that aos does not recognise, so nothing was pressed: answer it on the screen (aos-agent open)"
    cell.tmux("send-keys", "-t", cli_base.TMUX_SESSION, "Enter")
    time.sleep(1)
    if goal_replace_prompt(screen()):
        return "; codex asked \"Replace goal?\" and aos pressed Enter for \"1. Replace current goal\", but the question is still there: check the screen"
    return "; codex asked \"Replace goal?\" and aos chose \"1. Replace current goal\" (yes) for you"


def slash_of(bodies, goal):
    if goal or len(bodies) != 1:
        return None
    text = bodies[0]["content"].strip()
    if text == GOAL or text.startswith(GOAL + " "):
        return GOAL
    return text if text in SLASH else None


def cli_goal(kind, transcript):
    """CLI 自己的對話檔裡最後記下的 goal（/status 用）："目標 (狀態)"；沒有＝None。claude＝attachment goal_status（condition、met）；
    codex＝event thread_goal_updated（objective、status）。11-12 實測：清掉（/goal clear）兩邊都沒另記一筆，所以只說「最後記下的」。"""
    last = None
    try:
        with open(transcript, encoding="utf-8") as f:
            for line in f:
                if "goal" not in line:
                    continue
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(m, dict):
                    continue
                if kind == "claude":
                    a = m.get("attachment")
                    if isinstance(a, dict) and a.get("type") == "goal_status" and a.get("condition"):
                        last = "%s (%s)" % (a["condition"], "met" if a.get("met") else "not met yet")
                else:
                    p = m.get("payload") if isinstance(m.get("payload"), dict) else m
                    g = p.get("goal") if isinstance(p, dict) and p.get("type") == "thread_goal_updated" else None
                    if isinstance(g, dict) and g.get("objective"):
                        last = "%s (%s)" % (g["objective"], g.get("status") or "?")
    except (OSError, TypeError):
        return None
    return last


def note(text):
    return aos_flags.aos_note("slash", text)


def model_of(cfg):
    flags = cfg.get("flags", [])
    return flags[flags.index("--model") + 1] if "--model" in flags[:-1] else "(the CLI's default)"


def slash_status(cfg, cell, stack):
    sid = cell.read("session.txt")
    found = cli_cell.transcripts(cfg["kind"], sid)
    goal = cli_goal(cfg["kind"], found[0]) if found else None
    return note("/status: %s, model %s; conversation %s; screen %s; history %d messages; transcript %s%s" % (
        cfg["kind"], model_of(cfg), sid or "(none yet: the next message starts one)",
        "open" if cell.alive() else "closed", len(history_rows(stack)), found[0] if found else "(none)",
        "; last goal the CLI recorded: %s" % goal if goal else ""))


def slash_usage(cfg, ws):
    """claude：另起一次 claude -p（不存對話、不碰這隻的 session）問 /usage，原樣回它的字；codex exec 沒有對應的。"""
    if cfg["kind"] != "claude":
        return note("/usage: codex has no usage report outside its own screen; open the screen (aos-agent open) and type /usage there")
    try:
        r = subprocess.run(["claude", "-p", "--output-format", "json", "--no-session-persistence"], input="/usage",
                           stdout=subprocess.PIPE, text=True, cwd=ws, timeout=cfg.get("timeout_ms", 600000) / 1000)
    except FileNotFoundError:
        raise Fail("CliMissing", "claude is not on PATH")
    except subprocess.TimeoutExpired:
        raise Fail("CliFailed", "claude -p /usage did not finish in time")
    out = None
    for line in (r.stdout or "").splitlines():                     # json 是一個物件；保險起見取最後一個帶 result 的那行
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and "result" in ev:
            out = ev
    if r.returncode != 0 or not isinstance(out, dict) or out.get("is_error") or not isinstance(out.get("result"), str):
        raise Fail("CliFailed", "claude -p /usage exited %d: %s" % (r.returncode, (r.stdout or "").strip()[-300:]))
    return out["result"]


SCREEN_WAIT = 120                                  # 秒：貼進 claude 畫面的 /clear、/compact 等 hook 改完 history 的上限（compact 實測 4～25 秒）


def history_bytes(stack):
    try:
        with open(os.path.join(stack, "history.jsonl"), "rb") as f:
            return f.read()
    except FileNotFoundError:
        return b""


def on_screen(command, cfg, cell, stack):
    """畫面開著：/clear、/compact 照人打的一樣打進畫面（使用者 Q2「幫我貼進去」）；aos 這邊靠畫面 hook 跟上（id、history）。
    claude＝等 hook 把 history 改掉（SessionStart clear／compact）再回，免得這輪接的 user／回答被 hook 一起搬走；等不到（上限 SCREEN_WAIT）照回、多說一句。
    codex＝這時沒有事件：/clear 等下一輪 notify 看到新 thread 才清；/compact 等它的 rollout 多一個 compacted（上限 SCREEN_WAIT），
    再 cli_hook.codex_sync_compact（history 換成從 replacement_history 撈出的對話；撈不到＝不動、回一句，Q5）。"""
    before = history_bytes(stack)
    sid = cell.read("session.txt")
    if cfg["kind"] != "claude" and command == "/compact" and sid:
        n0 = cli_hook.codex_note_compacts(cell, sid)            # Q5：打之前壓過幾次＝基準
        cli_ask.type_line(cell, command)
        deadline = time.time() + SCREEN_WAIT
        while time.time() < deadline and cli_hook.codex_compacted(sid)[0] <= n0 and cell.alive():
            time.sleep(0.5)
        try:
            got = cli_hook.codex_sync_compact(cell, sid, stack)
        except OSError as e:
            raise Fail("WriteFailed", "cannot rewrite history.jsonl: %s" % e)
        if got is None:
            return note("/compact: typed into the open screen; codex did not record a compaction within %d s, aos's history is left as it is" % SCREEN_WAIT)
        if got[0] == "unrecognized":
            return note("/compact: typed into the open screen; codex compacted, but aos could not read the conversation out of it, so aos's history is left as it is")
        return note("/compact: typed into the open screen; history replaced by the conversation codex kept (%d messages moved to history_removed.jsonl)" % got[1])
    cli_ask.type_line(cell, command)
    if cfg["kind"] != "claude":
        later = ("aos clears its history when the next answer comes from the new thread" if command == "/clear" else
                 "there is no conversation yet, so there is nothing for aos to follow")
        return note("%s: typed into the open screen; %s" % (command, later))
    deadline = time.time() + SCREEN_WAIT
    while time.time() < deadline and history_bytes(stack) == before and cell.alive():
        time.sleep(0.5)
    if history_bytes(stack) == before:
        return note("%s: typed into the open screen; aos's history did not change within %d s (check the screen: aos-agent open)"
                    % (command, SCREEN_WAIT))
    done = "history moved to history_removed.jsonl" if command == "/clear" else "history replaced by claude's summary (the old messages are in history_removed.jsonl)"
    return note("%s: typed into the open screen; %s; conversation %s" % (command, done, cell.read("session.txt")))


def slash_turn(command, cfg, cell, template, ws, stack, box, good, bodies, on_busy):
    """⑭ 做這個指令、照一般一輪記 history（user 那封＋一則回答；/clear、/compact 先改 history 再記），信收掉、after_queue 照跑。
    沒畫面、交給 claude -p 的 /goal、/compact 整段照一般一輪（Handoff：交出去那刻收信、失敗記冷卻與 brain_failed、成功冷卻歸零；11-12 晚）。
    畫面開著時 /clear、/compact 打進畫面（on_screen；畫面正在跑一輪＝busy.txt 在＝這次不動、信留 cur/、下一輪再試），/exit＝關畫面。"""
    kind, alive = cfg["kind"], cell.alive()
    cleared, hand = None, None
    if command == GOAL:                                             # /goal …：CLI 自己的 goal，aos 只負責交到它手上
        full = bodies[0]["content"].strip()
        if alive:
            if os.path.exists(cell.file("busy.txt")):
                return 0                                            # 不打斷正在跑的那輪
            cli_ask.type_line(cell, full)
            text = note("/goal: typed into the open screen; the CLI's own answer shows there (a goal it runs on is also kept in turns.jsonl)%s"
                        % (confirm_goal_replace(cell) if kind == "codex" and full != GOAL else ""))
        elif kind == "claude":
            hand = Handoff(template, stack, box, good, bodies)
            got = hand.ask(cfg, cell, ws, full, on_busy)              # claude -p 認得：設了就照跑一輪
            if got is None:
                return 0                                            # SessionBad：同一般一輪，信留 cur/
            text = got.strip() or note("/goal: claude printed nothing")
        else:
            text = note("/goal: codex has /goal only on its screen (codex exec would read it as a plain question); "
                        "open the screen (aos-agent open) and send it again")
    elif command == "/status":
        text = slash_status(cfg, cell, stack)
    elif command == "/usage":
        text = slash_usage(cfg, ws)
    elif command in ("/clear", "/compact") and alive:
        if os.path.exists(cell.file("busy.txt")):
            return 0                                                # 不打斷正在跑的那輪
        text = on_screen(command, cfg, cell, stack)
    elif command == "/compact" and kind == "claude":
        if not cell.read("session.txt"):
            text = note("/compact: no conversation yet, nothing to compact")
        else:
            hand = Handoff(template, stack, box, good, bodies)
            got = hand.ask(cfg, cell, ws, "/compact", on_busy)         # claude -p --resume 認得：同一個 id 壓縮
            if got is None:
                return 0                                            # SessionBad：同一般一輪，整批留 cur/，下一次再試
            sid = cell.read("session.txt")
            found = cli_cell.transcripts("claude", sid)
            summary = cli_hook.compact_summary(found[0]) if found else None
            try:                                                    # Q3：history 換成 claude 的摘要；交出去那刻接進的 /compact 留在摘要後面（keep_tail）
                moved = None if summary is None else cli_hook.replace_history(cell, "compact", summary, stack, keep_tail=True)
            except OSError as e:
                raise Fail("WriteFailed", "cannot rewrite history.jsonl: %s" % e)
            text = got.strip() or note("/compact: claude compacted conversation %s (same id); %s" % (sid,
                "history replaced by its summary (%d messages moved to history_removed.jsonl)" % moved if moved is not None
                else "no summary found in its transcript, history left as it is"))
    else:                                                           # /clear、codex 的 /compact、/exit：動小格，拿 lock
        f, ok = cell.lock()
        if not ok:
            if on_busy == "yield":
                return 0
            fcntl.flock(f, fcntl.LOCK_EX)
        with f:
            if command == "/exit":
                if not alive:
                    text = note("/exit: no screen is open, nothing to end (the agent stays; aos-agent ctl stop stops it)")
                elif cell.clients():
                    text = note("/exit: someone is attached to the screen; not closed (they can type /exit there)")
                else:
                    cli_cell.close(cell)
                    text = note("/exit: closed the screen; the conversation stays and the next message goes on without a screen")
            elif command == "/compact":                             # codex exec 不認 /compact：換新 thread、帶 aos 的紀錄過去（同 ⑧）
                cli_cell.drop_session(cell)
                text = note("/compact: codex cannot compact outside its screen; the next message starts a new codex thread "
                            "that carries aos's record of this conversation (up to reseed_bytes)")
            else:
                try:
                    cleared = cli_hook.clear_history(cell, stack)
                except OSError as e:
                    raise Fail("WriteFailed", "cannot clear history.jsonl: %s" % e)
                cli_cell.drop_session(cell)
                text = note("/clear: %d messages moved to history_removed.jsonl; the next message starts a new %s conversation" % (cleared, kind))
    if hand:                                                        # 交出去那刻已接進 history、收信、after_queue 跑過
        append_history(stack, {"role": "assistant", "content": text})
        note_sum(stack, cell, False)
        hand.done()
        return 0
    for body in bodies:
        append_history(stack, body)
    for sig in good:
        must_post(["done", box, sig])
    try:
        for sig, body in zip(good, bodies):
            fire("after_queue", {"letter": sig, "content": body["content"]}, template, stack)
    finally:
        append_history(stack, {"role": "assistant", "content": text})
        note_sum(stack, cell, False)
    return 0
