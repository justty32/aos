# 查證 01n（ok-skyrim 隊 ok-skyrim-sol-3 原文）：回 proto8 程式查借鑑清單的「aos 現況」——max_subagents 怎麼算、腦預算怎麼分帳、subagent add 經不經門、limits 是不是逐隻、獨佔資源有沒有表示

← [README](README.md)｜[02 借鑑清單](02-借鑑清單.md)｜[06 採納與查證修訂](06-Argon採納與查證修訂.md)｜隊員原文照收，隊長只加這兩行；靜態讀碼、沒有實跑。

# v3 配額查證：子名額各自算，腦有共用總額，subagent add 依 AOS_KERNEL 走門。

## 結論與讀法

五題依序判為「部分成立、部分成立、部分成立、成立、部分成立」。腦不只分 sender 帳，subagent add 不是固定不經門；一格且可追 sender，不等於一般資源鎖。證據與替換句分列各題。

以下 `proto8/…` 都相對 `/home/lorkhan/repo/aos/`；活樹定義另寫絕對路徑。這是原始碼靜態查證，沒有執行程式、測試或指令，也沒有讀其他 agent 的 stack。範圍見 `/home/lorkhan/repo/aos/wf/temp/ok-skyrim/briefs/v3.md`。

## 1. max_subagents 是否逐隻各有一份

判定：部分成立。每隻各算自己用這支工具登記的直屬子 agent，沒有在這個計數器裡扣祖先的總額；但 4×4×4 是第三代的數量，不是整棵樹總數，也不是保證能開出的數量。

證據：

- `proto8/templates/agent-fsm/subagents.json:1` 原文 `{"max_subagents": 4}`；`proto8/lib/agent/subagent/_entry:55` 是 `MAX_SUBAGENTS_DEFAULT = 4`。
- `proto8/lib/agent/subagent/_entry:118` 原文 `for d in (me.get("def"), me.get("stack"))`，接著 `cfg.update(v)`：設定讀自己的定義，再疊自己的 stack。
- `proto8/lib/agent/subagent/_entry:18` 寫明帳在 `$AOS_STACK/subagents.json`，此處是工具小格 `tools/subagent/`；`:178` 用 `book_path = os.path.join(stack, CFG)`。這與 agent 定義／stack 根目錄的同名設定檔不同。
- `proto8/lib/agent/subagent/_entry:93` 的 `reconcile()` 讀本帳，拿名字與 stack 對 daemon 表；`:106` 保留排隊中的項目。`:189` 只判 `if len(alive) >= n`，滿額即 `SubagentSlotMissing`；`:195` 寫回自己這本帳。沒有沿 owner 或祖先往上加總。
- `proto8/lib/aos/kernel/procs_rules.py:195` 另有 `len(running) + len(admitted) + len(fresh) > cap` 的站級檢查。因此本工具沒樹總額，不等於外部完全沒有共用限制。

準確替換句：

「subagent 的 max_subagents 預設 4，各 agent 以自己的工具帳限制直屬子項（含排隊項），不自動分割祖先配額。若每隻都有工具、各代都能開滿且沒有其他限制，往下三代分別是 4、16、64 隻，後代合計 84 隻，連根 85 隻；64 只是第三代。站級 max_running 仍可能限制實際數量。」這是前述計數程式的條件推算，不是實測。

## 2. 腦預算是否只照寄件 stack 各算各的

判定：部分成立。寄件 stack 確實是 sender 分帳鍵；但同一個 llm kernel 同時有總額、endpoint 包額度與 sender 額度，不是互不相干的個人錢包。

證據：

- `proto8/impls/aos-llm/src/send/send.cpp:110` 原文 `opts.sender = aos::stack_identity()`；`:122` 的短註解是 `$AOS_STACK ＞ identity()`。寄件者是問腦 proc 的 stack，不是 workspace。
- `proto8/impls/aos-llm-kernel/src/budget/budget.cpp:200` 讀 kernel stack 的 `used.json`。`:247` 的 `add_used` 同時增加總數、`packs` 與 `senders`；`:258` 原文 `count_in(u.senders, sender_key(sender, stack), t)`。`:44` 把 sender 路徑改成相對 kernel stack 的鍵；不是用子目錄前綴把一家人歸戶。
- `proto8/impls/aos-llm-kernel/src/serve/serve.cpp:140` 先判 `spent(budget_, used_, n + busy_)`（kernel 總額），`:158` 判包額度，`:174` 查 `budget_.senders.find(who)`。sender 沒列限額時不套 sender 專額，總額與包限制仍在。
- 同檔 `:149` 判總 `slots_`，`:191` 判 `w.pack.slots`，`:198` 判 backend slots／同時包數。slots 是同時在飛數量，與 calls／tokens 的時間窗預算分開。
- `proto8/impls/aos-llm-kernel/src/serve/reply.cpp:101` 帳在 kernel stack 的 `ledger.jsonl`；`:106` 記 `endpoint`、`sender`，`:127` 記 `child`，`:160` 才更新 used。ledger 是逐封紀錄，不是另一套祖先配額扣帳。
- Python 問腦包也相同：`proto8/lib/aos/kernel_llm/budget.py:208` 的 `add_used` 同記總額、包、sender；`proto8/lib/aos/kernel_llm/llm_rules.py:466` 先判總額，`:440` 查 sender 額度；`proto8/lib/aos/kernel_llm/ledger.py:18` 留逐封 endpoint／sender。出廠範本 `proto8/kernel/llm-kernel/daemon.json:1` 仍叫 `aos-llm-kernel`（C++）。

