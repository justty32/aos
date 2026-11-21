# `knowledge/wf/workflows/_index.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/workflows/_index.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**（index：鍵 → 一句說明）

| 鍵 | 說明 |
|---|---|
| `_description.json` | 這一夾是什麼、路徑怎麼讀、派發通則（怎麼選、可以跳流程、都不符去哪）；不確定該走哪條時讀。 |
| `decisions.json` | 記決定的流程（只記結論、來源與前提）；使用者說「記個決定」「為什麼選 A 不選 B」、或選定方案後日後可能被問時讀。 |
| | （其他鍵：`{"kind": "workflow", "source": "kernel"}`） |
| `planning.json` | 想法成熟管線（idea → roadmap → 詳規 → 執行）；使用者說「記個想法」「以後要做」「排進 roadmap」「幫我規劃」、開發專案說「討論方案」「寫動工計畫」時讀。 |
| | （其他鍵：`{"kind": "workflow", "source": "kernel"}`） |
| `gotchas.json` | 記／查踩坑的流程（第二次撞到才記）；使用者說「記個踩坑」「記／查踩坑」「上次也是這樣」、或動手前要查以前撞過沒時讀。 |
| | （其他鍵：`{"kind": "workflow", "source": "kernel"}`） |
| `user.json` | 記使用者偏好與確認邊界的流程；使用者說「我的偏好是…」「以後直接做／先問」、或講定語言、分支慣例、時區時讀。 |
| | （其他鍵：`{"kind": "workflow", "source": "kernel"}`） |
| `feature-dev.json` | 功能開發／修 bug 的流程，從讀 code map、增量修改、驗證綠燈到 commit；使用者說「我想開發／修改某個功能」「這裡壞了，修一下」「修 bug」時走它 |
| | （其他鍵：`{"kind": "workflow", "source": "dev"}`） |
| `testing.json` | 跑測試／驗證的流程：挑要跑的驗證、agent 自己跑或交使用者；使用者說「跑測試」「驗證一下」「這樣改有沒有壞」、改完程式或重構前記基準時走它 |
| | （其他鍵：`{"kind": "workflow", "source": "dev"}`） |
| `refactor.json` | 行為不變的重構／拆檔／整理結構流程（程式碼）；使用者說「重構」「拆檔」「整理結構」或結構門檻超標時走它（整理工作文檔走 `tidy.json`） |
| | （其他鍵：`{"kind": "workflow", "source": "dev"}`） |
| `moving-things.json` | refactor 的搬移專章：搬檔、改目錄名、拆 repo 的鐵律、六類會斷的東西與驗證程序；使用者說「搬檔案」「改目錄名」「拆 repo」時走它 |
| | （其他鍵：`{"kind": "workflow", "source": "dev"}`） |
| `analysis.json` | 陌生專案分析：初次接觸外部 repo 時分 Level 建立可延續的分析產物；使用者說「這個陌生專案是怎麼運作的」「幫我分析這個 repo」時走它（只回答一個窄問題走 investigation） |
| | （其他鍵：`{"kind": "workflow", "source": "dev"}`） |
| `investigation.json` | 調查／解讀外部系統／可行性：只讀不改、回答一個窄問題、留一篇筆記；使用者說「查清楚這是怎麼運作的」「這樣做可不可行」時走它（初次接觸、要整套產物走 analysis） |
| | （其他鍵：`{"kind": "workflow", "source": "dev"}`） |
| `dev-env.json` | 開發環境、指令、外部工具與 env var 的流程；使用者說「環境怎麼裝」「fresh clone 後要做什麼」「指令是什麼」或要加工具、環境變數時走它 |
| | （其他鍵：`{"kind": "workflow", "source": "dev"}`） |
| `patch.json` | 獨立 patch 包：做一包交給冷啟動 agent 套用到別的 repo 的修改，含產物結構、PATCH.md 必答、APPLY.md 結構；使用者說「做一包 patch 給別的專案／別的 agent 套」時走它 |
| | （其他鍵：`{"kind": "workflow", "source": "dev"}`） |
| `tidy.json` | 文件整理（封存過時、分類雜亂、抽資料檔、內容精簡）怎麼跑一輪；使用者說「整理 X」「封存過時的」「檔案太多／太雜」「太大要拆」「只留結論」時走它（整理程式碼結構走 `refactor.json`）。 |
| | （其他鍵：`{"kind": "workflow", "source": "kernel"}`） |
| `tidy` | tidy 的子檔：六條原則、內容精簡的步驟；照 `tidy.json` 做時由它的 `$ref` 指過去。 |
| `tidy-manager-brief.json` | tidy 的管理線簡報範本；tidy 一個範圍派一條管理線、管理線再派工人時讀。 |
