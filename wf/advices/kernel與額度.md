# kernel 與額度

← [README](README.md)

llm kernel（lib/aos/kernel_llm）、腦額度、找 kernel、kernel_gate 的意見。

## BudgetMissing 只給一行文字，agent 不知道何時能重試

- 主題：kernel 與額度
- 哪裡：llm kernel 對超額請求回的 `{"error": {"code": "BudgetMissing", "msg": ...}}`（`lib/aos/kernel_llm/llm_rules.py`）；agent-fsm `wait.py` 的 BudgetMissing 分支。
- 現象：錯誤只有一行英文，例如 `budget.senders key "..." (sender ...): max_calls 150 reached in this window (day); not run`。agent 讀不到「窗口何時結束」「是不是 `window: "all"`、永不重置」。AK17 只好用固定冷卻（30 秒起加倍、30 分鐘封頂）盲目重寄：day 窗口可能白敲幾小時，all 窗口會每 30 分鐘敲一次、永遠敲下去。Argon 審 AK17 時也提過（A1），當時要解析 msg 才做得到，所以放棄。
- 建議：error 物件多帶結構化欄位，例如 `"window": "day"`、`"resets_at": "<ISO 時間>"`（all 給 null）、`"key": "<sender key>"`。wait.py 把冷卻的 until 設成 resets_at；null 就只通知不重試，或拉長間隔。
- 痛的程度：拖慢
- 提出者與日期：ok-astra 2026-11-14
- 出處：wf/temp/ok-astra/aos-advice/budget-refusal-structured-retry.md；proto8/thinking/2026-11/14/astra-kernel-1114.md AK17 節；commit 2368ee3af
- 狀態：已解（ok-astra，313ce20ec）。kernel 的 BudgetMissing 多帶 `scope`、`window`、`since`、`resets_at`（all 為 null）、`limit`、`max`、`endpoint`／`key`；agent-fsm 冷卻等到 `resets_at`＋5 秒，`window all` 寄 BLOCKED 後停下（退 1、不記冷卻）；舊 kernel 照 AK17（2368ee3af）的冷卻。換樹清單見 astra-kernel-1114 ADV 節，等換樹才在活樹生效。

## aos-llm ls 沒設 AOS_LLM_KERNEL 就不能用

- 主題：kernel 與額度
- 哪裡：`aos-llm ls`。
- 現象：`aos-llm: error: LlmKernelMissing AOS_LLM_KERNEL is not set (the llm kernel stack, e.g. ~/llm_kernel)`。eca kernel 身上通常沒有這個變數，只想看有哪些腦包也得先自己找路徑。
- 建議：沒設時到 `$AOS_DAEMON` 的 procs 裡找 llm kernel 並列出；或加 `--kernel NAME`。
- 痛的程度：小不便
- 提出者與日期：ok-pilot 2026-11-14
- 出處：wf/temp/ok-pilot/aos-advice/小坑三則.md 第 1 則；wf/temp/ok-pilot/notes.md 第一輪「摩擦」第 4 點
- 狀態：未處理
- 相關：[fsm 範本「漏設 AOS_LLM_KERNEL」](fsm範本.md)，同樣是「找不到 kernel 要自己帶路徑」。

## before_verdict hook 拒信只能回 HookRejected，做不了「額度用完、晚點再試」

