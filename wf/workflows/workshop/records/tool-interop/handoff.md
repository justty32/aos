# aos 工具協作 — 轉交提案

← [本場索引](README.md)｜[workshop](../../README.md)

八條要交出去的提案，全部未拍板。

---

## 轉交提案（未拍板，不自行改規格／roadmap）

1. **先拍板並實作 `aos deliver` 的最小公開契約。**需決定 WORLD／FILE 位置參數、單筆是否接受、
   `--key`／`--durable`／`--to` 是否進第一版、成功／錯誤 JSON、退出碼、receipt、檔名 suffix，以及
   key 在沒有 ledger 時是否只作 correlation。四位已對原子寫入順序與只負責投遞形成強訊號。

2. **把 runtime tool set 收成 Deliver＋Status／Inspect＋Exec。**需拍板查詢工具叫 `status` 還是
   `inspect`、回哪些 world／queue／`.runi` 欄位，以及 Exec 是否維持現有 CLI；Init 另列建置期，
   不占 coding agent 的最小三支。

3. **若先驗 pi，做 `.agents/skills/aos/SKILL.md`＋CLI，不做 pi MCP。**skill 應教直接 tool-call／
   bash 呼叫 Deliver、讀 machine JSON、處理 `.runi` 與批准；先核對 pi 真正支援的 session 旗標、
   JSONL final event 與 RPC 穩定性，不把 `--session-dir` 當既定事實。

4. **若要支援其他 MCP agent，再做無狀態 façade。**第一版只暴露 Status＋Deliver；Exec 明示 opt-in。
   每次重讀磁碟、用 root allowlist 限 world、共用同一 CLI／lib 語意，server 記憶體與 agent session
   都不當真源。

5. **拍板 coding agent 的預設權限。**可選「只 Deliver、由人 Exec」或「在 container 內允許自動
   Exec」；aos 本身不補權限彈窗。無論哪個，模型輸出不得以任意 argv 穿透高權 MCP／adapter。

6. **若要完成 stdout→stdin 方向，另定專用 context 出口。**不能用 raw `aos exec` stdout；可從
   request file、既有 Status JSON，或日後 `aos prompt／emit` 選一種。追問輪只定了回程用 Deliver，
   去程仍需使用者拍板是否值得做成 core tool。

7. **用這場 workshop 當第一個端到端 interop 驗證。**前置是 Deliver、四個 agent 結果的原子
   capture、完成 commit 與 join；先跑一輪 briefs→四 responses→書記 record，逐點測 agent 已付費
   但 raw 未落盤的 unknown。這能同時驗 pi／其他 CLI adapter 與 aos 磁碟契約。

8. **正式刪除 ingest／accept 的自然語言解析責任。**adapter 仍可負責啟動 agent、搬 JSONL、保存
   raw 與 exit，但不再解析 final prose 來猜 instruction；instruction 只能經 typed Deliver tool-call
   進 queue。
