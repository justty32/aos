結論：現有 `limits` 已有「每支 proc 的份額、預設值、天花板」，但 rlimit 不會從父層總額扣帳；「父層圈住全部子孫、子層再細分」出現在 cgroup 計畫。LiteLLM 設定找到在 `/home/lorkhan/repo/llm_proxy/`，未找到部門預算、金額上限、RPM／TPM 或花費記帳設定；訂閱週額度也沒有可直接換算成 token／美元的確定數字。

以下 repo 相對路徑均以 `/home/lorkhan/repo/aos/` 為根。本次只讀檔，未呼叫模型、未操作 daemon、未修改檔案。

## A. CPU／記憶體資源限制

### 1. 欄位與限制範圍

| 欄位 | 意義與範圍 | 出處 |
|---|---|---|
| `mem_mb` | `RLIMIT_AS`＋`RLIMIT_DATA`；每個行程的虛擬位址／資料空間，不是整樹 RSS；不設定 `RLIMIT_STACK` | `proto8/impls/aos-daemon/docs/09-份額.md:14` |
| `cpu_s` | `RLIMIT_CPU`；單一行程的 CPU 秒，fork 子行程重新起算，不是整隻 agent 累計 CPU，也不是 CPU 使用率 | `proto8/impls/aos-daemon/docs/09-份額.md:31` |
| `procs` | `RLIMIT_NPROC`；同一 uid 的全部行程，不只是該 proc；不換 user 時會警告但仍套用 | `proto8/impls/aos-daemon/docs/09-份額.md:23` |
| `file_mb` | `RLIMIT_FSIZE`；單檔大小，不是工作區或全部檔案總量 | `proto8/impls/aos-daemon/docs/09-份額.md:32` |
| `files` | `RLIMIT_NOFILE`；開啟 fd 的限制，鍵不是 `nofile` | `proto8/impls/aos-daemon/docs/09-份額.md:14`、`wf/workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md:40` |
| `user` | 身分切換欄位，不是數值份額；現行 daemon 文件寫本機帳號名 | `proto8/impls/aos-daemon/docs/09-份額.md:14` |
| `mem_total_mb` | B5 計畫新增；整個 cgroup、連同子孫的記憶體限制，設定 `memory.max` 並將 `memory.swap.max` 設 0 | `proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:62`、`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:75` |
| `procs_total` | B5 計畫新增；以 `pids.max` 限制整格行程／執行緒總數，不依 uid 計數 | `proto8/thinking/2026-11/13/kernel-limits-plan/07-cgroup可選.md:30`、`proto8/impls/aos-daemon/docs/09-份額.md:34` |

五個 rlimit 數值鍵均為正整數。daemon 在 fork 的子行程內直接呼叫系統呼叫，不是真的 exec s6；後續身體與其子行程繼承限制。出處：`proto8/impls/aos-daemon/docs/09-份額.md:14`、`proto8/impls/aos-daemon/docs/09-份額.md:17`。

### 2. 預設值從哪來；`{}` 的意思

- **daemon 預設**來自 `daemon.json` 頂層 `limits`；沒寫代表 daemon 不額外施加限制。列上的 `limits` 沒寫、`null` 或 `{}` 都用 daemon 預設。出處：`proto8/impls/aos-daemon/docs/09-份額.md:13`。
- **列上非空 `limits` 整份取代預設的數字鍵**，不是逐鍵合併。例如只寫 `files`，預設裡其他數字限制會消失；唯一例外是預設 `user`，列沒寫時會補上。這是使用者 11-14 選 a 的裁定。出處：`proto8/impls/aos-daemon/docs/09-份額.md:15`、`proto8/thinking/2026-11/14/kernel-limits-1114.md:227`。
- **kernel 站另有一層預設**：先取 `limits.default`，再讓完全相等的 `limits.by_sender[sender]` 逐鍵覆蓋；請求已有非空數字 limits 時，不與這份預設合併。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B1-limits-rule.md:80`。
- kernel 規則開啟時，請求 `{}` 也是「用預設」；最後沒有任何限制可加，就刪掉請求的 `limits` 鍵，交由 daemon 預設處理。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B1-limits-rule.md:83`。
- **操作慣例，不是全域內建常數**：07 文件記 sol 預設帶 `{"mem_mb":1024,"files":256}`；eca 不設 rlimit、請其自行收斂，agent-fsm 可以設。出處：`wf/workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md:40`。