- 主題：kernel 與額度
- 哪裡：`lib/aos/kernel_llm` 的 `before_verdict` hook（README「hooks」表）；agent-fsm `wait.py` 只對 BudgetMissing 走冷卻。
- 現象：hook 退 10 一律回 `{"error": {"code": "HookRejected", ...}}`。agent-fsm 只對 `BudgetMissing` 走 AK17 冷卻重試，`HookRejected` 當一般 BrainFailed，agent 會停。所以想用 hook 外加額度規則（例 llmk2 的部門配額）時，只能直接殺掉那封請求，不能叫它晚點再來。
- 建議：讓 `before_verdict` 能在 stdout 回 `{"error": {"code": "BudgetMissing", "msg": "..."}}`，站照這個代號回信（代號白名單：BudgetMissing、HookRejected）。外加額度規則就不用改站本體。可和上一條的結構化欄位一起做。
- 痛的程度：小不便（規劃時發現，擋住「用 hook 做部門額度」這條路）
- 提出者與日期：ok-llmk2 2026-11-14
- 出處：wf/temp/ok-llmk2/aos-advice/kernel-llm-hook-reject-code.md；proto8/thinking/2026-11/14/llmk2-1114/03-計劃.md §2.3
- 狀態：已解（ok-kmsg，d6a564191）。改在共用的 `lib/aos/kernel/hooks.py`：`before_verdict`／`after_verdict` 的 hook 退 10 且 stdout 印 `{"error":{"code":"BudgetMissing","msg":"…","resets_at":"…"}}` 就回 BudgetMissing，回信帶 `resets_at`、`scope: "hook"`、`hook: <名>`，agent-fsm 照 313ce20ec 的冷卻等到 `resets_at`；不給 `resets_at` 照 30 秒起加倍的間隔重試。hook 給的 `window` 等其他鍵不帶（要對方停下照舊印純文字＝HookRejected）；其他 stdout 行為不變。等換樹才在活樹生效。設計與 Argon 採納表：proto8/thinking/2026-11/14/ok-kmsg-1114.md。

## llm kernel 沒開時，外人只看到 listen 逾時、沒有提示

- 主題：kernel 與額度
- 哪裡：`proto8/templates/daemon-root/README.md`（「它沒開時 agent 只是一直等、不會壞」那句）；`aos-agent … listen`；`aos-daemon-ctl ls` 的 REASON 欄。
- 現象：範本 README 有寫 llms 要放在專案旁邊（`.env` 預設 `AOS_LLM_KERNEL=${AOS_WS}/../llms/stacks/llm`）。但照文件打字的外人如果漏起了 llms、或擺的位置不同，agent 會一直等；他看到的只是 `timeout 60 … listen` 時間到、什麼都沒印，不知道是腦沒開。投稿隊是照 README 推的，**沒實測這個情況**。
- 建議：
  1. `listen` 等不到時，如果發現 agent 正在等腦，印一行「agent 在等 llm kernel（找的是 <路徑>）；沒開就照範本 README 起一個，或設 AOS_LLM_KERNEL」。
  2. 或讓 `aos-daemon-ctl ls` 的 REASON 欄標出「等腦」。
- 痛的程度：投稿沒寫；整理者看是拖慢（對照文件第一次用的外人來說可能擋路）。
- 提出者與日期：ok-release 2026-11-14
- 出處：wf/temp/ok-release/aos-advice/腦沒開時listen只會逾時.md；templates/daemon-root/README.md；草稿「開始用」第 3 步與疑難排解「agent 不回」一節（proto8/thinking/2026-11/14/release-1114/06-草稿/v1/_src/docs/zh/）
- 狀態：已解（ok-kmsg，d6a564191；採建議 1）。agent-fsm 的 wait 寄出請求後記 `think/brain_wait.json`（信名、kernel stack）；`aos-agent listen`／`say`／`ask`（含 `subagent` 工具的 ask／listen）發現 agent 在等腦而 kernel 的 `state.json` 不在、phase 不是 running／waiting／stopping 或 pid 不在時，stderr 印一行 `NAME is waiting for its brain, but the llm kernel at <路徑> is not running (…)`，逾時的 AnswerMissing 行尾也帶同一句；kernel 資料夾不在時印 `NAME cannot reach its brain: …`。`cmd/aos-agent` 那半已生效，`wait.py` 等換樹；建議 2（`ctl ls` 的 REASON 標等腦）沒做。10 分鐘的 stderr 警告照舊。
- 相關：[fsm 範本「漏設 AOS_LLM_KERNEL 時 agent-fsm 靜靜卡住」](fsm範本.md)（已解，只管變數沒設；有設但 kernel 沒開這條沒管）。

