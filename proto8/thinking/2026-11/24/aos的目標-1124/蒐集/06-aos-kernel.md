# 06 aos kernel：現在是什麼、以前說過什麼、差在哪

蒐集隊員交件，只讀、只蒐集事實與差距。路徑都從 `/home/lorkhan/repo/aos` 起算。
標記：**有程式**＝我讀到程式；**有文件無程式**＝只有說明或規劃；**只在討論**＝只在 thinking／使用者原話。
我沒有跑任何東西，「實測」都是別人 thinking 裡寫的。

## 一、現況

### 1. kernel 是什麼：一套約定加幾支程式，不是一個固定的 agent

- 知識庫定義：kernel＝「資源管理加排程，從寄件的一方看過去」；你把請求送去的那個地方就是你的 kernel，它決定跑不跑、何時跑；什麼都不做也算一種（daemon 叫它啟動什麼就啟動什麼）。`proto8/knowledge/aos/kernel.md:3`（正本英文，中文映照 `proto8/knowledge-zh-md/aos/kernel.md`）。**有文件**。
- 請求可以經好幾站：agent -> kernel_1 -> kernel_2 -> daemon；站與站之間全是 aos-post 的信。同檔「What a kernel is」節。**有文件，且有程式支撐**（下面 3、4）。
- 「任何從信箱拿請求信、並決定怎麼處理的 proc 都是 kernel」。同檔「Writing your own kernel」節。**有文件**。

### 2. 有哪幾種 kernel（讀到的程式）

| 種類 | 程式 | 管什麼 | 狀態 |
|---|---|---|---|
| 通用骨架（每拍一輪：收信、排先後、三個 hook、放行／拒／留隊） | `proto8/py/tools/aos/kernel/round.py:69`（`run`）、`round.py:49`（`ordered`） | 不認得任何請求，規則由「包」給 | 有程式 |
| 掛 proc 的包（白名單、`max_running`、先來先掛的排隊、寄件人期限、份額 `limits`） | `proto8/py/tools/aos/kernel/procs_rules.py`、`queue_fifo.py`、`limits_rule.py` | 啟動／停止 proc 的請求 | 有程式 |
| 問腦的包（llm kernel） | `proto8/py/tools/aos/kernel_llm/`（`llm_rules.py`、`order.py`、`slots.py`、`budget.py`、`ledger.py`、`packs.py`） | 腦呼叫（LLM 端點）的格數、優先序、額度、記帳 | 有程式 |
| 自己跑的零件 | `proto8/py/tools/aos/kernel/runner.py`（`mount` 行 111、`settle` 行 133） | 把一件工作掛成 daemon 的 proc、收成品、逾時、重掛一次 | 有程式，目前只有問腦那包在用（`跨agent資源鎖-kernel-1124/README.md` 「現況」表） |
| 當 kernel 的 agent：`kernel_gate` | `proto8/py/tools/agent/kernel_gate/`；說明 `proto8/knowledge/aos/kernel.md` 「Being a kernel yourself」節 | 規則放行的啟動請求先扣住，agent（腦）逐封 pass／refuse | 有程式 |
| 範本 | `proto8/templates/kernels/`：`daemon-kernel`、`procs-kernel`、`llm-kernel`、`llm-team`、`kernel-python` | 抄了就能起 | 有程式 |

一句話：**kernel 是「一個每拍起一次、做一輪就退出的 Python 行程」（站），加一份定義夾（`kernel.json`、hook 清單）**。它不是常駐的 agent。這是讀 `proto8/py/tools/aos/kernel/README.md` 開頭與 `kernel_llm/docs/01-用法.md` 得來的。只有 `kernel_gate` 是「腦點頭」的版本。

### 3. `AOS_KERNEL` 與 `AOS_LLM_KERNEL` 是兩條路

