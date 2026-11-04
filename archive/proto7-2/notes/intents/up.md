# up 意圖卡（設計中，F1／F2）

← [intents](README.md)｜[藍圖](../blueprint-firstrun.md)

**①解決什麼**：一行起一個會收信、問 AI、回信的 node；新人只學五個詞、三個指令，帳／回合／預留／ack／退出碼全藏在預設值後面。

**②必要的副作用**（都是替別包做它們本來要人手做的事）：wfnode init；建 `budget/llm` grant＋帳任務；連 3 本技能＋索引；`aos7-ctl add` 四個 keep 任務（含 routines 任務，但**不預設任何例行列**——原卡寫「預設一列 routines」，10-09 RV 核過沒做、改卡不改程式）；建人的信箱 `you/`；register＋起 daemon（前景）；`.aos/up.json`。`--model` 才連網花錢。**節拍可設定**（使用者 10-09：有人要固定、有人不要）：`--interval 秒`、`--early`／`--fixed` 記進 up.json、重跑沿用、寫進 timeline.json；預設不給＝1 秒固定、不碰 timeline；只寫在 ADVANCED，README／QUICKSTART／`--help` 不出現。

**③不做**：不改 lib/、不改任何包；不自動開真 AI；brain 一回合最多處理一封 REQUEST、失敗回 BLOCKED 不重試（非 REQUEST 的信會整批歸檔不算處理——多回合時要不要改由 B5 定）；不做多 node。

**④規則（給 F1／F2）**：各包多出來的副作用（routines add 裝任務、mail 建 events、skills 碰 ledger.lock）由 up 統一負責，各包自己**不再**做；up 是唯一「會動好幾個包的檔」的入口。退出碼照 [blueprint-errors](../blueprint-errors.md)；ask 逾時退 0 照藍圖。
