← [入口](../2026-11-17-重構與tidy盤點.md)｜涵蓋：repo 層雜項、要使用者裁的題、查了沒問題的、沒查到／沒把握的｜上一份 [04-文件-proto8](04-文件-proto8.md)

## repo 層雜項

| # | 東西 | 現況（證據） | 建議 | 工作量 | 已知／新 |
|---|---|---|---|---|---|
| R1 | `proto8/impls/aos-llm-kernel/`（未追蹤） | Windows 與 WSL 兩邊都在，只剩 `bin/`、`lib/`（`git status` 列 `??`）；這專案自己的 `.gitignore` 隨 `726f73952` 刪了，所以 `lib/` 冒出來；WSL 的 `~/.local/bin/aos-llm-kernel` 捷徑（11-13 08:23）還指著它 | 整夾與捷徑刪掉（刪檔，使用者點頭或親手） | 小 | 新 |
| R2 | `proto8/extras/aos-view/ui/v2/dist/` 被追蹤 | 3 檔，`index-CiFlI67e.js` 343100 B；git log 有三次手動清舊雜湊檔（`278bad7`、`0fd53a6`、`65c5d3a`） | 見裁題 Q3 下方的 dist 一題 | 小 | 新 |
| R3 | 特別大的被追蹤檔（非封存） | 前幾名都在 thinking：`13/aos-wu-1113-待你裁.html` 413687、`14/release-1114/06-草稿/v1|v2` 的 png 各 329892／237423（兩兩相同）、`13/aos-wu-1113-r2-待你裁.html` 257004、`13/decide_20261113_wu.json` 243372、`12/thinking-to-docs/提取總表.json` 203759；另有 `wf/tools/index_gen_desc.json` 166270、`designs.json` 151626、`docs/index.html` 105992（上線的宣傳頁，正常） | 隨 D1～D3 處理 | — | 新 |
| R4 | repo 根的 `trim2.py`（Windows，未追蹤） | 25 行，開頭讀寫 `~/.claude.json`——看來是今天清 `~/.claude.json` 用的一次性腳本 | 搬出 repo（不進 git）；`.gitignore` 不必為它加規則 | 小 | 新 |
| R5 | `.gitignore` | `__pycache__/`、`*.pyc`、`build/`、`bin/`（cmd、extras 的 bin 有例外）、`wf/temp/` 都擋了；`git ls-files` 裡 `__pycache__`／`.pyc` 0 檔、`wf/temp` 0 檔；被追蹤的 `bin/` 全在 `archive/` | 沒問題 | — | — |

## 要使用者裁的題

- **Q1 thinking 11-13～11-17 怎麼處理**：A 先跑 thinking→docs 提取再分批精簡（推薦；照 10-29～11-12 那輪的做法，條文跟得上、量能從 7.8 MB 降下來）；B 只精簡不提取（快，但決定可能沒進條文）；C 先不動（這幾天的題還有在跑的，等收完）。後果：A 要開好幾條 opus 線、還要逐句對讀，大工。
- **Q2 `release-1114/06-草稿/v1`**：A 刪 v1 整夾（推薦，網頁已上線、v2 在）；B 封存；C 只刪跟 v2 一模一樣的兩張 png（省約 567 KB）。
- **Q3 aos-view 的 `aide-def` 複製了一整份 agent-fsm 的格**：A 改成只放差異、其餘從範本抄（推薦，免得兩邊走樣：wait.py 已差 287 行）；B 併回範本當選項；C 照現在各管各的。另一小題：`ui/v2/dist` 要不要繼續進 git——A 繼續追蹤但讓建置自己清舊檔（推薦，換樹抄得到成品、不用在活樹 build）；B 不追蹤、換樹時現建。
- **Q4 `subagent` 的 BookOld 擋舊名冊**（11-15 才加）：A 留到下次換樹確認沒有舊名冊後拿掉（推薦）；B 現在就拿（照「當沒有舊版」）；C 永久留。
- **Q5 hook（`context_wrap`、`brain_notify`、`mail_notify`、`hook_fire`）自寫 die／read_json、沒走 `tool_io`**：慣例寫「lib 工具走 tool_io」，hook 算不算工具不清楚。A 算，收進 tool_io（推薦，輸出格式一處管）；B 不算，寫明 hook 是例外。
- **Q6 `wf/advices/` 7 檔 197 KB**：A 按主題拆、條列抽資料檔（照鐵律 6）；B 當意見庫原樣留（推薦先問用途：是給人翻的還是給 AI 查的）。
- **Q7 `wf/salvage/`、`workflows/digest`、`experiments`、`investigations`**：A 已做完的整夾封存進所屬 `archive/`；B 照紀錄類原樣留（推薦 B，除非你確定 salvage 那包已沒用）。
- **Q8 `install.sh --uninstall` 會去拿掉舊的 `aos-proto8.pth`**：這是替舊版留的清理。A 拿掉這段（照「當沒有舊版」，推薦——家機、公司 11-15 後都沒 pth 了才行，沒核）；B 留著當一次性清理。
- **Q9 NORMS 附錄 1～3（條號表、各批出處、舊名對照）**：A 照「沿革只留結論」清；B 留當出處表與舊名表（推薦 B，它們本身就是出處／對照，清了就沒用了）。（上次報告也列了這題。）

