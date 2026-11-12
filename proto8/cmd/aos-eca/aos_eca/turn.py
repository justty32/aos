# aos_eca/turn.py - 平級形的一輪（one_turn）：認領一批、hook、slash 分流、交給 cli_session、回答接進 history、冷卻。
import os

import aos_flags

from .common import NAME, Fail, cli_session, cooldown, hooks, goal_state, must_post, names, post, warn
from .history import SUM, append_history, history_changed, history_sum, note_sum
from .hook import before_queue, fire, tool_added
from .batch import SEP, goal_prompt, letter_body, note_progress, pick_one, take_all, transcript_now
from .slash import slash_of, slash_turn
from .reseed import reseed
from .handoff import Handoff


def one_turn(template, stack, ws, empty_code, on_busy, prompt):
    box = os.path.join(stack, "queue")
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        must_post(["init", box])                                   # 先建好，aos-agent say／listen 認得
    try:                                                           # ⑫ on_clock：每輪開頭（queue 建好之後）看一次時鐘（冷卻、退讓的那輪也看）
        hooks.clock_tick(template, stack, warn=lambda line: aos_flags.warn(NAME, line))
    except (hooks.HookFailed, hooks.HooksBad) as e:
        raise Fail(type(e).__name__, e)
    cfg = cli_session.load_cfg(template)
    cell = cli_session.Cell(os.path.join(stack, cfg["kind"]))
    cool, _ = cooldown.state(stack)                                # ⑨ 認領信之前看冷卻（06）
    if cool == "cooling":
        return 0                                                    # 一封都不認領：new/、cur/、history 都不動
    goal = None                                                     # ⑬ 這輪是 goal 提醒＝(題目, 交出去那刻寫的 goal)
    if cool == "due":
        good, bodies, dropped = pick_one(stack, box, prompt, template)       # 冷卻到了：只試最舊的一封
        if not good:
            if dropped:
                return 0
            goal = goal_prompt(stack)
            if goal is None:
                return empty_code
            bodies = [{"role": "user", "content": goal[0]}]
    else:
        take_all(stack, box, prompt)                               # 這輪要答的＝cur/ 全部（上次沒交出去的＋剛認領的）
        batch = names(box, "cur")
        if not batch:
            goal = goal_prompt(stack)
            if goal is None:
                return empty_code
        bodies, good = ([{"role": "user", "content": goal[0]}] if goal else []), []
        for sig in batch:                                           # ② 照順序讀信
            body, why = letter_body(box, sig)
            if body is None:                                        # 壞信一律丟（N-16、決定 27 不通知寄信人）
                post(["done", box, sig])
                warn(stack, sig, why)
                continue
            body = before_queue(stack, box, sig, body, template)   # hook：可改 content、可丟掉這封（整批都丟＝同整批壞信）
            if body is None:
                continue
            bodies.append(body)
            good.append(sig)
        if not good and not goal:
            return 0
    tool_added(cfg, template, stack)                                # hook：登記檔多了誰（交出去之前；hook 停下＝信留 cur/）
    history_changed(stack, cell)                                    # ⑩ history 被改過＝開新對話
    command = slash_of(bodies, goal)
    if command:                                                     # ⑭ 一封信就是一個 slash 指令：aos 這層照 CLI 的意思做
        return slash_turn(command, cfg, cell, template, ws, stack, box, good, bodies, on_busy)

    def count_goal():                                               # ⑬ 交出去才算丟了一次：先記數再接進 history
        try:
            goal_state.write(stack, goal[1])
        except OSError as w:
            aos_flags.warn(NAME, "cannot write %s: %s" % (goal_state.path(stack), w))
    hand = Handoff(template, stack, box, good, bodies, count_goal if goal else None)
    before = transcript_now(cfg, cell)                              # ⑬ 進展：交出去之前對話檔多大
    had_sum = os.path.exists(cell.file(SUM))                        # ⑭ 畫面 hook 跟上 CLI 改 history 時會刪掉它（cli_session.replace_history）
    text = hand.ask(cfg, cell, ws, SEP.join(b["content"] for b in bodies), on_busy,
                    lambda limit: reseed(stack, ws, limit))         # 一批一次（11-03）；跟工具形同一段；stack 給 aos-mcp（11-03 eca-tools）
    if text is None:
        return 0                                                    # SessionBad：整批留 cur/，下一次再試
    synced = had_sum and not os.path.exists(cell.file(SUM))         # 這一輪中間是畫面 hook 跟著 CLI 改的（codex 的 /clear、/compact 在 notify 時才跟上）
    edited = hand.mid is not None and history_sum(stack) != hand.mid and not synced   # ⑩ 這一輪中間被改了（腦叫了 self_history）；跟上 CLI 的不算
    append_history(stack, {"role": "assistant", "content": text[:-1] if text.endswith("\n") else text})
    note_sum(stack, cell, edited)
    note_progress(cfg, cell, stack, before)                         # ⑬ 這輪叫了工具＝goal 計數歸零
    hand.done()                                                     # ⑨ 成功一次＝冷卻歸零；after_queue 停下的最後才報
    return 0
