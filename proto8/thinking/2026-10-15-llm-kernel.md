# 2026-10-15 LLM kernel：請求自己填優先級

← [討論紀錄](README.md)｜前情：[kernel 截流](2026-10-15-kernel-intercept.md)（閘門／信箱草案、六題未決）｜規範：[N-42](../NORMS/09-kernel.md)、[N-16 信箱](../NORMS/05-基礎設施-窗.md)｜概念：[C-47、C-11、C-13](../CONCEPTS/04-kernel.md)｜[`_metainfo`](2026-10-13-json-path/02-metainfo.md)

## 原文（10-15，照記）

「管LLM那塊，這塊很多時候都是確定性的，比如根據誰先來，誰就先上，或是根據token消耗量是否見底來看看說要不要擋，這個沒啥可說的，但我這邊想要提個：在"請求.json"的格式這塊，可以由發送者自己填寫一個優先級key，比如發送者覺得自己不急，那就填低一點，如果很急，那就填一個obj，裡面包括分級、分類、時限等。」

「隨意。我們可以先只處理priority和deadline兩個就好。json就是這點好，因為可以隨意擴充key，反正我們只要處理我們認得的。有需要再用json schema去限制。」（答六題未決）

## 決定（使用者 10-15 定）

- **LLM kernel 的基本規則是確定性的**：誰先來誰先上；token 額度見底就擋。不用腦判斷。
- **請求.json 有一個發送者自己填的優先級 key**：不急就填低一點（簡單值）；很急就填一個物件，裡面有分級、分類、時限等。

## 結論（AI 整理，待使用者確認）

**key 的形狀**：暫叫 `priority`，三種寫法都收——
- 簡單值：`"priority": "low"`（或 `"high"`、或數字 `3`）。
- 物件：`"priority": {"level": "high", "class": "chat", "deadline": "2026-10-15T18:00:00+08:00"}`，欄位都選填。
- kernel 收到先**正規化**：簡單值＝`{"level": 那個值}` 的縮寫；沒寫 key＝`{"level": "normal"}`，照先來先上排。物件裡 kernel 不認得的欄位照帶、不報錯。

**跟 `_metainfo` 的分工**：`_metainfo` 是被叫的 inst 作者自報的「這支跑下去是什麼樣」（靜態、跟著定義走）；`priority` 是呼叫者說的「我這一次多急」（動態、跟著請求走）。兩個都是排序格的輸入（C-11、C-15），建議順序：先看 `level`，同級再看 `_metainfo`（例：樹淺的先、便宜的先），都一樣就先來先上。`_metainfo` 從不蓋過 `level`——急不急只有呼叫者知道。

**跟閘門草案的接法**：agent 不管成本（C-20），所以 `priority` 不由腦或 agent 填，由**閘門**抄進信裡：來源依序＝閘門設定的 `priority` → 環境變數 `AOS_PRIORITY` → 不填。誰起 agent 就誰決定急不急，一整棵樹共用一個值；子 agent 想更急得自己在它的閘門設定寫。信的形狀＝截流草案那封再加一格 `priority`。

**token 額度怎麼擋**：額度放 kernel 自己的 state 窗（例 `{"budget": {"used": …, "limit": …, "since": …}}`），每封回信寫 usage 就加上去；閘門、agent 都不知道額度存在。「擋」＝不排隊、直接回信 N-29 的錯 `BudgetExhausted`，閘門照吐，agent 走既有 `BrainFailed`、連錯停住。不選「等額度回來」：等會吃掉呼叫者的 `timeout_ms`，分不出排隊跟壞了。快見底時可留一段只給 `high` 過（保底）。
- **第一版只處理 `priority`（level）與 `deadline` 兩個**；其他 key（`class` 等）照樣帶著、kernel 不認就不管；需要時再用 JSON schema 限制。`class` 出本版範圍。
- 其餘六題使用者「隨意」＝照建議預設定案（10-15 使用者『隨意』，照建議）：
  - `level` 名字 `low`／`normal`／`high`，數字也收（`<0`／`0`／`>0`）。
  - `deadline` 兩者：越近越前排；到達時已過期不跑、回 `DeadlineMissed`。
  - 濫用：先信任，之後再加每發送者配額。
  - aging：每等 10 拍升一級。
  - token 額度：全局、usage total tokens、一天一期歸零。

## 未決

無（`class` 排序、每發送者配額留待之後）。
