# 任務書：proto5-2 規範草稿唯讀審查（astra，2026-09-24）

你是唯讀審查者。**不要改任何檔**，只把報告寫成你的最後回覆（會被存成 `proto5-2/notes/2026-09-24-spec-review-astra-report.md`）。用繁體中文、白話。

## 背景

repo 根目錄有 `proto5/`（現行規範＋程式）與新寫的 `proto5-2/`（規範草稿，未實作）。proto5-2 在 proto5 之上，把 kernel／daemon 改成以「池」為單位、宣告式。
使用者 2026-09-24 定了六點（原文）：

(a) kernel 的 cpu 表改成**池表**（池名、daemon 家、daemon 那邊的池名、要幾顆、envs），不列每顆；cpu 種類由池的 envs 決定（llm 池帶 `AOS_LLM_CONFIG`），入池的 cpu 繼承。
(b) **宣告式**：kernel 只告訴 daemon「池 P 要 N 顆」，daemon 自己補到 N、死了自己重拉（要節流）、多了自己收；kernel 不記 pid，只看池摘要。
(c) **daemon 內部也按池管孩子**，一個 daemon 可帶多個池（一池一 daemon 可以但不強制）；指令全帶 `--pool`：`aos-daemon boot／halt --target D`、`ls [--pool P]`（按狀態數活／忙／dead／重拉中，`--pool` 才展開）、`scale --pool P --count N`、`kill --pool P NAME`。孩子表不整份重寫 state.json（上萬顆一改就幾 MB），改一顆一小檔或只記差異；kill 階梯批次做。
(d) `aos-kernel cpu add [--target K] --pool P [--count N] [--env K=V]`／`cpu rm NAME|--pool P --count N`／`cpu ls` 就是改池的數字與看池摘要；`aos-kernel ls` 也按池摘要。kernel 每格重讀 info，下一格看到池數字變了就告訴 daemon，不用 boot。
(e) `aos-kernel init --target K --config xxx.json` 只剩 kernel 參數＋池定義，cpu 可空。
(f) 每格成本從 O(cpu 數) 變 O(有事的 cpu 數)：例如 cpu 有回音時往 kernel 家丟一個通知檔，kernel 只掃那個目錄；派工也不能每格掃每顆找閒的。

## 要讀的

- `proto5-2/README.md`、`proto5-2/spec/*.md`（全部，約 13 份小檔，從 `spec/README.md` 開始）。
- 對照：`proto5/spec/kernel.md`、`daemon.md`、`cpu.md`（被取代或補充的節）、`aos-agent.md`（特別是 §5、§10、§11 偷看 `K/state.json` 的地方）、`agent.md`（池相關欄位）、`aos-exec.md`、`inst-posix.md`、`directives.md`（`$ref` 的中心與 envs）。
- 需要時可看 `proto5/lib/` 的實作確認現況（例如 `aos_kernel_engine.py`、`aos_daemon.py`、`aos_exec_cpu.py`、`aos_inst.py`、`aos_directives.py`）。

## 要找的（每條都要附：哪一檔哪一節、為什麼是問題、建議怎麼改或要問使用者什麼）

1. **六點有沒有漏或走樣**：逐點對照，說落實了沒、哪裡跟原文不一致（例如 `cpu rm NAME` 的 NAME、`ls` 的四種狀態、`--env` 的語意）。
2. **kernel ↔ daemon 協定的洞**：崩潰窗口（kernel、daemon、cpu 任一方在任一步崩掉）、對帳（kernel 的 `sent`／`pending`／`free`／`busy` 與 daemon 的 `pool.json`／孩子的實際狀態會不會分歧而永遠不收斂）、重送是否真的冪等、boot 交接會不會讓兩格 tick 同時跑、halt 後再 boot 的順序、daemon 重開後 kernel 鏈接不接得上、通知（`resp-`）漏掉或重複時會不會卡死或重判。
3. **上萬顆時哪裡還是 O(N)**：spec 自己列了一些（`scale.md`），找它漏列的、或宣稱 O(有事) 其實不是的（例如 `delayed` 插入、`busy` 輪轉、`free` 重整、`ready` 裡已被 rm 的行程、`K/requests/` 列目錄、summary 重寫）。
4. **跟 proto5 不變那幾份有沒有矛盾**：`cpu.md`（除了 notify）、`agent.md`、`aos-agent.md`、`aos-llm-call.md`、`aos-exec.md`、`inst-posix.md`、`directives.md`。特別看：aos-agent 偷看 `K/state.json` 的 `procs`／`queue`／`cpus` 等欄位、`kernel check --agent` 的池檢查、agent 的 `llm.pool`／`tool_pool`／`tick.pool` 語意、cpu fd 1 改接 `/dev/null`、`$ref` 取 envs 裡的 `$opt`。
5. **實作者還得猜的地方**：欄位型別、預設、錯誤代號、順序、檔名、邊界值（`count` 0、`skip` 很大、池名撞到 `kernel`、info 裡的池被刪掉又加回來…）沒寫清楚的。

## 報告格式

- 開頭一段總評（三五句）。
- 然後一條一條列，編號 `R1`、`R2`…，每條標嚴重度 `高`（會卡死／丟工作／兩格同跑／資料錯）、`中`（實作者會猜錯或規模退化）、`低`（措辭、漏寫小細節），並標類別（六點／協定／O(N)／矛盾／要猜）。
- 最後一節「要使用者拍的」：只列真的需要使用者定方向的題目（不要把你能直接建議修法的放這裡）。
- 不要客套、不要重述規範內容；找不到問題的類別就寫「沒找到」。
