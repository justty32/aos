# 2026-10-15 報時員（agent 當工具）用 LM Studio 實跑

← [thinking](README.md)｜前一次 LM Studio：[topics §9](2026-10-15-topics/03-試146-qwen與LM-Studio.md#9-試-lm-studioqwen3-17b)｜demo：demo/fsm（已刪，見 git 歷史 aa2fec1f）｜機制：agent.md

**原文**：使用者 10-15「用 LM Studio 實跑一次報時員」。

**做法**：`lms server start -p 1234`、`load qwen/qwen3-1.7b -c 4096 --ttl 600 -y`（3.4 秒載好）。在 scratchpad 複製 demo/fsm，外層與報時員的腦都換成 LM Studio（各包一層計時包裝，只記時間、不改請求）；放一封信「現在幾點？」。只改實跑副本：`loop.json` 的 `timeout_ms` 20 秒→600 秒、`times` 10→14、`tools/clerk.json` 120→500 秒、`cells/tool.json` 150→550 秒、`max_steps` 20。共跑 2 趟、7 次 chat 請求。收尾 `unload --all`、`server stop`，`lms ps` 空、server 沒開、1234 連不上。

**結果**

| 趟 | 外層叫 clerk | clerk 叫 clock | 最後回覆 | 叫腦延遲 | 全程 |
|---|---|---|---|---|---|
| 1 | 是（引數 `{"question":"現在幾點？"}`） | **沒叫**，直接編了「現在是10:30:45」（真實時間約 12:03，編的） | 「現在是10:30:45。」 | 外層 3.3／3.7 秒、clerk 5.1 秒 | 16.4 秒 |
| 2 | 是 | 是（`clock`，arguments `{}`），拿到 12:03:08 | 「現在時間是12:03:08。」 | 外層 2.7／4.9 秒、clerk 3.9／4.0 秒 | 20.4 秒 |

- 外層 tool 那拍（clerk 整趟）5.5～9 秒，外層只拿到 `{"reply","ticks"}`；第 1 趟 ticks=2（少了 tool 那圈）、第 2 趟 5。
- tool_calls 沒有畸形：id 是 32 字亂數、arguments 都是合法 JSON 字串、content `""`。外層一次只叫一個工具，沒有一次多個。
- 語言與簡短：兩層都是繁體中文、一句話，system.md 有被遵守（沒有簡體、沒有英文）。
- 外層把 clerk 的結果自己加了句號重述，沒亂改時間。

**挖到的邊緣狀況（攤給使用者）**
- **小模型有時不用工具、直接編答案**（1.7B 在 2 趟裡有 1 趟）。clerk 的 system.md 已寫「用 clock 查，不要自己猜」仍會發生；外層看不出（回的格式一樣、只有 ticks 少），上層沒辦法驗真偽。要治只能靠提示加強、換大模型，或在 clerk 規則上強制至少叫一次工具；是否值得做由使用者定。
- 預設 demo 的 `loop.json` 20 秒（含 clerk 內整趟）對真腦太緊，這次實跑 16～20 秒，剛好卡邊；README 已有提醒，沒改預設檔。

- **決定**：10-15 使用者「隨意」→ 先不處理小模型（Qwen3-1.7B）不查 clock 就編答案的問題；proto8 接受此限制。日後要治時的候選：加強提示、換大模型、在表上強制「沒叫過工具不准回答」（環境保證，C-22b 思路）。
