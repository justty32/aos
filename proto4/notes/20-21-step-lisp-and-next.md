# proto4 想法筆記 §20–§21：逐步 lisp 與下一步
← [索引](2026-09-08-ideas.md)｜[README](../README.md)

## 20. 第一個程式：逐步 lisp（proto4-4，2026-09-13）

使用者原話（照錄，出門前分幾句講的）：

> 先確認我們目前 cpu 架起來了，然後我們來實現第一個程式：逐步 lisp。也就是 inst 的行為，就是逐一執行指定 .janet 檔案中的每個 list。
> janet 你可以去 ~/repo/langs/janet 參考。我說的架起來，指的是架構能否支撐我們現在要做的事情。然後 janet 那邊，我記得有做一個 lib，也就是把檔案呼叫弄成一個 janet lib。
> 其中還包括資料夾呼叫。遵循我們的 inst 這塊。如果 proto4-3 太臃腫，那就新開 proto4-4。

### 20.1 架構撐不撐得住（我的判斷）

撐得住，兩個地方要知道：

1. **每一格是一個新進程**（cpu＝aos-run 反覆叫 aos-exec），所以「上一個 form 定義的東西」不會自己留到下一格，得由程式自己存。Janet 有 `make-image`／`load-image` 可以把整個環境（含 `defn` 出來的函式）存成一個檔再讀回來，我在 1.41.2 上實測過：第一個進程 `(def x 10)` 存 image，第二個進程讀回來 `(def y (+ x 5))` 沒問題。
2. **kernel v1 沒有「行程做完」這回事**（§18 說的：行程不會自己結束）。所以逐步 lisp 跑完最後一個 form 之後，cpu 還是會每格來叫它一次，它只能什麼都不做地退出。這條就是 §17.2 第 1 條那個 open 項，這次先不動 kernel，等使用者回來看要不要順勢做。

其餘都對得上：行程＝一份 inst.json（`argv` 指到執行器、`cwd` 指到那個資料夾），丟進 `procs/` 就會被排上 cpu；狀態照 §8 放在 cwd 自己的資料夾裡；相對路徑照 §11 以 cwd 為中心。cpu 本身這台機器上 185 條測試全綠（含真開 daemon＋kernel 的），所以「架起來」這件事是測試在保證，不必再手動架一次。

### 20.2 那個 Janet lib

使用者說的是 `~/repo/langs/janet-lab/modules/aos/`：把「資料夾當函式、檔案當指令」包成 Janet 函式庫（`call`／`call-async`／`inst`／`exec-file`…）。但它對的是**舊那條規格線**（`proto/aos.py`、spec 07／04 那套 land／delivery），不是 proto4-3 的 inst.json。這次只當寫法參考，不接它；proto4-4 自己寫一個小的，**遵循 inst 的做法＝直接叫 `proto4-3/aos-exec`**，不重做 inst.json 的解析，規則就一定一樣。

### 20.3 定案（我定的，使用者回來可翻案）