注意：B1 背景仍留著舊句「`limits:{}`＝不限」，已被 B4 與後續現行文件改成「用預設」，不能拿舊句當現行契約。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B1-limits-rule.md:19`、`proto8/thinking/2026-11/14/kernel-limits-1114/B4-daemon-tighten.md:23`。

### 3. 天花板怎麼定

- **daemon `limits_max` 是設定者寫入的數字物件**；未見自動按 RAM／CPU 推算天花板的規則。`null`／空物件代表不封頂，不接受 `user`。頂層 `limits` 必須包含每個封頂鍵，而且預設值不得超過 max，否則整台 daemon `CfgBad` 不起。出處：`proto8/impls/aos-daemon/docs/09-份額.md:16`。
- 啟動某列時，超過 max，或漏掉被封頂鍵而被視為不限，都只讓該列 `LimitBad`、留 `stopped`＋reason；其他列照跑。**daemon 拒絕，不夾值**。出處：`proto8/impls/aos-daemon/docs/09-份額.md:16`。
- **kernel `limits.max` 則會夾值**：超過改成 max，缺鍵也補成 max，記入 `limits_clamped`。所以 default／by_sender 是預設，真正防取消要靠 max。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B1-limits-rule.md:81`。
- 另受 **daemon 自己繼承的 Linux hard limit** 約束；請求比它寬會在父行程預檢時 `LimitBad`。已在跑、被 adopt 接回的列不重驗新天花板，等下次啟動才驗。出處：`proto8/impls/aos-daemon/docs/09-份額.md:19`、`proto8/impls/aos-daemon/docs/09-份額.md:27`。

### 4. 有沒有份額、軟／硬上限、嵌套分配