- `AOS_KERNEL`：啟動、停止、睡、醒的請求送去哪；沒設就直接進 `AOS_DAEMON` 的 ctl 信箱。`proto8/knowledge/aos/kernel.md:25`。權限站是可選、預設關、「給守規矩的 proc 的規則，不是一道牆」。`kernel.md:18`。**有程式、有文件**。
- `AOS_LLM_KERNEL`：腦的請求送去哪。`proto8/knowledge/aos/kernel.md` 「Where to send requests」；agent-fsm 的問腦走這個：`proto8/py/aos/apps/agent_fsm/brain.py:2`。**有程式**。
- 初始 kernel＝最小核心＋llm 件＋權限件，「更多可選部分：還沒決定」。`proto8/knowledge/aos/kernel.md:18` 附近（英文「The initial kernel」節）。**文件寫明待定**。

### 4. 它管哪些資源、用什麼演算法（寫死 vs 可設）

**問腦（llm kernel）**，全部是 `kernel.json` 的旋鈕加程式裡寫死的規則：

- 格數：總格 `slots`、保留給 high 的 `reserved.high`、每包 `slots`、每後端 `backends.<名>.slots` 與 `max_packs`。`proto8/py/tools/aos/kernel_llm/slots.py:1-60`、`kernel_llm/docs/02-token-回報與額度.md` 「一次」第 6 點。**有程式**。
- 排序是寫死的：級數（宣告 level 加「等了幾格除以 `aging_cycles`」）大的先 → 期限近的先 → 同後端黏著 → 包的 `speed` → 等得久的先 → 先寄的先。`proto8/py/tools/aos/kernel_llm/order.py:128-133`、`02-token-回報與額度.md` 「一次」第 5 點。**有程式**。旋鈕只有 `aging_cycles`、`reserved`、`speed` 之類，**排序公式本身不是 agent 或設定檔決定的**。
- 額度：`max_calls`、`max_tokens`，三層（kernel、包、寄件人），窗 hour／day／all，到頂 `refuse` 或 `wait`。`proto8/py/tools/aos/kernel_llm/budget.py:36-53`、`02-token-回報與額度.md` 「token 與額度」節。**有程式**。token 數來自端點函數回信的 `usage`，kernel 不驗（`kernel_llm/docs/04-已知限制.md:3`）。
- 記帳：逐封 `ledger.jsonl`、窗 `used.json`、`queue.json`。`kernel_llm/docs/02-token-回報與額度.md` 「逐封帳」節。**有程式**。
- 不做：搶位（殺在飛的低級信）、信裡寫 `max_cost`／`max_wait_ms`、到頂自動降級。`kernel_llm/docs/04-已知限制.md` 「排程不做的」那條。

**啟動 proc（通用 kernel）**：`max_running`、`queue`（先來先掛）、`allowed`、`limits`（每支新 proc 的份額預設、天花板、照寄件人）、`users`（換身分）。`proto8/py/tools/aos/kernel/README.md` 「kernel.json」表。**有程式**。

**cpu／mem／行程數**：不在 kernel 手上，在 daemon。`limits` 用 rlimit（`mem_mb`、`cpu_s`、`procs`、`file_mb`、`files`），可選 cgroup v2（`mem_total_mb`、`procs_total`）。`proto8/cpp/aos-daemon/docs/09-份額.md`。**有程式**（C++，`cpp/aos-daemon/src/child/cgroup.cpp`、`limits.cpp`）。kernel 只是在轉信時夾值或補預設（`kernel/limits_rule.py:102,130` 的 `limits_clamped`）。

**子 agent 數量**：`max_subagents`，預設 4，寫在 `subagents.json`，由 `subagent` 工具數。`proto8/py/tools/agent/subagent/_entry:25`、`proto8/py/aos/apps/agent/ctl/state.py:218`。**有程式**，但這是工具自己數，不是 kernel 判。

