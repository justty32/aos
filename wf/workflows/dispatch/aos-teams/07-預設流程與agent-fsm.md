# 正統規劃流程、sol 走 agent-fsm、commit 與回報的細節

← [入口](../aos-teams.md)｜涵蓋：正統規劃流程、sol 走 agent-fsm、commit、回報（寄信怎麼寫）、頂層也當 kernel｜上一份 [06-公司WSL活樹與任務書硬規則](06-公司WSL活樹與任務書硬規則.md)

只寫今天的做法（2026-11-14 改寫，使用者專區「q2:move」；11-23 照 eca-aos 這邊的工作室改了施工歸誰與回報對象，分工見 [wf/org](../../../org/README.md)）。入口短卡已有的指令不重抄，這裡補它沒寫的細節。11-13 那幾版（sonnet 搜集、等 agent-fsm 有雛形、terra、codex、astra 帶 sol）的原文已刪（11-17 刪掉各 archive/），要看去 git 歷史，最後還在的 commit 是 `31a64d4a7`（路徑 `wf/workflows/dispatch/archive/`）。

<a id="正統規劃流程11-13-2340-重述"></a>
## 正統規劃流程

**sol 蒐集 → opus 匯總 → fable 設計 → opus 細化出實作計劃 → Argon 審 → opus 逐條寫採納表 → 實作：寫程式與重要的施工由 Claude 做，機械式的可給 sol（11-23）。**

