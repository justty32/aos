# 待答問題：權限、宿主與第一支 agent CLI
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)｜[白話導讀](../background/questions-host-and-trust.md)

第 4–6 題：模型輸出先給到什麼權限、第一個宿主整合走哪條、golden slice 先綁哪支 agent CLI。

## 擋住事情的

### 4. 模型與工具先給到什麼權限？

**問題｜**首版是全信任實驗、只准 Deliver 等人 Exec，還是在 container／sandbox 內允許自動 Exec？  
**為什麼卡著｜**模型輸出若能直通任意 argv，就能碰檔案、網路與憑證；root 的唯一權力若只靠守約，也不是安全邊界。  
**在哪問過｜**〈核心行程與子行程〉、〈四個懸而未決的設計選擇〉、〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；兩批共 8 位獨立地問了。  
**候選答案｜**

- **全信任＋具名工具映射**——先跑玩具 golden slice；未知工具停住，但不承諾隔離真實資源。
- **只 Deliver、人工 Exec**——agent 只能排隊，由人核准後推世界一回合。
- **container 內自動 Exec**——上層 coding agent／OS sandbox 負責隔離，aos 不新增批准彈窗。

### 5. 第一個整合入口先驗哪個？

**問題｜**第一個宿主先做 pi 的 skill＋CLI，還是先做其他 coding agent 的 MCP façade？  
**為什麼卡著｜**pi 明確不走 MCP；兩條路要驗證的宿主、session 與 tool protocol 不同。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；1 位獨立地問了。  
**候選答案｜**

- **pi skill＋CLI**——建立 `.agents/skills/aos/SKILL.md`，由 pi 的 bash tool 呼叫同一套 aos CLI。
- **其他 agent 的 MCP**——先做無狀態薄殼，第一版暴露 Status＋Deliver，Exec 明示 opt-in。

### 6. golden slice 先用哪支真 agent CLI？

**問題｜**模型→具名工具→模型的第一條可執行 golden slice，要先鎖定 pi、Codex，還是 Claude 的 CLI？  
**為什麼卡著｜**stdout／JSONL、tool-call、session、取消、截斷與 exit 的實際形狀尚未測過，adapter 與 crash 記錄不能先定。  
**在哪問過｜**〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；3 位獨立地追問第一支 CLI。  
**候選答案｜**

- **pi**——先驗 skill＋CLI、`--no-session`、JSONL／RPC 與實際 session 旗標。
- **Codex**——先驗現有 CLI 的 tool-call、結果捕捉、session id 與 hard-kill 現場。
- **Claude**——先驗另一個 coding agent CLI 的 request／result 與 session 快取介面。

