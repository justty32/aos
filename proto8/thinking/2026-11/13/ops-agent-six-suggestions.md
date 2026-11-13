# ops-agent 用了一天 aos 寄來的六點建議（11-13 評估＋查證，只讀沒施工）：六點的事實都查過（讀碼加暫存樹實測），兩個另問有確定答案，順帶抓到兩個 bug；留三題給使用者裁，附回信草稿

← [11-13 日索引](README.md)｜相關：[eca-a2a-notify](eca-a2a-notify.md)（第 1 點跟它的裁定連動）、[main-session-in-aos](main-session-in-aos.md)（第 5 點對照它的第四題）｜分檔：[01-原信](ops-agent-six-suggestions/01-原信.md)、[02-第1點](ops-agent-six-suggestions/02-第1點-hook看不到CLI工具.md)、[03-第2到5點](ops-agent-six-suggestions/03-第2到5點.md)、[04-第6點](ops-agent-six-suggestions/04-第6點-on_clock每天幾點.md)、[05-回信草稿](ops-agent-six-suggestions/05-回信草稿.md)

## 來由

`~/aos-home` 樹裡的 `ops-agent`（eca claude 身，做區網機器運維）用了一天 aos，寄來六點建議，自己說「對 aos 行為的判斷多半來自文件、沒有逐一實測」。原信逐字在 [01-原信](ops-agent-six-suggestions/01-原信.md)。調度者（頂層 `repo-aos`）要的是：每點事實對不對、歸哪一類、怎麼做，加一封回信草稿。

讀碼與實測橫跨 commit `d57f21367`～`909b076ad`（別的線同時在改 proto8；HEAD 從 `d57f21367` 走到 `909b076ad`；引到的程式檔與知識庫檔這段時間都沒被動到，a2a 線新增了 `lib/agent/cli_a2a.py`、`cmd/aos-eca/aos_eca/midturn.py`）。實測用 claude 2.1.323、模型 haiku，全在 `~/code/ops-try-1113/`。

## 兩個另問的確定答案

1. **eca 閒著沒有新信時，on_clock 照樣定時檢查**（讀碼＋實測）。eca 的 loop 每 0.3 秒叫一次 `aos-eca-turn`，它第一件事就是看時鐘，跟有沒有信無關。知識庫 `body.json` 那句「each turn」寫得不準。不檢查的只有三種時候：aos 正在等 CLI 答一封 queue 的信、睡著、沒有時鐘。ops-agent 的試點可以做。細節在 [04](ops-agent-six-suggestions/04-第6點-on_clock每天幾點.md)。
2. **aos 起的 claude 會讀工作區的 `.claude/settings.json`，裡面的 hooks 會生效**（實測；條文 P-43 本來就寫了，知識庫沒寫）。跟 aos 的 `--settings` 並存、`dontAsk` 模式下：hook 回 deny＝不跑；hook 回 ask＝**畫面開著時畫面上跳確認框等人按**，畫面沒開（非互動）時等於拒絕。`dontAsk`＋`--allowedTools` 底下 Bash 沒有任何確認。細節在 [02](ops-agent-six-suggestions/02-第1點-hook看不到CLI工具.md)。

## 六點一覽

| 點 | 它說的事實 | 證據 | 分類 | 做法一句 |
|---|---|---|---|---|
| 1 hook 看不到 CLI 的工具 | 對 | 讀碼＋實測 | 文件缺；要不要做橋是設計題 | 補文件、教它用 CLI 自己的 hook（現在就能用）；橋的三種收法給使用者裁 |
| 2 索引沒有檢查工具 | 對 | 讀碼 | 新功能 | `index_check` 規格寫好了；建議先讓 ops-agent 自己寫成 aos 工具、跑順再收 |
| 3 `index_view` 收字串形 | 一半對：字串形只印鍵、那句話被丟掉，不是「照樣印出」 | 實測＋讀碼 | 文件缺（補一句） | `tools/index_view.json` 加一句；不加警告（C-88、代定 I14） |
| 4 信的留底進不了工作區 | 對；另外寄出的信完全沒留底 | 讀碼＋實測 | 新功能（小）；現在有避法 | `keep` 收檔名、收寄都能留；避法是 `aos-mailbox read --keep -j >> 檔` |
| 5 沒有工作區的跨 session 清單 | 對 | 讀檔 | 不做 | 跟今天 main-session-in-aos 第四題的結論同向，沒有要補的 |
| 6 on_clock 缺「每天幾點」範例 | 範例確實沒有；「這棵樹沒有 AOS_CLOCK」不對（樹有，是人開的畫面沒拿到） | 讀碼＋實測＋唯讀看現場 | 文件不準＋文件缺＋一個 bug | 改三處文件、加範例（已寫好實跑過）；修畫面的環境變數 |

## 順帶抓到的兩個 bug（原信沒提、查的時候撞到）

