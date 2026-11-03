# 題目導讀：痛點、scope 與產品體驗
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### 題目：最近一次覺得 workflows 不好用時，主要卡在安裝升級、路由／遵守流程、活狀態維護，還是定時喚醒？

**這題其實在問什麼**：你原本造 aos 想消掉的第一個摩擦究竟是哪一個；若只能先少做一步手工事，要少的是哪一步。
**為什麼會有這題**：[workflows 場](../records/workflows-on-aos.md) 只能從檔案推測 drift、升級、路由與 tick 可能痛，沒有一件是你已確認的真事故。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| 安裝／升級 | 可追來源、檢查差異、少手工合併 | 活狀態與喚醒仍全手工 | 其實安裝只做一次，每天痛的是忘記進度 |
| 路由／遵守 | agent 較容易找對入口並照流程做 | 不會幫你記住做到哪 | 現有 Markdown 路由其實好用，只是偶發一次漏讀 |
| 活狀態 | `start/wait/resume/done/status` 取代手動搬項 | 模板與定時仍不處理 | 實際上你想保留的是自由 Markdown，機器狀態反而增加摩擦 |
| tick／schedule | 到期判斷與投遞不再靠記憶 | 不解決日常流程路由與進度搬運 | 定時事其實很少，卻先造了 scheduler |

**如果現在不決定會怎樣**：會擋住第一個 workflows 功能的 scope 與真源位置；不會擋住 T5 golden slice，所以可先做 agent loop 實驗。
**最小的驗證方式**：花 30 分鐘回放最近三次真實使用 workflows 的過程，每次只記「本來要做什麼、額外手工做了什麼、真正停住在哪」；哪一類在三次中反覆出現，就是比研討推測更強的證據。

### 題目：近期 scope 要只留最小 Deliver，保留 Publish→Deliver→Effect 三項，還是繼續連行程控制平面一起設計？

**這題其實在問什麼**：在第一條模型→工具→模型尚未跑過前，你要先補已知的投遞缺口，還是一次把外呼恢復與多工作管理都定成核心契約。
**為什麼會有這題**：[agent loop 場](../records/agent-loop-architecture.md) 曾經 4/4 收成三原語，但[回頭審視](../records/step-back-review.md) 又 4/4 收回公開 Publish 與近期 Effect，形成互斥 roadmap。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| 只做最小 Deliver | 最快補現存協定缺口，讓實驗開始 | 遠端 unknown、多檔發布、多工作管理先靠腳本／人 | 第一條 loop 立刻在同一個可通用故障點重複卡住 |
| 先做三項 core 原語 | 投遞、發布、外呼證據有共同語言 | 先承擔目錄交易、fsync、resolve ABI | 真 CLI 的問題根本在 session/輸出格式，而不在這三個原語 |
| 保留完整控制平面 | 一次設計多工作、授權、升格、join 與提交 | 磁碟 ABI、生命週期與安全威脅模型會大幅擴張 | 長久只有單 world，大半機制沒有第二個實例可驗證 |

**如果現在不決定會怎樣**：會擋住 core API 與 roadmap 排程；但實際 T5 可以以私有腳本與直接 temp＋rename 先跑，只是要明說那不是穩定介面。
**最小的驗證方式**：花一小時用一支私有 helper 跑一次三回合串行 loop，逐段人工中止；只記「temp＋rename 重寫了幾次、哪個 unknown 無法靠本機處理、有沒有第二個工作需要管理」，三個數字會分別給三種 scope 證據。

### 題目：第一個做好的體驗，是人在 coding agent 裡呼叫 aos，還是 aos 無人值守地批次召喚 coding agent？

**這題其實在問什麼**：第一位主角是人還是 driver；是 agent 幫人操作 aos，還是 aos 把 agent 當一支可能付費、可能斷掉的外部程式來跑。
**為什麼會有這題**：[工具協作場](../records/tool-interop.md) 發現兩者共用 CLI，但前者的難點是教 agent 用對工具與批准，後者的難點是 session、結果原子捕捉、exit 與 unknown。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| coding agent 互動入口 | 人在對話中立刻可用 Status/Deliver，批准可沿用宿主 | 無人結果 capture、crash 恢復與批次調度仍未驗 | 真正要解的是自動 workshop／agent loop，互動手感不會暴露 unknown |
| aos 批次召喚 agent | 會直接驗證 request、CLI 啟動、raw/final capture、exit 與 unknown | 人在常用 agent 裡的輕量入口會晚點出現 | 最後使用方式其實都是互動的，卻先承擔了無人值守的故障契約 |

**如果現在不決定會怎樣**：會擋住第一個整合的驗收準則、session 優先度與 unknown 責任；Deliver 自身仍可以獨立設計。
**最小的驗證方式**：用同一支現成 agent CLI 做兩個 20 分鐘快速實驗：一次由人在 agent 對話中呼叫假 Deliver，一次由 shell 無人啟動它並捕捉 final/exit；比較哪一邊先出現必須由 aos 解的摩擦。

