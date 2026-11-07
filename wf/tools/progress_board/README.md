<!-- 說明 aos 進度看板的開關、回報、待裁題、回答、匯總與檔案位置。 -->
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

## 檔案在哪

預設在 `~/Desktop/aos-進度`；可用環境變數 `AOS_PROGRESS_DIR` 換位置。開機或收集會覆蓋頁面與這份說明。

| 路徑 | 內容 |
| --- | --- |
| `index.html`、`app.js`、`asks.js`、`style.css`、`README.md` | 頁面與說明 |
| `data/progress.jsonl` | 各線回報 |
| `data/answers.jsonl` | 使用者逐次送出的回答，保留重答紀錄 |
| `data/state.json`、`data/state.js` | 最新快照 |
| `data/load_history.jsonl` | 最近 720 筆機器取樣 |
| `data/server.pid`、`data/server.log` | 伺服器行程與紀錄 |
| `summary/latest.md`、`summary/history/` | 最新與歷次匯總 |
| `summary/cost.jsonl`、`summary/cursor.json` | 成本與上次涵蓋範圍 |
