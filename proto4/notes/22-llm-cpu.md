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

## 22.7 Fable 的決定（使用者：「都隨你」，2026-09-13）

1. **排程層做 kernel module**。理由：「請求等 endpoint 容量」跟「proc 等 cpu」是同一個模型，kernel 本來就是管這個的；投請求走 syscall 收件匣（fix-r3 已建），不必再發明一條通道。
2. **順序：先抽第一層**。`aos-llm call`（像 cuda 的一次呼叫）從 proto4-5 的 worker 抽出來變獨立指令，lisp 立刻能用；排程照現在的 `llm-cpu tick` 跑；kernel module 是下一本任務書（22.8）。

第一層規格（任務書 `proto4-5/notes/codex-task-3.md`）：`aos-llm call ENDPOINT REQ OUT`——ENDPOINT 是「一個 endpoint 物件的 .json」或「endpoints.json#名字」；REQ 是請求檔或 `-`（stdin）；OUT 是結果檔或 `-`（stdout）。結果形狀＝v1 的 results；`ok:true` 退出 0、`ok:false` 退出 1（結果照寫）、用法錯 2。另給 `aos-llm models ENDPOINT`（GET /models，看 LM Studio 目前載哪顆）。`llm-cpu worker` 改成叫同一個函式庫。lisp 端 `(aos/llm ENDPOINT req-table OUT &opt opts)`：把 req 寫成檔、叫 aos-llm、`:read :json` 讀回來。

## 22.8 kernel module 機制定案（Fable，任務書 `proto4-5/notes/codex-task-4.md`）

- `config.json` 多 `"modules": [絕對路徑…]`，`aos-kernel-init --module PATH`。一個 module＝一個 Python 檔，五樣約定：`NAME`、`OPS`（它認的 syscall op）、`handle(h,cfg,st,ticket)`、`tick(h,cfg,st)`、`status(h,cfg)`、`cli(h,cfg,argv)`。載不起來、跑到一半炸，kernel 都只記一句、照跑。
- 接線三處：syscall 單的 op 不是內建的就問 module；tick 在處理完 syscalls 之後跑每個 module 的一格；`aos-kernel <NAME> …` 轉給 module 的 cli；`ls` 多印 module 的 status 一行。
- **llm module 很薄**：家在 `K/llm/`，`handle`＝把單裡的請求 submit 進 `K/llm/requests/`，`tick`＝就是 proto4-5 的 `llm_cpu_tick.tick(K/llm)`，`cli`＝`aos-kernel llm K req.json [--wait N]`。`--wait` 是給 lisp 暫時用的同步路（一格等到結果為止）；「不等」的語意（form 說「這格還沒好」）還是要另外定。
- `llm-cpu` 獨立行程的掛法保留，但 README 推薦 module。

**22.7 落地補記**：第一層抽出來了（codex gpt-sol）：`proto4-5/aos-llm call|models`（`aos_llm.py` 224 行是純函式庫，worker 縮到 57 行只剩讀寫檔）、lisp 端 `aos/llm`／`aos/llm-text`；Python 39 條、Janet 37/12/34 全綠。真打 LM Studio：`aos-llm models` 列出 gemma、`aos-llm call` 回 Hello。lisp 那條一開始**不通**：aos-step 把 `aos/*` 綁進 form 用的是寫死清單，codex 只用 import 測過 `aos/llm`、沒走 aos-step，新名字漏綁。我改成自動綁函式庫所有公開名字（`test/step.janet` 加一條），再跑 `aos-step` 的 form 叫 `aos/llm` 回 Hola!。另一個小坑：Janet 的 `import` 吃不了絕對路徑，README 原本那句是錯的，改成加 `module/paths` 的寫法。**撞到一個 inst 慣例的邊**：普通檔案目標不能帶 argv（README 定的），所以 `aos/llm` 是寫一份短命 inst.json 叫 `aos-llm call …` 再刪——能用，但這暗示「lisp 叫指令帶參數」是常見需求，之後可能要讓 `aos/call` 對普通檔案接受 args（等碰到第二個例子再定）。