## eca 當 gate 時，下屬的唯讀查詢也被 hold，連讀信都 KernelFailed

- 主題：kernel 與額度（kernel_gate）
- 哪裡：`proto8/lib/agent/kernel_gate/hold`、`triage`；下屬帶 `AOS_KERNEL` 時 aos 工具經 gate 查自己的 stack 路徑（body 帶 `procs_state_path`）。
- 現象：skyrim 那邊的 eca（skyrim-agent-agentctl）掛在開了 gate 的 eca 底下，帶 `AOS_KERNEL` 的 aos 工具呼叫都經 gate；連讀信這種只查路徑的請求也被 hold，gate 忙時 3 秒逾時回 `KernelFailed`，要等一下重試。11-14 下午它自己累計 9 次（開場、寄 DONE、讀信都有），工人另回報 2 次。
- 建議：投稿沒寫；整理者看：只查路徑、不起東西的請求不該被 hold。
- 痛的程度：拖慢（每次都要重試）
- 提出者與日期：skyrim-agent-agentctl 2026-11-14（skyrim-agent 轉來，頂層 14:27 回過信）
- 出處：`~/repo/moddings/skyrim/agentctl/tmp/aos/skyrim-agent-agentctl/notes.md`「踩到的」第 1 條、「14:2x 追加」「14:3x 狀態」的逾時累計；底座部 ok-kf 查證
- 狀態：已解（c3c1877ea，ok-kf 11-14）：kernel_gate 的 hold、triage 看到 body 的 procs_* 只有 `procs_state_path: true` 就直接放行（不留，triage 記一行 pass），跟其他鍵並寫才照其他鍵判；測試 test_query_daemon（真 daemon，3 秒內回到原寄件人）。活樹待換樹（活樹的 lib 是另一份，11-14 晚換樹才生效）。
- 相關：本檔「gate 站掛在主人的 on_clock，主人長回合時下屬逾時」（同一個 KernelFailed 的另一半成因，還沒解）。

## gate 站掛在主人的 on_clock，主人長回合時下屬逾時

- 主題：kernel 與額度（kernel_gate）
- 哪裡：kernel_gate 的框架站靠開 gate 那隻 agent（主人）的 on_clock hook 推進。
- 現象：主人正在跑一個長回合時，站不跑，下屬經 gate 的請求等不到，3 秒逾時回 `KernelFailed`。上一條修好之後，唯讀查詢不再被 hold，但要經站處理的請求遇到主人長回合仍會逾時（頂層 14:27 給 skyrim 那邊的信也這樣說）。
- 建議：投稿沒寫。這是目前的設計使然（站跟著主人的鐘走），怎麼改由 ok-kf 出設計。
- 痛的程度：拖慢
- 提出者與日期：skyrim-agent-agentctl 2026-11-14（skyrim-agent 轉來）
- 出處：同上一條；頂層 11-14 14:27 給 skyrim-agent-agentctl 的信（筆記「14:3x 狀態」有記）；底座部 ok-kf 查證
- 提出者與日期（第十三批併入）：ok-kf 2026-11-14（程式位置與三個方案）
- 出處（第十三批併入）：wf/temp/ok-kf/wrapup-1114/建議.md 第 2 則（引給 head-core 的查證信 01794637514318574262.912280.2609996）
- 第十三批補：程式位置是 `proto8/lib/agent/kernel_gate/_entry` 第 103、107 行（站掛在主人的 on_clock 上，只在主人不在回合裡時每個 clock 週期跑一次）和 `proto8/py/daemon_ctl/state_path.py` 的 `QUERY_S = 3`（第 15 行）、`_asked`（第 16 行：快取只在單一行程內，所以每個工具行程都會重問一次；skyrim-agent 實測）。帶 AOS_KERNEL 的下屬幾乎每次開場都卡。ok-kf 列的三個方案：甲，把問到的表檔路徑存成小檔；乙，站改成 daemon 表上獨立的小行程；丙，只調等待秒數和快取。整理時查：上面行號都對。
- 狀態：已排入（ok-kf，11-15 出設計）。