- **新開 `proto4-4/`**（proto4-3 根目錄已經 19 個檔、README 700 多行，而且這是「跑在 OS 上的程式」，不是 OS 本身）。Janet 寫，測試也用 Janet（照 proto4 的 `check` 風格），跑 `janet test/xxx.janet`。
- **一個 `.janet` 檔＝一個行程**。執行器叫 `aos-step`：`aos-step PROG.janet` 跑「下一個」頂層 form，一次一個；`--status` 印狀態；`--reset` 從頭來。放上 cpu 的 inst.json 是 `{"argv":["<絕對路徑>/aos-step","prog.janet"],"cwd":"<那個資料夾>", …}`，`argv[0]` 一律絕對路徑（同 §18.1 不靠 PATH）。
- **狀態放 PROG 所在資料夾的 `.aos-step/`**：`pc`（下一個要跑的索引）、`env.img`（環境 image）、`error`（上次失敗的紀錄）、`done`（全跑完的記號）。都是寫暫存檔再 rename。
- **form 每次重新切**（檔案可能被改）：按索引數，所以改了前面的 form 會錯位——先接受，寫進「沒做什麼」。
- **失敗＝pc 不動、下一格再試同一個 form**（跟 aos-run「壞了也活著」同一個脾氣）；把檔案改好它就自己往下走。不跳過、不停機。
- **做完＝建 `done`、之後每格退出 0 什麼都不做**（見 20.1 第 2 條）。
- **函式庫 `aos.janet`**：`(aos/call target)`（三種目標原封不動交給 aos-exec）、`(aos/call-dir dir)`（資料夾呼叫）、`(aos/call-json path)`、`(aos/ok? r)`；回 `@{:code :kind :stderr}`，`kind` 用「退出碼 125／2 ＋ stderr 有 `aos-exec:` 那行」判。**不切 cwd**（跟 proto4 舊版 `runf` 不同）：相對路徑就是行程自己的 cwd。aos-exec 的位置走 `AOS_EXEC`，沒有就相對於函式庫檔案往 `../../proto4-3/aos-exec` 找。
- form 裡看得到 `aos/*`、`here`（PROG 所在資料夾）、`pc`。
- 派工：整包交給 codex gpt-sol（使用者出門前說「盡量用 gpt-sol」），任務書副本放 `proto4-4/notes/`；我收線時跑測試、commit、push。

## 21. 下一步的方向：逐步 lisp 之上做 agent 狀態機；前提是 LLM cpu 與 kernel syscall（2026-09-13，使用者在外面用手機講的）

使用者原話（照錄）：

> 這邊有新想法：在逐步 lisp 的基礎上，去做 agent 狀態機。但要達到這一步，我們需要先把 llm 這個特殊 cpu 處理好。除此之外還要實現 aos kernel 的 system call。lisp 這邊是原形，在我們弄出以檔案／資料夾作為 atom／list 做呼叫之後，很多東西就不拘泥於 lisp 了，你想用啥語言都可以，反正就是弄成檔案。

我聽懂的順序（沒開工，等他確認）：

1. **proto4-4 逐步 lisp 收掉**（正在做）——它只是「一格跑一個 form」的原形，證明「檔案／資料夾＝atom／list、呼叫＝跑 inst」這條路走得通。之後語言不重要，什麼都可以，反正每個東西都是一個檔案或資料夾。
2. **LLM 這顆特殊 cpu**——先弄好。這是 §7.3 以來一直懸著的：cpu 原本＝aos-run 反覆跑一份 inst.json，LLM 的一次推論要怎麼放進這個框（一格＝一次推論？結果落哪個檔？等回應那幾秒 cpu 算跑著還是停著？）。
3. **aos kernel 的 syscall**——§19.5 講的 `aos-kernel <什麼>`：行程跟 kernel 講話的入口（fork、要資源、說「我做完了」）。§17.2 第 1 條「行程做完」的機制大概也是在這裡解。
4. 有了 2 和 3，才在逐步 lisp 上做 **agent 狀態機**（§7 那段的定義：LLM 推論 → 工具 → 執行 → 取得 prompt → …）。

我要問他的（他回一句就好）：

- LLM cpu 的「一格」是什麼：一次推論（送 prompt、拿回一段回答＋工具呼叫）？還是整個「推論→工具→執行」一圈？我傾向前者，工具那段是普通 cpu 的事。
- LLM cpu 是 daemon 認得的**另一種 cpu**（韌體不同，`ctl add` 時指定），還是就是一顆普通 cpu 跑一份 argv 指到 LLM 程式的 inst.json？我傾向後者（daemon 不用改，§13 說 daemon 是硬體、不管上面跑什麼），LLM 那支程式讀 cwd 裡的 prompt 檔、寫回答檔。
- syscall 第一批要哪幾個：我猜「做完了」（exit）、「生一個行程」（fork／spawn，把一份 inst.json 丟進 `procs/`）、「問狀況」（`ls`）三個就夠開始。

### 21.1 使用者回答（2026-09-13，手機）

原話（照錄）：

