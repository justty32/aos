# 待答問題：agent context、session 與工具集合
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)｜[白話導讀](../background/questions-agent-context.md)

第 18、19、24 題：送進 agent 的 context 從哪來、要不要靠 agent session 續談、首版工具集合有幾支。題號不連續是照〈[白話導讀](../background/questions-agent-context.md)〉的分組走。

## 擋住事情的

### 18. stdout→stdin 的穩定 context 從哪裡來？

**問題｜**coding agent 的 stdin 要吃 request file、`status --json`，還是新的 `aos prompt／emit`？  
**為什麼卡著｜**四位已排除 raw `aos exec` stdout；去程沒有 envelope，就無法與回程 Deliver 組成可靠閉環。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；4 位共同留下這個缺口。  
**候選答案｜**

- **request file**——driver 直接把 world 裡已提交的 request／context 檔餵給 agent stdin。
- **`status --json`**——由現有查詢工具輸出穩定 machine context，不新增 prompt 命令。
- **專用 `prompt／emit`**——新增只輸出帶 turn／source envelope 的 context exporter。

### 19. agent session 要先求可攜還是續談速度？

**問題｜**第一版預設 `--no-session` 從 world 重建，還是優先使用 agent session 作續談快取？  
**為什麼卡著｜**session 定址、JSONL final event 與 RPC 的跨版本承諾尚未核對；若先依賴它，skill 與 adapter 會被宿主格式綁住。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地都碰到。  
**候選答案｜**

- **`--no-session` 可攜預設**——world 保存完整 request／history，session 遺失不影響重建。
- **session 快取優先**——先核對並固定實際旗標與 event 格式，把綁定記在 world，但仍不當真源。
- **RPC／JSONL adapter 優先**——先驗跨版本介面，再由 adapter 捕捉 final／exit；不用未核對的 `--session-dir`。

### 24. coding agent 的首版 runtime tool set 有幾支？

**問題｜**首版只公開 Deliver，公開 Deliver＋Status＋Exec，還是再把 Init 放進同一組？  
**為什麼卡著｜**skill／MCP 的 schema、權限面與實作範圍取決於首版工具集合。  
**在哪問過｜**〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地整理過。  
**候選答案｜**

- **只有 Deliver**——近期只補現存投遞缺口，Status／Exec 沿用既有人工 CLI。
- **Deliver＋Status＋Exec**——四位共同的最小 runtime 三支；Status 可讀、Exec 另授權。
- **再加 Init**——把 world 建立也放入 agent tool set，不另列建置期。