## subagent add 之後馬上 ask，回 SubagentMissing，工人被從名冊刪掉

- 主題：kernel 與額度（只設 AOS_KERNEL 時的 subagent）
- 哪裡：`proto8/lib/agent/subagent/_entry`（名冊 subagents.json、對帳）。
- 現象：skyrim 那邊的 eca 帶 `AOS_KERNEL`、經 gate 掛工人：`subagent add` 後馬上 `ask`，回 `SubagentMissing`，工人被從名冊刪掉，但工人其實活著（`aos-daemon-ctl -d $AOS_DAEMON ls` 查得到）。名字也不能再用，下一隻只好換名。繞法：改用 `mailbox_send` 派工，叫工人做完自己 `self_ctl rm`。
- 建議：投稿沒寫。
- 痛的程度：拖慢（要換名、改走寄信派工）
- 提出者與日期：skyrim-agent-agentctl 2026-11-14（skyrim-agent 轉來）
- 出處：`~/repo/moddings/skyrim/agentctl/tmp/aos/skyrim-agent-agentctl/notes.md`「踩到的」第 2 條；底座部 ok-kf 查證
- 狀態：已解（c3c1877ea，ok-kf 11-14）：活樹的 lib 是舊的才會這樣。新版 subagent、fork 以 `ctl who` 回的自己那列 stack（絕對路徑）為基準，叫 aos-agent 不帶 `--daemon`、照 kernel 路由，subagents.json 存絕對路徑；只設 AOS_KERNEL、沒有 AOS_DAEMON 也能掛子、對帳、收子（新測試 kernel_fixture）。活樹待換樹（11-14 晚換樹才生效，換樹前照舊用 mailbox_send 派工）。

## kernel_hold 通知分不出「工人要移除自己」還是「別人要移除它」

- 主題：kernel 與額度（kernel_gate）
- 哪裡：kernel_gate 的 hold 通知（`[aos] kernel_hold: …`），由 `proto8/lib/agent/kernel_gate/gate_lib.py` 的 `lines()`、`notice()` 組（116～120 行：每封印 letter、from、request、deadline、其他鍵）。
- 現象：工人做完後 `self_ctl rm` 自己，頂層收到的 hold 通知裡 from 是工人自己的 stack 夾；要對照 request 那行裡的名字才知道是「工人要移除自己」，一眼看不出來。
- 建議：通知分開列「誰發的請求（caller）」和「對誰做（target）」；兩者相同時加註 self。
- 痛的程度：小不便
- 提出者與日期：skyrim-agent 2026-11-14（skyrim-agent-opus-1 整理投稿）
- 出處：`~/repo/moddings/skyrim/tmp/aos-skyrim-agent/top/aos-advice/skyrim-1114.md`「kernel_hold 通知裡，工人 self_ctl rm 的寄件位置顯示成工人自己的夾」；skyrim 那邊自己的 hold 程式在 skyrim repo 的 `agentctl/aos/gate/gate_hold.py`
- 狀態：未處理。整理時查：`lines()` 只印 `from: <sender>` 和原樣的 request，沒有 target、沒有 self 標記。
- 相關：本檔「eca 當 gate 時，下屬的唯讀查詢也被 hold」「gate 站掛在主人的 on_clock」（同一場、同一個 gate）。

## 提示快取命中率低：llm kernel 沒送固定的 session id

