壓完補回走 hook：agent-fsm 開 `before_compact`（能攔、能改指示、能直接給摘要）與 `after_compact`（摘要好了還沒寫進 history 時，能改摘要、能交一段補回的字）兩個點；預設不掛任何 handler，各家要補什麼、要不要整個換掉自己掛。

← [README](README.md)

## 為什麼是這兩個點、為什麼「補回」要在寫進 history 之前

- 今天 hook 想在壓完補東西，只能往自己 queue 寄信：那封信要被答，會多一輪腦呼叫，還要等 idle 才收。
- 若在 history 寫完之後才「接一則 user」：idle 發起的壓縮本來以 `compact done`（assistant）結尾、直接回 idle；尾巴多一則 user 就會多叫一次腦去回應它。
- 所以補回的字跟摘要一起寫：放在摘要那則後面、`compact done` 前面，腦下次真的想事情時看到，不多一輪。這跟 `after_tool`「工具跑完、結果進 history 之前，能改 content」是同一種形狀（phase after、但還能改），有前例。

## 宣告草稿（加進 `templates/agent-fsm/hook_points.json`，抄本一起；格式照現行，見 Q3）

```json
"before_compact": {
 "when": "idle or think: a /compact is about to be done (enough to fold), before old tool outputs are cleared and before the brain is asked",
 "phase": "before",
 "fields": {"letters": "the /compact letter names, in order",
            "instructions": "the words after /compact in the first letter, or an empty string",
            "mid_turn": "true when it came in the middle of a turn",
            "foldable": "how many messages would be folded",
            "clear": "true; a hook may set false to keep old tool outputs as they are",
            "summary": "null; a hook may set one, then the brain is not asked and this summary is folded in"},
 "change": {"instructions": "string", "clear": "any", "summary": "nonempty_string"},
 "block": true,
 "if_blocked": "nothing is cleared or folded and the brain is not asked; the /compact letters get one answer 'compact blocked by hook H' followed by the hook's stdout, shaped like compact not needed (aos.compact, aos.skipped)",
 "fired_in": ["idle.py", "brain.py"]
},
"after_compact": {
 "when": "wait (idle or think when a hook gave the summary or clearing alone was enough): the result is ready, just before history.jsonl is rewritten",
 "phase": "after",
 "fields": {"letters": "the /compact letter names",
            "mode": "summary, or clear when clearing old tool outputs alone was enough",
            "summary": "the summary text; null in clear mode",
            "by": "brain, or the name of the before_compact hook that gave the summary",
            "replaced": "messages folded into the summary (0 in clear mode)",
            "cleared": "tool outputs cleared",
            "mid_turn": "true when it came in the middle of a turn",
            "restore": "null; a hook may set text that goes in as one user message right after the summary (when it is not null, add to what you got)"},
 "change": {"summary": "nonempty_string", "restore": "string"},
 "fired_in": ["wait.py", "idle.py", "brain.py"]
}
```

- 兩點都不收 `condition`（不像工具有名字可比）。`mode` 那個值要等 Q1；Q1 選「不省摘要」就只有 `summary`、`clear` 欄位也還在（關掉清）。
- 每份事件照現行都有 `event`、`hook`、`stack`；handler 要更多就自己讀 stack 裡的檔（`history.jsonl`、`compact.json`、`goal.json`、`tools/todo/todo.json`、`tools/do_task/tasks.json`、`handoff.md`）或叫 `aos-agent history ls`，不往事件裡塞整份 history。
- 太短不做的（`compact not needed`）兩點都不發：沒事發生。

## 補回的字怎麼進對話

- `after_compact` 有人回了 `restore`（非空）：body 寫一則 `{"role": "user", "content": "[aos] restored after compact: …"}`，放在 `[aos] summary:` 那則之後、`compact done` 之前；clear 模式沒有摘要那則，就放在 `compact done` 之前。
- 這則不帶 `aos.letter`（不是信、不用答）。`brain.py` 的 task 模式往回找摘要那段照樣找得到：它找的是「摘要到起點之間的 assistant 都是 compact done」，中間多一則 user 不影響（施工時要加測試守）。
- 多個 hook 照名字排序跑，後一個看得到前一個改過的 `restore`；要接在後面得自己串（說明裡寫明）。

## 「大家各自的 compact 方式」靠 hook 怎麼換

由淺到深三層（Q2 問要開到哪層）：

1. **調**：`before_compact` 改 `instructions`（例：要求摘要照某個格式、加 aos 自己在意的項目），或 `clear: false`（這隻的工具輸出都很小或很重要，不清）。
2. **補**：`after_compact` 交 `restore`。
3. **換**：
   - `before_compact` 直接回一份 `summary`：body 不叫腦，當場用它摺（照舊加要求列再摺，走同一條 `fold`、同樣搬原文進 `history_removed.jsonl`）。handler 可以用便宜的模型自己寫（自己叫 `aos-llm`），也可以完全不用模型（例：拼 `handoff.md` 最後一節＋todo）。
   - `before_compact` 攔下（退 10）：body 什麼都不做，信回一句「被 H 攔下」。handler 可以在攔之前自己用 `aos-agent history rm／summarize／set`（第 3 刀之後還有 `clear-tools`）把 history 改成它要的樣子；body 攔下後不再讀舊的那份。hook 是同步跑的，這段時間沒有別的格在寫 history。

使用者 11-21 說 hook 體系「唯一約定，就是要在interfaces.json中宣告，有宣告就能用，至於怎麽實作的，就是各家自己的事情」：這兩個點宣告在 agent-fsm 的提供者檔，別的身體要有自己的 compact 點，各自宣告。

## 可以補什麼（只列點子，不設計、不預設掛）

照 11-14「需求不清先發想」，下面只是點子，等用起來真的缺什麼再寫 handler：todo 清單；goal 與它的狀態；開著的 do_task（紀錄點已被摺掉，至少讓腦知道還開著）；子 agent 表；board 上自己的項目；從被摺掉的工具呼叫抽出最近碰過的檔名；工作區 `notes.md`；`handoff.md` 上一節；信箱還有幾封沒讀；知識庫入口一句。

## 別家的材料（只當參考；憑對它們的了解，沒讀原始碼、沒逐條查證）

- **Claude Code**：手動 `/compact [指示]` 與快滿時自動壓；壓前有 `PreCompact` hook（帶 trigger＝manual／auto 與自訂指示，就我所知不能改摘要）；壓完以 `SessionStart`（source＝compact）hook 的輸出補進 context——本 repo 的 `.claude/settings.json` 就是這樣掛 `wf/tools/compact_reload.sh` 重讀規矩。另外它在壓之前會先把舊的工具結果清掉（microcompact），壓完重新附上最近讀的檔、待辦。
- **Anthropic API 的 context editing**（`clear_tool_uses`）：快到門檻時把舊的工具結果換成佔位，參數有觸發門檻、留最近幾則（預設 3）、至少清多少、哪些工具不清、要不要連工具輸入一起清（預設不清）。本稿「留最後 3 則、arguments 不清」跟它同向，數字自己量過才定。
- 跟 aos 不同的地方：aos 的 system 提示每次從檔讀、不在 history，不用像 Claude Code 那樣壓完重讀規矩；aos 有 `history_removed.jsonl` 留全文，清掉的東西隨時找得回來。
