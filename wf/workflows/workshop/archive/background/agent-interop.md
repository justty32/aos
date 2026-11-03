# 名詞表：agent 宿主與外部介面
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### skill（agent 操作手冊）

**白話**：一份寫給 coding agent 看的說明書，告訴它什麼時候用 aos、怎麼下命令、哪些事不能自作主張。
**嚴格**：由 agent host 發現、在適用任務時載入的指令套件，核心通常是 `SKILL.md`，可附 reference/template/script；它描述操作流程，不自動新增權限或 runtime。
**在 aos 裡具體是什麼**：`.agents/skills/aos/SKILL.md` 目前還不存在，是 pi 整合候選；它會教 agent 以 bash 呼叫同一套 Deliver/Status/Exec CLI。
**為什麼會冒出這個詞**：這是 coding-agent 生態的既有概念；[工具協作場](../records/tool-interop.md) 用它服務明確不走 MCP 的 pi。所以可以照「給 agent 的 README 加使用規則」理解，但差別是宿主會自動發現與載入它。

### MCP（Model Context Protocol）

**白話**：讓 coding agent 用統一的方式看到「有哪些外部工具、每支要填什麼參數、呼叫後回什麼」，免得每個宿主各寫一種接法。
**嚴格**：一個 client–server protocol，host 內的 MCP client 可發現 server 暴露的 typed tools/resources/prompts，再以結構化 request/result 呼叫；它是互通協定，不是 aos 的 queue 或 sandbox。
**在 aos 裡具體是什麼**：目前沒有 MCP server；候選是為支援 MCP 的 coding agent 做無狀態薄殼，暴露 Status＋Deliver，Exec 明示 opt-in。pi 不走這條。
**為什麼會冒出這個詞**：這是外部 agent/tool 生態的既有協定；[工具協作場](../records/tool-interop.md) 想讓 aos 成為多種 agent 的 tool set，但也特別澄清 pi 明確不做 MCP。

### façade（薄殼／門面）

**白話**：外面換一個別人熟悉的插座，裡面還是轉接到同一套 aos 命令與規則。
**嚴格**：不擁有狀態真源與業務語意的 interface adapter，只在 MCP typed arguments/results 與同一 CLI/lib contract 之間轉接，每次呼叫重讀 world。
**在 aos 裡具體是什麼**：目前不存在，特指候選 MCP server；它不應再實作一次 Deliver parser、receipt 或錯誤碼。
**為什麼會冒出這個詞**：[工具協作場](../records/tool-interop.md) 要同時支援 CLI、skill 與 MCP，又不想讓三個入口長成三份磁碟協定。

### session（coding-agent 續談狀態）

**白話**：agent 宿主幫你記住上次聊到哪裡，下次少重塞一些前情；它丟了不應該讓 world 的事實也消失。
**嚴格**：由特定 coding-agent host 維護的 conversation/runtime cache，可以以 ID/path resume/fork；格式與旗標可隨宿主版本變化，不應作 aos 的耐久真源。
**在 aos 裡具體是什麼**：目前沒有 session 綁定格式；T5 候選預設 `--no-session` 從 world 重建，或經實測後把某宿主 session 只當快取。
**為什麼會冒出這個詞**：[工具協作場](../records/tool-interop.md) 要在可攜重建與快速續談之間取捨，並發現 pi/Codex/Claude 的實際事件與 session 介面都還沒核對。

### envelope（有來源的訊息外包裝）

**白話**：不只丟一段文字給對方，還在外面標上這是哪一回、誰送的、成功還是失敗。
**嚴格**：將 payload 與 source、turn/request identity、schema/version、status 等 metadata 合在穩定機器介面中，讓消費者不必從無結構 stdout 猜測語意。
**在 aos 裡具體是什麼**：目前沒有專用 context envelope；`aos exec` raw stdout 是子指令任意輸出且可能交錯，所以不能當 agent stdin 協定。
**為什麼會冒出這個詞**：[工具協作場](../records/tool-interop.md) 四位都否定直接把 raw `aos exec` stdout pipe 進 agent，因為模型無法分辨來源、回合與退出狀態。