- 主題：kernel 與額度（llm kernel）
- 哪裡：`proto8/lib/aos/kernel_llm/llm_rules.py` 的 dispatch（寫 `request.json` 那一步）；endpoint pack（`packs.py`）。
- 現象：llm-gpt 帳本上提示快取只命中 29%。LiteLLM 的 chatgpt 後端每個請求送一個 session id，呼叫方沒給就每次換一個，上游接不回同一隻 agent 前一次的快取。對照實驗：兩隻 sol 同時跑、各問腦 15 次，帶固定 `litellm_session_id` 的那隻命中 88%，不帶的 18%（不帶的最多只中兩隻共用的開頭那段）；正式補丁再跑一輪是 82% 對 31%。
- 建議：llm kernel 送請求時帶一個固定的 session id，值由寄件 agent 的 stack 路徑算；非 LiteLLM 的端點收到不認得的鍵會怎樣沒測過，做成 endpoint pack 的開關。
- 痛的程度：拖慢（燒額度：同樣的工作，沒命中快取的提示 token 從 194,859 降到 27,511）
- 提出者與日期：ok-fsm 2026-11-14
- 出處：`proto8/thinking/2026-11/14/ok-fsm-1114/01-預設工具包-設計稿.md`「第二步對照實驗結果」「正式補丁與第二輪對照」；commit 7ce38e7cf
- 狀態：已解（7ce38e7cf，ok-fsm 11-14；使用者專區回信准、ok-kmsg 審、head-tools 放行）。endpoint pack 多一個鍵 `session_key`，預設關：開了的包，dispatch 在 request 頂層加 `{鍵名: sha256(寄件人 stack 路徑) 前 32 個十六進位字}`，請求自己已有那個鍵、或信沒有寄件人就不加；沒寫＝請求原樣交出去。新測試 `tests/test_session_key.py` 6 支。**活樹還沒開**：要在活樹 llm-gpt 的 kernel.json 的 `sol-high` 包加 `"session_key": "litellm_session_id"` 才生效，換樹後由頂層開。但書：實驗只跑兩隻、各 15 次、提示最大約 2.6 萬 token，活樹十幾隻、提示 10 萬以上的規模沒測。

## state 和 ctl ls 看不出隊員是在排腦的隊、額度被拒，還是卡住

- 主題：kernel 與額度（也碰到指令與工具的 `subagent state`、`aos-agent ctl ls`）
- 哪裡：`subagent {"op":"state"}`、`aos-agent ctl state`、`aos-agent ctl ls` 的 REASON 欄；llm kernel 的 slots 與 `requests/new|cur`；`proto8/templates/agent-fsm/wait.py` 的 `slow_reason()`；d6a564191 起 stack 裡的 `think/brain_wait.json`；`aos-llm`。
- 現象：
  - ok-kmsg：兩隻 sol 蒐集員 50 分鐘沒有任何產出，`state` 只說 running、history 幾則，看不出那封問腦的信是排在 kernel 的 `requests/new`（名額滿）還是正在跑；最後是部長告知 sol-high 名額只有 2。
  - head-core：部內三條線的 sol（ok-sec 四隻、ok-devt 兩隻、ok-limits 一隻）開工 20～35 分鐘各只走十幾步或零 diff，都在等腦；頂層 13:42 查到 12 個請求在排，使用者 13:43 裁 slots 不放寬。全部收掉改用 Claude 子 agent 後，ok-sec 第 1 期 15 分鐘交件。各線自己沒有辦法查「現在排了幾個」。
  - ok-misc：暫存 llm kernel 用完日額時，5 隻 sol 一起停，每隻只在自己的 stderr 留一行 BudgetMissing；要一隻隻翻 stderr 才知道原因，再找出 kernel.json 在哪個定義夾。
