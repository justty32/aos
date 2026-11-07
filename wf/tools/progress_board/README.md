<!-- 說明 aos 進度看板的開關、回報、匯總與檔案位置。 -->
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
| `handoff` | 交棒給下一位 |

最後可接多個連結或路徑；文字請用引號包住。伺服器沒開也能回報。

## 怎麼加一條線

改程式旁 `config.json` 的 `lines`，或直接用新線名 post，就會自己長出卡片。
交棒路徑相對於 `aos_repo`，也可用絕對路徑或 `~`。

## 匯總

`config.json` 裡的 `summary.enabled` 控制開關，`min_interval_min` 設最短間隔，`model` 選模型。
有新回報、交棒更新或新 commit 才會自動跑；失敗也會等間隔，避免一直重試。
手動跑：`python3 ~/repo/simple_tools/aos/wf/tools/progress_board/dash.py summarize --force`，強制時會略過開關與間隔。
總結在 `summary/latest.md`，每次耗時與 tokens 記在 `summary/cost.jsonl`。

## 檔案在哪

預設在 `~/Desktop/aos-進度`；可用環境變數 `AOS_PROGRESS_DIR` 換位置。開機或收集會覆蓋頁面與這份說明。

| 路徑 | 內容 |
| --- | --- |
| `index.html`、`app.js`、`style.css`、`README.md` | 頁面與說明 |
| `data/progress.jsonl` | 各線回報 |
| `data/state.json`、`data/state.js` | 最新快照 |
| `data/load_history.jsonl` | 最近 720 筆機器取樣 |
| `data/server.pid`、`data/server.log` | 伺服器行程與紀錄 |
| `summary/latest.md`、`summary/history/` | 最新與歷次匯總 |
| `summary/cost.jsonl`、`summary/cursor.json` | 成本與上次涵蓋範圍 |
