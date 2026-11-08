<!-- 說明 aos 進度看板的開關、回報、待裁題、回答、匯總、細節頁與檔案位置。 -->
# 這是什麼

把各線回報、交棒、commit 與機器負載放在同一頁，細節點開才看。

## 怎麼開

`python3 ~/repo/simple_tools/aos/wf/tools/progress_board/dash.py start`

然後開 http://127.0.0.1:8765/ 。設定檔每輪重讀；改連接埠後要重開。

## 不開伺服器

直接開 `~/Desktop/aos-進度/index.html` 看最後快照。
用 `python3 ~/repo/simple_tools/aos/wf/tools/progress_board/dash.py collect` 重產。

## 怎麼關

`python3 ~/repo/simple_tools/aos/wf/tools/progress_board/dash.py stop`

## 各線怎麼回報

`~/repo/simple_tools/aos/wf/tools/progress_post.sh progress-board progress 'Built the snapshot' README.md`

| 狀態 | 意思 |
| --- | --- |
| `start` | 開始這條線 |
| `progress` | 回報進度 |
| `done` | 完成 |
| `blocked` | 卡住 |
| `decision` | 替使用者先做的決定 |
| `ask` | 放一道題目等使用者裁 |
| `handoff` | 交棒給下一位 |

最後可接多個連結或路徑；文字請用引號包住。伺服器沒開也能回報。

## 放題目給使用者裁（ask）

`~/repo/simple_tools/aos/wf/tools/progress_post.sh progress-board ask 'How should we refresh?' --option 'A：Refresh automatically; uses more resources' --option 'B：Refresh manually; requires a click' --recommend A README.md`

每個選項寫成「代號：做法＋後果」，推薦代號必須是其中一個選項；也可不設選項，讓使用者只填補充。指令回傳題目 ID；看板在「待你裁」區列出最近七天的題目。使用者選選項或填補充、按「送出」後才存進本機；已回答的題目會收起。API 可再次送出同題回答，最後一次有效回答為準。離線快照只能看題目，回答要開本機伺服器。

## 讀回答（progress_answers.sh）

`~/repo/simple_tools/aos/wf/tools/progress_answers.sh --line progress-board --since 2026-11-07T00:00:00+08:00`

不帶旗標讀全部回答；`--line` 限定線名、`--since` 限定時間、`--open` 改列尚未回答的題目、`--json` 輸出 JSON Lines（每行一筆 JSON）。讀取不會消耗或刪除回答；agent 用題目 ID 接回原題，依選項和補充繼續工作。

## 怎麼加一條線

改程式旁 `config.json` 的 `lines`，或直接用新線名 post，就會自己長出卡片。
交棒路徑相對於 `aos_repo`，也可用絕對路徑或 `~`。

## 匯總

`config.json` 裡的 `summary.enabled` 控制開關，`min_interval_min` 設最短間隔，`model` 選模型。
有新回報、新回答、交棒更新或新 commit 才會自動跑；失敗也會等間隔，避免一直重試。
「需要使用者決定的事」只列最近七天尚未回答的題目；新收到的回答列在「跟上次比進展了什麼」。
手動跑：`python3 ~/repo/simple_tools/aos/wf/tools/progress_board/dash.py summarize --force`，強制時會略過開關與間隔。
總結在 `summary/latest.md`，每次耗時與 tokens 記在 `summary/cost.jsonl`。

## 細節頁

看板頂端或各線卡片按「看細節」：可看完整時間線、即時交棒檔、相關 commit 的改檔清單、正在跑的 codex 與試驗場報告，每五秒更新。匯總的「看全文」與「歷史匯總」也會開啟渲染後的細節頁。
細節頁與 `/api/line`、`/api/commit`、`/api/codex`、`/api/reports`、`/api/file` 都是唯讀；要開本機伺服器才看得到。

