「小工作室的個人筆記」調查報告留底（11-22，線 studio-notes-1122 調查、studio-notes-1122-doc 搬進 repo；只調查、沒改程式、沒動活樹）。

# 小工作室的個人筆記：調查（11-22）

← [2026-11-22](../README.md)｜相關：[公司體制發想（公司體制-1122）](../公司體制-1122/README.md)、[工作區與 _stack 規劃（工作區與stack-1122）](../工作區與stack-1122/README.md)

**使用者體驗那一輪還沒做**（怎麼聯絡特定 agent、怎麼看它的筆記與資產；使用者用 VS Code 看、命令行也可以）。

## 使用者原話（2026-11-22，逐字）

語音輸入；「eca aso kb」＝eca-aos-kb，「地下人」＝底下的人。

- 「可以先考慮小工作室啦，比如最近一個比較新的需求就是說你知道eca aso kb ，他住了一些東西讓我會跟他說比說日期不要有，然後原話這塊就是例外，就這種事情就很適合在記記在他的筆記裡面這樣子然後以後他身上部門主管的之後他又可以分給地下人去看」
- 「這塊就走正規調查流程」
- 「然後可以的話考慮他使用者體驗」
- 「好比說我要怎麼去聯絡特定的代理人然後只是說我要怎麼去訪問特定代理人的筆記或是看到他的資產我常用的是vs Code，命令行也可以」
- 「vs Code我只是拿來看的」

## 調查員交回的報告全文（逐字，沒改寫）

以下是調查員最後一則回報的原文，從開場白到出處清單整段照貼。

---

我讀完了規矩卡、知識庫（me、compact、body、definition、agents、subagent、self_hook、kits），也看了三個地方：`wf/ws/`、`~/aos-home` 裡 eca-aos 和 eca-aos-kb 的 stack（只讀），以及 eca-claude 範本的 `cli.json` 和 `compact_hook`。過程中沒有寫檔，也沒有 commit。

# 調查報告：小工作室的「個人筆記」（線 studio-notes-1122）

## 結論

筆記放在地盤裡（`wf/ws/<上層>/<名>/notes.md`）是對的：它進 git、換機會跟著走，而且只屬於那一隻 agent。**現在缺的是指路的人。** eca-aos-kb 的 `system.txt` 沒提到 `notes.md`，壓縮之後讀回來的是頂層的交接。所以下次換對話或 `/clear` 之後，它多半不會想到去讀筆記。

## 現況：交代的事能放哪

| 放哪 | 誰讀得到 | 什麼時候讀 | 換機跟不跟 | 出處 |
|---|---|---|---|---|
| stack 的 `system.txt` | 只有它自己 | agent-fsm：每次問腦前重讀；eca claude：每輪附在 Claude 自己的系統文字後面 | 不跟。它在 stack 裡，要等 `_stack` 換機那次 commit | `knowledge/aos/me/self_system.md`、`body.md#/System text, history`、`templates/agent-fsm/brain.py` 115–117 行 |
| 定義夾（範本的 `system.txt`） | 用同一份定義的每一隻 | 同上 | 跟（定義在 repo 裡） | `definition.md`。eca-aos-kb 沒有自己的定義夾，直接跑範本（`procs/eca-aos-kb/exec.json`） |
| `AGENTS.md`、`wf/` 規矩 | 工作區在 repo 的每一隻 eca（Claude Code 從 `CLAUDE.md` 讀進來） | 開場；壓縮後由 `compact_reload.sh` 貼回 `user.md` 全文 | 跟 | `templates/eca-claude/cli.json`（`--setting-sources project,local`）、`.claude/settings.json` |
| `wf/HANDOFF.md` | 一樣是每一隻 eca，subagent 也讀到 | 壓縮後貼第一條 | 跟 | `wf/tools/compact_reload.sh`、`user/02` |
| `wf/progress.json` | 頂層 | 開場掃一次；HANDOFF 是空的時候，壓縮後也會貼 | 跟 | `AGENTS.md`、`compact_reload.sh` |
| stack 的 `handoff.md` | 它自己 | agent-fsm 每壓一次就往後加一段；eca 壓縮後由 `compact_hook start` 印出最後約 8000 字 | 不跟 | `me/compact.md`、`templates/eca-claude/compact_hook` 的 `LIMIT`、`context_wrap` 的 `wrap_text` |
| Claude 自動記憶 | 工作區在同一個資料夾的所有 Claude Code，四隻 eca 加上人開的 session，共用一份 | 開場（Claude Code 自己的行為，這次沒實測） | 不跟 | `~/.claude/projects/-home-lorkhan-repo-aos/memory/MEMORY.md`，現在是 0 B |
| aos history（`history.jsonl`） | 它自己 | 一直在對話裡，壓縮後只剩摘要，`/clear` 後就沒了 | 不跟 | `body.md` |
| 壓縮的 hook（`before_compact`、`after_compact`） | 它自己 | 壓縮那一刻可以補一段字回對話（agent-fsm 是 `after_compact` 的 `restore`；eca 只能在 `before_compact` 給 `restore`） | 看 hook 掛在哪 | `me/self_hook.md#/Hook events` |

