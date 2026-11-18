這份教你手動幫 eca-claude 做 compact（把長對話壓成摘要），並用 `aos-agent history` 自己改對話紀錄當替代（試驗 19，11-18 晚在家機用 haiku 實跑過）。
← [目錄](README.md)

使用者原話：「手動幫它 compact」

## 結論

- **最簡單：把 `/compact` 當一句話寄給它**：`aos-agent say -t ann /compact`（或 `/compact 指示`）。這是 eca-claude 範本的規矩（範本 README 寫「寄一封內容只有 `/compact` 的信」）。`/compact` 那封自己成一批，不會跟別的話混在一輪。
- 壓完之後回你一行 `[aos] slash: /compact: claude compacted conversation <編號> (same id); history replaced by its summary (N messages moved to history_removed.jsonl)`。**對話編號沒變**、claude 還認得摘要裡留下的事（我先告訴它暗號 `MANGO-42`，壓完問它，答 `MANGO-42`）。
- `aos-agent history ls` 看到的紀錄也跟著換了：前面全部換成**一則** `[aos] summary: …`，加上你那句 `/compact` 與它的回覆。**原文沒丟**，搬到 stack 的 `history_removed.jsonl`。
- **`/compact 指示` 的指示是真的有用的，也真的會丟東西**：我寫 `/compact keep only the color, drop everything else`，壓完它只記得顏色，動物（OTTER）它說「沒留」。別拿重要的事賭，要留的就寫進指示或交接檔。
- 替代做法：自己用 `aos-agent history summarize／rm` 改紀錄（先 `ctl pause`）；一樣把原文留在 `history_removed.jsonl`。

都在 `~/aos-home` 打，樹照 [README 的「共同準備」](README.md#共同準備)起好、ann 掛上、haiku。

## 一步一步

**1. 先讓它有東西可以忘**

```sh
aos-agent -d .stack -t ann ask "Remember this: the secret word is MANGO-42. Reply with the single word: ok"
cat .stack/procs/ann/claude/session.txt; aos-agent -d .stack -t ann history ls | wc -l
```

會看到 `ok`；`session.txt` 是對話編號（例 `4e088aeb-08ef-4ffa-8736-a930d90adb9a`）。我這時對話裡已經有 16 則（前面幾個試驗留下的），所以壓出來的摘要才有東西。

**2. 寄 /compact**

```sh
L=$(aos-agent -d .stack -t ann say /compact); aos-agent -d .stack -t ann listen --letter $L --timeout-s 120
```

會看到：

```
[aos] slash: /compact: claude compacted conversation 4e088aeb-08ef-4ffa-8736-a930d90adb9a (same id); history replaced by its summary (16 messages moved to history_removed.jsonl)
```

**3. 看變成什麼樣**

```sh
cat .stack/procs/ann/claude/session.txt; aos-agent -d .stack -t ann history ls | cut -c1-150
```

```
4e088aeb-08ef-4ffa-8736-a930d90adb9a
1	user	[aos] summary: lines 1-16, 16 messages. This session is being continued from a previous conversation that ran out of context. The summary below covers the earlier portion of the conversation.\n\n<syst…
2	user	/compact
3	assistant	[aos] slash: /compact: claude compacted conversation … (same id); history replaced by its summary (16 messages moved to history_removed.jsonl)
```

第 1 則就是 claude 寫的摘要全文（我這份約 2.7 KB，分「Primary Request and Intent」「Key Technical Concepts」等段，裡面有 `MANGO-42` 那句）。`history_removed.jsonl` 有 16 行，每行 `{"removed_at", "op": "compact", "line", "message"}`。

**4. 問它還記不記得**

```sh
aos-agent -d .stack -t ann ask "What is the secret word? Reply with the word only."
```

會看到 `MANGO-42`。

**5. 帶指示的 /compact**

```sh
aos-agent -d .stack -t ann ask "Remember: the color is TEAL-7 and the animal is OTTER. Reply: ok"
L=$(aos-agent -d .stack -t ann say "/compact keep only the color, drop everything else"); aos-agent -d .stack -t ann listen --letter $L --timeout-s 120
aos-agent -d .stack -t ann ask "What are the secret word, the color and the animal? Short."
```

會看到壓完回 `… (7 messages moved to history_removed.jsonl)`。問它的答案：

```
- **Secret word:** I don't have one. None was given in the conversation I still have.
- **Color:** TEAL-7
- **Animal:** Not kept. Your `/compact` asked me to keep only the color. The earlier transcript has OTTER, and I can read it if you want it back.
```

指示被照辦了：連上一輪的 `MANGO-42` 也一起被丟。它說「earlier transcript」還讀得到：原本的 claude 對話檔（`~/.claude/projects/…`）沒刪。

**6. 替代：自己改紀錄（history summarize／rm）**

```sh
aos-agent -d .stack ctl pause ann
aos-agent -d .stack -t ann history summarize 1-3 "earlier talk was small tests; the animal is OTTER"
aos-agent -d .stack -t ann history ls | cut -c1-120
aos-agent -d .stack ctl resume ann
aos-agent -d .stack -t ann ask "What is the animal? one word"
```

會看到：`replaced 3 messages with one user message at line 1; the originals are in history_removed.jsonl in the stack of ann`；紀錄變成 `1 user [aos] summary: lines 1-3, 3 messages. earlier talk was small tests; the animal is OTTER` 加後面的對話。`resume` 之後問動物，答 `OTTER`：**eca 下一輪認出紀錄被改過，開新對話、帶著改過的紀錄過去**（範本 README 的說法；我是從答案看到摘要生效，沒另外去看新的對話編號）。

`history rm 1` 刪第一則，說 `removed 1 message from line 1; the originals are in history_removed.jsonl in the stack of ann`。範圍寫法 `N`、`A-B`、`A-`；`--no-keep` 才不留原文。

## 自動 compact（沒實測）

範本有一個 hook `context_wrap`（`hooks.json` 裡的格，每 5 秒看一次用量）：context 用到 35% 時，先寄一封叫它把手上的事寫進交接檔（`<stack>/handoff.md`），答完、queue 空了，再自己寄一封 `/compact`。範本的 `cli.json` 另帶 `PreCompact`／`SessionStart` 兩個 hook（`compact_hook`），壓完提醒它讀回交接檔。這次的對話太短，用量沒到門檻：`hooks/context_wrap/` 裡只有 `event.json`、`on_clock.json`，沒有 `state.json`（到門檻才會寫），所以這一段**未實測**。

## 沒實測的

- 自動 compact（`context_wrap`）整條，含 `handoff.md`、`compact_hook` 印出的提醒。
- 一輪進行中寄 `/compact`、或暫停時寄 `/compact`。
- 用 `aos-agent history set LINE JSON` 整則換掉某一行。
- 真的對話長到快滿的時候壓縮要多久（這次沒計時）。

## 發現的問題

1. **指示會丟東西**：`/compact keep only …` 連前一次摘要裡的暗號也丟了，要留的事自己寫進指示。
2. `history ls` 預設截 200 字，摘要整份要 `history ls -l` 或直接 `python3` 讀 `history.jsonl`（不能用 `aos-json-view`，見 [17](17-手動看agent狀態.md)）。
