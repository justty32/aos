# `knowledge/wf/knowledge/live-lists.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/knowledge/live-lists.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

活清單（工作區的 `wf/progress.json` 進度；等使用者做、驗、裁的也記這裡）怎麼寫：誰記哪裡、何時寫、條目欄位、開場怎麼看、骨架。工作區的活狀態只有兩軸：信、進度。「只列 open、完成即刪」已在 `wf/layers.json#/layers`（第 3 條），日誌寫法在 `wf/layers.json#/logs`，這裡不重講。

---

**`#/which`**（陣列，3 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/which/i`）

| i | `waiting_for` | `where` |
|---|---|---|
| 0 | 使用者做／驗證／決定 | 工作區的 `wf/progress.json` 一條，`status` 寫「等使用者」 |
| 1 | 同 repo 另一個 session／fork，或自己還沒做完的 | 工作區的 `wf/progress.json` 一條，`status` 寫 `open`（停著的寫「暫停」或「凍結」） |
| 2 | 別資料夾的 agent | 信件（在 aos 裡同一棵樹的 agent 之間是 mailbox，見 `aos/mailbox.json`；不在樹裡的照工作區自己的做法） |

**`#/session_start`**：每個 session 開場先掃兩軸：先看信（`#/which` 第三列），再數進度條目：`python3 -c "import json;print(len(json.load(open('wf/progress.json',encoding='utf-8'))['open']))"`；非 0 才讀；檔不存在就當 0。

---

**`#/progress`**（原文是字串陣列，8 行）

檔還沒有 → 把 `#/skeleton` 抄成工作區的 `wf/progress.json`。
寫入時機：
1. 開始多步驟工作前先寫一條（不是做完才寫）；硬中斷時這份才有「進行中」。
2. 每次 commit 後更新或刪除該條。
條目：`open` 底下一條一個鍵（短的英文代號），欄位照 `#/skeleton/_fields`；完成即刪那一鍵，歷史交給 git log，決策落到 `wf/workflows/decisions.json` 那份記錄。
等使用者的：需要使用者親自做／驗證／決定的事——實機測試、外部服務登入、環境變數、權限、付費、需帳號的下載、去開另一個 agent——也記一條，`status` 寫「等使用者」，`what` 寫請使用者做什麼、`next` 寫做完我接著做什麼。agent 做到結構性驗證的極限，跨不過的那關記這裡；等別的 session／agent 的照 `#/which`。
讀寫：用 json 工具或程式載入、改、寫回（縮排照檔、中文不轉義），不整份手改。
膨脹時：一條的細節寫到別處、`see` 指過去，條目本身留一句。

---

**`#/skeleton`**（物件，3 個鍵：`_description`、`_fields`、`open`）

**`#/skeleton/_description`**：進度：只放還沒完成的活狀態，一條一個鍵，完成就刪那一鍵；等使用者親自做、驗、裁的也記在這裡，status 寫「等使用者」。

---

**`#/skeleton/_fields`**（物件，7 個鍵：`title`、`status`、`flow`、`what`、`next`、`see`、`since`）

**`#/skeleton/_fields/title`**：一句標題

**`#/skeleton/_fields/status`**：open｜等使用者｜暫停｜凍結

**`#/skeleton/_fields/flow`**：哪個工作流（空＝不屬任何工作流）

**`#/skeleton/_fields/what`**：一句現況與剩什麼

**`#/skeleton/_fields/next`**：下一步（空＝寫在 what 裡）

**`#/skeleton/_fields/see`**：細節連結（markdown 連結，相對本檔）

**`#/skeleton/_fields/since`**：YYYY-MM-DD

**`#/skeleton/open`**：`{}`（空物件）

---

**`#/aos_note`**

`aos/mailbox.json#/rules` 有 `NEEDS-USER` 狀態；使用者 2026-11-13 裁（收工待裁頁 W11）當時不改、通用版照舊另開一份等使用者清單；2026-11-18 選項框「跟著改 (Recommended)」，通用版改成兩軸（信、進度），等使用者的記進 `wf/progress.json`。