- **「份額」是文件明用的概念**；原始需求包含 daemon/kernel 自己受限，再給 proc 分配份額。出處：`proto8/impls/aos-daemon/docs/09-份額.md:5`。
- **rlimit 有 soft／hard**：通常兩者等於設定值；`cpu_s` 特例為 soft＝N、hard＝N＋1 秒，以先收到 SIGXCPU；若父 daemon hard 只容得下 N，hard 退回 N。這不是保底份額或可借用額度。出處：`proto8/impls/aos-daemon/docs/09-份額.md:14`。
- **rlimit 只有繼承天花板，沒有父池扣帳**：三列各 `mem_mb:1024`，總和可以超過 daemon 自己的 1024；子 daemon 往下只能維持或收緊繼承的 hard。出處：`proto8/impls/aos-daemon/docs/09-份額.md:26`、`proto8/impls/aos-daemon/docs/09-份額.md:36`。
- **cgroup 計畫明確寫嵌套**：子 daemon 位於父給的格內，自己開 `auto` 就再往下分；子層 `off` 則整串共吃父格總量。父格上限約束整串子孫。出處：`proto8/thinking/2026-11/13/kernel-limits-plan/07-cgroup可選.md:19`、`proto8/thinking/2026-11/13/kernel-limits-plan/07-cgroup可選.md:34`。
- **未找到自動按比例分池、子額度加總檢查、保底份額或借用／歸還機制**；B5 使用 `memory.max`／`pids.max`，沒有列 `memory.high`／`memory.low` 或權重式分配，且明列不做 `cpu.max`。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:75`、`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:177`。

### 5. `limit_hit`／`limit_suspect`

- `limit_hit:"cpu_s"`：直接子行程以 SIGXCPU 結束，且有設 `cpu_s`；`"file_mb"` 同理看 SIGXFSZ。包 shell 沒用 exec，或程式攔截訊號，都可能看不到。出處：`proto8/impls/aos-daemon/docs/09-份額.md:21`。
- `limit_suspect:"mem_mb"`：直接子行程正常退 1，而且有設 `mem_mb`；**只是猜，不證明記憶體耗盡**。adopt 的 running proc 沒有 wait status，不推測。出處：`proto8/impls/aos-daemon/docs/09-份額.md:22`。
- B5 計畫增加：`memory.events` 的 `oom_kill>0` → `"mem"`；`pids.events` 的 `max>0` → `"procs"`。優先判 cpu／file，再 mem，再 procs；有 hit 就清 suspect。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:224`。
- 這些不是完整歷史帳：B5 明定只保留在仍在表上的列；主行程退 0 的列照舊移除，結束 log 不增加這兩欄。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:279`。

### 6. B5 的分層與狀態

- **分層**：systemd 委派的 `base` 下，daemon 自己進 `base/daemon/`，工作進 `base/procs/<名>/`；必須在 base 與 procs 逐層啟用 memory／pids 控制器。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:21`、`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:40`。
- **開關**：預設 `off` 完全不碰 cgroup；`auto` 探測失敗警告降級；`on` 失敗則 `CfgBad` 不起。關閉／降級卻指定總量鍵時，照起但警告並列 `limits_ignored`。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:34`、`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:48`、`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:83`。
- **收尾**：既有停機路徑不改，補 cgroup.kill 收整格；判斷是否仍有子孫用 `cgroup.events/populated`。每次 launch 重建格子，讓事件計數歸零。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:101`、`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:216`。
- **這輪不做**：自動 `launch.json.wrap`、`cpu.max`、kernel B1 default／max 接受兩個總量鍵、aos-sandbox 接受兩個總量鍵。要委派由起樹者自行包 systemd-run。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:174`。
- **安全邊界**：還沒接 subuid 前，同 uid proc 可改自己的 cgroupfs；B5 防失控，不防同 uid 故意改限制。出處：`proto8/thinking/2026-11/14/kernel-limits-1114/B5-daemon-cgroup.md:260`。
- **已完成與計畫要分開**：紀錄明寫 B4 已 commit `f662b9a17`、binary／knowledge 待換樹；B5 仍見施工與測試更正，未找到完工交件紀錄。notes 亦記 sol-4 正在做 B5。出處：`proto8/thinking/2026-11/14/kernel-limits-1114.md:283`、`wf/temp/ok-limits/notes/naming.md:10`。

指定的 notes 三份都讀了：主要是必讀／安全規矩、命名與工作區、讀規矩查核，未提供另一套資源配額規則。出處：`wf/temp/ok-limits/notes/brief-header.md:1`、`wf/temp/ok-limits/notes/naming.md:1`、`wf/temp/ok-limits/notes/sol-readcheck.md:1`。

## B. 模型、訂閱與花費

### 1. LiteLLM 設定位置及記帳設定

- **主設定**：`/home/lorkhan/repo/llm_proxy/litellm.yaml`，include 五份 `models/{deepseek,ollama,lmstudio,chatgpt,claude}.yaml`。出處：`/home/lorkhan/repo/llm_proxy/litellm.yaml:9`。
- **啟動預設**：啟動腳本預設讀同目錄 litellm.yaml、port 4000、host 127.0.0.1；wf 也指向這個 repo。這證明設定／預設起法，不等於確認目前服務實際載入它。出處：`/home/lorkhan/repo/llm_proxy/start_litellm.sh:17`、`/home/lorkhan/repo/llm_proxy/start_litellm.sh:20`、`wf/workflows/dev-env/01-跨機與外部工具.md:25`。
- **有無憑證欄位**：有 `api_key` 欄位／環境變數引用；Claude 設定註解記 callback 每請求從外部登入憑證讀 token。本次未輸出其值，也未讀 auth.json／credentials 檔內容。出處：`/home/lorkhan/repo/llm_proxy/models/deepseek.yaml:8`、`/home/lorkhan/repo/llm_proxy/models/lmstudio.yaml:7`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:4`。
- **有 callback，但找到的是驗證用途**：主設定掛 Claude auth handler；另設 drop_params、重試 2 次、request timeout 600 秒。出處：`/home/lorkhan/repo/llm_proxy/litellm.yaml:22`、`/home/lorkhan/repo/llm_proxy/litellm.yaml:24`。
- **未找到預算／速率／花費紀錄設定**：主設定與五份 include 未命中金額 budget、RPM／TPM、rate_limit、spend log 或花費資料庫設定。Claude 的 `budget_tokens` 是推理 token 預算，不是金額／部門額度。檢查範圍：`/home/lorkhan/repo/llm_proxy/litellm.yaml:9`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:2`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:12`、`/home/lorkhan/repo/llm_proxy/models/deepseek.yaml:2`、`/home/lorkhan/repo/llm_proxy/models/lmstudio.yaml:2`、`/home/lorkhan/repo/llm_proxy/models/ollama.yaml:2`。