- 建議：
  1. `state` 在 agent-fsm 等腦時多寫一句「waiting for the brain N s (queued at the kernel, position k / running)」。資料 `slow_reason()` 已經會算，現在只在滿 10 分鐘時寫進 stderr；外面的指令可以用 `brain_wait.json`（信名＋kernel 路徑）直接去看 kernel 的 `requests/new|cur`。
  2. `aos-agent ctl ls` 的 REASON 欄直接帶出 BudgetMissing 的 endpoint 和 resets_at；BudgetMissing 的訊息附上預算設定檔的路徑。
  3. `aos-llm` 加一個各線都能跑的唯讀查詢「現在排隊幾個」。
- 痛的程度：拖慢（head-core 原稿寫「會擋工作：今天靠 Claude 額度補位才沒卡」）
- 提出者與日期：ok-kmsg 2026-11-14；head-core 2026-11-14；ok-misc 2026-11-14
- 出處：wf/temp/ok-kmsg/wrapup-1114/建議.md「subagent state 看不出隊員是『在排腦的隊』還是卡住」（引 `proto8/thinking/2026-11/14/ok-kmsg-1114.md` 第四、六節）；wf/temp/head-core/wrapup-1114/建議.md「llm-gpt 的 slots 讓 sol 在部內幾乎不能用」（引 ok-sec 13:38、ok-devt 13:41、ok-limits 13:45 的回報）；wf/temp/ok-misc/wrapup-1114/建議.md 第 2 則（引 `~/code/misc-1114/root/.stack/procs/sol-2/stderr.txt` 尾段、`kern/llm-sol/kernel.json:22`）
- 狀態：未處理。整理時查：`brain_wait.json` 只有 `proto8/cmd/aos-agent/aos_agent/hints.py`（第 57 行，d6a564191 的「kernel 沒在跑」提示）在讀，state、ctl ls 沒用它。head-core 另建議在 aos-teams 短卡補一句「線多時 sol 排隊會慢到不能用」，那是 wf 的派工文件，由頂層定。
- 相關：本檔「llm kernel 沒開時，外人只看到 listen 逾時」（那條的建議 2「ctl ls 的 REASON 標等腦」沒做，跟這條的建議 1、2 是同一個方向）；[fsm範本](fsm範本.md)「sol 讀完必讀後只回一句『我會照做』就結束回合」（隊長分不出「還在做」和「回合已結束」）。

## 掛 proc 的寄信人收到 BudgetMissing 不會晚點再試，錯誤行也沒印 resets_at

- 主題：kernel 與額度
- 哪裡：`lib/agent/subagent/_entry`、`agents_ctl` 等寄信給掛 proc 的 kernel 的工具；`proto8/lib/aos/kernel/hooks.py`（d6a564191 起兩種站的 hook 都能回 BudgetMissing＋`resets_at`）。
- 現象：問腦那邊 agent-fsm 會照 `resets_at` 冷卻重寄；掛 proc 這邊工具只把 error 印出來。hook 作者在掛 proc 的站回「晚點再試」，實際上等於直接拒絕。讀碼發現，沒人實際撞到。
- 建議：工具的錯誤行把 `resets_at` 印出來（「try again after HH:MM」）；要不要自動重試另議。
- 痛的程度：小不便
- 提出者與日期：ok-kmsg 2026-11-14
- 出處：wf/temp/ok-kmsg/wrapup-1114/建議.md「掛 proc 的寄信人收到 BudgetMissing 不會晚點再試」（引 `proto8/lib/aos/kernel/README.md` hook 段，d6a564191 加的說明）。提出者讀碼發現、沒實測；整理時沒另核。
- 狀態：未處理
- 相關：本檔「before_verdict hook 拒信只能回 HookRejected」（已解 d6a564191，問腦那一半）。

## llm kernel 的帳本看不出快取命中率，要自己寫腳本加總

