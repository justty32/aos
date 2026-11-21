活清單（工作區的 `wf/progress.json` 進度；等使用者做、驗、裁的也記這裡）怎麼寫：誰記哪裡、何時寫、條目欄位、開場怎麼看、骨架。工作區的活狀態只有兩軸：信、進度。「只列 open、完成即刪」已在 `wf/layers.md#/分層原則`（第 3 條），日誌寫法在 `wf/layers.md#/日誌寫法`，這裡不重講。

# which

## 0

- waiting_for: 使用者做／驗證／決定
- where: 工作區的 `wf/progress.json` 一條，`status` 寫「等使用者」

## 1

- waiting_for: 同 repo 另一個 session／fork，或自己還沒做完的
- where: 工作區的 `wf/progress.json` 一條，`status` 寫 `open`（停著的寫「暫停」或「凍結」）

## 2

- waiting_for: 別資料夾的 agent
- where: 信件（在 aos 裡同一棵樹的 agent 之間是 mailbox，見 `aos/mailbox.md`；不在樹裡的照工作區自己的做法）

# session_start

每個 session 開場先掃兩軸：先看信（`#/which` 第三列），再數進度條目：`python3 -c "import json;print(len(json.load(open('wf/progress.json',encoding='utf-8'))['open']))"`；非 0 才讀；檔不存在就當 0。

# progress

檔還沒有 → 把 `#/skeleton` 抄成工作區的 `wf/progress.json`。
寫入時機：
1. 開始多步驟工作前先寫一條（不是做完才寫）；硬中斷時這份才有「進行中」。
2. 每次 commit 後更新或刪除該條。
條目：`open` 底下一條一個鍵（短的英文代號），欄位照 `#/skeleton/_fields`；完成即刪那一鍵，歷史交給 git log，決策落到 `wf/workflows/decisions.md` 那份記錄。
等使用者的：需要使用者親自做／驗證／決定的事——實機測試、外部服務登入、環境變數、權限、付費、需帳號的下載、去開另一個 agent——也記一條，`status` 寫「等使用者」，`what` 寫請使用者做什麼、`next` 寫做完我接著做什麼。agent 做到結構性驗證的極限，跨不過的那關記這裡；等別的 session／agent 的照 `#/which`。
讀寫：用 json 工具或程式載入、改、寫回（縮排照檔、中文不轉義），不整份手改。
膨脹時：一條的細節寫到別處、`see` 指過去，條目本身留一句。

# skeleton

```json
{
 "_description": "進度：只放還沒完成的活狀態，一條一個鍵，完成就刪那一鍵；等使用者親自做、驗、裁的也記在這裡，status 寫「等使用者」。",
 "_fields": {
  "title": "一句標題",
  "status": "open｜等使用者｜暫停｜凍結",
  "flow": "哪個工作流（空＝不屬任何工作流）",
  "what": "一句現況與剩什麼",
  "next": "下一步（空＝寫在 what 裡）",
  "see": "細節連結（markdown 連結，相對本檔）",
  "since": "YYYY-MM-DD"
 },
 "open": {}
}
```

# aos_note

`aos/mailbox.md#/Mailbox rules` 有 `NEEDS-USER` 狀態；使用者 2026-11-13 裁（收工待裁頁 W11）當時不改、通用版照舊另開一份等使用者清單；2026-11-18 選項框「跟著改 (Recommended)」，通用版改成兩軸（信、進度），等使用者的記進 `wf/progress.json`。