準確替換句：

「腦的帳集中在各 llm kernel stack：used.json 同記全站、endpoint 包及信封 sender（問腦 proc stack）的用量，ledger.jsonl 留逐封帳。限額可同時設全站、包與指定 sender；沒有自動把某 sender 的子孫合併到它名下。共享同一 kernel 的請求仍受該站總額與 slots 約束。」

## 3. kernel 只管經過的請求，subagent add 是否不經門

判定：部分成立。站確實只在處理自己的信時判規則；但「subagent add 不經門」與 repo 現碼相反。ok-skyrim 的實際環境值則不能只憑定義確認。

證據：

- `proto8/lib/agent/subagent/_entry:193` 是 `cmd.parse_added(cmd.agent(argv, ...))`，不是自己寫 daemon 信箱。`proto8/lib/agent/agents_cmd.py:216` 組 `argv = ["ctl", "add"]`；`:117` 的 `agent` 轉叫 `aos-agent`。`:67` 的 Popen 傳 `env=env`，正常未另外給 env，沿用呼叫端環境。
- `proto8/cmd/aos-agent/aos_agent/ctl/add.py:149` 的 `if via_kernel()` 分支轉 `add_via_kernel`；`proto8/cmd/aos-agent/aos_agent/common.py:91` 原文「設了 AOS_KERNEL，而且沒明給 --daemon」。subagent 組出的 add 沒有 --daemon。
- `proto8/py/daemon_ctl/post.py:29` 原文「沒給 direct 且設了 AOS_KERNEL＝那個 kernel 的收件箱」；`:31` 起讀環境，非空先回 kernel box，否則才取 daemon 的 `procs_requests`。`proto8/cmd/aos-agent/aos_agent/ctl/shared.py:115` 的 `ctl_wait` 以 `dc.send` 寄出請求。
- `proto8/lib/aos/kernel/procs_rules.py:81` 數的是 `count_daemon` 表中全部 `running`／`stuck` 名字，不只本站曾放行的項目；`:195` 再加本輪放行名字與新名字。`allowed` 在 `:179` 只檢查 `procs_added` 的名字。規則能拒的是本站手上的信，不能倒回去阻止已從別路掛上的 proc。
- `proto8/lib/agent/kernel_gate/_entry:44` 預設只有 `after_verdict`、`condition: pass` 的 hold hook；`:96` 只有不存在 kernel.json 才寫。`proto8/lib/agent/kernel_gate/hold:5` 原文 `print('{"verdict": "hold"}')`。預設未設 allowed／max_running，不是自帶數字上限；也不替別人自動設定 AOS_KERNEL（`_entry:106` 明說寄件人須設定）。
- `/home/lorkhan/aos-home/agents/fable-kernel/system.txt:3` 原文「Your own start/stop requests go through repo-aos's kernel_gate (AOS_KERNEL).」這是定義的指示。已列含隱藏檔的定義目錄，沒有 `.env`；`_entry:1` 只有 `["aos-loop", "loop.json"]`，`loop.json:1` 沒有設定 AOS_KERNEL。
- 繼承機制存在：`proto8/impls/aos-daemon/src/child/child.cpp:64` 起只重設 stack／daemon／ws；`proto8/lib/agent/cli_print.py:52` 用 `dict(os.environ, **env)` 或預設繼承起 CLI；`proto8/lib/agent/cli_mcp.py:115` 的保存清單包含 AOS_KERNEL。但掛在 repo-aos 底下本身不證明變數已設定，仍取決於啟動環境或 envs。

準確替換句：

「kernel 站只審經它收件箱的請求；max_running 讀指定 daemon 的 running／stuck 全表再加輪內放行數。subagent add 轉叫 aos-agent ctl add，有 AOS_KERNEL 時會先寄該站，沒設才寄 daemon。fable-kernel 的 system 指示要走 repo-aos gate；本次未讀執行中環境，不能確認 ok-skyrim 當下的值。」

## 4. --limits 與 B1 是否只是單隻限制

判定：成立，限於「單 proc 設定與逐隻套上限」的意思；不是各層可分配、會扣餘額的總池，也不保證所有新鍵已能在現有 daemon 執行。

證據：

