#!/usr/bin/env python3
# train - 訓練迴圈的「跑」格（round3 § 8.2）：set.json 的訓練題 × writers 每個強制跑一次（題目 JSON 加 "writer"＝題目級覆寫），
# 小格 $AOS_STACK/epochs/NNN/runs/<題名>-<寫手>/{ws,stack}，根用 aos-exec --ws 小格/ws 跑；已有 ws/out/<題名>/score.json 的跳過（被殺重跑接著做）。
# 每跑一題之前看一次預算（budget.json 的 max_calls／max_tokens／max_elapsed_ms，算整個訓練 stack 的用量），到頂＝BudgetSpent 退 2。
# 跑完把這個 epoch 的用量寫進 epochs/NNN/usage.json（{counter_calls, counter_tokens}；calls 數寫手、評審 history 的 assistant 則數，tokens 加 usage.jsonl）。
# 只寫 stack，不碰樹。錯：stderr 一行「train: 代號 原因」、退 1——StackMissing、StateBad、SetBad、RunFailed（根退非 0；現場在小格）。
import os, sys

sys.dont_write_bytecode = True                      # 不在樹裡留 __pycache__/
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as c  # noqa: E402

st = c.stack()
sets, budget = c.settings()
n = c.epoch(st)
here = c.edir(st, n)
for q in sets["train"]:
    base = q[:-5] if q.endswith(".json") else q
    for w in sets["writers"]:
        cell = os.path.join(here, "runs", "%s-%s" % (base, w))
        if os.path.isfile(os.path.join(cell, "ws", "out", base, "score.json")):
            continue
        c.check_budget(st, budget)
        rc, _ = c.run_question(cell, q, writer=w)
        if rc != 0:
            c.die("RunFailed", "訓練題 %s × %s 結束碼 %d（現場在 %s）" % (q, w, rc, cell))
c.save(os.path.join(here, "usage.json"), c.usage_of(here))