**優先級／權限**：優先級只有問腦那條有（信裡的 `priority.level`）。權限：Linux 檔案權限＋daemon 上限；kernel 權限站是可選規則，不是牆。`proto8/knowledge/aos/kernel.md:18`。

### 5. 誰呼叫它

- agent 的腦呼叫：`aos-llm send/recv/ask` 寄信到 `$AOS_LLM_KERNEL/requests`，kernel 每 300 ms 一拍處理。`跨agent資源鎖-kernel-1124/README.md` 「請求怎麼進出」。
- 啟動／停止：`aos-agent ctl`、`subagent` 工具等，有設 `AOS_KERNEL` 就經它。`proto8/knowledge-zh-md/aos/kernel.md`「透過 kernel 讀表」節。
- 呼叫者是誰，kernel 不驗（信封 `sender` 是自報）。`kernel_llm/docs/04-已知限制.md`「寄信的人是誰 kernel 不驗」。

### 6. 「自行設計 kernel」現在做到哪

讀到七種形式，今天有五種有程式（比 11-19 htop 線寫的多一種）：

1. kernel.json 旋鈕：有程式（上面第 4 點）。
2. hook：有程式。三個時機 `before_verdict`、`after_verdict`、`before_reply`，handler 是任何程式；可改 body（含 priority）、改判決（pass／refuse／hold）、指定單封的下一站。`proto8/py/tools/aos/kernel/README.md` 「hooks」「分流」節。11-21 起 hook 清單改由 `interfaces.json` 的 `hookeds` 指（舊的 `kernel.json` 裡 `hooks` 鍵不報錯但不跑）。
3. 另寫一包交給骨架：有程式（`kernel_llm` 就是這樣寫的）。
4. 當 kernel 的 agent：有程式（`kernel_gate`，只管啟動類請求的 hold）。
5. `kernel.py` 編譯成定義夾：**有程式**，`proto8/templates/kernels/kernel-python/README.md`、入口 `proto8/py/aos/py/kernel/`（`from aos.py.kernel import defs`，commit `9bc49aeba`，11-21）。但範本出廠只是「全部轉下去、什麼都不管」（`README.md` 第 1 行）。
6. 前面串一站策略站：有程式（`llm-team` 就是這個形狀）。
7. 策略 proc 算表、kernel 查表：**半有**，查表那半就是 `budget.senders`，只能放上限（`aos-htop-1119/03-自訂kernel-形式與最小實測.md`）。

### 7. 「kernel 嵌套堆疊」現在做到哪

- **有程式、有測試**：問腦 kernel 可以串。轉交型 kernel＝端點函數換成 `llm_forward` 的普通 llm kernel；上層把期限、級數往下帶，下層把子帳位置（`child`）往上帶一層。程式 `proto8/py/tools/aos/llm_forward/`、範本 `proto8/templates/kernels/llm-team/`、測試 `proto8/py/tools/aos/kernel_llm/tests/test_nesting.py`、`test_nesting_live.py`。設計全文 `proto8/thinking/2026-11/07/kernel-nest/README.md`（結論節）。
- **有程式**：啟動類請求的 kernel 也能串（`next`、`after_verdict` 指單封下一站）。`proto8/py/tools/aos/kernel/README.md`「分流」節；`proto8/templates/kernels/tests/kernel-chain-check`。
- 帳：各層都記，加總只加一層（葉子行）。`kernel_llm/docs/02-token-回報與額度.md` 「逐封帳」節末。
- 沒做／限制：同一台本機模型（LM Studio）的包必須放在同一台 kernel，互斥不跨 kernel（`04-已知限制.md` 最後兩條）。

### 8. 「由 agent 決定排程」做到哪