> lisp 呼叫檔案，以我們的 inst 作為呼叫慣例，所以照理來說會有 stdin/out/err 等東西，一開始最原始的版本就是都不接住，就跑完結束，後續可以幫忙接住，把檔案內容讀進 lisp，乃至於順路解析成 json 之類，還可以接上 pipe 等，快速弄。然後 llm cpu 的一格，你可以參考 proto2,3,4，我是認為 llm cpu 他就是很普通的，收到很多個 llm 呼叫請求，然後做排序，分發給不同 endpoint 那樣，整圈推論工具執行那是 agent 的事情。llm cpu 可以先基於普通 cpu 去做，也就是你說的那樣。syscall 要做啥隨你，也可以一邊做，一邊發現需求然後順便增加實現。

拆成定案：

1. **lisp 叫檔案＝照 inst 慣例叫**，所以三條流本來就在 inst.json 裡。**最原始版：都不接住，跑完就結束**（proto4-4 現在這版就是這樣：`aos/call` 只回退出碼與 kind）。後續順序：接住 → 把 stdout 檔內容讀進 lisp 當回傳值 → 順路解析 JSON → 接 pipe。都是小步，快速做。
2. **LLM cpu＝一顆普通 cpu 上跑的一支程式**，不是 daemon 的新 cpu 種類。它做的事很單純：**收很多個 LLM 呼叫請求 → 排序 → 分發給不同 endpoint**。一格＝處理一輪排隊中的請求。「推論→工具→執行」那整圈是 agent 的事，不在 cpu 這層。寫的時候參考 proto2／proto3／proto4 裡 LLM 那塊怎麼排隊與打 endpoint。
3. **syscall 要哪幾個我自己定**，邊做邊長：碰到需求就加。第一批先「做完了」「生行程」「問狀況」。

### 21.2 使用者補一句（2026-09-13）：「總之 agent 這塊應該很後面了，先把前面這邊的基礎打穩」

所以順序是：proto4-4 收掉 → 「lisp 叫檔案」把三條流接住（讀 stdout 進來、解 JSON、pipe）→ LLM cpu（普通 cpu 上的排隊分發程式）→ kernel syscall（邊做邊長）。agent 狀態機放很後面。

### 20.4 落地補記（proto4-4 第一版，codex gpt-sol 做，2026-09-13）

做出來了：`proto4-4/`——`src/aos.janet`（96 行，函式庫）、`src/step.janet`（170 行，逐步執行器）、`aos-step`（5 行入口）、三支測試 `test/aos.janet` 15 條、`test/step.janet` 23 條、`test/cpu.janet` 4 條，全綠；proto4-3 的 185 條沒動也還綠。任務書與回報副本在 `proto4-4/notes/`。

codex 自己決定的（我看過認可）：`--status` 那行手寫、保留 `:error nil`；Janet 環境綁定不能塞裸值，`here`／`pc` 要包成 `@{:value …}`；放上 cpu 時 inst.json 的 `stdout` 檔每格會被截斷（inst 規則就是「建立並清空」），所以要留紀錄得自己 append 到別的檔（`test/cpu.janet` 就是這樣寫 `log.txt`）。

### 21.3 kernel 應急版「行程做完了」（2026-09-13，使用者：「想個應急用的處理方法，先做，之後再看怎麼更好，盡量簡單，KISS」）

我定的最簡做法：**一個保留退出碼＝「我做完了，別再排我」**。

- 碼是 **100**（aos-exec 自己用 125／2，shell 用 126／127／128+N，100 沒人用）。放 kernel `config.json` 的 `done_exit`，`aos-kernel-init --done-exit N` 可改，`0`＝關掉。
- kernel 每回合本來就從 daemon 的 `state.json` 拿每顆 cpu 的 `runs`／`last_exit`／`last_kind`。看到 `last_kind=child` 且 `last_exit=100`，而且 `runs - runs_at >= 2`（換人那一刻正在跑的那一次還是前一位的，所以要多等一次才確定這個碼是現在這位的），就把它從 cpu 拿下來：inst.json 搬去 `procs/done/<pid>.json`（留個痕跡），cpu 換回 idle。兩步用跟換人一樣的硬連結＋rename，不留空窗。
- 逐步 lisp 那邊配合：`aos-step` 所有 form 跑完之後改回 100（原本回 0），這樣放進 kernel 就會自己下車。
- 沒做的：行程不能自己「叫」kernel（那是 syscall 的事，§21.1 第 3 條）；做完的 cwd 資料夾不動；`procs/done/` 不會自動清。
- 派 codex gpt-sol 做 kernel 端（`proto4-3/notes/codex-task-kernel-done.md`），aos-step 端另一輪。