- 主題：kernel 與額度
- 哪裡：llm kernel 的 `ledger.jsonl`；`aos-llm`；知識庫 `aos/brain.json`。
- 現象：命中率只有 29% 這件事，是 ok-fsm 為了別的題目自己寫 Python 加總 `usage.prompt_tokens_details.cached_tokens` 才看到的（1,599 次問腦、1.18 億 token）。在那之前沒有任何地方會顯示，燒額度而沒人知道。
- 建議：`aos-llm` 加一個看帳的子指令（或全景頁加一格）：每個包、每個寄件人的問腦次數、提示 token、命中 token、命中率。至少在知識庫 `aos/brain.json` 寫一句「帳本裡有 cached_tokens，命中率低先查 session id」。
- 痛的程度：拖慢
- 提出者與日期：ok-fsm 2026-11-14
- 出處：wf/temp/ok-fsm/wrapup-1114/建議.md「llm kernel 的帳本看不出快取命中率」（引 `proto8/thinking/2026-11/14/ok-fsm-1114/01-預設工具包-設計稿.md`「另外發現」、commit 7ce38e7cf）
- 狀態：未處理。整理時查：`proto8/knowledge/aos/brain.json` 沒有 `cached_tokens` 字樣；aos-llm 的子指令整理時沒逐一看。
- 相關：本檔「提示快取命中率低：llm kernel 沒送固定的 session id」（已解 7ce38e7cf，命中率低的原因那一半）；本檔「Claude 用量沒有任何 aos 入口能看」。

## kernel_llm 管「寄出請求」的測試在乾淨複本跑不了

- 主題：kernel 與額度
- 哪裡：`proto8/lib/aos/kernel_llm/tests/test_batch8_live.py`。
- 現象：dispatch 寫 request.json 那一步只有這檔的三支 live 測試會走到，它們要編好的執行檔；`git archive` 的乾淨複本沒有，三支固定紅。ok-fsm 改那一行（7ce38e7cf）時，規定要的「乾淨複本全套」驗不到改動本身，只能另外起一棵暫存樹實跑。
- 建議：給 dispatch 補一支不靠執行檔的測試（假的 runner.mount，只驗寫出去的 request.json）；或讓這三支在沒有執行檔時 skip 並印原因，不要算紅。
- 痛的程度：小不便
- 提出者與日期：ok-fsm 2026-11-14
- 出處：wf/temp/ok-fsm/wrapup-1114/建議.md「kernel_llm 管『寄出請求』的測試在乾淨複本跑不了」（引 `~/code/fsm-1114/logs/sx-kernel_llm.txt`、`base-kernel_llm.txt`）
- 狀態：未處理。整理時查：`test_batch8_live.py` 裡沒有 skip 字樣；7ce38e7cf 另加的 `tests/test_session_key.py` 有沒有蓋到 dispatch 寫檔那一步，整理時沒核。

## Claude 用量沒有任何 aos 入口能看

- 主題：kernel 與額度
- 哪裡：llm kernel 與全景頁的 `power`（電力卡）。
- 現象：Claude eca、fable、Argon 的呼叫都不經 llm kernel，aos 看不到最緊的資源。ok-llmk2 量出來，本週主帳號的 Claude 輸出約 60% 在 aos 外（`proto8/thinking/2026-11/14/llmk2-1114/` 的 `06-Claude電表原型.md:9`）。額度剩 5% 時，沒有一個地方能看出是誰燒的；11-14 收線就是因為額度。
- 建議：施工 v1-c，把 Claude 電表做成正式指令並接上電力卡。使用者已裁 q1:b、q2:a：aos 外也列，只顯示、不分配（de7abef5b）。
- 痛的程度：擋路（原稿寫「卡住。今天收線就是因為額度」）
- 提出者與日期：ok-llmk2 2026-11-14
- 出處：wf/temp/ok-llmk2/wrapup-1114/建議.md 第 4 則；commit de7abef5b；原型在 `~/code/llmk2-1114/meter/claude_meter.py`（wf/temp/ok-llmk2/wrapup-1114/交接.md 第 48 行）。60% 這個數字是提出者量的，整理時沒重量。
- 狀態：已排入（ok-llmk2，v1-c；方向題使用者已裁，還沒施工）。