- **只有 `kernel_gate` 是 agent 在決定**，而且只決定「啟動請求放不放」，不是問腦排程。腦逐封點頭，agent 長回合時整站停，底下所有 agent 讀信、寄信會 `KernelFailed`（`proto8/knowledge/aos/kernel.md` 「When the kernel is slow or busy」節）。
- 問腦排程**沒有 agent 版**。`aos-kres-1120/README.md` 結論 4：問腦總機不是 agent、不能扣信等人點頭；agent 要管問腦請求時，自己的問腦信會排進自己的隊而卡住（雞生蛋）。
- 11-19 線實測：用兩支 hook 就能做到「耦合度高，planner 的信改 high」；寫的是假數字、假腦，`signals.json` 手寫（`aos-htop-1119/03-自訂kernel-形式與最小實測.md` 「最小實測」節）。這是 repo 外複本上的實驗，**不是進了 repo 的功能**。

### 9. 把 token、可理解性、耦合度當資源：做到哪

- token 用量：**有程式**（額度、記帳，見第 4 點）。
- 金額、已快取、掌控度（多久沒看）、耦合度、人類可理解性：**只在討論**。我在 `proto8/py/tools/aos/kernel*`、`kernel_llm` 沒找到任何程式讀這些。（grep 耦合／kernel 目錄無命中。）
- 資源基底（請求帶一塊 json 宣稱成本、kernel 粗化／細化、記帳）：原型在 repo 外，接成 hook 試跑過（`aos-kres-1120/09-接成hook試跑.md`）；**沒進 repo 的功能**。

## 二、以前說過什麼

### 使用者原話

1. 2026-11-06（`wf/user/advice/20261106.md` 約第 32-35 行）：
   > 而在此之上，我先規劃了aos kernel，這是aos的核心，其回歸本質，以幫助人類更好的使用硬體爲目標。
   > linux等普通作業系統，其優化目標以時間，資源消耗最小化爲主。但在agent時代，還有其他目標如token用量，人類可理解性，易操作性等等。所以aos系統的目標就是優化任意目標。
   > ps.aos kernel被設計爲一號行程，但實際上，我們在aos體系中標明，任何管理行程與資源的行程，都可以用kernel做稱呼，只是說標準實作上我們提供的kernel通常都是一號行程，占有對於某個daemon的唯一控制權。
2. 2026-11-13 夜（`wf/user/advice/20261113.md` 第 1 段）：
   > aos的全名，就是akatosh operating system，這個操作系統很特別，他並非基於硬體，而是基於任意資源。……只要最後能夠影響到linux proc/aos proc就算，甚至沒有影響也可以。
   > 比如一個資源cost，他的表示可能是cost:{token:10,time:1s}，要粗化，那就是cost:7，這可能是透過某種公式轉的……
   > 下一步，aos既然能處理很多東西，那我們的目標就可以稍微廣泛一些，首先是人類的可理解性這類，就可以透過aos kernel來優化了。
   > 端點同時間也只能處理十幾個請求，想必也只有aos這套能夠最好的處理上千上萬個agent(共享一個端點)。
3. 2026-11-15（`wf/user/advice/20261115.md` 第 21-47 行）：
   > 允許在僅有少數endpoint的情況下，同時運行千萬個agent。並且可以奇跡般地高度自定endpoint使用排程。 ps.尚未實測，並且這建立在大部份agent處於待命狀態的情況下。
   > 一個經典的例子是資源分配，也就是讓kerenl用你的奇妙需求去排程。讓agent成爲你的kernel，就是如此。
   > 而kernel，就是管理素材的核心。
4. 2026-11-19 下午（`proto8/thinking/2026-11/19/aos-htop-1119/00-使用者原話.md`）：
   > 現有的htop他就是看cpu/mem/網路這樣，但是在aos體系下，我們還要考慮各種資源，包括token、已快取、金額、使用者掌控度(你多久沒有實際看)、程式碼耦合度...
   > 好比程式碼耦合度，kernel自己會控管，當耦合度過高時，kernel會傾向讓負責規劃的agent的行動優先級提高這樣。
   > 並且記什麼、怎麼分配，都必須是完全可以自訂的，也就是大家都可以自訂kernel