### 21.4 兩句話規則（2026-09-13，使用者手機）

- 「janet 那邊如果因為程式語言太冷門，實作失敗很多次的話，那就改成定下 json 規範，然後用 python 實現。」→ Janet 不是信仰：逐步 lisp 的介面（狀態資料夾、pc、done、函式庫的 call）如果 Janet 那邊一直做不順，就把這些寫成 JSON 規範、換 Python 做同一件事。到 §21.4 為止 Janet 兩輪都一次過（15＋23＋4 → 34＋26＋4 條），還不用換。
- 「本地 LM Studio 我打開了。一次只能 load 一個模型，要用另一個模型要先 unload。」→ 之後 LLM cpu 實測用 `localhost:1234`，換模型前先 unload。

### 20.5 落地補記（第二輪「接住三條流」，codex gpt-sol，2026-09-13）

`aos/call` 多了 `:stdin`／`:capture`／`:read`／`:read-err`／`:json`，加 `aos/value`、`aos/pipe`（串接、不是真 pipe）。測試 34＋26＋4 條全綠。codex 自己決定的：沒 capture／read 就不放 `:out`；`pipe` 回最後一段的複本再掛 `:steps`（避免 table 循環）；**spork 的 JSON 是 cfunction、存不進 image**，所以 form 裡拿到的 `:value` 是解好的純資料、解碼器每次臨時載入——這是「image 裡放不進去的東西」第一次真的撞到。

### 21.5 每段做完都派人「試玩」（2026-09-13，使用者手機）

原話：「也可以另外讓 opus 或 gpt-sol 去試玩看看，看順不順手。判斷標準是容易上手、容易理解、複雜的東西都被隱藏起來、外層的控制結構簡單但全面、要背的東西少。每次做完一個段落都可以讓他們去玩玩看，給建議，然後我們改進。」

做法：每個段落 commit 之後，開一個**沒看過設計筆記、只拿到 README 入口**的 agent（Opus 或 gpt-sol，最好各一個）當新使用者，照 README 把東西架起來、寫一個自己的小程式跑過、故意弄壞幾樣看訊息，然後照五條標準各打分＋舉例：① 容易上手 ② 容易理解 ③ 複雜的東西有沒有藏好 ④ 外層控制結構簡單但全面 ⑤ 要背的東西少。回報放 `proto4/notes/play/`，一輪一檔。我們看完挑要改的。

### 21.6 Claude 訂閱怎麼接（2026-09-13，使用者拍板）

查證（`wf/workflows/experiments/claude-subscription/`）：Anthropic 2026 年起明文禁止第三方拿訂閱 OAuth 冒充 Claude Code 吃方案額度、伺服器端會擋、有人被封號；但**正式允許**第三方工具用訂閱帳號登入、用量算「extra usage」按 token 計費（pi 原生 `/login anthropic` 就是這條）。gotgenes/pi-anthropic-auth 那個套件多做的是塞假的 `x-anthropic-billing-header`＋換掉 system prompt 躲指紋，目的是被當成 Claude Code 本尊——**這部分不做**（我不冒充自家客戶端；使用者：「好吧，你說的對，我也怕被封號」）。

定案：aos 只走正路——讀 pi 存在 `~/.pi/agent/auth.json` 的 OAuth token、會 refresh、照 pi 原生 transport 的 header 打 Messages API、誠實報身分；用量走 extra usage（使用者要先在 claude.ai 方案設定打開）。之後 LLM cpu 的 endpoint 三個：LM Studio、DeepSeek、Claude。

### 20.6 落地補記（第三輪：aos-step 做完回 100、接上 kernel，codex gpt-sol，2026-09-13）