檔案只能讀 `config.json` 的 `read_roots` 底下，且限 `.md`、`.txt`、`.log`、`.json`、`.jsonl`；會解析符號連結，不能跨出允許的根目錄。
要加試驗場報告，在 `report_globs` 加一個 glob；要加可讀位置，在 `read_roots` 加根目錄（可用 `~`）。若用 `AOS_PROGRESS_DIR` 換看板位置，也要把該位置加進 `read_roots`，才能看匯總全文。
要加某線的 commit，在該線 `commit_filters` 加 `{"repo":"aos","path":"wf/tools/progress_board/","grep":"fix"}`；`repo` 對應 `repos` 的名稱，`path` 與 `grep` 可省略，同一條 filter 兩者都有時須同時符合，多條 filter 合併去重。沒有 `commit_filters` 的線不列 commit。

## 輪次頁

各線卡片或細節頁按「輪次」，開啟 `rounds.html?line=<id>`。由新到舊列出各輪里程碑、狀態數字、全部事件、代定與卡住；頁首顯示目前輪次與白話說明。每五秒更新有變動的輪次，保留展開狀態、捲動位置與章節連結；直接開檔案則讀最後快照、不輪詢。

任何狀態都可加 `--round '<name>'`，例如：

```sh
~/repo/simple_tools/aos/wf/tools/progress_post.sh arknights-kb progress 'Reviewing the next batch' --round '第三輪'
```

未指定時，依文字中首次出現的 `第[一二三四五六七八九十0-9]+輪` 或 `批\s*[0-9]+[a-z]?` 推斷；「批5」「批 5」統一為「批 5」。仍找不到就沿用同線上一筆的輪次，第一筆沒有輪次則歸「未分輪」。`state.json` 的各線含 `rounds` 統計與 `current_round`；輪次內保留完整事件。

在 `config.json` 的各線設定 `"round_pages": {"第一輪": "arknights/round1.html", "第二輪": "arknights/round2.html", "第三輪": "arknights/round3.html"}`。對應檔案確實存在時，該輪才顯示「看完整的本輪報告」。

`"sites": [{"mount": "arknights", "dir": "~/Desktop/aos-arknights"}]` 讓本機伺服器以 `/arknights/` 唯讀提供靜態檔案，只允許 GET／HEAD；不列目錄，解析真實路徑後仍須留在根目錄內。看板的網站連結在 HTTP 使用 `arknights/index.html`，檔案快照保留 `../aos-arknights/index.html`。

每次啟動／收集都從該網站複製 `assets/style.css` 到看板的 `assets/ak-style.css`；來源缺少時使用程式隨附的 `web/ak-style.fallback.css`。額外樣式只放 `rounds.css`，原網站始終不寫入。

## 檔案在哪

預設在 `~/Desktop/aos-進度`；可用環境變數 `AOS_PROGRESS_DIR` 換位置。開機或收集會覆蓋頁面與這份說明。

| 路徑 | 內容 |
| --- | --- |
| `index.html`、`app.js`、`asks.js`、`eli5.js`、`detail.html`、`detail.js`、`md.js`、`style.css`、`README.md` | 頁面與說明 |
| `rounds.html`、`rounds.js`、`rounds.css`、`assets/ak-style.css` | 輪次頁與共用網站樣式 |
| `data/progress.jsonl` | 各線回報 |
| `data/answers.jsonl` | 使用者逐次送出的回答，保留重答紀錄 |
| `data/state.json`、`data/state.js` | 最新快照 |
| `data/load_history.jsonl` | 最近 720 筆機器取樣 |
| `data/server.pid`、`data/server.log` | 伺服器行程與紀錄 |
| `data/llm.lock` | 匯總與白話模型呼叫共用的跨行程檔案鎖 |
| `summary/latest.md`、`summary/history/` | 最新與歷次匯總 |
| `summary/cost.jsonl`、`summary/cursor.json` | 成本與上次涵蓋範圍 |

## 白話（ELI5）

