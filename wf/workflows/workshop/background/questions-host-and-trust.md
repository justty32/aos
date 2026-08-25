# 題目導讀：權限、宿主與第一支 agent CLI
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### 題目：首版是全信任實驗、只准 Deliver 等人 Exec，還是在 container／sandbox 內允許自動 Exec？

**這題其實在問什麼**：第一版裡模型所排的 POSIX 工作能不能立刻碰真正檔案、網路與憑證，以及隔離究竟由誰保證。
**為什麼會有這題**：`aos exec` 可以執行任意 argv；若模型輸出直通，prompt injection 就得到使用者權限。root/capability 在同 UID 下只是守約，不是防線。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| 全信任＋具名工具映射 | 最快跑玩具 slice，仍擋住任意 argv | 不保護玩具世界之外的真實資源 | 實驗不小心用到真憑證或不可回復工具 |
| 只 Deliver、人工 Exec | 模型只能排隊，人看過才造成作用 | 無人 loop 不閉合，每一回都需要人 | 每次批准只是機械點擊，且無法測自動 crash 路徑 |
| container 內自動 Exec | 可跑無人閉環，隔離交給上層 agent/OS | 需要準備 image、mount、network/secrets 政策 | 沙盒邊界配錯導致實驗假安全或功能與真環境不同 |

**如果現在不決定會怎樣**：任何讓模型輸出實際進 queue 的實驗都沒有明確安全範圍；可以先做只有 `echo`/讀臨時檔的無外部作用測試。
**最小的驗證方式**：花一小時寫一張只有兩支工具的固定映射（例如讀實驗目錄一個檔、寫一個可刪的結果檔），分別在普通玩具目錄與現有 sandbox 跑；觀察你是否真需要中間每步人工批准。

### 題目：第一個宿主先做 pi 的 skill＋CLI，還是先做其他 coding agent 的 MCP façade？

**這題其實在問什麼**：第一次整合要驗證「一份說明書教 agent 呼叫 CLI」，還是「一個 typed server 把 aos 工具正式掛進宿主」。
**為什麼會有這題**：pi 明確不走 MCP，而其他 coding agent 可能支援；兩條路共用 Deliver/Status/Exec 語意，但宿主發現、session、tool schema 與權限線不同。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| pi skill＋CLI | 最薄整合，可先驗證使用手感與現有 bash tool | 沒驗 MCP typed schema/server 生命週期 | 第一個實際宿主不是 pi，得立刻再做 façade |
| 其他 agent 的 MCP | 一次驗 typed tools、結構化錯誤與權限暴露 | 要先做 server 包裝，且對 pi 沒用 | 後來發現 CLI 契約還沒穩定，façade 只是包著移動中的目標 |

**如果現在不決定會怎樣**：會擋住第一個整合產物，但不擋住先把 Deliver CLI 契約跑通；兩個入口都應包同一套語意。
**最小的驗證方式**：不先做完整整合：用同一個假 `aos deliver` 命令，一邊寫 20 行以內的 pi skill 叫它用 bash 呼叫，一邊用目前最熟的 MCP host 手工宣告一支等價 typed tool；各做一次錯誤修參數，就能看哪條才是你要驗的宿主摩擦。

### 題目：模型→具名工具→模型的第一條可執行 golden slice，要先鎖定 pi、Codex，還是 Claude 的 CLI？

**這題其實在問什麼**：先選一支你真的會在本機啟動、中止、捕結果的 agent 程式，別再對假想的「某支 LLM CLI」設計 adapter。
**為什麼會有這題**：三支 CLI 的 stdin、JSONL/final event、session、取消、截斷與 exit 形狀沒有一支被實測；adapter 與 crash 記錄必須依真實形狀長出來。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| pi | 同時驗 skill＋CLI、print/JSONL/RPC 與 no-session | 不驗 MCP，且需先核對實際 session 旗標 | 本機主要工作不用 pi，實驗難以持續 |
| Codex | 驗目前已用的 CLI、tool-call、result capture、session id 與 hard-kill | 先驗到的是 Codex-specific event 形狀 | 把未穩定的特定事件格式誤當 aos 通用 ABI |
| Claude | 驗另一家 coding-agent CLI 的 request/result 與續談方式 | 得另外熟悉旗標與事件格式 | 只因「也該支援」而選，實際開發回饋最慢 |

**如果現在不決定會怎樣**：T5 無法開始，所有 adapter/session/unknown 設計繼續只靠想像；這題是真正的動工門檻。
**最小的驗證方式**：不比完整功能；對你機器上已裝、已登入的候選各跑一次同一 prompt，記錄「stdin 可否用、machine output 是否可分辨 final、如何取 session id、中途 kill 留什麼」；45–60 分鐘內就能以當下可用性排除不合格者。