另外兩件和這題直接有關的事：
- 系統文字不能 include、也沒有變數，送出去的就是整份（`kits.md`）。所以「筆記讀進來」只有兩條路：指一條路讓它自己讀，或者把全文貼進去。
- agent-fsm 範本的 `system.txt` 已經寫了「Keep notes in your workspace」，但那句講的是工作進度，不是使用者交代的規矩。

## 做法

**A. 地盤放 `notes.md`，`system.txt` 寫一句指路（我推薦先做這個）**
- 怎麼做：上層開 subagent 時，在它的 `system.txt` 寫一句「你的筆記在 X，開工前和壓縮後都讀；使用者交代你的事照格式加進去」。範本也可以加一句通用的。
- 好處：不用改程式，今天就能做；指路那句每一輪都看得到；內容要用時才讀，不佔對話。
- 代價：要靠 agent 自己守。eca 預設沒有 `self_system`，自己改不了指路那句，只能靠上層或人改。
- 會出問題的地方：壓縮後的提醒叫它去讀「工作區規矩說的交接檔」。這個 repo 的規矩指向 `wf/HANDOFF.md`，那是頂層的，所以它會讀錯檔。

**B. A 加上 hook 自動貼**
- 怎麼做：eca 的 `compact_hook start` 多印一段筆記；agent-fsm 用 `after_compact` 的 `restore` 補回來；開場時用 `before_queue` 把筆記接在第一封信前面。
- 好處：不靠自律，最穩。
- 代價：要改範本程式，還要有一份機器讀得到的「這隻的地盤在哪」，現在沒有。每次壓縮都會多貼一段字。
- 會出問題的地方：如果和 `compact_reload.sh` 疊在一起，每次壓縮要貼 30 KB 以上。

**C. 筆記全文直接放進 `system.txt`**
- 好處：一定看得到；要分給底下的人，上層用 `subagent system` 抄一段過去就好。
- 代價：不進 git；長了每一輪都吃 context；每改一次就讓提示快取失效一次；agent 自己改不了。

**D. 規矩跟著「地方」放，不跟著「人」放**
- 怎麼做：「知識庫不寫日期註記」這類條文寫在知識庫的寫法說明裡，個人筆記只留自己學到的做事步驟。
- 好處：以後換別隻 agent 來改知識庫，也看得到這些規矩。
- 代價：跟使用者說的「記在他的筆記裡」字面不同；還要再決定寫法說明放哪。

## 「分給底下的人」與衝突

- **上層派工時抄進任務書。** 現在就是這樣做的：eca-aos 把四條原話貼進了給 kb 的信。好處是清楚，代價是漏抄就沒有。
- **下層自己往上讀。** 地盤是照掛的層級嵌套的，所以上層筆記的路徑算得出來。可以約定筆記裡分一段「給底下的人」，下層只讀那一段。aos 的 json 工具能直接讀 md 的段落，例如 `json_get` 讀 `../notes.md#/給底下的人`。這樣也避免上層自己的事（例如派工規則）被下層拿去誤用。
- **hook 自動帶。** 等 B 做了再一起考慮。
- **衝突怎麼裁（建議）：**
  1. 使用者原話比轉述準。
  2. 同一題，越新的越準。
  3. 上層「給底下的人」那段，比下層自己的推論準。
  4. 下層發現衝突時回報上層，不自己裁。這跟規矩卡的「原文為準」是同一個精神。

## 筆記的形狀與怎麼不讓它越長越長

- **用 md。** 使用者 11-21 說新寫的預設用 md；規矩卡第 6 條的 1 KB 門檻只是建議。用標題分段，json 工具就能一段一段讀。
- **每條寫原話（逐字）、日期、出處和怎麼照做。** eca-aos 轉來的話標「轉述」。語音輸入的字照錄，另外附一句讀法。
- **設上限。** 例如跟規矩卡一樣 8 KB。現在 kb 的筆記約 5.4 KB。
- **超過就整理：**
  - 對每一隻都成立的條文，升到 `user.md` 或規矩卡，筆記裡留一句指過去。
  - 做事步驟搬進 `wf/public` 的做法頁。
  - 被推翻的條文，學 `user/01` 的做法收進「已被取代的原話」，或直接刪掉，舊的看 git。
  - 原話不改寫。

