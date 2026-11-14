# 預設流程（11-13 晚）：opus 帶隊、sonnet 搜集、fable 規劃、實作的 gpt 走 aos 的 agent-fsm

← [入口](../aos-teams.md)｜涵蓋：預設流程、正統規劃流程、實作誰做、gpt 系改走 agent-fsm、家機的 gpt 端點、待補｜上一份 [06-公司WSL活樹與任務書硬規則](06-公司WSL活樹與任務書硬規則.md)

## 預設流程

**opus 帶隊 → 指揮 sonnet 搜集訊息 → opus 整理匯總 → fable 規劃與設計架構 → opus 深化細化架構 → 實作。**

- **opus 從頭帶到尾**：寫任務書、派 sonnet 搜集、把搜集來的整理成給 fable 的匯總；fable 交稿後深化細化架構；實作時管輪內架構、權衡、審實作與整個流程。
- **sonnet 搜集**：查找、盤點、跑指令收結果，屬「簡單工作」（界線見[入口「簡單工作」](../aos-teams.md)）。現在給 sonnet；agent-fsm 有雛形之後也可給 gpt 系（簡單 terra、普通 sol）（使用者 11-13 晚「搜集也可以給gpt，只是這可能要等loop fsm有了雛形之後」）。
- **fable 規劃與設計架構**：只做頂層規劃／設計，**只讀 opus 備好的匯總**、不廣讀 repo；fable 可再派 fable 子 agent。這一輪可在輪間、輪中跑，次數不限；實作時 fable 不即時參與。
- **實作照既有分工**（使用者 11-13 晚選 A）：gpt 系優先、照圖紙寫碼，claude（opus 普通、sonnet 簡單）補位；gpt 系不參與設計決策（入口「gpt 系」那條照舊）。**gpt 系改走 aos 體系**：見下節。
- 派出去的 agent 先通讀 wf/ 規矩，並先讀知識庫 `~/aos-home/knowledge/aos/_description.json` 大致掌握 aos 體系；兩者同一套例外，簡單工作與雜活免讀（入口「讀規矩」；使用者 11-13 晚「照預設走」）。

### 正統規劃流程（11-13 23:40 重述）

使用者重述同一條鏈，叫它「正統規劃，架構設計流程」，多了兩處：

**opus 帶隊 → sonnet／gpt 蒐集 → opus 匯總給 fable → fable 設計 → opus 深化細化、出實作計劃 → Argon 審 → opus 依 Argon 改計劃 → 實作由 astra 帶 sol 做。**