### 2. 設定列出的模型

以下是設定名單，未連 `/v1/models` 驗證目前可用性。

| 類別 | 基礎名稱／別名與變體 | 出處 |
|---|---|---|
| ChatGPT | `chatgpt-gpt-6-astra`、`chatgpt-gpt-6-sol`、`chatgpt-gpt-6-luna`、`chatgpt-gpt-5.6-terra` | `/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:21`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:48`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:56`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:64` |
| ChatGPT | `chatgpt-gpt-6.1-sol`、`chatgpt-gpt-6.1-terra`、`chatgpt-gpt-reserve`、`chatgpt-codex-auto-review` | `/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:73`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:80`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:88`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:96` |
| ChatGPT 別名 | `chatgpt-gpt-astra`→6-astra、`chatgpt-gpt-sol`→6.1-sol、`chatgpt-gpt-luna`→6-luna、`chatgpt-gpt-terra`→6.1-terra | `/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:106`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:112`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:119`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:127` |
| ChatGPT 變體 | 各族有 low／medium／high／xhigh／max；非 astra 族另有 nothink；astra 未列 nothink | `/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:39`、`/home/lorkhan/repo/llm_proxy/models/chatgpt.yaml:49` |
| Claude | `claude-opus-5-5`、`claude-sonnet-5`、`claude-fable-5-1`、`claude-fable-5` | `/home/lorkhan/repo/llm_proxy/models/claude.yaml:18`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:39`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:47`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:54` |
| Claude 舊版 | `claude-opus-4-8`、`claude-opus-4-7`、`claude-opus-4-6`、`claude-sonnet-4-6`、`claude-opus-4.5`、`claude-sonnet-4.5`、`claude-haiku-4.5` | `/home/lorkhan/repo/llm_proxy/models/claude.yaml:61`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:69`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:78`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:87`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:95`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:110`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:117` |
| Claude 別名／變體 | `claude-opus`→5-5、`claude-sonnet`→5、`claude-fable`→5-1、`claude-haiku`→4.5；有推理強度後綴，但各族支援不完全一致 | `/home/lorkhan/repo/llm_proxy/models/claude.yaml:125`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:131`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:138`、`/home/lorkhan/repo/llm_proxy/models/claude.yaml:144` |
| DeepSeek | `deepseek-chat`、`deepseek-reasoner`、`deepseek-v4-pro` | `/home/lorkhan/repo/llm_proxy/models/deepseek.yaml:5`、`/home/lorkhan/repo/llm_proxy/models/deepseek.yaml:19`、`/home/lorkhan/repo/llm_proxy/models/deepseek.yaml:29` |
| LM Studio | `lm-gemma-4-12b`、`lm-gemma-4-e4b`、`lm-qwen3.5-9b`，三者各有 nothink | `/home/lorkhan/repo/llm_proxy/models/lmstudio.yaml:6`、`/home/lorkhan/repo/llm_proxy/models/lmstudio.yaml:21`、`/home/lorkhan/repo/llm_proxy/models/lmstudio.yaml:29`、`/home/lorkhan/repo/llm_proxy/models/lmstudio.yaml:42` |
| Ollama | `ollama-qwen3-32b`、`ollama-qwen2.5-14b`、`ollama-deepseek-r1-8b`、`ollama-gemma3-1b` | `/home/lorkhan/repo/llm_proxy/models/ollama.yaml:6`、`/home/lorkhan/repo/llm_proxy/models/ollama.yaml:21`、`/home/lorkhan/repo/llm_proxy/models/ollama.yaml:29`、`/home/lorkhan/repo/llm_proxy/models/ollama.yaml:39` |

模型列在設定裡不代表准用；wf 另明定不用 `lm-*`／`ollama-*`，本次也未呼叫它們。出處：`wf/workflows/dev-env/02-模型端點.md:10`、`wf/workflows/dev-env/02-模型端點.md:12`。

