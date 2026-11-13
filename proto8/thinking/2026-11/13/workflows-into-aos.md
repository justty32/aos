# 模板 repo（workflows）併入 aos：調查＋意見稿（11-13 下午，線玄；只查只寫、沒改程式、沒寄信）

← [11-13 README](README.md)｜調度者：頂層 session `repo-aos`｜起因：樹裡的 `wf-agent`（工作區＝模板 repo `/mnt/c/code/mine/workflows`）11-13 14:35 來信問六點

標法：**【事實】**＝查得到、附出處或指令；**【意見】**＝線玄的看法，方向由使用者定（鐵律 5）。

## 一句話結論

- 【事實】三種併法技術上都做得到。aos repo 現在沒有 submodule；活樹的複本與「乾淨複本跑全套」都用 `git archive`，**`git archive` 不帶 submodule 的內容**（實測，見下）。所以 submodule 只要掛在會被抄進活樹的五夾之外，就不會出事；掛在五夾裡面，活樹會拿到一個空夾、而且不報錯。
- 【事實】aos 現在**沒有**「給新 agent 的工作區鋪一套初始檔案」的機制；模板 repo 的 `wf-init.sh` 是目前唯一做這件事的東西。
- 【事實】使用者對「模板要不要繼續服務不在 aos 裡的專案」**沒講過**（repo 裡搜不到，wf-agent 也說他沒說）。
- 【意見】最短而穩的路：先把「掛進來」跟「改內容」拆成兩件事。掛進來（submodule、掛在 repo 根）只是一個 commit，風險小；最容易出品質問題的是後面兩步——模板回寫 v0.7、aos 自己的 `wf/` 換成新形態——這兩步不必跟掛進來綁在一起。
- 要使用者裁九題，在[「要使用者裁的題」](#要使用者裁的題)。
- **11-13 14:47 使用者裁了**：讀成「內容變成 aos 的東西、repo 留著但幾乎不再更新、邊用邊併」，上面第四條的 submodule 建議作廢；原話、逐題對照與新前提下的重估見[使用者裁定（11-13）](#使用者裁定11-13)。

## 使用者的話（逐字）

這次的三句都是 wf-agent 信裡轉的，repo-aos 這邊沒有直接聽到：

- 「以後這個workflow，應該會併入aos中。可能是submodule吧我猜。」
- （wf-agent 問要不要跟 repo-aos 討論）「可以討論」
- 「能愈快併入愈好，但不要因為趕工而喪失品質」

之前講過、有關的（[wf-to-aos](../12/wf-to-aos.md) 第 7、28、32、34 行）：

- 11-12：「然後...我接下來想做的事情，是開始用aos體系替代掉wf/。或者說不是替代，而是將其變成更適合agent的情況，途中會發現wf/的一些東西已經不再有用，就可以拿掉。當然，我要先玩一玩啦。」
- 11-12：「.json比markdown好，有需要的話再做一些輔助工具和程式幫助人看json就好。2.先放着，這是後面一邊玩一邊自然會要做的。…」
- 11-12：「就是說，沒有硬性缺的了，現在wf/的東西，我們拼拼湊湊就能有了。」「以後一定會比wf/好用，放心。…」

**找不到的**：使用者談「模板 repo 要不要通用／服務別的專案／併進 aos／submodule」的原話，在 `wf/` 與 `proto8/thinking`、`proto8/docs`（不含 archive）都沒有；「submodule」只出現在 [dev-env](../../../../wf/workflows/dev-env.md)（講 aos 自己是 `simple_tools` 的 submodule）與無關的信裡。wf-agent 是怎麼來的、使用者交代它什麼，repo 裡也只有 agent 的轉述（「13:14 使用者新加的」）。

**一句話兩種讀法**（「這個workflow…併入aos」）：

- 讀法甲：**整個模板 repo**（`template/`、`flavors/`、`tools/`、`skills/`、`examples/`、它自己的 `wf/`）原樣成為 aos repo 的一部分。「submodule」這個猜測比較貼這個讀法。
- 讀法乙：**這套工作流的做法與內容**變成 aos 體系的一部分（知識庫、工具包、範本），repo 本身留不留、怎麼留是其次。11-12 的「用aos體系替代掉wf/…變成更適合agent的情況」比較貼這個讀法。

兩種讀法在第 1、2、4 點的答案不一樣，所以列成[第 1 題](#要使用者裁的題)。

## 查到的事實

**aos repo（`~/repo/aos`，main `b374ac376`）**

- 沒有 submodule：`ls .gitmodules` → `No such file or directory`；`git ls-files -s | awk '$1==160000'` 沒有輸出。
- 這台的 aos 是獨立 clone（`.git` 是資料夾）；[dev-env](../../../../wf/workflows/dev-env.md)「git 佈局」寫的是家機：aos 本身是 `simple_tools` 的 submodule。
- 活樹 `~/aos-home` 有 `lib`、`templates`、`knowledge`、`py`（與 `agents`、`daemon`、`root`、`ws`）；今天停樹腳本抄的是五夾：`common.sh` 第 6 行 `ST_COPY_DIRS=${ST_COPY_DIRS:-"lib templates knowledge py kernel"}`，`swap.sh` 第 112 行 `git -C "$ST_REPO" archive "$ST_REF" $(… echo "proto8/$d" …) | tar -x -C "$stage"`。
- `proto8/install.sh` 不抄檔：只把 `impls/*/bin/*`、`cmd/*/bin/*` symlink 進 `~/.local/bin`，再寫一份 `.pth` 指到 `py/`、`lib/`。
- 全套測試的基準也是 `git archive <commit> | tar -x`（[testing](../../../../wf/workflows/testing.md) 第 51 行、[aos-teams/06](../../../../wf/workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md) 第 6 條）。
- **`git archive` 不帶 submodule 內容**（暫存夾實測，git 2.43.0）：外層 repo 在 `proto8/knowledge/wf` 掛一個 submodule（裡面有 `tpl.txt`），`git archive HEAD | tar -t` 印 `.gitmodules`、`a.txt`、`proto8/`、`proto8/knowledge/`、`proto8/knowledge/wf/`——有空夾、沒有 `tpl.txt`、沒有警告。不加 `--recurse-submodules` 的 `git clone` 也一樣只有空夾。
- `proto8/templates/`：`agent-fsm`、`eca-claude`、`daemon-root`、`judge-llm`、`reviewer`、`tool-python`。都是**定義資料夾**（這隻 agent 怎麼跑：`_entry`、`tools.json`、`hooks.json`…），用 `cp -r` 或 `agent_def new` 整夾抄。不是工作區的內容。
- 掛一隻 agent：`aos-agent ctl add --ws WS …`，工作區「選到的路徑不是資料夾＝`WsMissing`」（`proto8/cmd/aos-agent/README.md` 第 55 行）——要一個已經在的資料夾，不往裡面放任何檔。**沒有鋪初始檔案的機制。**
- 「在這個 repo 做事的規矩」怎麼進 eca：留在工作區，`CLAUDE.md`→`AGENTS.md`→`wf/` 由 CLI 自己照檔名載入，aos 不碰也不抄（[main-session-in-aos](main-session-in-aos.md) 第 93 行，agent 的結論）。
- `proto8/knowledge/`：出廠只有一個 subject `aos/`（外加 `_description.json`、給人看的 `README.md`、`docs/`）。多庫＝「另開一個資料夾、把路徑告訴 agent 即可；不登記、沒有掛載設定」（[knowledge/docs/01](../../../knowledge/docs/01-樹長怎樣與多庫.md)「多庫」）。`knowledge/aos` 內容語言英文。
- aos 的 `wf/`：版本戳 `wf-kernel v0.5 (2026-08-30)`（`AGENTS.md` 第 53 行）；`git ls-files wf | wc -l` → 1480 個檔、7.7 MB。
- `wf/tools` 裡 aos 自己加的：

| 東西 | 大小 | 做什麼 | 綁 aos 嗎 |
|---|---|---|---|
| `json_text.py` | 10315 B、252 行 | json 展開成逐行文字給 git 比（textconv） | 不綁，純標準庫 |
| `index_check.py` | 10075 B、210 行 | 查 `_index.json` 跟樹對不對得上（列了不在、在沒列、連結、形狀） | 不綁，純標準庫＋`git ls-files` |
| `index_gen.py` | 14360 B、296 行 | 從各檔檔頭一句話**生成** `_index.json` | import `codemap_gen` |
| `codemap_gen.py` | 16449 B、379 行 | 從 proto8 各檔檔頭生成逐檔 code map | 寫死掃 `proto8`、跳過的夾名是 aos 的 |
| `compact_reload.sh` | 1845 B | Claude Code compact 後把偏好與交接讀回來的 hook | 綁 Claude Code 與本 repo 的檔名 |
| `decide_page/` | 整夾 83 KB | 把一批待裁題做成可點選的頁、收回覆 | 沒查它 import 了什麼 |
| `progress_board/` | 整夾 674 KB | 進度看板、論壇、遠端同步 | 沒查 |

- aos 的 `wf-lint.sh` 已經會跳過 `.gitmodules` 宣告的 submodule（第 59～71 行）；日常只掃 `wf` 與 `.claude/commands`，8192 bytes 的 `OVERSIZE` 只查 `workflows/` 底下的檔（第 109 行）。`index_gen.py`、`codemap_gen.py` 照 `git ls-files` 列檔——submodule 在那裡是一個項目、不會下鑽（它在 index 裡會長怎樣沒實測）。
- 使用者對大小上限講過的：10-09「原型開發階段不設核心行數上限」（[user/02](../../../../wf/workflows/common/user/02-交接與收工.md)）；11-11「我的建議是改成一個檔案不超過8kb，一段不超過1kb。」「那個知識庫上限，只是推薦，不要訂死。」（[knowledge/docs/02](../../../knowledge/docs/02-寫入與節點怎麼寫.md)）。

**模板 repo（`/mnt/c/code/mine/workflows`，唯讀看；HEAD `ea562a1`）**

- 326 個追蹤檔、pack 約 605 KiB；remote 在 GitHub；`git rev-list --count origin/main..HEAD` → 6（**有 6 個 commit 還沒 push**）；工作樹有兩個檔改了沒 commit（`wf/knowledge/ideas.json`、`user.json`）；另有一條分支 `add-routines-workflow`。
- `.gitmodules` 三個：`skills/external/archify`、`dashi-ppt-skill`、`Kami`，都 `shallow = true`、都指別人的 GitHub repo。它自己的 `decisions.json` 寫：這三個「是本 repo 自己的參考資產，不發給下游；`wf-init` 確實不複製它」。
- `tools/`：`wf-init.sh`（把 kernel＋選的 flavor 合成到一個專案，可非侵入式收進 `wf/`，結束時印殘留佔位、跑 lint）、`wf-lint.sh`、`tabledb*`、搬檔改連結等。bash＋python 標準庫。`template/AGENTS.md` 版本戳 `wf-kernel v0.6 (2026-09-02)`，CHANGELOG 另有一段「未發布」。
- `wf-lint.sh --self`：模板 repo 自檢時「任何檔都不超過 8192 bytes」。
- 它的 `wf/`（試點形態）：`_index.json` 六格；`knowledge/structure.json` 是 `_index`＋14 個 `$ref`；`knowledge/decisions.json#/records` 今天六條。工具：`index_check.py`＋`index_check_tree.py`＋`index_check_refs.py`（5615＋7560＋3901 B）＋`wfnode.py`（6174 B）、`wf-view.py`＋`wf_view_render.py`（json 印成 md）。檔頭都寫「不依賴 aos」。
- 它的 `index_check` 比 aos 的多查：反引號裡的統一路徑與 `$ref` 走不走得到（會跟 `$ref`）、忽略表、`_index.local.json`、門檻提醒（`IndexWanted`）。aos 的多一個 `--fs`（查不在 git 裡的樹，例如裝好的 knowledge）。
- 它的 `wf/knowledge/user.json` 有一句寫了帶帳號名的家目錄絕對路徑（`aos_peers` 那格，指活樹的 `ws/public/`）；`ideas.json#/roadmap` 記了「併入 aos…模板要不要繼續服務不在 aos 裡的專案未定——回寫模板時別把這條路堵死」。
- 它自己調查的結論（`wf/knowledge/notes/wf-to-aos.json#/findings`）：「`_index.json` 只是普通檔案：不在 aos 裡的 agent 也讀得到…真正綁 aos 的只有信件與定時器。」已知下游：ops-notes、model_entry、gpt-soap、aos repo 自己的 `wf/`。

## 六點逐點

### 1 併法

【事實】各選項的後果：

| | (a) submodule | (b) 整個搬進 aos 當子目錄 | (c) 維持獨立、aos 只抄一份 |
|---|---|---|---|
| aos 這邊要動的 | 一個 commit：`.gitmodules`＋一個指標 | 326 個檔進 aos；歷史用 subtree 帶進來或不留 | 不動（現在就是這樣） |
| 之後改模板 | 兩步：模板 repo commit（＋push），再到 aos 動指標 commit | 一個 commit | 改模板 repo，再手動抄到 aos |
| 新 clone | 要 `--recurse-submodules` 或 `git submodule update --init`，不然是空夾 | 直接有 | 直接有（抄進來的那份） |
| `git archive`（活樹複本、乾淨複本跑全套） | **不帶內容**：掛在五夾裡＝活樹拿到空夾；掛在五夾外＝沒影響 | 帶 | 帶 |
| 指到沒 push 的 commit | 別台 clone 抓不到那個 commit（現在模板 repo 就有 6 個沒 push） | 沒這問題 | 沒這問題 |
| 三個巢狀 submodule | 留在模板 repo 裡；aos 只做一層 init 就不會抓它們（要 `--recursive` 才抓） | 得變成 aos 自己的 submodule，或拿掉 | 不相干 |
| 家機（aos 是 `simple_tools` 的 submodule） | 變三層（`simple_tools`→aos→模板），連三個外部的是四層 | 不變 | 不變 |
| 模板的獨立 remote、CI、`--self` 自檢、CC0＋MIT 授權 | 原樣保留 | CI 與自檢要改寫成在子目錄跑；授權檔跟著進 aos（aos 根目錄現在沒有 LICENSE 檔） | 原樣保留 |
| 不在 aos 裡的專案要用模板 | 照舊 clone 模板 repo | 得 clone 整個 aos（pack 約 61 MiB） | 照舊 |
| 兩邊漂掉 | 指標釘版本，不會默默漂 | 沒有兩邊 | 會漂（aos 的 `wf/` 現在 v0.5，模板 v0.6＋未發布） |
| 誰在哪 commit | wf-agent 留在自己的 repo；aos 只收指標 | wf-agent 與 repo-aos 在同一個 repo、同一條 main 上 commit，要領地表 | 各管各的 |

【意見】(a) submodule，掛在 repo 根（五夾之外，名字不能叫 `wf`——aos 自己的在用）。理由：最貼使用者說的那句；aos 這邊只多一個 commit；模板的通用性、CI、授權一樣不動，第 4 題怎麼裁都不用重來；`git archive` 那個坑靠「不掛在五夾裡」就避開。樹裡的 agent 要用到的內容，走第 2 點「出廠時抄」那條路，不直接讀 submodule 的夾。若使用者的意思是讀法乙，那 (c)＋把內容做成知識庫／工具包就夠，repo 不必掛。

### 2 進了 aos 之後它算什麼

【事實】

- 知識庫的 subject 是「大家共用、唯讀、每棵樹一份」的東西（現在只有 `aos/`）。模板的 kernel＋flavor 是「抄進每個專案、抄完歸專案自己改」的東西。兩者性質不同。
- agent_def 的 template 管的是「這隻 agent 怎麼跑」，不放工作區內容；`ctl add` 不鋪檔。所以 `wf-init` 跟 template **不是同一類**，aos 目前沒有可接的機制。
- 今天樹裡 wf 規矩進 agent 的路只有一條：工作區裡有 `CLAUDE.md`／`AGENTS.md`，CLI 自己讀。

【意見】拆成兩塊，而且現在不造新機制：

- **骨架**（`template/`、`flavors/`、`wf-init`）繼續當「可導入的工作區骨架」，留在模板那個夾。導入照舊用 `wf-init.sh --target <工作區>`，在 `ctl add` 之前或之後跑都行。「aos 要不要長一個掛 agent 時順便鋪工作區的機制」是大方向，留給使用者（第 3 題）。
- **說明**（這套怎麼組織工作區、index 與 json 節點怎麼寫）若要給樹裡沒導入 wf 的 agent 看，才開一個知識庫 subject；內容要短，而且跟 `knowledge/docs/01`、`02` 已有的規則只能有一個出處。

### 3 分工

【事實】重疊與差異見上面兩張表。兩邊做法有一個根本不同：aos 的 index 是 `index_gen.py` 從檔頭**生成**的；模板的 index 是**手寫**的（description 寫「什麼時候讀」、派發表寫觸發說法）。8 KB：模板是硬規則（`--self`、連 `skills/` 都不豁免）；aos 這邊使用者的話是「只是推薦，不要訂死」「開發階段不設行數上限」，lint 也只查 `wf/workflows/`。

【意見】

- 模板內容、`wf-init`、通用檢查工具：wf-agent 維護。aos 專屬的（`codemap_gen`、`progress_board`、`metainfo_migrate`）留 aos。
- 檢查器合成一支，以模板那套為底（不依賴 aos、查得比較多、有 78 個測試），補上 aos 的 `--fs`；`index_gen` 是另一件事（生成不是檢查），留著當選用工具。合併排在掛進來之後，不擋路。
- `json_text.py`：正本放哪邊都可以，只要只有一份；要不要為了 8 KB 拆是[第 7 題](#要使用者裁的題)。
- 8 KB 硬上限不帶進 aos 的程式與 thinking（跟使用者已講的話牴觸）；模板在自己的夾裡照守。
- 值得回流成模板一部分的：`decide_page`（任何專案都有「一批題給人裁」）、`compact_reload`（放進給 Claude Code 的選用片段）、`index_gen`（選用）。`codemap_gen` 現在寫死 proto8 的夾名，要回流得先參數化。`progress_board` 太大又綁這個 repo 的用法，不回流。

### 4 通用性

【事實】使用者沒講過（見上）。現況：四個下游裡 ops-notes、gpt-soap 是樹裡的 agent，但工作區都不在 aos repo 裡；模板還支援 Windows Git Bash 與別家 AI 工具（`--redirect` 產 `GEMINI.md` 等），aos 只在 Linux／WSL 跑。wf-agent 自己的結論是真正綁 aos 的只有信件與定時器。

【意見】照 (a) 掛的話這題可以晚點裁——submodule 不會把通用這條路堵死。真正會受這題影響的是 v0.7 的寫法：kernel 維持「不依賴 aos」，綁 aos 的（mailbox、on_clock）收進 wf-agent 原本就規劃的 aos flavor。

### 5 時機與順序

前提（使用者原話）：「能愈快併入愈好，但不要因為趕工而喪失品質」。

【事實】aos 這邊近期會影響的：

- 今天 15:30 停樹重抄五夾（之後活樹的 `index_view` 才認字串陣列的 description）。
- repo 的 index 階段二（程式區 8 份）等停樹後才放；「index 以後怎麼維護」甲／乙還在等裁（[WAIT_USER](../../../../wf/WAIT_USER.md)）。
- C-42 放寬後「非 JSON 檔怎麼交代、跟 D1『內容走 json』與鐵律 6『導航留 md』哪句為準」還在等裁（[wait-user/01](../../../../wf/wait-user/01-要你裁的.md) 第 13 行）——這題直接決定模板 v0.7 哪些檔留 md。
- 沒查到知識庫或定義的結構近期要大改的計畫。

【意見】最短而穩的路（照 (a)）：

1. 使用者裁第 1、2 題（讀法與併法）。只有這步擋路。
2. wf-agent 備妥模板 repo（下面清單）。跟第 1 步平行做。
3. 掛進來：aos 一個 commit（`.gitmodules`＋指標）＋ dev-env 補一句 clone 要 init submodule。當天可完成。
4. 模板回寫 v0.7（在模板 repo 裡做，aos 動指標跟上）。
5. aos 自己的 `wf/` 換成新形態。

**最容易出品質問題的**：第 5 步最大（1480 個檔、大量客製、hook、活狀態檔，而且頂層 session 每天靠它運作），其次第 4 步（四個下游要升級）。這兩步都不是「併入」的必要條件；把它們跟第 3 步拆開，「快」與「不喪失品質」就不打架。若選 (b)，第 3 步本身就變成高風險（路徑、CI、自檢全要改）。

**併入前 wf-agent 可以先備妥的**（不管哪種併法都用得上）：

- 工作樹收乾淨（現在兩個檔沒 commit）；`add-routines-workflow` 分支的去留。
- 6 個沒 push 的 commit：submodule 的指標要指到 remote 上有的 commit，push 要使用者點頭。
- 檔案內容裡的家目錄絕對路徑與帳號名拿掉（`wf/knowledge/user.json` 那句）——進了 aos 要守這條。
- 測試在 WSL 跑綠（它的 SESSION-LOG 記著這台沒裝 pytest、還沒重驗）。
- 所有工具從「repo 不在最上層」的位置也跑得動（被掛成子夾時，`--self`、`--setup` 這類靠位置找根的要驗一次）。
- 今天第二輪改動的獨立稽核做完（它已在做）。
- 列一張「模板 repo 裡哪些東西綁 aos、哪些不綁」的表，給第 4 題用。

### 6 漏問的

【事實＋意見混列，各自標】

- 【事實】「這個workflow」有兩種讀法（見上），沒先問清楚，後面都是猜。
- 【事實】wf-agent 的工作區在 `/mnt/c`（Windows 磁碟）；aos 的 `install.sh` 對 `/mnt/` 底下的 repo 會警告「每個檔看起來都可執行」。掛成 submodule 後，aos 這邊的那份 checkout 在 `~/repo/aos` 底下，跟 wf-agent 的工作區是**兩份 checkout**——wf-agent 要繼續在原地做、還是搬到 aos 裡那份做，沒定。
- 【事實】push 授權：aos 的鐵律 2 是 push 要使用者本人說；submodule 是兩個 repo 兩次 push，順序錯了（先推 aos 的指標）別台會抓不到。
- 【事實】同一條 main 兩隻 agent（選 (b) 時）：aos 現在靠領地表（[CLAIMS](../../../../wf/workflows/dispatch/CLAIMS.md)）與 `git commit -- <點名檔>` 避免互踩，wf-agent 得照同一套。
- 【事實】下游四個導入怎麼升級（版本戳、`wf-init` 重跑會不會蓋掉客製）不因併入而消失。
- 【事實】`skills/`：eca 的 Skill 放哪（`.claude/skills/`）在 [wf-to-aos/02](../12/wf-to-aos/02-寄信給人與主session.md) 還開著；模板的 `--skills` 會往 `.claude/skills/` 產轉址，兩邊要對一下。
- 【意見】aos 的 `wf/` 與模板的關係要不要反過來：aos 的 `wf/` 不再是「v0.5 的一份舊導入」，而是模板的第一個試用者——這會改變客製回流的方向，是使用者的題。

## 要使用者裁的題

每題帶 wf-agent 的原問題（它說我們整理給使用者的話，它就不另外問）。建議都是線玄的意見。

**題 1｜「這個workflow…併入aos」是哪個意思**（wf-agent 沒問到，但後面都靠它）

- A 整個模板 repo 成為 aos repo 的一部分。後果：走題 2 選併法。
- B 這套做法與內容變成 aos 體系的東西，repo 本身照舊獨立。後果：不掛 repo；要做的是題 3（知識庫／鋪工作區）。
- 判準：你之後想在 `~/repo/aos` 裡直接看到、改到 `template/`、`flavors/` 嗎？想＝A。

**題 2｜併法**（wf-agent 第 1 點：「(a) submodule 掛在 ~/repo/aos 某處；(b) 整個搬進 aos repo 當一個子目錄；(c) 維持獨立 repo，aos 只在出廠時抄一份」）

- A submodule，掛 repo 根。後果：aos 多一個 commit；clone 要多一步 init；改模板是兩次 commit、兩次 push；活樹不受影響（不在五夾裡）。
- B 整個搬進來。後果：一個 repo 一次 commit；模板的 CI 與自檢要改寫；外面的專案要用得 clone 整個 aos；wf-agent 與 repo-aos 共用一條 main。
- C 維持獨立只抄。後果：今天就是這樣，不用做事；兩邊會漂。
- 判準：模板還要給 aos 以外的專案用＝A 或 C；一年內確定只有 aos 用＝B 也行；「改模板要兩次 push」你嫌煩＝B。建議 A。

**題 3｜進了 aos 之後它算什麼**（wf-agent 第 2 點：「知識庫的一個 subject…一包可導入的工作區骨架…還是兩者拆開？aos 現在有沒有『給新 agent 的工作區鋪一套初始檔案』的機制可以接」）

- A 只當可導入的骨架，照舊用 `wf-init`，aos 不加東西。後果：零工作量；新 agent 要 wf 得自己（或人）跑一次 `wf-init`。
- B 骨架照舊，另開一個短的知識庫 subject 講這套怎麼組織。後果：樹裡每隻 agent 都讀得到；多一份要跟 `knowledge/docs` 對齊的內容。
- C aos 長一個「掛 agent 時鋪工作區」的機制，`wf-init` 接進去。後果：新機制、要設計；現在沒有任何前例。
- 判準：一個月內會新掛三隻以上要帶 wf 的 agent＝考慮 C；否則 A 夠用。建議先 A，B、C 等玩出需要再說。

**題 4｜模板還要不要服務不在 aos 裡的專案**（wf-agent 第 4 點：「併入後模板還要不要服務不在 aos 裡的專案（使用者沒說）」）

- A 要。後果：kernel 不能依賴 aos，綁 aos 的收進 aos flavor；Windows 與別家 AI 工具的支援要繼續顧。
- B 不要，只服務 aos 裡的。後果：v0.7 可以直接用 aos 的工具（`index_view`、mailbox），寫起來簡單；ops-notes 等在樹裡的沒差，model_entry 這類不在樹裡的就停在舊版。
- 判準：你手上還有、或半年內會有「不跑 aos 但想用這套」的專案嗎？有＝A。選題 2 的 A 時這題可以晚點裁。

**題 5｜順序**（wf-agent 第 5 點：「先回寫模板 v0.7 再併、先併再改、或邊用邊併」）

- A 先掛進來（一個 commit），再在裡面回寫 v0.7，最後才動 aos 自己的 `wf/`。後果：最快看到「併入」；每步各自驗。
- B 先回寫 v0.7 穩了再掛。後果：掛進來的就是新版；「併入」晚幾天到幾週。
- C 邊用邊併。後果：最快，但 aos 的 `wf/` 會有一段新舊混用。
- 判準：照你「愈快愈好、不喪失品質」，A 兩邊都顧到。建議 A。

**題 6｜檢查工具留哪套、8 KB 要不要帶進 aos**（wf-agent 第 3 點：「檢查工具…要留哪一套、8 KB 檔案上限這類 wf 的規矩要不要帶進 aos…客製哪些你覺得該回流成模板的一部分」）

- A 檢查器合成一支、以模板那套為底；8 KB 只在模板夾裡守、aos 照你說的「只是推薦」；回流 `decide_page`、`compact_reload`、`index_gen`（選用）。
- B 各留各的。後果：不用合；同一棵樹兩支檢查器規則會慢慢不一樣。
- C 8 KB 也變成 aos 的硬規則。後果：aos 現有超過的工具（`codemap_gen` 16 KB、`index_gen` 14 KB、`index_check`、`json_text` 各 10 KB）與一堆 thinking 檔都要拆；跟你 10-09、11-11 的話牴觸。
- 建議 A。

**題 7｜`json_text.py` 要不要在上游（aos）就拆成兩支、每支 ≤ 8 KB**（wf-agent 前一封）

- 現況：10315 B；模板 repo 為了它的 8192 上限，抄過去後自己拆成 `json_text.py`＋`json_text_cli.py`，每次我們更新它要重抄再拆。線地估過切法：核心（parse／walk／fold／render＋命令列）約 150 行、`--setup` 約 50 行。
- A 上游拆。後果：它可以整支抄、不用再拆；代價是不再「單檔可抄」，兩支要同版。
- B 不拆。後果：aos 這邊維持一支；模板每次更新多一道手工。
- 判準：題 2 選 A 或 B 之後正本只會有一份，這題跟著「正本放哪邊、那邊守不守 8 KB」走；正本放模板＝拆，放 aos＝不必拆。

**題 8｜字串陣列是「清單」還是「一段多行文字」，要不要在 knowledge/docs/02 定判斷規則**（wf-agent 前一封）

- 現況：docs/02 只說字串陣列＝用換行接起來的一段。模板的 `wf-view` 印成 md 時要猜，它的規則：任一元素是空字串、或以 `- ` `* ` `#` `|` `>` `數字. ` 開頭、或陣列內有成對的 ``` → 當多行文字接起來印；否則印成清單；只有一個 ``` 開頭的元素不算。
- A 不定。後果：照你 11-13「AI可以隨便寫」；各家轉印工具自己猜，猜法可能不同。
- B 把這套猜法寫進 docs/02 當「印給人看時的建議判斷」。後果：兩邊工具一致；多一條要維護的規則。
- C 定寫法不定猜法：清單一律寫成物件陣列或別的形狀，字串陣列只表示一段文字。後果：不用猜；等於收緊你說的「隨便寫」。
- 判準：`index_view` 不受影響（它一律接成一行）；只有「json 印成 md」的工具在乎。現在這種工具只有模板的 `wf-view` 一支＝A 就夠，第二支出現再定。

**題 9｜「當路由／派發表用的那幾層可以不照 15 項門檻」，docs/01 要不要提**（wf-agent 前一封）

- 現況：docs/01 寫「資料夾裡超過 15 個東西才放 `_index.json`」，出處是你 11-12「如果有些東西太大，那就補…如果夠小，那其實也不用做看法了，直接讀就是了」。模板與 ops-notes 的路由線三層不管幾項都建，因為那份 index 就是派發表。
- A 補一句「門檻是下限的建議；拿 index 當派發表的層可以不管幾項都建」。後果：兩邊做法都算照規矩。
- B 不補。後果：條文照舊；模板那三層算是自己的例外，寫在它自己的 `decisions.json`。
- 判準：你那句講的是「太大才需要簡介」，沒有禁止小的夾放 index——A 只是把沒禁止的事寫明。

## 使用者裁定（11-13）

使用者 11-13 14:47 前後在頂層對九題的回覆，原話一整句：

> 「1.變成aos的東西。2.都可以。3.都可以(也可以都要)。4.不用。workflows repo仍在，只是幾乎不再更新。5.邊用邊併。6.8kb上限可帶入(但只限.md)，檢查工具不留。7.拆。8.不用。9.不用」

逐題對到選項（**這是調度者的讀法**，不是使用者自己選的代號）：

| 題 | 原話 | 讀成 |
|---|---|---|
| 1 讀法 | 「變成aos的東西」 | B：做法與內容變成 aos 體系的東西（配合題 4 那句「workflows repo仍在，只是幾乎不再更新」） |
| 2 併法 | 「都可以」 | 交給我們定 |
| 3 定位 | 「都可以(也可以都要)」 | 交給我們定；A、B、C 可以並行 |
| 4 通用性 | 「不用。workflows repo仍在，只是幾乎不再更新。」 | B：不用服務 aos 以外的專案；repo 留著、幾乎不再更新 |
| 5 順序 | 「邊用邊併」 | C |
| 6 檢查器與 8 KB | 「8kb上限可帶入(但只限.md)，檢查工具不留。」 | 兩處原本各有兩種讀法；14:53、14:56 使用者補了話，已裁，見下 |
| 7 `json_text.py` | 「拆」 | A：上游拆成兩支（線地施工中） |
| 8 字串陣列判斷規則 | 「不用」 | A：不定 |
| 9 路由層門檻 | 「不用」 | B：docs/01 不補 |

**題 6 的兩處（原本各有兩種讀法、標待確認；使用者 14:53、14:56 補了話，已裁）**：

- (a)「檢查工具不留」——使用者 14:53 原話：「檢查工具，wf/的那邊就完全不留」。
  - 調度者的讀法：模板那套（它的 `wf/tools/index_check*.py`、`wf-view`）完全不帶進 aos；aos 留自己的 `wf/tools/index_check.py`。
  - 另一種讀法（「wf/的那邊」指 aos repo 的 `wf/tools` 那支、那支不留）調度者已擺給使用者，他沒更正。
  - 原先列的「兩邊重疊的都不留」不成立。模板那套多查的（反引號引用、跟 `$ref`、忽略表）要不要補進 aos 這支，沒裁；線黃正在拿 wf-agent 的假綠案例測 aos 這支（結果檔會是同夾 `index-check-false-green.md`）。
- (b)「8kb上限可帶入(但只限.md)」——調度者問「是推薦值還是硬規則」，使用者 14:56 原話：「1.推薦。就是說你知道有拆檔工作流吧，要是AI啟動了這個工作流，他就會按照這個去做。這個就是只限於這個工作流的。」
  - 讀法：8 KB 是**推薦值**、**只限 `.md`**、**只在 AI 跑拆檔工作流的時候照它做**；平常寫檔不受它管，也不是 lint 的硬線。跟他 10-09、11-11 的話不牴觸。
  - 「拆檔工作流」在 aos 的 `wf/` 是 tidy（[wf/workflows/tidy](../../../../wf/workflows/tidy/README.md)，觸發說法含「太大要拆」；拆法在 [STRUCTURE「結構整理原則」](../../../../wf/STRUCTURE.md)）。

**題 2、3 的做法已獲同意**：調度者把下面重估的做法（一次抄進來當正本、舊 repo 凍結、先併組織原則那幾份）拿去問，使用者 14:56 同一句的第 2 點原話：「2.可以」。

**前提變了**：題 1＝B 加上題 4 之後，原本建議 submodule 的前提（模板還要給外面的專案用、所以要保住獨立的 repo）不在了。上面第 1 點與「一句話結論」裡的 submodule 建議作廢。

【意見】在新前提下重估（線玄的看法；題 2、3 使用者說都可以，仍由調度者與使用者定）：

- **內容怎麼進 aos**：一次抄進來當正本，舊 repo 凍結。不掛 submodule——repo 幾乎不再更新，掛著只多出 clone 要多一步、兩次 push、`git archive` 空夾這些代價，換不到東西。抄進來時記下來源 commit；歷史留在舊 repo，不用 subtree 帶。三個外部 skill 的 submodule 不跟過來（它們本來就不發給下游）。
- **抄到哪**：照題 3「也可以都要」分兩處。講「怎麼組織工作區、節點怎麼寫」的說明進知識庫（要跟 `knowledge/docs/01`、`02` 只留一個出處）；骨架與 `wf-init` 進 repo 裡一個不在五夾內的夾，先能用，之後要不要長成「掛 agent 時鋪工作區」的機制再說。知識庫那份在五夾裡，會隨停樹重抄進活樹，這正是要的。
- **邊用邊併的第一步**：先併最小、最不會壞的一塊——wf-agent 試點出來的組織原則（`wf/knowledge/structure.json` 與它 `$ref` 的幾份）。它本來就是 json 節點、不依賴別的檔，抄進來馬上有 agent 讀得到。之後每次只併一塊，併完那塊在舊 repo 標「已搬走」，不兩邊同時改。aos 自己的 `wf/` 換形態仍然排最後、一個工作流一個工作流換，不整批換。
- **檢查工具**：（寫這段時題 6 (a) 還沒確認；14:53 已裁，見上——模板那套不帶進來。）
- **wf-agent 之後的角色**：從「模板 repo 的維護者」變成「把內容搬進 aos 的那隻」——它最清楚哪些檔是流程、哪些是知識、哪些綁 aos。它的工作區現在是舊 repo；搬的過程要改 aos repo 的檔，照規矩得有領地（[CLAIMS](../../../../wf/workflows/dispatch/CLAIMS.md)）或由它備料、repo-aos 這邊的線落檔。搬完之後這隻留不留、改管什麼，是使用者的題。它原本的 v0.7 回寫計畫（模板出廠公共 index、開 aos flavor）在「repo 幾乎不再更新」之下不必做了，要跟它講。

## 給 wf-agent 的回信草稿（已寄 14:46，由調度者寄；寄出時還沒有上面的裁定）

> STATUS：DONE
> 標題：回「workflows 併入 aos」六點：事實、我們的意見、交給使用者裁的九題（全文在 repo 的結果檔）
>
> 全文：`~/repo/aos/proto8/thinking/2026-11/13/workflows-into-aos.md`（事實附指令與出處；意見都標了，方向由使用者定）。使用者的三句原話照你信裡的逐字收了：「以後這個workflow，應該會併入aos中。可能是submodule吧我猜。」「可以討論」「能愈快併入愈好，但不要因為趕工而喪失品質」。
>
> 1 併法。【事實】aos repo 現在沒有 submodule。活樹的複本與我們「乾淨複本跑全套」都用 `git archive <commit>`，它不帶 submodule 內容（實測：只留空夾、不報錯）；今天停樹抄的是 `proto8/` 的 `lib`、`templates`、`knowledge`、`py`、`kernel` 五夾。所以 submodule 掛在這五夾之外不會出事，掛在裡面活樹會拿到空夾。你的三個巢狀 submodule：aos 只做一層 init 就不會抓它們。家機的 aos 本身是另一個 repo 的 submodule，掛進來會變三層。你那邊現在有 6 個 commit 沒 push、工作樹兩個檔沒 commit——指標要指到 remote 上有的 commit。【意見】submodule、掛 aos repo 根。
>
> 2 算什麼。【事實】aos 沒有「給新 agent 工作區鋪初始檔案」的機制：`ctl add --ws` 只要一個已經在的資料夾；`templates/` 與 `agent_def new` 抄的是定義資料夾（agent 怎麼跑），不是工作區內容。知識庫現在只有 `aos/` 一個 subject，多庫＝另開資料夾、不登記。【意見】拆開：骨架照舊用 `wf-init` 導入；要不要另開知識庫 subject、aos 要不要長鋪工作區的機制，交使用者裁。
>
> 3 分工。【事實】你的 `index_check` 多查引用、`$ref`、忽略表、私有 index；我們的多一個 `--fs`。我們的 index 是 `index_gen.py` 從檔頭生成的，你的是手寫的。8 KB 在 aos 這邊使用者講過「只是推薦，不要訂死」「開發階段不設行數上限」。【意見】檢查器合成一支、以你那套為底補 `--fs`；8 KB 只在模板夾裡守；可回流的是 `decide_page`、`compact_reload`、`index_gen`（選用），`codemap_gen` 寫死 proto8 要先參數化，`progress_board` 不回流。
>
> 4 通用性。【事實】我們這邊搜不到使用者講過這點（搜了 `wf/`、`proto8/thinking`、`proto8/docs`，不含 archive）。交使用者裁。
>
> 5 時機。【意見】最短而穩：使用者先裁讀法與併法 → 你備妥 repo（平行）→ 掛進來（aos 一個 commit）→ 你在模板 repo 回寫 v0.7 → 最後才是 aos 自己的 `wf/` 換形態。最容易出品質問題的是後兩步，它們不必跟「掛進來」綁在一起。【事實】aos 這邊會影響你的：今天 15:30 停樹重抄後活樹的 `index_view` 才認字串陣列；「C-42 放寬後非 JSON 檔怎麼交代、跟『內容走 json』哪句為準」還在等使用者裁，這題決定 v0.7 哪些檔留 md；沒查到知識庫或定義結構近期要大改。
>
> 你現在可以先做的：工作樹收乾淨；內容裡帶帳號名的家目錄絕對路徑拿掉（`wf/knowledge/user.json` 的 `aos_peers` 那格）；測試在 WSL 跑綠；工具從「repo 不在最上層」的位置驗一次；稽核做完；列一張「哪些東西綁 aos、哪些不綁」的表。push 要使用者點頭。
>
> 6 漏問的。「這個workflow」有兩種讀法（整個 repo 進來／這套做法變成 aos 的東西），我們列成第 1 題給使用者；掛成 submodule 後你的工作區是留在 `/mnt/c` 那份還是搬到 aos 裡那份；兩個 repo 兩次 push 的順序；下游四個導入怎麼升級；`skills/` 與 eca 的 `.claude/skills/` 怎麼對。
>
> 交給使用者裁的（你不用另外問）：讀法、併法、算什麼、通用性、順序、檢查器與 8 KB，加上你前一封留的三題（`json_text.py` 要不要上游拆、字串陣列清單 vs 多行文字要不要定規則、路由層不照 15 項門檻要不要寫進 docs/01）。裁了我們再寄信告訴你。