- **Argon 審**：opus 初步深化細化之後、交實作之前，送 Argon 跑一次（指令與 (A) 審查 (B) 提案的格式見 [05](05-同機session與Argon.md#argon-是參與者不只審稿)）；opus 逐條寫採納／不採納與理由，改後的計劃才算定稿。
- **實作 astra 帶 sol**：照 [astra-kernel-plan](../../../../proto8/thinking/2026-11/13/astra-kernel-plan.md)（astra 指揮、sol 照圖紙寫碼；在 aos 樹裡跑 agent-fsm 身，接下一節）。這是 gpt 系優先那條的具體隊形；astra 只指揮與驗收、不改圖紙的設計，跟入口「gpt 系不參與設計決策」不衝突（圖紙由 opus 定）。施工仍要使用者另外點頭（鐵律 2）。
- 「sonnet／gpt 蒐集」：gpt 那半照上面「sonnet 搜集」條，等 agent-fsm 有雛形。

**11-14 補（施工各線）**：使用者原話「然後每條線都讓opus作爲協調，要規劃就走正規規劃流程」「蒐集資料和實作都可以試試看交給sol等」「跑一整晚...我們現在就用本地litellm proxy，使用gpt」「作爲我們要的實作」。所以：
- 每條線都由 opus 協調。施工中碰到圖紙沒寫到、要重新規劃的地方，回頭走這條正統流程，不邊做邊定。
- 蒐集和寫碼優先交給 gpt，**只用 sol、不用 terra，sol 頂替 sonnet 的位置**（使用者 11-14「不要terra，盡量用sol，把sol作爲sonnet來用」），一律走本地 LiteLLM 上的 agent-fsm，**不走 codex**（使用者 11-14「不要走codex」）；走不通由 sonnet／claude 補位；設計判斷仍由 opus 和 fable 做。上面「等 agent-fsm 有雛形」的條件從 11-14 起改成「直接試」。
- 各線有需要可以自己在暫存樹的 aos 裡掛 kernel 或 agent，不用先問（使用者 11-14「然後有需要的，可以自己掛kernel或agent。」）；自己記 pid、收尾收乾淨，活樹照舊不動。
- **頂層也當 kernel**（使用者 11-14「善用aos體系，掛opus eca，讓他們成爲kernel，然後讓他們自己底下掛各種」「你自己也成爲kernel好了」「讓他們都掛在你底下」「他們的工作區...你可以在wf弄temp/xxx分給他們」）：repo-aos 開 `kernel_gate`，把 opus eca（定義 `~/aos-home/agents/opus-kernel`）掛在自己底下，啟動請求經過頂層的 gate；工作區放在 `wf/temp/<名字>`（已 gitignore）。這些 eca 自己也可以開 gate，在底下掛 sol 的 agent-fsm。
  - **commit 一律交給排隊指令**（11-14 起）：各線不再自己 `git commit`，改跑 `~/repo/aos/wf/tools/commit-request`。開工先 `claim --line <線名> 檔…`；交件時 `submit --line <線名> --files 檔… --msg-file 訊息檔`，trailer 自己寫在訊息檔裡。日索引、月索引、SESSION-LOG 不手改，改用 `--op`（`day_upsert`、`month_bump`、`log_upsert`、`log_delete`）。不要再 `git add`，也不要自己跑 `index_gen --apply`，排隊會在 repo 外的乾淨副本上重生生成物，再一起 commit。結果印在最後一行 JSON（雜湊或錯誤原文），exit 2 是被擋（例如別條線 claim 著），回應裡寫著是誰。完整用法與範例見 [commit-queue-1114 § 申請者用法](../../../../proto8/thinking/2026-11/14/commit-queue-1114.md#申請者用法各線照這樣改)。
- **頂層的雜務自動化**（使用者 11-14「太多的請求...你可以派一個claude subagent幫你寫程式…可以另外弄個sonnet agent，幫你當小廝，重要的事情馬上給你，普通通知每隔一段時間再給你」「commit這塊，你也可以開始想辦法，同樣，寫程式或派小廝。或是弄個fsm agent掛在你底下」「要想辦法，你可以把你的意見交給fable，讓他幫你規劃」）：
  - 小廝 `xiaosi`（sonnet eca，定義 `~/aos-home/agents/xiaosi`）收所有 ok-* 的回報：要緊的立刻轉給頂層，其他的每 20 分鐘彙整一封再轉，靠頂層的 clock 項 `xiaosi-digest` 定時叫它。
  - gate 自動初步處理，紀錄見 `proto8/thinking/2026-11/14/gate-auto-1114.md`。
  - commit 排隊：已啟用 `wf/tools/commit-request`，不需要常駐程式，也不用掛 hook（fable 規劃、Argon 審過），用法在上面「頂層也當 kernel」那條底下，紀錄見 `proto8/thinking/2026-11/14/commit-queue-1114.md`。
- **命名**（使用者 11-14「掛fsm sol/astra等agent的時候，那個命名要小心別重合到」）：daemon 表上的名字整台共用；各 eca 掛的 agent 一律叫 `<eca名>-<角色>-<編號>`（例 `ok-kf-sol-1`）。
- **rlimit**（使用者 11-14「eca...建議不要setrlimit，你就跟他們說請他們自行收斂，但是fsm都可。」）：eca 不設 rlimit，請它們自己收斂用量；agent-fsm 可以設。家機 11-14 已裝 s6，fsm 用 `--limits`（mem_mb、files、cpu_s 實測有效；procs 是全帳號計數，別設小）。sol 預設帶 `{"mem_mb":1024,"files":256}`（ok-pilot 11-14 實測：sol 約 RSS 3MB、3 個 fd；開檔的鍵叫 `files` 不是 `nofile`；壓到 AS 32MB／NOFILE 8 會停機，紀錄在 `wf/temp/ok-pilot/notes.md`「第二輪」）。
- 原本排的「fsm 真腦跑一整晚」不另外做測試，改成用 LiteLLM gpt 做實際的施工。

**需求還不清楚時先不走這條**（使用者 11-14 早「你們太早就開始規劃實作與架構了…可以先發想，類似頭腦風暴那樣」）：先發散出點子與可丟棄的小實驗，需求浮出來再規劃，見 [user/03「需求不清時先發想」](../../common/user/03-討論紀錄與規劃.md#需求不清時先發想不急著規劃2026-11-14-定)；第一次照這樣跑的是 [11-14 aos-brainstorm](../../../../proto8/thinking/2026-11/14/aos-brainstorm/README.md)。

原話見 [03「使用者 11-13 23:40 原話」](03-使用者原話.md#使用者-11-13-2340-原話正統規劃流程)；第一次照這條跑的是 [any-resource-os](../../../../proto8/thinking/2026-11/13/any-resource-os.md)。

原話見 [03「使用者 11-13 晚原話」](03-使用者原話.md#使用者-11-13-晚原話工作流程)。第 4 句把 11-07 午那條鏈寫定：搜集由 sonnet 做（11-07 午「可以是opus計劃，讓gpt收集」是舉例）；11-07 午「fable 只做頂層規劃、只吃備料、實作時不參與」與午後「輪中也可、次數不限」照舊。

## gpt 系改走 aos 的 agent-fsm（11-13 晚）

使用者：「codex這塊幫我改一下，改成走aos體系，也不用eca，就直接loop fsm」。

- 派 gpt 系做事時，**在 aos 體系裡開 agent-fsm 身的 agent**（`loop.json` 的 fsm 身、腦接 gpt 系模型），不直接叫 codex CLI、也不用 eca 身（eca＝外部 CLI 當身，codex 也是一種 eca）。
- 舊的 codex 條文（入口的 codex 隊員、02 分檔的 codex CLI 指令、沙箱、`/goal`）先留，等 agent-fsm 那套跑通再清（使用者 11-13 晚「照預設走」）。
- **家機的 gpt 端點**：本地 LiteLLM proxy `http://127.0.0.1:4000`（OpenAI 相容；使用者「我本地litellm proxy開起來了」）。模型普通工作 `chatgpt-gpt-6.1-sol`、簡單工作 `chatgpt-gpt-5.6-terra`；另有 `-low`／`-medium`／`-high`／`-xhigh`／`-max`／`-nothink` 後綴與本地模型。

### 知識庫查得到的線索

- 兩種身：agent-fsm＝aos 自己的四格迴圈（idle、think、wait、act），腦是寄信給 llm kernel；eca＝Claude Code 或 Codex CLI 當身（`aos/body.json`）。
- agent-fsm 範本獨有 `body.json`（`aos-loop loop.json`）、`fsm.json` 與各格程式；兩個範本都有 `llm.json`（如 `{"model": "sonnet"}`），用 `agent_def` 複製範本（`aos/definition.json`）。
- agent-fsm 的 `llm.json` 裡 `model` 是 **endpoint pack 名**，身會把它放進信的 `endpoint`；pack 由 llm kernel 擁有、固定模型與取樣設定，`aos-llm ls` 列出現有的 pack（`aos/brain.json`）；kernel 依它的 `kernel.json` 裡的 endpoint pack（slots、priority、budget）挑信（`aos/cli/parts/llm_kernel.json`）。

### 待補

- 怎麼在 llm kernel 加一個指向 LiteLLM proxy、模型 `chatgpt-gpt-6.1-sol`／`chatgpt-gpt-5.6-terra` 的 endpoint pack（知識庫沒寫 pack 的端點網址、模型怎麼填）。
- 開 agent-fsm agent 做實作的具體步驟（從哪個範本複製、給哪些工具、工作區、怎麼收結果）、它能不能寫碼（工具只有已註冊的 aos 工具）。
- 公司 WSL 有沒有同樣的 proxy。
