# diag 意圖卡（llmdiag 併入後）

← [intents](README.md)｜[包 README](../../modules/diag/README.md)｜回頭審 [blueprint-simplify-2 §1](../blueprint-simplify-2.md)

**①解決什麼**：一個唯讀的診斷入口。`aos7-diag <root> [node]` 看核心：判不出的槽是哪些、為什麼、怎麼恢復（照抄 status 的 `last_error`、對到操作手冊）；`aos7-diag --llm <node>` 看 LLM 線路：沒回條的 llmcall（pending／unknown）、已 halted 的學徒 job、inflight>0 的 budget——原 `aos7-llmdiag` 的三張表，JSON 逐字照舊。

**②必要的副作用**：零。只讀 status.json、slot 檔、llmcall 的 request／raw／receipt、author frame、budget ledger；stdout 一行 JSON；不寫 node、不鎖、不起程序、不連網、不花錢。

**③不做**：不修帳差、不補回條、不改 job／request／ledger；不判 inflight 成因；不做身分掃描、不收程序；結論是掃描前的樣子，只供參考。

**④對照現狀多出來的（併入時）**
- 舊入口 `aos7-llmdiag` → **改成轉址 stub 一輪**（印一行「改用 aos7-diag --llm」退 1），r5 移除；程式 git mv 到 `proto7-2/archive/llmdiag/`。
- diag、llmdiag 都不在 `tests/error_path.json` 一致性清單 → **保留並補列**：`--llm` 的 node 不是資料夾退 2、讀寫出錯退 3（llmdiag 原本 `--help` 退 2 這種不統一的在併入時消失）。
- 入口停用 bytecode 寫入（llmdiag 原本的做法）→ **保留**（唯讀工具不該留 `__pycache__`）。