「白話」框用日常說法補充總覽、各線、待裁題與細節區塊，原有內容照常保留；沒有說明就不顯示框。
總覽、各線、每道待裁題與細節區塊各自用輸入的 SHA256 判斷變動；只重寫有變的項目，其餘沿用原文字與更新時間。總覽與細節都用 `summary.eli5_min_interval_min` 設最短間隔（預設 4 分鐘），不必等匯總成功才檢查。
每個框末顯示「白話更新於 HH:MM」；原始資料已變、白話還沒跟上時，旁邊顯示「白話更新中」。各線直接提供的待裁題說明改標「各線自己寫的白話」，不顯示更新中。
`summary.eli5_enabled` 控制白話開關，`summary.eli5_max_tokens` 控制每次上限（預設 2500）；連線、模型與逾時沿用匯總設定。
手動更新：`python3 ~/repo/simple_tools/aos/wf/tools/progress_board/dash.py eli5 --force`，略過開關與間隔，仍只重寫有變的項目；加 `--all` 才重寫全部。模型只回一部分時，已成功的項目先存下，缺漏的項目保留舊說明與更新中標記，下輪再試，不把整批誤當成功。
結果放在 `eli5/main.json`、`eli5/detail.json`，每個項目各存文字、更新時間與輸入雜湊，頁面共用 `eli5.js` 顯示；每次請求（包含重寫）都記進 `summary/cost.jsonl`，`kind` 分為 `summary`、`eli5-main`、`eli5-detail`。
發待裁題的人請加 `--eli5 '<plain text>'`，直接說清楚在問什麼、每個選項會怎樣；這份說明優先使用，沒有才自動產生。例如：`~/repo/simple_tools/aos/wf/tools/progress_post.sh progress-board ask 'How much detail?' --eli5 'Choose how much explanation you want.'`。

匯總、總覽白話與細節白話共用 `data/llm.lock`。伺服器碰到鎖已被占用就略過這輪；手動指令最多等 120 秒，仍忙則印 `dash: warning: busy, skipped`。拿到鎖後重新檢查輸入與間隔，避免同時啟動時重複呼叫模型。

## fable 的設計（designs.html）

看板頂端「fable 的設計」按鈕開 `designs.html`：fable（頂層設計者）寫過的每份設計一張卡——一句話結論、一張圖、白話比喻、後來怎樣了，原檔與數字收在「細節」摺疊裡。蒸餾放第一張。

- **卡的內容**在程式旁 `designs.json`（`wf-table/1`，一列一張卡；欄位：`id`、`order` 排序、`doc` repo 相對路徑、`title`、`topic`、`date`、`conclusion`、`eli5`、`figure_svg`、`figures`（多張圖，`[{svg, caption}]`）、`outcome`、`outcome_tag`（採用／部分採用／被翻案／實測沒過／進行中）、`details_md`）。
- **自動發現**：每輪收集照 `config.json` 的 `designs.globs`（預設 `proto8/thinking/**/*fable*.md`）掃 repo；沒寫卡的檔排在最後、標「還沒寫卡」，只顯示檔頭第一句。fable 的規劃檔檔名請帶 `fable`，不然要把 glob 加進 config。
- **圖**：inline SVG，不寫顏色值，只用 class（框 `f-box`＋`f-ok`／`f-bad`／`f-warn`／`f-acc`／`f-muted`，線 `f-line`、箭頭 `marker-end="url(#arr)"`，字 `f-t`、`f-s` 小字、`f-b` 粗），亮暗主題由 `designs.css` 上色。
- **新卡誰寫**：卡的內容是取捨，由該線隊長（opus）讀原檔與後續簡報／代定後寫，或交給 board-fable 線；gpt 不做內容取捨。原設計之後被翻案、實測有新數字，同一位更新 `outcome`／`outcome_tag`。改完 `designs.json` 不用重開伺服器，下一輪收集（15 秒）就生效。
- 結果寫在看板 `data/designs.json`、`data/designs.js`（離線快照也能看）。

## 手機遠端看板

使用者出門時用手機看的 claude.ai artifact（進度、待你裁、論壇）；本機推快照、使用者回答拉回本機。推拉步驟與 db 格式見 [remote/README](remote/README.md)，腳本 `remote_sync.py`。