### 使用者裁定（11-17）

原話（逐字）：「要我裁的那九題，wf/advices是蒐集AI對aos的意見，可以封存，只提取精簡。salvage,digest,experiments,investigations通通封存，只提取精簡後的一點點東西，放到wf/advices。精簡後的東西，wf/advices希望只剩下兩三個小於8kb的檔案。9.要清掉。4.現在就拿掉。3.建置成品不進git，現有的都清掉。盛夏都按照推薦」（「盛夏」頂層讀作「剩下」）

| 題 | 裁定 |
|---|---|
| Q1 | 照推薦 A：先跑 thinking→docs 提取再分批精簡 |
| Q2 | 照推薦 A：刪 `release-1114/06-草稿/v1` 整夾 |
| Q3 | `aide-def` 照推薦 A（只放差異、其餘從範本抄）；`ui/v2/dist` **不進 git，現有的都清掉**（不照推薦） |
| Q4 | **現在就拿掉** BookOld（不照推薦） |
| Q5 | 照推薦 A：hook 算工具，收進 `tool_io` |
| Q6 | `wf/advices/` 是蒐集 AI 對 aos 的意見：**封存，只提取精簡**；精簡後 `wf/advices` 只剩兩三個小於 8 KB 的檔 |
| Q7 | `salvage`、`digest`、`experiments`、`investigations` **通通封存**，只提取精簡後的一點點放進 `wf/advices`（不照推薦） |
| Q8 | 照推薦 A：拿掉 `install.sh --uninstall` 清舊 `.pth` 那段 |
| Q9 | **要清掉** NORMS 附錄 1～3（不照推薦） |

### 使用者追加：條文精簡（11-17）

原話（逐字）：「對了，現有的concept, norms也需要tidy了，要去精簡，去除掉各種有的沒的例子，或是說把栗子跟純概念拆開。就是說，我希望一兩個8kb以下的檔案就可以把概念瀏覽完，而norm這塊可以放寬到三四個」「convention也要」

- CONCEPTS：一兩個 8 KB 以下的檔瀏覽完（線 concepts-1117，11-17 開工）。
- NORMS：放寬到三四個檔；等封存線清完附錄後開。
- CONVENTION：也要；檔數使用者沒講，頂層先照 CONCEPTS 的一兩個檔做，裝不下再問。

## 查了沒問題的

- 單向分層：impls 沒人 include 別專案 `src/`；lib 沒有 import `py/`。
- C++ 程式裡沒有舊格式相容碼（只剩註解，見 C10）；CMake 全用 GLOB，沒有漏編。
- `proto8/kernel/` 只有設定與一支 54 行假腦。
- py 每個模組都有人 import；cmd 9 支自訂 `die` 都只轉給 `aos_flags.die`；`aos-daemon-ctl ls` 判活走 `dc.check_alive`、沒自讀 /proc。
- `lib/packs`、`templates/agent-fsm` 沒放 `_index.json` 是 `wf/tools/index_gen.json`（第 2、109 行）刻意設的（SESSION-LOG 第 32 行的「超過門檻沒放」是已知、已登記 WAIT_USER）。
- knowledge：155 個 json 都有 `_description`，`_index.json` 120 項全指得到。
- `wf/temp/` 不進 git；`wf/tools/` 沒有明顯孤兒腳本（引用最少的是被 import 的庫）。
- aos-teams 入口的沙箱說法已照 11-13 裁定改好；`conventions/01:23`「六類」跟 C-52 續現行表 6 列對得上（表號跳過 ②，只是編號缺口）。
- 抽 11-13／14 thinking 相對連結 30 條，30 條都在。

## 沒查到／沒把握的

- SESSION-LOG 48 條 open 沒逐條讀到底判斷是否已完，只標了開頭就看得出的幾條。
- 程式重複只抽查常見函式名，沒做全面相似度比對；lib 與 py 之間沒逐函式比。
- 中型 Python 檔（mailbox、entry.py、history.py、json-view、sandbox、share、tools_def、fork）只看了大綱。
- `child.cpp:81–90` fork 後 `setenv` 有沒有風險，要看 daemon 是不是單執行緒，沒查。
- C-54 R8 的 `max_calls` 現在算不算數、`aos-wu-1113-待你裁.html` 是否被 r2 取代、`progress_board` 看板還用不用。
- 各夾 README 只看大小沒逐句核內容；10 月 thinking 精簡到什麼程度沒逐份看；`wf/knowledge/*.json` 沒全掃。
- 沒碰：`impl_cpp/`（使用者手寫）、`archive/` 與各 `archive/`、`wf/inbox/done/`、arknights 相關。