- **每條線由 opus（或 fable）協調**（使用者 11-14「然後每條線都讓opus作爲協調，要規劃就走正規規劃流程」）：寫任務書、派 sol 蒐集、把蒐集來的整理成給 fable 的匯總；實作時管權衡、審實作、驗收。
- **蒐集與雜活交給 sol（打雜工）**，掛不起來才由 sonnet 的 Claude 子 agent 補位；**寫程式與重要的施工用 Claude**，照對照表改名、搬檔、套格式這類不必判斷的機械式施工可以給 sol（使用者 11-23「蒐集算打雜，但施工這塊，如果是重要的部分，那確實還是得用claude」「尤其是寫程式」，七題第 4、5 題，見 [wf/org](../../../org/README.md)）。11-14 那句讓 sol 也做實作的話，實作那一半已被 11-23 這兩句取代（原話留底在 [03 檔尾](03-使用者原話.md)）。設計判斷仍由 opus 和 fable 做，sol 只照圖紙做。
- **fable 設計**：只做頂層規劃與設計；**規劃用的材料只用 opus 備好的匯總**、不廣讀 repo（使用者 11-07 午「他所需要的資材必須是我們準備給他的」），規矩照[入口「讀規矩」](../aos-teams.md)先讀知識庫入口與[規矩卡](../../common/rules-card.md)；fable 可再派 fable 子 agent。輪間、輪中都可以跑，次數不限；實作時 fable 不即時參與。
- **Argon 審**：opus 細化之後、交實作之前送 Argon 跑一次，(A) 審查 (B) 提案（指令與格式見 [05](05-同機session與Argon.md#argon-是參與者不只審稿)）。opus 逐條寫採納／不採納與理由，改完的計劃才算定稿。
- **astra 不當常設隊長**：線星實測 astra 當門能跑，但不比 gpt 隊省，次數和 token 多 10～50%（[astra-kernel-1114](../../../../proto8/thinking/2026-11/14/astra-kernel-1114.md)），所以由各線的 opus 直接指揮 sol、驗收（使用者 11-14 答「按照推薦」）。
- **做到一半發現圖紙沒寫到**、要重新規劃的地方，回頭走這條流程，不邊做邊定。
- 施工仍要使用者另外點頭（鐵律 2）。

**需求還不清楚時先不走這條**（使用者 11-14 早「你們太早就開始規劃實作與架構了…可以先發想，類似頭腦風暴那樣」）：先發散出點子與可丟棄的小實驗，需求浮出來再規劃，見 [user/03「需求不清時先發想」](../../common/user/03-討論紀錄與規劃.md#需求不清時先發想不急著規劃2026-11-14-定)；第一次照這樣跑的是 [11-14 aos-brainstorm](../../../../proto8/thinking/2026-11/14/aos-brainstorm/README.md)。

這條鏈的使用者原話在 [03「11-13 晚」](03-使用者原話.md#使用者-11-13-晚原話工作流程)與 [03「11-13 23:40」](03-使用者原話.md#使用者-11-13-2340-原話正統規劃流程)（那兩段裡的 sonnet 搜集、astra 帶 sol 已被上面 11-14 的話取代）；第一次照這條跑的是 [any-resource-os](../../../../proto8/thinking/2026-11/13/any-resource-os.md)。

## sol 走 agent-fsm

使用者 11-13 晚：「codex這塊幫我改一下，改成走aos體系，也不用eca，就直接loop fsm」。11-14：「不要terra，盡量用sol，把sol作爲sonnet來用」「不要走codex」。

- **是什麼**：在 aos 體系裡開一隻 agent-fsm 身的 agent（aos 自己的四格迴圈 idle、think、wait、act），腦是寄信給 llm kernel。不叫 codex CLI，也不用 eca 身。
- **腦**：家機本地的 LiteLLM proxy `http://127.0.0.1:4000`（OpenAI 相容）。配給包 `kits/gather/` 的 `llm.json` 決定走哪包，`AOS_LLM_KERNEL` 決定寄給哪個 llm kernel：
  - `llm.json` 內容是 `{"model": "sol", "reasoning_effort": "high"}`（llm kernel 範本 11-21 起沒有 `sol-high`）。`model` 填的是 **endpoint pack 名**，pack 由 llm kernel 擁有（知識庫 `aos/brain.md`）。
  - `AOS_LLM_KERNEL` 由掛的人那邊（上層 daemon 那一列）傳下來，包裡沒有 `.env`（11-23 刪了；[kits/card](../kits/card.md) 第 1 步）：公司那台 11-23 起是 `~/aos-home/.stack/procs/llm`（llm kernel 掛在 `~/aos-home` 的根底下）。還沒改成 `~/aos-home` 一套的機器，掛的人在 `subagent add` 的 `envs` 帶，或自己在定義夾放 `.env`（11-23 是家機，llm kernel 自己一台、stack 是 `~/aos-home/.llm-stack`，見[換機說明書](../../dev-env/03-換機.md)）。
- **蒐集和施工不用 terra**，只用 sol；terra 只用在使用者點名的地方（例如全景頁的小幫手）。
- **怎麼掛、怎麼驗收**：步驟在 [kits/card](../kits/card.md)，包的內容與已知限制在 [kits](../kits/README.md)，帶 sol 的心得在 [sol-crew](../../../public/sol-crew.md)。蒐集員、審稿員用「看」包，不抄別線的 system.txt（使用者 11-14「都按照推薦」，[onboard-1114](../../../../proto8/thinking/2026-11/14/onboard-1114.md)）。
- **自己掛 kernel 或 agent 不用先問**（使用者 11-14「然後有需要的，可以自己掛kernel或agent。」）：掛在暫存樹（`~/.aos/scratch/<線名-日期>/`，使用者 11-15 裁「4.a」）的 aos 裡，自己記 pid、收尾收乾淨，活樹照舊不動。
- **隊長的 shell 是 zsh，範例指令要分詞的一律包 `bash -c`**（11-14 ok-misc 與頂層各踩一次：ok-misc 因此把一封信寄錯對象，頂層開線失敗一次）：zsh 的 `$VAR` 不分詞，`for p in "a b"; do set -- $p; …` 切不開、`for f in $(cat list)` 只跑一圈。一次對多隻 agent 下指令、逐行讀清單這類寫法，寫成 `bash -c 'for n in a b c; do …; done'`（清單直接寫在 `in` 後面），或 `bash -c 'mapfile -t F < list; for f in "${F[@]}"; do …; done'`；清 `AOS_*` 的腳本同理要是 bash（[06 硬規則第 2 條](06-公司WSL活樹與任務書硬規則.md)）。另見 [pitfalls「隊長的 shell」的「zsh 不分詞」](../../../public/pitfalls.md#隊長的-shellbash-工具)。
- **蒐集員的交件要先想好怎麼落地**（ok-view 11-14 踩到）：只掛 look、gadgets、json、index 的蒐集員只有 JSON 寫入，寫不出 Markdown。任務書擇一寫明：① 「全文放在最後一則回答裡」，隊長用 `subagent listen`（`last: 1`）或 `aos-agent history -t <名字> ls -j` 取出存檔；② 先替它掛寫檔的包：定義的 `tools.json` 的 `$override` 加 `lib/packs/ws-write.json`（工具 `ws_write`：只能寫進自己的工作區，一次上限 256 KiB，不刪檔；38271da3b，換樹後活樹才有），任務書寫明交件檔名。
- **沒掛 shell 包的 sol 沒有 shell**（看包和多數施工定義都是；掛了 shell 包的 sol 有，但有 guard 會擋，見 [sol-crew](../../../public/sol-crew.md)）：查版本、查環境、跑指令收結果這類事，派工的人自己跑好，把輸出貼進任務書或寫成檔叫它讀，不要讓 sol 靠讀檔去猜（ok-view-sol-7 為了查 `node --version` 翻了 117 步）。
- **命名**（使用者 11-14「掛fsm sol/astra等agent的時候，那個命名要小心別重合到」）：daemon 表上的名字整台共用，各 eca 掛的 agent 一律叫 `<eca名>-<角色>-<編號>`（例 `ok-kf-sol-1`）。
- **rlimit**（使用者 11-14「eca...建議不要setrlimit，你就跟他們說請他們自行收斂，但是fsm都可。」）：eca 不設，自己收斂用量；agent-fsm 在 `subagent add` 時帶 `limits`。
  - 資源的鍵：`mem_mb`、`cpu_s`、`procs`、`file_mb`、`files`，另有整隻 agent 的總量 `mem_total_mb`、`procs_total`（要 daemon 開 cgroup）與 `user`。開檔數的鍵叫 `files`，不是 `nofile`。
  - sol 預設帶 `{"mem_mb":1024,"files":256}`。
  - `procs` 算的是整個帳號的程序數，別設小（看包的隊員乾脆不設）。
  - `cpu_s` 只按單一程序計時，管不到整隻 agent 的總 CPU。
  - 實測數字與表在 [sol-crew「rlimit 實測與腦額度」](../../../public/sol-crew.md#rlimit-實測與腦額度)。
- **腦額度每隻 sol 一份**：用光會被拒 `BudgetMissing`：額度窗是 hour／day 時 agent-fsm 不會停，等到窗重置再重試；窗是 `all` 時不重試，停下。兩種都由 `brain_notify` hook 寄一封 BLOCKED 給掛它的人（額度窗見知識庫 `aos/brain.md` 的 `priority`；實測見 [sol-crew](../../../public/sol-crew.md)）。「看」包目前還沒掛這個 hook（kits「已知限制」），用看包的隊員額度用光時不會來信，隊長要自己看。

還沒確認：公司 WSL 有沒有同樣的 proxy。

## commit

**只有一條路：`~/repo/aos/wf/tools/commit-request`**（鐵律 3；使用者 11-14 專區「q1:fix」）。各線不自己 `git commit`、不 `git add`、不自己跑 `index_gen --apply`。兩行指令在[入口第 1 件](../aos-teams.md)，這裡是它沒寫的：

- **開工 `claim`、交件 `submit`**：`claim --line <線名> 檔…` 宣告在改哪些檔；`submit --line <線名> --files 檔… --msg-file 訊息檔` 交件。trailer 自己寫在訊息檔裡，排隊不改訊息。
- **日索引、月索引、`wf/progress.json` 不手改，用 `--op`**：`day_upsert`、`month_bump`、`progress_upsert`、`progress_delete`；月索引那天的份數要直接設成某個數時用 `month_set`（份數＝日索引的列數）。
- **生成物由排隊重生**：它在 repo 外的乾淨副本上跑 `index_gen`，生成物跟你的檔同一個 commit。
- **看結果**：stdout 最後一行是 JSON（雜湊或錯誤原文）。exit 0 是做完；exit 2 是被擋（例如別條線 claim 著那個檔），回應裡寫著是誰，去信協調。
- **直接 `git commit` 會被 `.git/hooks/pre-commit` 擋下**（使用者 11-14「1.好。2.好」）；人要手動 commit 時加 `--no-verify`。
- **指令在哪**：任務書與範例一律寫全路徑。家機 2026-11-14 暫時有一個連結 `~/.local/bin/commit-request` 指到 `wf/tools/commit-request`，直接打 `commit-request` 也找得到；這是過渡，之後會拔掉，所以別依賴它。
- 完整用法、其他 exit 碼、`--dry-run`、`--rm`、`doctor`：[commit-queue-1114「申請者用法」](../../../../proto8/thinking/2026-11/14/commit-queue-1114.md#申請者用法各線照這樣改)；新資料夾、中文檔名、共用的 progress.json 條目這些坑：[patch-and-commit](../../../public/patch-and-commit.md)。

## 回報

**回報寄任務書指定的對象。** 工作室（11-23 起）沒有部長也沒有小廝，對象是 eca-aos（七題第 6 題，見 [wf/org](../../../org/README.md)）。

下面兩條是 11-14 公司那台舊樹的隊形（頂層底下分幾個部、各線寄自己那一部的部長），留著當由來，工作室沒有這兩層：

- **部長做的**（舊樹）：收線的回報、放行或擋下 commit、協調。寫活樹、push、刪檔、開線或關線，部長不自己做，轉給頂層。現在這些由 eca-aos 管：位子在自己範圍內先交後報，跨範圍、帶 `--rm`、要跑 `install.py`、動活樹的先問 eca-aos（第 6 題）。
- **小廝 `xiaosi`**（舊樹的 sonnet eca）管使用者專區、通知和群發，並彙整部長的信給頂層；寄到頂層的信由頂層照中轉表轉給部長。工作室沒有小廝。
- 這套的由來：使用者 11-14「太多的請求...你可以派一個claude subagent幫你寫程式…可以另外弄個sonnet agent，幫你當小廝，重要的事情馬上給你，普通通知每隔一段時間再給你」。gate 自動初步處理的紀錄在 [gate-auto-1114](../../../../proto8/thinking/2026-11/14/gate-auto-1114.md)，commit 排隊的紀錄在 [commit-queue-1114](../../../../proto8/thinking/2026-11/14/commit-queue-1114.md)。

### 寄信怎麼寫

各線與它們底下的隊長都適用（頂層 11-14 採用；出處 skyrim 的「領導轉發三條規矩」，見 [skyrim-agentctl 02、04](../../../../proto8/thinking/2026-11/14/skyrim-agentctl/04-wf改稿.md)）：

1. **標題寫你的判斷，不轉貼隊員原話**：「線 X 做完，Y 已 commit（雜湊）」「線 X 卡在 Z，已試過 A、B」；不寫「完成」「報告」「sol 回報如下」。
2. **標題或第一句標明你要什麼**：要使用者裁（status `NEEDS-USER`）、要 eca-aos 給資源或放行（`BLOCKED`）、只是報備（`PROGRESS`／`DONE`）。收信的人只看 status 與標題分輕重，寫錯就會被排進定時彙整或被誤當急件。
3. **正文先寫你已經排除的可能**：卡住或出錯的信，第一段列「試過什麼、為什麼不是那個」，上面才不用重跑一次你做過的判斷。

要使用者拍板的題目另外寄專區（[入口第 2 件](../aos-teams.md)）。

## 頂層也當 kernel

使用者 11-14：「善用aos體系，掛opus eca，讓他們成爲kernel，然後讓他們自己底下掛各種」「你自己也成爲kernel好了」「讓他們都掛在你底下」「他們的工作區...你可以在wf弄temp/xxx分給他們」。

- 頂層（當時在 daemon 表上叫 `repo-aos`）開 `kernel_gate`，各線是掛在它底下的 eca，啟動請求經過頂層的 gate。
- 定義在 `~/aos-home/agents/`（公司那台舊樹）：`opus-kernel`、`fable-kernel`，小廝是 `xiaosi`。
- 工作區是 `wf/temp/<名字>`（已 gitignore；11-22 起改了，見下一條）。
- 這些 eca 自己也可以開 gate，在底下掛 sol 的 agent-fsm。

**11-22 新定（家機搬進 repo 裡的 stack 之後；11-23 起那個資料夾叫 `.stack`）**：使用者 11-22「然後工作區仍然就是~/repo/aos」「現在就是讓他們有自己的私有地盤這樣」（[01-決定與調查](../../../../proto8/thinking/2026-11/22/工作區與stack-1122/01-決定與調查.md)）。

- 兩台的樹都是 `~/repo/aos/.stack`（根定義 `wf/tree/root/`；被 git 忽略、每台各有各的，使用者 11-23）。家機頂層是住在裡面的 eca-aos，底下掛三個 subagent；公司那台 11-23 起樹，表上先只有 eca-aos；11-23 起那台的 `.stack` 是 `~/aos-home` 根底下的子 daemon（列 `repo-aos`），家機照說明書跟上。上面四條是公司那台舊樹（`~/aos-home`）的做法。
- 線與隊員的工作區一律是 repo 根 `~/repo/aos`；草稿、任務書、自己做的定義夾放私有地盤 `wf/ws/<上層>/<名>/`（照掛的層級嵌套），不進 git 的放地盤裡的 `temp/`（[wf/ws](../../../ws/README.md)）。
- 新做的定義放 `wf/tree/` 或地盤裡，不放 `~/aos-home`（那裡只放這台的根定義、llm kernel 與根的 stack）。
