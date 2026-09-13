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

## 22.5 落地補記（2026-09-13 晚上）

- v1 做出來了（codex gpt-sol，兩輪）：`proto4-5/` 六個程式檔約 670 行、26→28 條測試全用假 server。
- **真打 LM Studio**（我自己做，`lms load google/gemma-4-e4b`）：submit「Say hi in one word」→ tick 派工 → 下一格收尾，結果 `Hello`、usage 21/2/23、97 ms。model 對得上。
- **真打 DeepSeek** 抓到一個坑：設定 `deepseek-chat` 是別名，回應的 `model` 是 `deepseek-flash`，被「model 不符」擋成 `ok:false`。第二輪加 endpoint 選填欄 `strict_model`（預設 true，LM Studio 要嚴格；DeepSeek 範例設 false），結果多一欄 `model_requested`。改完再打一次：`ok:true`、`Hi`、420 ms。
- 兩個 endpoint 都用 `params.max_tokens` 壓到 5～20，花費可忽略。gemma 還載在 LM Studio 上沒卸。
- **下一步要使用者拍板**：lisp 怎麼「等」結果——逐步 lisp 一格跑一個 form、跑完 pc 就前進，沒有「這格還沒好、下格再來」的概念。要接 LLM cpu 就得定一個「等待」語意（例如 form 回一個特殊值 `:aos/wait`，aos-step 不推 pc、退出 0，下一格重跑同一個 form）。這是 tick 模型的核心決定，不是我該自己定的。

## 22.6 使用者修正：LLM cpu 其實是兩層（2026-09-13，手機）

原話：

> 其實 llm cpu 這塊，他會分兩塊，一個是提供可以呼叫 endpoint 的指令，讓 inst 可以用的指令集，這就類似於 cuda，包裝了一些操作，對整個運作模型進行了一次舒服的抽象。另一種則是排程，用於整理目前需要使用 llm 的傢伙的請求，然後分配的，這是在 cuda 之上的。後面這個，他的角色跟 kernel 有點像，將其作為 kernel module 也未嘗不可。

對到 proto4-5 現況（Fable）：

- **第一層「像 cuda 的指令集」**＝現在的 `llm-cpu worker`：給它一份 endpoint 描述＋一份請求，它打一次、寫一份結果檔。它現在被綁在 llm-cpu 的家裡（要從 `requests/running/` 讀、寫回 `results/`），應該抽成獨立指令 `aos-llm call ENDPOINT.json REQ.json OUT.json`（同步、無佇列、無家，任何 inst 都能直接叫；lisp 用 `aos/call`＋`:read :json` 就接上）。這一層不管誰在排隊。
- **第二層「排程」**＝現在的 `llm-cpu tick`：收請求、排序、按 endpoint 容量派、收尾。它管的是**資源**（endpoint 有容量上限，像 cpu），跟 kernel 管 cpu 是同一件事。做成 kernel module 的形狀：投 LLM 請求＝一個 syscall（`K/syscalls/` 收件匣已經有了，fix-r3 的 rm 就是第一張單）；kernel tick 每回合順手跑 module 的一格（就像現在先處理 syscalls 那步）；module 派工時開背景 worker 去叫第一層的 `aos-llm call`。
- 這樣分完，proto4-5 v1 的東西沒有白做：worker 的請求／結果／usage 形狀直接變第一層的規格，tick 的五步直接變 module 的一格。

沒定的（等使用者）：(1) 排程層是**kernel module**（kernel 要認得「LLM 請求」這種單）還是**獨立行程**（kernel 只知道它是一個 proc，像現在）；(2) 兩層分開的順序——先抽第一層 `aos-llm call` 出來、排程層照舊，還是一次改成 module。