`aos-step` 全部 form 跑完之後改回 100（`--done-exit N` 可改，限 0–255），放進 kernel 的 `procs/` 會自己被收走。`test/cpu.janet` 加了一條真的走 daemon＋kernel 的整合測試：三個 form 的行程丟進 `procs/1.json`，約 2 秒後出現在 `procs/done/1.json`、`log.txt` 剛好 3 行、cpu 換回 idle、`aos-kernel ls` 印 `done: 1`。Janet 測試 34＋12＋28 條、proto4-3 188 條全綠。`proto4-3/docs/kernel.md` 補了 `procs/done/`、`done_exit`、五步裡的「先看做完沒」。**這一段（逐步 lisp＋kernel 應急版行程結束）到此收線。**

**21.6 續（使用者拍板）**：「拿 pi -p 當子行程用。pi coding agent 用的人超多，要是 anthropic 封這個，那就有得吵了。」→ LLM cpu 的 Claude endpoint＝開 `pi -p` 子行程（登入、條款、額度都是 pi 的事，aos 不碰 token）。參考 `~/repo/langs/janet-lab/modules/pi-shell/`（已經把 `pi -p`／`claude -p` 包成子行程殼）。endpoint 三種：LM Studio（OpenAI 相容 HTTP）、DeepSeek（OpenAI 相容 HTTP）、pi 子行程。

### 21.7 使用者的「餿主意」：直接拿 Claude Code headless 當 agent（2026-09-13，手機）

原話：「還有一種餿主意：拿 claude code headless 來用。或者是我們的 agent 那套換個型式，原本我們是自己從頭開始造狀態機，弄 llm 弄 tools，現在我們直接拿 claude code 作為 agent，tools 就是給他 mcp，然後我們給他收發訊息，就是接入他的 stdin/out。」

我的看法：**不是餿主意，這是唯一一條「用訂閱額度」又完全合規的路**——Claude Code 本尊的 `-p`（headless）是官方功能，用的是你的 Max 方案額度，Anthropic 擋的是「別的程式冒充它」，不是「你用它」。而且形狀跟 aos 對得很齊：

- **一個 agent 行程＝一份 inst.json，argv 是 `claude -p …`**，cwd 就是它的家（§8：本體在 cwd）。本機 claude 2.1.270 有 `--output-format stream-json`／`--input-format stream-json`（stdin 進訊息、stdout 出事件，一行一個 JSON）、`--resume <session-id>`／`--session-id`、`--mcp-config`、`--allowedTools`、`--permission-mode`、`--append-system-prompt`、`--max-turns`。
- **接進 tick 模型的兩種做法**：(a) 一格＝一回合：每格開一次 `claude -p --resume <id> --max-turns 1`，session id 存在 cwd，跟逐步 lisp 的 pc 同一個味道，kernel 完全不用改；(b) 常駐：一顆 cpu 開一支 `claude -p --input-format stream-json` 不關，aos 往它 stdin 塞訊息、讀 stdout。(a) 簡單、可搶佔、狀態在檔案裡；(b) 省 session 重載、但 cpu 要會「餵 stdin」（現在 aos-run 不會）。先做 (a)。
- **tools＝MCP**：aos 自己開一個 MCP server，把「叫資料夾／叫檔案」（proto4-4 那套 call）、「丟一個行程進 procs/」、「問 kernel 狀況」暴露成 MCP tools——**這就是 §19.5 的 syscall**，等於 syscall 的形式順便定了：對 lisp 是函式、對 claude 是 MCP tool、底下同一支程式。
- **pi -p 是同一個形狀**：所以「agent cpu」其實是「跑一支 CLI agent 當子行程」，claude／pi／codex 都套得進去，janet-lab 的 pi-shell 已經是這個抽象。

代價與邊緣（先記）：headless 每回合冷啟動幾秒；`--permission-mode` 要選對不然卡在問權限；session 檔在 `~/.claude/projects/` 不在 cwd（要不要搬、怎麼對應）；plan 額度用完就停（§19.6 那種「結果沒人接」）；多個 agent 同時跑會搶額度、要靠 kernel 的排程壓。

**沒開工**：這條會改 roadmap（agent 狀態機可能不用從頭造），要使用者回來拍板順序——是先做 LLM cpu（排隊分發、三種 endpoint），還是直接做「CLI agent 當行程」。