5. 2026-11-20（`proto8/thinking/2026-11/20/aos-kres-1120/08-使用者已答.md`、`wf/progress.json` 的 aos-kres 條）：給位置和格式、「當然，這都是可選的，kernel自己可以選擇不給」；「誰判」先不定；第 5 題「先不定。但是可以先做寄信問kernel……算是基礎協議吧」。（引自 progress.json 摘要，我沒逐字重讀 08。）
6. 2026-11-24 晚（`wf/user/advice/20261124.md:56-66`，即本題的原話）：
   > 假設以後有上千個 agent 在跑，他們需要爭搶有限的資源：從基礎的 cpu/mem，到權限/優先級、少量的 LLM 端點等。
   > 所以 aos 提供了一個很酷的東西：允許自行設計 kernel，從資源到排程，並且允許 kernel 嵌套堆疊。
   > 而 aos kernel 則將 Linux 視作底層硬體，並將各種抽象的東西視作間接硬體，去管理／排程各種五花八門的東西：從 token 用量到人類可理解性，再到更專業更細分的程式碼耦合度等。
7. 2026-11-24（`wf/progress.json:558`）：「跨agent的資源鎖這塊，可以往kernel那邊想想。」

### 以前有人替他答過／他答過的選項框（11-19，`aos-htop-1119/README.md` 「使用者已答」）

- 優先管多深：「先不定」。
- 自訂 kernel 先走哪條：「先不定，讓它自然長」。
- 認人：「照舊自報，風險自擔」。
- 耦合度量哪份程式碼：「由量的人自訂」。

結論：「token 用量、人類可理解性、耦合度當資源」**以前不只提過，11-06、11-13、11-19 各講過一次**，11-19 還有整條線做了發想與實測。

### 其他討論

- `proto8/thinking/2026-11/07/kernel-nest/README.md`：嵌套的設計（已做完，見現況 7）。
- `proto8/thinking/2026-11/24/跨agent資源鎖-kernel-1124/README.md`（11-24 最近的討論，必讀項）：
  - 起因：arena_cheater 的工具自己 flock 全機一份 Node，等鎖上限寫死 180 秒，逾時重試。
  - 結論四句：零件幾乎都在；arena 重試不是 aos 造成的；kernel 能多給「有先後的隊、看得到誰在用誰在等、持有者死了格子自己回來、等的人可以不卡著」四樣；推薦「代跑式」（請求＝跑登記過的工作，格子的生死＝那支 proc 的生死）。
  - 四種「往 kernel 想」：甲代跑式、乙發牌式、丙現成掛 proc 站、丁只出工具（`aos-lock`）。
  - 五題等使用者答，進度 `wf/progress.json:558` 寫「③ 發想 28ddf25d3 五題等使用者」。**我沒找到使用者對這五題的答案。**
  - 它也引了先前定案：隔離等級「甲，先只防失誤」；六題第 ③ 題「只做回報那半，鎖／排隊等准入先不做」。
- `proto8/thinking/2026-11/20/aos-kres-1120/`：資源基底九個零件、粗化／細化、排程介面。
- `proto8/thinking/2026-11/21/kernel-攔截daemon存取-1121/`：使用者給原則「只防走規矩的存取」（`wf/progress.json:419` 附近摘要）。
- `proto8/thinking/2026-11/20/aos-init-kernel-1120/`：初始 kernel 切法。
- 使用者 09-19 時代的說法：「aos-kernel要去分配cpu, 管理正在跑的程式」（`wf/user/advice/2026-09/2026-09-19.md:66`）。

### wf/advices 的 llm-kernel 回饋（commit 6e4f82bfb 收進）

