# proto4 筆記 §22：LLM cpu（2026-09-13 晚上開工）

← [索引](2026-09-08-ideas.md)｜前一節 [§20–§21](20-21-step-lisp-and-next.md)｜撈舊 proto 的報告 [llm-cpu/legacy-harvest.md](llm-cpu/legacy-harvest.md)

## 22.1 它是什麼（使用者 §21.1 的定義，照錄）

> llm cpu 他就是很普通的，收到很多個 llm 呼叫請求，然後做排序，分發給不同 endpoint 那樣，整圈推論工具執行那是 agent 的事情。llm cpu 可以先基於普通 cpu 去做。

所以：**一顆普通 cpu（aos-run 反覆跑一份 inst.json）上跑的一支程式**，每格：收請求 → 排序 → 派給 endpoint → 收結果。不做 agent 迴圈、不做工具。endpoint 三種：LM Studio（本機、一次一顆模型）、DeepSeek（`DEEPSEEK_API_KEY`）、`pi -p` 子行程（這版只佔設定槽，§21.6）。

## 22.2 先撈遺產（使用者：「先前幾個版本的 proto 都是可以參考的遺產，只是謹慎採用」）

派 codex gpt-sol 讀 proto／proto2／proto3 系／proto4-1、4-2／reference/llmkit／core/llm，寫成逐題「採／改採／不採＋為什麼」，在 [llm-cpu/legacy-harvest.md](llm-cpu/legacy-harvest.md)（198 行）。最值得撿的三樣：

1. **proto2 的跨格作法**：tick 只派工——把請求搬進 `running/`、開一支背景 worker 去打 API、tick 立刻返回；下一格再依 pid／結果檔收尾。這正面解掉「一格幾秒、推論幾十秒」的衝突。
2. **proto 的「結果不明就不重送」**：送出去之後 worker 掛了、狀態不明，一律標 error（worker_died），絕不自動重送——避免重複扣款與雙回覆；要不要重投是呼叫者的事。
3. **llmkit 的欄位**：請求就是 chat/completions 的 body；usage 正規化成 prompt／completion／total／cached／reasoning 五欄，缺的留 null。

報告問了五件，我全部照它的預設（已告知使用者，他可翻案）：(1) 背景 worker、tick 絕不等網路；(2) 請求只指定 endpoint 名字、model 固定在設定；(3) priority 整數大者先、同分 FIFO；(4) 送出後失聯一律 worker_died、不重送；(5) v1 不管 LM Studio 的 load／unload，只驗回應的 model 對不對。

## 22.3 v1 定案（任務書 `proto4-5/notes/codex-task-1.md`，codex gpt-sol 做）

- 新資料夾 `proto4-5/`，Python 標準庫，一支 `llm-cpu`：`init DIR`／`tick [DIR]`／`submit [DIR] REQ.json|-`／`ls [DIR]`／`worker DIR ID`（內部）。
- 家：`endpoints.json`、`inst.json`（argv＝`llm-cpu tick .`，所以 `aos-kernel add K DIR/inst.json` 就上 cpu）、`requests/`→`requests/running/`→`requests/done/`、`results/<id>.json`、`usage.jsonl`、`log/<id>.log`、`state.json`。
- 請求最小是 `{"messages":[…]}`；選填 endpoint／priority／timeout_ms／params；**不准寫 model**。結果檔統一形狀：`ok`、`text`、`finish_reason`、`usage` 五欄、`raw`、`error{kind,msg,status,retryable}`。
- 一格五步：收尾 running（結果出現→done；pid 死→worker_died；超時→kill＋timeout）→ 驗新請求（壞的當格寫 bad_request）→ 排序 → 每台 endpoint 派到 `max_concurrent` 為止 → 寫 state／log。tick 永遠退出 0（它是服務，不回 100）。
- 不做：串流、取消、重試、批次、費用、公平、load／unload、process 型 endpoint、agent、MCP。
- 測試全用本機假 OpenAI server（echo／slow／fail／badjson／model:other），不打真網路；端到端一條用 `proto4-3/aos-exec` 跑一格。

## 22.4 跟其他段的關係

- **syscall**：fix-r3 把 `aos-kernel rm` 做成第一個 syscall（`K/syscalls/` 收件匣、tick 每回合先處理）——之後「生行程」「問狀況」照這個形狀長；MCP 版是同一批東西換個殼（§21.7）。
- **lisp 投請求**：這版只做 CLI；下一步在 proto4-4 包一個 `aos/llm`（用 `aos/call-dir` 叫 submit、`:read :json` 讀 `results/<id>.json`）。
- **agent 狀態機**：很後面（§21.2、§21.7）。