1. **人開的畫面沒有 `AOS_CLOCK`**（也沒有 `AOS_KERNEL`、`AOS_LLM_KERNEL`）：畫面裡的 claude 與 `aos-mcp` 繼承的是開畫面那個人的殼，不是這隻 proc 在 daemon 底下的環境。後果是同一隻 agent 畫面一開，`peek_clock`、`clock_register` 就回 `ClockMissing`。ops-agent 說「這棵樹沒有 AOS_CLOCK」就是撞到這個。修法與證據在 [04](ops-agent-six-suggestions/04-第6點-on_clock每天幾點.md)。
2. **`cli.json` 的 flags 裡寫 `--settings` 會被靜默蓋掉**：CLI 只認命令列上最後一個 `--settings`，aos 自己的接在後面。`lib/agent/cli_cfg.py` 的註解寫它「可重複，不擋」，跟實際不符。修法併在第 1 點的乙。

## 建議的施工順序

1. **純文件，可以馬上做**（一人一兩個小時；都在 `proto8/knowledge/aos/` 正本，改完要重抄到 `~/aos-home/knowledge` 才到 agent 手上）：
   - `body.json#/brain_tools` 的 Hooks 句（第 1、6 點各改半句）；
   - `cli/eca.json` 加 `cli_hooks` 一段；
   - `tools/index_view.json` 加一句（字串形不算條目）；
   - `me/self_hook.json#/clock` 加三句、加 `daily` 一段、`#/examples` 加一行；
   - `clock.json#/choose` 加一行、`world.json` Time 段加一句；
   - `templates/eca-claude/README.md` 權限段加指路與 hook 範例。
   每一處的原句與新句都寫在各分檔的「文件怎麼改」。
2. **回信**（[05](ops-agent-six-suggestions/05-回信草稿.md)）：文件改完、三題裁完就能寄；它現在就能用的避法都在信裡。
3. **修 bug 1（畫面的環境變數）**：一人半天。會動 `lib/agent/cli_screen.py`、`cli_mcp.py`，跟 a2a 那條線改的是同幾個檔，排在它後面或交給同一條線。
4. **第 1 點乙（定義帶 CLI 設定＋修 bug 2）**：一人半天，同樣碰 `cli_screen.py`／`cli_print.py`，跟第 3 步一起做。
5. **第 4 點 `keep` 收檔名**：一人半天，獨立，隨時可排。
6. **第 2 點 `index_check`**：看裁定；照建議就是等 ops-agent 的版本。

## 要使用者裁的（3 題）

### 第 1 題：要不要讓 aos 的 hook 管到 Claude Code 自己的工具（Bash 這些）？

背景（白話）：現在 aos 的 hook 只看得到 aos 自己給的工具；agent 用 Bash 連正式主機，aos 這層完全不知道，也沒有人按確認。實測發現不用改 aos 就有辦法：在工作區放一份 Claude Code 自己的 hook 設定，它會照讀，還能在畫面上跳確認框等你按。

- **甲：不做，只把這個辦法寫進文件、附範例。** 後果：今天就能用；規矩放在工作區，同一個資料夾裡的所有 session（包含你自己開的 Claude Code）都會吃到；aos 的 `self_hook` 管不到它。
- **乙：甲，再加一小步——讓 agent 的定義可以自帶 Claude Code 的設定。** 後果：多半天工；規矩可以跟著那隻 agent 走、不影響同資料夾的別人；順便修掉一個「寫了卻被悄悄蓋掉」的坑。
- **丙：做完整的橋，Bash 每次執行都先過 aos 的 `before_tool`。** 後果：一隊一天到一天半；規矩一套寫法，agent 能自己用 `self_hook` 加；但只對 claude 身有效（codex 沒有對應的接點）、要替 aos 的 hook 新增「問人」這種回答、現有沒設條件的 hook 會變成每次 Bash／讀檔都被叫到；而且跟「eca 的內建工具歸 CLI 自己管」（P-43）方向相反。

建議：**乙**。甲解了眼前的痛，乙補上「跟著定義走」。丙照現有原則推不出要做；只有在你想要「不管哪種身，規矩都寫在 aos 這一層」時才值得。

**裁定：乙**（使用者 11-13 對這三題的回覆，逐字：「都按照建議」）。施工見 [ops-fixes-施工結果](ops-fixes-施工結果.md)。

使用者 11-13 補的一段（在 ops-agent 畫面上直接對它說的，經 ops-agent 來信轉述；逐字）：「我覺得沒差，eca的bash工具，就是讓eca自己的機制擋。頂多加個hook，在eca跳yes/no的時候幫忙接住，寄信給特定目標處理。這個之後再做，這有點麻煩。我覺得現在就是勇敢一點，就全面開放。後面再來做這塊。」——所以乙只做機制：範本預設不帶任何會擋 Bash 的 hook、不改預設權限（全面開放不變）；「eca 跳 yes/no 時由 hook 接住、寄信給特定目標處理」是之後的另一件事，今天不做。