## 跟 `user.md`、規矩卡怎麼分工

判斷方法是問一句：「換一隻做別的事的 agent，也要守這條嗎？」
- **要守**：寫進 `user.md`（原文），再濃縮進規矩卡。例如語言、push、說話方式。
- **只在做這隻的工作時才要守**：寫進個人筆記。
- **任何碰那個領域的人都要守**（例如凡是改知識庫的都不寫日期註記）：這就是 D 的情況，要請使用者決定放哪。

## 要問使用者的題目

1. **規矩記在「人」還是「地方」？**
   - (a) 只記在人的筆記：最貼近你說的，但別隻 agent 改知識庫時看不到。
   - (b) 只記在領域的寫法說明：誰改都看得到，但不是「他的筆記」。
   - (c) 兩邊都放：原話放人的筆記，領域檔指過去。最完整，但要維護兩處。
2. **誰負責讓它讀？**
   - (a) `system.txt` 一句指路：現在就能做，靠自律。
   - (b) hook 自動貼：穩，但要改範本程式。
   - (c) 先 a，以後再加 b。
3. **底下的人怎麼拿到上層的筆記？**
   - (a) 上層派工時抄。
   - (b) 下層自己讀上層筆記的「給底下的人」那段。
   - (c) 兩種都要。
4. **誰能改某隻的筆記？**
   - (a) 只有本人。
   - (b) 上層也能改下層的。
   - (c) 誰都能，就是現在地盤規矩第 5 條「不是牆」的狀態。
5. **筆記上限多大、誰決定把一條升到全域？**
   - (a) 本人提議、你拍板。
   - (b) 上層直接搬。

## 邊緣狀況

1. kb 的 `system.txt` 現在沒有指到筆記。`/clear` 或開新對話之後，它就不知道有這份筆記。
2. subagent 的工作區也是 repo，所以壓縮後也會被 `compact_reload.sh` 灌進 `user.md` 全文和頂層 HANDOFF，合計約 37 KB，可能把頂層的交接當成自己的。這是從設定推出來的，沒實測。
3. 四隻 eca 共用一份自動記憶。只要有一隻寫了，其他隻和人開的 session 都會讀到；而且它不跨機、不進 git。
4. `system.txt` 和 stack 的 `handoff.md` 不進 git，換機要等 `_stack` 那次 commit。agent-fsm 的 `handoff.md` 只會往後加，越來越長。
5. 語音輸入的錯字（「eca aso kb」「地下人」）照錄進原話的話，以後的人看不懂，要附讀法。
6. 同一條規矩在全域和筆記各寫一份，日後會不一致。
7. 子 agent 改名或換上層時，嵌套路徑會變，指路那句要跟著改。
8. 上層和本人同時改一份筆記時，commit-request 的 claim 會讓其中一方卡住。
9. 整理筆記時可能誤刪或改寫原話。
10. 同一個角色開好幾隻（共用一份定義或 kit）時，要決定共用一份筆記還是各寫一份。
11. pi 和 codex 讀系統文字的時機不同：codex 只在開新對話時讀，所以指路那句改了不會馬上生效。
12. Claude Code 會在讀到子資料夾的檔時順便讀那裡的 `CLAUDE.md`（Claude Code 自己的行為，這次沒實測）。如果有人在地盤裡放 `CLAUDE.md`，上層讀下層地盤時也會被讀進去，而且跟「頂層只留兩個入口」的佈局不合。

result: 調查完成：筆記放 `wf/ws/<上層>/<名>/notes.md` 可行而且會跟著換機，但現在沒人指路（eca-aos-kb 的 `system.txt` 沒提到筆記，壓縮後讀回的是頂層交接）。報告列了四種做法（推薦先在 `system.txt` 加一句指路）、5 題要使用者決定的題目和 12 條邊緣狀況。

主要出處：`/home/lorkhan/repo/aos/wf/ws/eca-aos/eca-aos-kb/notes.md`、`/home/lorkhan/aos-home/.stack/procs/eca-aos-kb/system.txt`、`/home/lorkhan/repo/aos/wf/tools/compact_reload.sh`、`/home/lorkhan/repo/aos/proto8/templates/eca-claude/compact_hook`、`/home/lorkhan/repo/aos/proto8/templates/eca-claude/cli.json`、`/home/lorkhan/repo/aos/proto8/knowledge/aos/me/compact.md`、`/home/lorkhan/repo/aos/proto8/knowledge/aos/me/self_hook.md`