- `wf/advices/feedback/llm-kernel.jsonl`（一筆，11-24 11:25）：luna/terra/sol/astra 都標 `cost=high`，只有 astra 的 summary 有相對價格，要「最便宜的端點」只能照名字猜；建議每個端點分級或在 summary 寫相對價錢。
- `wf/advices/feedback/llm.jsonl`（一筆，同時）：範本 `kernel.json` 11-24 把 `slots` 2 改 4，但在跑的 kernel 還是 2、沒重載；建議範本改動時註明在跑的 kernel 何時拿到。
- 兩筆都來自別棵樹（moddings/skyrim 的 fsm-gpt 報告）。
- 另兩份 advices（`01-daemon信件kernel安全.md`、`02-範本工具知識庫.md`）我沒讀。

## 三、差距（使用者說的 vs 現在有的）

每條附證據。只列事實，不給方案。

1. **「agent 自己設計並進行排程」**。現在問腦的排序公式寫死在 `kernel_llm/order.py:128-170`；agent 只能改旋鈕或掛 hook。agent 當 kernel 只有 `kernel_gate`，管啟動請求、逐封點頭（`kernel.md` gate 節）。問腦那條沒有 agent 版，且有「雞生蛋」（`aos-kres-1120/README.md` 結論 4）。**kernel 是 agent** 的說法目前只有半條路。
2. **「從資源到排程自行設計」**。形式上有（hook、另寫一包、`kernel.py`）。差在：`kernel.py` 範本只是「全轉下去」；沒有一個把「誰先」做成可插規則的口給 hook 用。`order` 在 hook 之前跑完，hook 改的 priority 這輪不影響排位（`aos-kres-1120/README.md` 結論 7，**看程式推的、沒實跑**）。
3. **「kernel 嵌套堆疊」**。問腦鏈與啟動鏈都有。差在：兩種 kernel 的串法各自一套（`llm_forward` vs `next`），沒有統一的「kernel 疊 kernel」概念；本機模型互斥不跨 kernel（`04-已知限制.md` 末兩條）。
4. **「把任意東西視作資源」**。實際管的只有：問腦格數與額度、啟動 proc 的 running 數與份額。cpu／mem 在 daemon 的 rlimit／cgroup，不在 kernel。資源基底（成本宣稱、粗化／細化）只有 repo 外的原型與一次 hook 試跑（`aos-kres-1120/09`）。沒有「資源」的共同資料格式進到程式。
5. **token 用量**：有，但靠端點函數照實寫 `usage`，kernel 不驗（`04-已知限制.md:3`），額度事後才知道（同檔第 2 條）。
6. **人類可理解性、程式碼耦合度、掌控度**：程式裡沒有；只有 11-19 的假數字實驗與 `04-全域指標-耦合度與掌控度.md` 的量法討論（我只讀了 README 的摘要）。
7. **cpu／mem 的跨 agent 搶用**：daemon 有每 proc 的 rlimit／可選 cgroup（`09-份額.md`），但「千個 agent 爭搶」的 admission 是 `max_running` 先來先掛、沒有優先級。優先級只在問腦那條。
8. **權限／優先級當成要搶的資源**：權限是 Linux＋daemon 上限；kernel 權限站可選、預設關、不是牆（`kernel.md:18`）。11-24 使用者說「權限這塊可以先記錄下來，之後可以來做」（`wf/progress.json:558`）。
9. **跨 agent 資源鎖**：零件有、沒接成；`aos-lock` 沒先後、死了不回收（`跨agent資源鎖-kernel-1124/README.md` 「現況」表）。**使用者尚未答五題**（我沒找到答案）。
10. **「以後有上千個 agent」**：使用者 11-15 自己寫「尚未實測，並且這建立在大部份agent處於待命狀態的情況下」。我沒找到上千 agent 的實測。11-24 的閒置輪詢 C++ 重寫（`proto8/thinking/2026-11/24/閒置輪詢C++重寫-1124/`）是在降待命成本，我只讀了名字與 progress 摘要。

## 四、已知的缺點與沒解的問題