- `proto8/cmd/aos-agent/aos_agent/ctl/add.py:108` 起解析 --limits，註解「--limits 整份蓋過宣告」；`proto8/impls/aos-daemon/src/daemon/reconcile.cpp:20` 原文 `spec.contains("limits") ? spec["limits"] : limits_`，每支選自己的設定或 daemon 預設，不扣兄弟餘額。
- `proto8/impls/aos-daemon/src/child/limits.cpp:28` 對照 mem_mb→RLIMIT_AS／RLIMIT_DATA、cpu_s→RLIMIT_CPU、files→RLIMIT_NOFILE；`:30` 的 procs 是 RLIMIT_NPROC，不能當作 aos 子樹計數器。`:148` 的 `apply_limits` 在子行程 setrlimit；`:156` 說超過 daemon 自己 hard limit 會報錯。這不是整棵 agent 家族共用的記憶體／CPU 總帳。
- `proto8/lib/aos/kernel/procs_rules.py:243` 在 `letters.forward` 前先 `limits_rule.apply(...)`。
- `proto8/lib/aos/kernel/limits_rule.py:89` 原文 `default.update((limits.get("by_sender") or {}).get(sender, {}))`，是 sender 完全相等的預設覆蓋。`:91` 逐一走 procs_added；`:109` 每支都 `copy.deepcopy(own if own else default)`，非空自帶份額不與 default 合併。
- 同檔 `:111` 逐鍵用 max 夾，缺鍵也補 max，`:130` 記 `limits_clamped`；`:107` 去掉請求自帶 user／groups，`:117` 以 proc 名字第一個 fnmatch 樣式選站方身分。groups 是群組名換號，不是資源配額池。
- 整個 `limits_rule.apply`（`:79` 起）只複製 body、修改每個 proc、回傳，沒有寫配額帳、扣父額、累加兄弟用量或把剩餘值傳給下一代。
- `proto8/thinking/2026-11/14/kernel-limits-1114.md:117` 原文「default／by_sender 本來就只是預設不是上限」；`:132` 記 B1 四個檔已完成。`:37` 明列舊 daemon 不認 limits_clamped／limits.groups／sub:N。現碼 `proto8/impls/aos-daemon/src/child/limits.cpp:91` 的已知鍵也只有五種數值與 user，沒有 groups；因此不能把站能產生的格式當成執行端都已支援。

準確替換句：

「--limits 是每支 proc 的作業系統限制設定。B1 站會在轉出 procs_added 前，逐支補 default／by_sender、以 max 夾值，再由 users／groups 指定身分；沒有父線總額扣帳或子孫份額守恆。mem_mb／cpu_s／files 也不是整棵子樹加總限額。新欄位另受 daemon 相容範圍限制。」

## 5. 名額一個且帶 owner 是否完全沒有表示

判定：部分成立。沒有看到通用資源鎖的 owner／釋放契約；但「一格、追到誰在用」不是全無表示。

證據：

- `proto8/lib/aos/kernel/procs_rules.py:81` 的 running 是 proc 名字集合；`:195` 用集合大小與 cap 比較。max_running 可填 1，但數的是指定 daemon 全表，不是某個 GUI 資源的持有人。
- `proto8/impls/aos-llm-kernel/src/pack/pack.cpp:23` 接受正整數 slots（含 1）；`proto8/impls/aos-llm-kernel/src/serve/serve.cpp:191` 原文 `inflight >= *w.pack.slots`。同檔 `:253`、`:255` 把 endpoint、sender 存進信的 proc.json，故能從在飛請求追到寄件 stack。
- Python 也保存：`proto8/lib/aos/kernel_llm/llm_rules.py:520` 原文 `proc["sender"] = waiting["sender"]`；`proto8/lib/aos/kernel_llm/slots.py:25` 從在飛 proc 回算佔用，`:51` 檢查包 slots。
- `proto8/lib/aos/kernel/letters.py:276` 的轉寄對照可記 sender，但這是代回／防重資料。`proto8/lib/aos/kernel/procs_rules.py:169` 的完整 verdict 只讀請求名字、running、admitted、cap；沒有資源 owner 相符才准釋放的檢查。

準確替換句：

「proc 站可設 max_running=1，腦站可設 slots=1，且在飛腦請求記有 sender，能追查誰佔用；這不等於任意資源的具名獨佔鎖。此次讀到的內建規則未提供 GUI／實機等資源的 acquire／release 與 owner 核對契約。」

## 沒讀到／不確定的

- fable-kernel 定義沒有 .env；system.txt:3 寫要走 gate，但未讀 ok-skyrim 的執行中環境或 stack，無法證實當下 AOS_KERNEL 值、實際 gate 規則或部署版本。
- 未執行 git，未驗 commit 7c435de4d 的歸屬；B1 以現有程式及 kernel-limits-1114.md:132 為證。該文件採後面的 B1 接手紀錄，不採舊標題。
- 未跑測試或真模型，未重驗文件的測試結果。未遍查自訂 hook／鎖工具，第 5 題只限已讀的 kernel 內建規則。