不管選哪個都要知道：這道閘擋得住「順手就做了」，擋不住存心繞過（它有 Bash，可以改設定檔）；確認框只有接上畫面的人按得到，`say`／`chat` 按不到——這跟你今天對 a2a 說的「真的有要的話，就自己open進去說」是同一件事。

### 第 2 題：索引檢查工具現在就做進出廠工具包嗎？

背景（白話）：索引是 agent 自己寫的「這裡有什麼」的筆記，檔案搬走了筆記不會自己跟上。ops-agent 想要一支工具幫它對一遍，它說會先自己寫。

- **甲：現在就由我們做進 index 包。** 後果：一人半天到一天；所有 agent 馬上都有；規格是我們想的，還沒被真實的幾十份索引用過。
- **乙：先請 ops-agent 把它那支寫成 aos 工具的形狀、掛在自己身上用，跑順了我們再收進出廠包。** 後果：我們現在不花工；規格先被真的用過；別的 agent 要晚一點才有。
- **丙：不做，各家自己寫。** 後果：零成本；同一件事可能每個工作區各寫一遍。

建議：**乙**。這正是你 11-07 說的路（先讓 agent 做，再慢慢變成函數）。

**裁定：乙**（使用者 11-13，逐字：「都按照建議」）——索引檢查工具先讓 ops-agent 自己寫，我們現在不做。

### 第 3 題：信要不要能留一份到工作區？

背景（白話）：agent 之間的信現在讀完就刪，要留也只留在 agent 自己的執行狀態夾（stack），不進 git、人不好找。ops-notes 原本的信是進 git 的紀錄。現在有土辦法（一行指令把信印成一行一封接進檔），但寄出去的信沒有任何留底。

- **甲：做——收信、寄信都能指定一個工作區的檔，留一行。** 後果：一人半天；預設行為不變（不指定就照舊）。
- **乙：只做收信那一半。** 後果：工少一點；紀錄只有一半（看得到別人寄來的，看不到自己回了什麼）。
- **丙：不做，文件寫明土辦法。** 後果：零成本；寄出的信還是沒留底，要 agent 自己另記。

建議：**甲**。

**裁定：甲**（使用者 11-13，逐字：「都按照建議」）——收信、寄信都能指定一個工作區的檔留一行。施工見 [ops-fixes-施工結果](ops-fixes-施工結果.md)。

## 照原則已定、不用問的（代定，可翻案）

- 第 3 點：格式就是物件形（C-88「值用物件」），字串形不當條目收、`index_view` 不加警告（代定 I14、C-88「不檢查」）；只補文件。
- 第 5 點：不做，沿用 main-session-in-aos 第四題的結論。
- 第 6 點：on_clock 不內建牆上時間，對人的時間由 handler 自己看牆鐘（N-01、C-56）；沒時鐘＝不跑照現況（11-11 clock-hook 的施工代定），只補文件。
- 兩個 bug 照 bug 修，不另立題。
- 第 4 點留底檔的格式代定 jsonl（跟 `self_history` 的 keep 同一種）。

## 未決／沒驗的

- 畫面上已經開著的 claude 會不會即時吃到改過的 `.claude/settings.json`：沒測（文件草稿保守寫成「下次起 CLI 才生效」）。
- 子 agent（Agent 工具叫出來的）跑 Bash 時工作區 hook 有沒有被叫：沒測，只確認了主對話。
- 確認框等人的期間 a2a 訊息擠進來會怎樣：沒測，建議列進 a2a 那條線的冒煙測試。
- `clock_register` 給 `daemon` 繞過 `AOS_CLOCK` 的避法：照知識庫的寫法，沒實測。
- bug 1 只在現場行程上看到（唯讀），沒在暫存樹重現一次「人開畫面」的完整流程。
- codex 身的對應做法（它自己的核准設定）這次沒看。

## 測試留下的東西

- `~/code/ops-try-1113/`：`cc/`（hook 測試夾與 log）、`idx/`、`mb/`、`unit/`、`tree/`（暫存樹，daemon 已用 `aos-daemon-ctl shutdown` 收掉）、幾支小腳本。都沒刪（邊界不准刪檔）。
- `~/.claude/projects/` 多了幾段 haiku 測試對話；`~/.claude.json` 多了 `~/code/ops-try-1113/cc` 這個夾的信任紀錄（互動測試要過信任那一關）。
- 測試中 `bob`（haiku）接到巡檢信、找不到巡檢筆記，自己跑了唯讀的 `find /` 約兩分鐘（會掃到 `/mnt/c`），收掉暫存樹才停；沒有寫入任何東西。這也是第 1 點「沒有任何確認」的現成例子。
- 沒碰 `~/aos-home` 的任何檔與行程（只讀了狀態檔與 `/proc` 裡的環境變數）；repo 裡只新增本檔與同名夾，日索引 README 沒加列（不在領地）。