### 3. 已知訂閱、週額度與相對價格說法

- **方案記錄**：plans 寫 Claude、GPT 各一個 200 美元方案；user/01 另寫 codex 200 美金方案可多用以省 Claude token。這是 wf 記錄，未查帳單確認現況。出處：`wf/workflows/team-model/plans.md:5`、`wf/workflows/common/user/01-說話授權與記憶.md:37`。
- **Claude 確有週上限的歷史紀錄**：11-07 信件記帳號撞週上限、當日 16:00 Asia/Taipei 重置；不能由此推定每週固定重置時間。出處：`wf/inbox/done/20261107T1600-aos-b0-PROGRESS.md:14`。
- **額度緊時的現行規矩**：主帳號改用 `.claude-alt` 帳號接手；99% 時各線暫停但不結束、寫 HANDOFF。出處：`wf/workflows/common/user/01-說話授權與記憶.md:43`。
- **Claude 週額度沒有確定換算**：封存待裁曾問「一週額度 10% 換多少」，列 `$10`／token／只算 aos 等選項；另記總量仍需使用者給。這不是已定價目，也不是現行部門預算。出處：`wf/workflows/common/archive/wait-user-2026-10-12/company-market.md:8`、`wf/workflows/common/archive/wait-user-2026-10-12/company-market.md:31`。
- **astra 約 sol 三倍**：使用者 11-06 原話稱 sol 一般工作相近、價格僅 astra 的 1/3；分級表照此記。屬已知相對價格說法，未找到對應美元/token 單價。出處：`wf/workflows/team-model/grades.md:26`、`wf/workflows/team-model/grades.md:45`。
- **其他相對消耗分級**：Claude 消耗約隨聰明度增加；GPT 整體下移兩級，sol 是 A 級能力／C 級消耗。這是使用者定的定性分級，不是可直接計費的倍率。出處：`wf/workflows/team-model/grades.md:36`、`wf/workflows/team-model/grades.md:43`。
- **fable 貴的操作證據**：使用者要求其只做頂層規劃、吃準備好的材料；改成 opus 蒐集匯總、fable 一次性規劃後，稱額度消耗大降。出處：`wf/workflows/dispatch/aos-teams/03-使用者原話.md:24`、`wf/workflows/dispatch/aos-teams/03-使用者原話.md:34`。
- **ChatGPT 訂閱沒有可算美元的價目**：11-07 報告明記 LiteLLM 沒有這些 chatgpt 模型價目，能用 token（in／out／cached）、calls、秒。另有「額度無上限／不用省」的使用授權文字，但不能解讀成供應商技術上沒有 quota。出處：`wf/workflows/refactor/reports/2026-11-07-arknights-kb/08-第二輪簡報.md:92`、`wf/workflows/dev-env/02-模型端點.md:8`。
- **resources.md 管機器，不管模型帳**：重運算用 nice 19、80% 是上限不是目標、並行 build 最多兩個；未在此找到 LLM 部門額度。出處：`wf/workflows/resources.md:49`、`wf/workflows/resources.md:58`。

## 沒找到／不確定

- 未找到 Claude／ChatGPT「目前剩餘週額度」、可靠的 token／美元換算，或按模型分開的訂閱扣額公式。
- 未找到 LiteLLM 設定中的部門 budget、金額封頂、RPM／TPM 或 spend log；這不證明套件預設或執行時沒有其他記錄。
- 未連線確認 port 4000 的服務、實際啟動參數與目前模型名單；以上是檔案設定，不是服務探測結果。
- B4 有已 commit 紀錄，但未驗證活樹已換上；B5 找到圖紙與施工紀錄，未找到完工／部署證據。
- 未找到自動把父額度按比例分給子層、預留／歸還、超賣檢查，或應用層「軟額度警告／硬額度拒絕」兩階段制度；rlimit soft／hard 不等同這種預算制度。
- 未讀任何登入憑證內容，無法確認其中實際 token 是否存在、有效或過期。

必讀實讀：已先讀 aos `_description.json` 並查看知識庫 index，再讀 `AGENTS.md`、`common/user.md`、`dispatch/aos-teams.md` 與其 06、07；六份均已讀。