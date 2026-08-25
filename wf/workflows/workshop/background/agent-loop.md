# 名詞表：agent loop 與工具執行
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### golden slice（可執行的最小端到端切片）

**白話**：不先做完整產品，只讓一條最短、但真的路從頭跑到尾，中間每一層都會經過。
**嚴格**：用最小功能與最少假件貫穿所有架構邊界的 vertical slice；這裡特指單 world、單一具名工具、串行的「模型→工具→模型看到結果」。
**在 aos 裡具體是什麼**：目前還沒跑過；[roadmap T5](../../../docs/roadmap.md#t5) 就是要用真 agent CLI、driver 腳本、具名工具與 Deliver 候選跑這一條。
**為什麼會冒出這個詞**：[回頭審視](records/step-back-review.md) 四位認為前面的抽象走得比實驗快，要先跑一條可殺死、可觀察的真 loop 才知道哪裡真痛。

### agent loop（模型─工具─模型的循環）

**白話**：模型看現況、叫一個工具做事、再看結果；它還有事就排下一步，沒事就停。
**嚴格**：由 driver 從已提交歷史組 context，調用 coding-agent/LLM adapter，將 typed tool call 轉為 instruction 並 Deliver，執行後再將 result 供下一次模型回合使用的耐久狀態機。
**在 aos 裡具體是什麼**：目前不存在；roadmap T5 明定先用 `.aos/inst.json` 加腳本與外部 CLI 實驗，不先新增 C++ `aos agent`。
**為什麼會冒出這個詞**：這是 [roadmap T5](../../../docs/roadmap.md#t5) 的下一步；[agent loop 場](records/agent-loop-architecture.md) 本來要找 core 原語，[回頭審視](records/step-back-review.md) 又把它收回先實跑。

### driver 與 adapter

**白話**：driver 決定下一步要做什麼；adapter 只負責把某家工具實際說話的方式接上來。
**嚴格**：driver 實作 prompt/context 組裝、步驟選擇、final/stop/budget 政策；adapter 實作 provider/CLI-specific 的啟動、JSONL/RPC 解碼、result capture、session 綁定與 provider 對帳，不重新實作 Deliver 語意。
**在 aos 裡具體是什麼**：目前沒有正式子命令或目錄；T5 會先是實驗腳本。`core/llms` 與 `core/tooljson` 已擱置，不是這個未實驗邊界的現成實作。
**為什麼會冒出這個詞**：[agent loop 場](records/agent-loop-architecture.md) 需要阻止 core 知道 prompt/tool/final；[工具協作場](records/tool-interop.md) 又拿掉了「從自然語言猜 instruction」的 adapter 責任。

### tool allowlist（具名工具映射）

**白話**：模型只能點菜單上有的工具；它給的是名字和參數，不是一整條可以任意拚的命令。
**嚴格**：只允許符合預先登記 schema 的 typed tool call，由可信 translator 映射到固定 executable/argv 骨架；未知工具拒絕或停住，不讓模型輸出直通 shell。
**在 aos 裡具體是什麼**：目前不存在，是 golden slice 必須實驗的最小信任邊界；它可先是腳本中一張固定映射表。
**為什麼會冒出這個詞**：[回頭審視](records/step-back-review.md) 三位指出模型任意 argv 等於拿到使用者的檔案、網路、憑證與命令權，這比先造 capability 更迫切。

### coding agent

**白話**：一個能看專案、跟人對話、自己呼叫讀檔與命令工具來完成編程工作的上層程式。
**嚴格**：維持對話與 tool-use loop、將模型輸出轉成工具調用、管理 session/批准/上下文的 agent host；pi、Codex、Claude CLI 是本討論的候選宿主。
**在 aos 裡具體是什麼**：aos 目前不內建 coding agent；候選用法是上層 agent 呼叫 aos CLI，或 aos driver 啟動某支 agent CLI。
**為什麼會冒出這個詞**：[工具協作場](records/tool-interop.md) 專門問 aos 怎麼成為 pi/Codex/Claude 可用的工具組，並反過來如何無人值守地呼叫它們。