都有文件出處；**讀到的**除非標「推測」。

- **kernel 不驗寄件人**：信封 `sender` 自報，寫得到信箱就能冒用別人的額度；使用者 11-19 選「照舊自報，風險自擔」。`kernel_llm/docs/04-已知限制.md`、`aos-htop-1119/README.md`。
- **權限站不是牆**：寄件者丟掉 `AOS_KERNEL` 直接寄給 daemon 就繞過。`kernel.md:18`。
- **在飛的錢收不回**：不搶位；HTTP 一砍錢已花。`04-已知限制.md`「排程不做的」。
- **kernel 站慢、忙會連坐**：`kernel_gate` 的 agent 長回合時整站停，底下的 `who`／信箱／時鐘呼叫 3 秒後 `KernelFailed`。`kernel.md`「When the kernel is slow or busy」節。
- **hook 一壞整輪停**：預設連坐，沒有「只 warning」選項（`kernel/README.md` hooks 節末）；每封多起一個行程；只有三個每封信的時機，沒有「每輪一次」。`aos-htop-1119/03`。
- **優先級只有擠才有用**：格沒滿 high 與 normal 一樣立刻跑；等久的 normal 約 3 秒就追上（`aging_cycles` 預設 3）。`aos-htop-1119/03`、`04-已知限制.md` 末段 `speed` 條。
- **「讓規劃者優先」有五種意思**，只有問腦先後今天有旋鈕；喚醒先後沒有任何 kernel 管。`aos-htop-1119/README.md`。
- **eca-claude（Claude Code 當腦）的花費不經過 llm kernel**，今天花最多的正是它們，kernel 管不到。`aos-htop-1119/README.md` 「最大的盲點」。
- **記錄型 hook 天生看得到整份 prompt**，寫磁碟有放大、對話內容留在 kernel stack。`aos-htop-1119/03`。
- **額度窗靠牆上時鐘**，時鐘撥動會多給或晚換窗。`04-已知限制.md`。
- **睡醒、kill -9 可能多花一次腦**。同檔。
- **共用信箱看得到別人的信**。同檔。
- **跨台 kernel 不互斥**（兩台放同一 LM Studio）。同檔。
- **範本改了、在跑的 kernel 不會自己重載**（回饋意見，`wf/advices/feedback/llm.jsonl`；我沒驗是否屬實）。
- **kernel 之間成本比較沒有結構**：回饋意見指出端點 `cost` 全是 `high`，要選最便宜只能猜名字（`llm-kernel.jsonl`）。
- **自訂 kernel 的「宣告」缺**：記了什麼、欄位單位，沒有慣例；`interfaces.json` 只說「哪個檔」。`aos-htop-1119/03` 卡點表。
- **資源鎖那條的邊緣**：非同步等待、持有者死亡、多資源互等、一拍 300 ms 的顆粒，都攤在 `跨agent資源鎖-kernel-1124/README.md` 「邊緣狀況」14 條，等使用者選方向。
- **觀察（我的，不是文件）**：使用者 11-24 說「agent 可以自己設計 kernel」，現在 repo 裡 agent 能碰的 kernel 只有 hook 與 `kernel_gate`；用到「問腦排序」那層時 agent 要自己寫 Python 包。這一點是我比對得出，沒有文件這樣寫。

## 我沒把握的地方

- 「`order` 在 hook 前跑，hook 改的 priority 這輪不算」是別人看程式推的，我沒重驗。
- 嵌套的測試我只確認檔案存在，沒讀內容、沒跑。
- 使用者是否已答跨 agent 資源鎖五題：只查了 `wf/progress.json` 與 `wf/user/待答-1122.md`，沒查最新 HANDOFF 或信箱；寫「沒找到」。
- `proto8/thinking/2026-11/19/aos-htop-1119/04`、`05` 與 `aos-kres-1120/03-07` 只讀了摘要，未全讀。