**22.8 落地補記**：做出來了（codex gpt-sol）：`proto4-3/aos_kernel_module.py` 67 行（機制）、`proto4-5/llm_cpu_module.py` 170 行（llm module）、`aos-kernel-init --module`、`aos-kernel llm K req.json [--wait N]`、`ls` 多一行 `llm: queued/running/done/endpoints`。測試 proto4-3 220、proto4-5 45、Janet 37/12/35，全綠。我真開 daemon 端到端：init 帶 module → boot → 改 `K/llm/endpoints.json` → `aos-kernel llm … --wait 30` → LM Studio 回 `Hello!`，整條不到一秒（syscall 單→module handle→背景 worker→結果檔→cli 印出）。codex 撞到的坑：module 檔在別的資料夾，載入時要暫時把它的目錄加進 `sys.path`，它才 import 得到隔壁的 `llm_cpu_*`。**LLM cpu 這段到此算收**：兩層都在、三個 endpoint 型別兩個真打通（pi 那格留著）。還沒定的：lisp「不等」的語意（§22.5 末）。

## 22.9 收尾拍板（使用者 2026-09-13 深夜，「1 可以、2 3 隨便你、4 下次再說」）

1. **aos-exec 普通檔案目標收 `-- args`**：使用者同意。任務書在 `proto4-3/notes/codex-task-plain-args.md`，compact 之後派（`aos/llm`、`llm_submit` 目前繞路寫短命 inst，做完可以拆掉）。
2. 試玩 r2 清單 #7（改動偵測要不要預設停住）→ **維持現狀**（警告照跑，Opus 說這樣剛好）；#8（健康顯示、done_exit 取名）→ **不做**。
3. harvest 五個預設（背景 worker／model 固定在設定／priority 大者先／失聯不重送／不管 load-unload）→ **全部留**。
4. `aos.janet` 剛好 300 行 → 下次加東西時再拆。

**落地補記（compact 後，codex gpt-sol 一輪）**：`aos-exec xxx -- ARG...` 對普通檔案生效、原樣成 argv[1:]；`.json`／資料夾目標帶 `--` 回用法錯 2 並提示「參數寫在 inst.json 的 argv」；aos-run 原樣轉傳。Janet／Python／Lua 三份 `call` 多了 `args`，三份 `llm`／`llm_submit` 都改走 `call + args`，短命 inst 與直接 subprocess 的繞路都拆了。測試 226、42／45／12、71 全綠。任務書 `proto4-3/notes/codex-task-plain-args.md`，回報 `codex-out-plain-args.md`。第 4 點順手做了：`aos.janet` 被加到 301 行，把路徑解析搬到 `src/paths.janet`（import 進去的名字是 private，不會被 aos-step 綁成 `aos/*`），剩 258 行。

## 22.10 試玩 r3 之後（2026-09-13 傍晚）

LLM 層是 r3 最低分（Opus 上手 2.5）：README 沒有 `endpoints.json` 範例是唯一「照做也做不出來」的地方。fix-r4a 落地：README 貼可抄的本機範例、結果欄位分「日常／除錯／raw」三組；module 預設 `endpoints.json` 只留 local（DeepSeek、pi 範例搬文件）、第一次生檔提示改 model；`strict_model` 的 endpoint 送 chat 前先比 `/models`，沒有就 `model_not_found` 不花 token（`/models` 打不到就照送、記在 `notes`）；`model` 一律是對方回的、沒回就 null；`--wait` 成功只印 text＋路徑（`--json` 才整份）；`--wait` 逾時：單子還在 inbox 就撤掉說「沒送出」，被撿走了就說「已送出、結果會在 X」；同名同內容（sha256）視為同一張退 0，內容不同才擋。任務書 `play/fix-r4a-task.md`。
