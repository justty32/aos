← [工具大開發時代](../README.md)｜[notes 索引](../../README.md)｜計畫 [plan.md](../plan.md)｜評分 [axes.md](../axes.md)｜上一隊 [T5](../t5/README.md)｜審查 [任務書](review-task.md)／[回報](review-astra.md)

# 第二波 A 隊（造工具）報告（2026-09-24）

**一句話**：例子 1（把 workflows 導入空專案）從 T5 的「模型 17～25 次、22～34 萬 token、141～183 秒」降到 **6～7 次、3.0～3.6 萬 token、42～54 秒**，3/3 都 done、Done when 11/11。
靠兩件事：`wf_fill` 照事實表機械填佔位；導入工人模板 `importer` 只裝導入用得到的 10 支工具，工具表少一半多。
另外做了造工具三個指令（`tools new／test／wrap-py`）、`route try`、mail 列題目。wrap-py 包出來的工具裝給工人、派工信叫它用，模型一次 bash 都沒寫。
基底：main `eacfcc2`（開工時 `12d67d4`，收尾前 rebase）。測試 81 檔 2265 條全綠（數字見 §9）。

## 1. 做了什麼

| 項 | 做了什麼 | 在哪 |
|---|---|---|
| A `tools new NAME` | 生工具包骨架：範例工具檔、可執行程式（本體留 TODO）、`_common.py`（base 逐字副本）、`config.json`、`cases.json`（四條固定案例）、README。生的包直接 `tools test` 全過、`tools add` 後 `check` 過。不寫 `_jail`＝預設關牢 | `lib/aos_agent_tools_dev.py`、[tools-dev.md](../../../spec/aos-agent/tools-dev.md) |
| B `tools test NAME\|DIR` | 照工具檔描述自動生案例：正例一條、每個參數型別錯一條、每個必填缺一條、「不是物件」一條，加包裡 `cases.json` 的固定案例。在拋棄式假家裡跑，**預設用 aos-jail 關牢**（只掛一個拋棄式 workspace、網路關）；沒 bwrap 或 `--no-jail` 才直接跑，第一行寫明「沒關牢」。印每支描述的 token 粗估（> 300 註明資源軸扣分）。`--args` 單跑一次 | 同上 |
| C `tools wrap-py FILE.py` | `ast` 靜態讀，不 import、不執行。有型別註解的頂層函式包成工具包，印收／拒收／跳過表。支援 str／int／float／bool／list／dict／Literal／Optional。拒收：沒註解、`*args`／`**kwargs`、positional-only、自訂類別、async、decorator、非頂層。產的 `run` 在執行時照簽名驗型別；例外回 `PythonError`（不噴 Traceback）；回傳不能 JSON 回 `ResultNotJSON`。不寫 `_jail`，也不需要額外掛載 | 同上；fixture [wrap_fixture.py](../../../lib/test/fixtures/wrap_fixture.py) |
| D `wf_fill` | 照事實 JSON 機械填 `{{…}}`，對不上的不猜、列出來附原因。一律刪〔模板說明〕。`drop_examples` 刪認得出範圍的範例，`drop_template_rows` 刪第一格是佔位的表格列。輸出列出：填了哪幾條（事實＝值 → 檔:行）、還剩什麼、沒用到的事實。跟 `wf_init` 同一把專案鎖。`wf_doc` 讀 IMPORT.md 的開頭提示、`wf_init` 的 next 都加一句 wf_fill | `tools/wf/_fill.py`、`wf_fill`、[wf README](../../../tools/wf/README.md) |
| E 工具表瘦身 | 選「**模板拆兩種**」：新增導入工人 `importer`（§3） | `templates/importer/`、[templates.md](../../../spec/team/templates.md) |
| F `aos-team route try "一句話"` | 印判決：命中哪條、抓到的群組、會跑的完整指令／會派給誰、落穿原因。不跑、不開單、不寄信、不寫 route.log。例句沒全過會多一行提醒 | `lib/aos_team_route.py`、[route.md](../../../spec/team/route.md) |
| G mail 小改 | 等人回答的題目也一題一行：`lead → 人  ASK  q-0001  等你回答（aos-team answer q-0001 "…"）  問：…`。答完那行先顯示 `已答「…」`。`--task` 連「落穿給領隊、開出這張單的那封人寫的信」一起列，挑法跟 score 的起點相同。`aos-team start／stop` 郵差、心跳那兩行開頭標 `郵差:`／`心跳:` | 新檔 `lib/aos_team_mail.py`（分派表改指它）、`lib/aos_team.py` |
| 派工信 | 驗收那行改成：「檔案在」「含某段字」驗收員會查，不用先 read 確認；有同名工具的檢查器可以先跑。真跑看到工人交件前會 ls／read 好幾輪自己確認 | `lib/aos_team_task.py` 的 `render_handoff` |
| 文件 | proto5 README 指令表與 templates 列、lib README（兩個模組、三個測試檔）、tools README、wf README（wf_fill 一節）、spec/aos-agent README、spec/team 的 cli／route／templates、examples/routes.json 導入規則的目標提 wf_fill、教程 08 加 route try 與 wrap-py 兩段、code-map | |

隊員分工：A／B／C 由一位 Opus 隊員做（含規範頁與 56 條測試），其餘隊長做。

## 2. 真跑

**環境**：模型 LiteLLM `localhost:4000` 的 `deepseek-chat`。kernel 池 default 3 顆、llm 2 顆，全程不變（跟 T5 一樣）。團隊在 `~/tmp/w2a-try/`，跟別隊分開。
每次都刪掉整個團隊資料夾和 `p` 重建，`p` 只放 T5 那份 `facts.json`。名冊比 T5 多一個 `importer-1`。
門房規則用 T5 的 `routes-try.json`，只改兩處：導入規則 `assignee` 換成 `importer-1`；目標加「再用 wf_fill 照 {facts} 填佔位，剩下的照它列的處理」。

### 正式（最後的程式與人格，3 次）

| 次 | 結果 | Done when | 模型呼叫（領隊／導入工人） | 秒 | token | score |
|---|---|---|---|---|---|---|
| ex1-r4 | done | 11/11 | 7（0／7） | 54 | 35,585 | L3 R4 F5 |
| ex1-r5 | done | 11/11 | 6（0／6） | 48 | 30,223 | L3 R4 F5 |
| ex1-r6 | done | 11/11 | 6（0／6） | 42 | 29,829 | L3 R4 F5 |

**跟 T5 比**（T5 正式三次：17／23／25 次、21.8～33.7 萬 token、141～183 秒）：

- 模型呼叫：少約 70%，目標是「5 次以內」，差 1～2 次（見下）。
- token：少約 87%。
- 秒數：少約 70%。

r6 的六步：

1. `read facts.json` 和 `wf_doc IMPORT.md` 一起叫
2. `wf_init`
3. `wf_fill`（帶 `drop_examples`、`drop_template_rows`）
4. `wf_residue` 和 `wf_lint` 一起叫
5. `team_say DONE`
6. 最後一句回話

「5 次以內」差的那一步是**最後一句回話**：寄完信模型還要回一句，這輪才會結束，這一次省不掉。r4 多的那一次，是 residue 和 lint 分兩次叫。

### 參考：調人格與 wf_fill 輸出的過程、別的組合

| 次 | 組合 | 結果 | 模型 | 秒 | token | 看到什麼、改了什麼 |
|---|---|---|---|---|---|---|
| ex1-r1 | importer 初版人格 | done 11/11 | 10 | 75 | 58,328 | wf_fill 叫兩次（第一次沒帶選項，看了「沒用到的事實」才帶）；交件前 ls＋read 三個檔自己確認 → 人格寫明「先 read 事實檔、事實說刪範例就第一次帶選項」「檔案在、含某段字驗收員會查」 |
| ex1-r2 | 改人格 | done 11/11 | 8 | 60 | 43,316 | 還是 read 兩三個檔確認有沒有填對 → 派工信的驗收那行寫明不用 read 確認 |
| ex1-r3 | 改派工信 | done 11/11 | 8 | 63 | 41,585 | 仍 read 兩個檔 → wf_fill 輸出加「填了哪幾條：事實＝值 → 檔:行」，模型看得到填在哪 |
| ex1-w1 | **一般工人 worker-1**＋wf_fill（工具表 20 支） | done 11/11 | 14 | 99 | 129,364 | 只加 wf_fill、不換模板：比 T5 少約 40% 次數、60% token；工人照舊 grep、read、edit、bash 自己確認一輪。**拆模板那一半的功勞在這裡看得出來** |
| wrap-r1 | 驗收②：wrap-py 產的 `words` 包（`count_words`）裝給 worker-1 | done 2/2 | 4 | 30 | 18,582 | 見下 |

**驗收②（wrap-py 裝給工人、模型沒寫 bash）**：

1. `aos-agent tools wrap-py lib/test/fixtures/wrap_fixture.py --only count_words --name words`
2. `tools test ./words`：7 條全過，關牢跑。
3. `tools add ./words --target …/worker-1`：`tools ls` 顯示 `count_words … jail`。
4. 門房規則 `數 README.md 的字` 開單給 worker-1，目標是「用 count_words 工具數…寫進 words.txt」。
5. 模型四步：`count_words(README.md)` → `write(words.txt)` → `team_say DONE` → 回話，**沒有 bash**。驗收 2/2（檔在、含 `tomatoes`）。

**時間花在哪**（score 拆的，r4～r6 平均，牆上約 46 秒）：

- 等模型 7 秒
- 跑工具 1.4 秒
- 等收件 6 秒
- 等驗收 10 秒
- 其他（排隊與郵差）約 22 秒

每輪模型與工具之間的排程等待還在（T5 §7 給 P 隊的那條）。步數少了，這一塊也跟著變小。

## 3. 工具表瘦身：選哪種、為什麼、前後多少

**選「模板拆兩種」**：新增 `importer`（導入工人），一般的 `worker` 不動。

| 候選 | 為什麼沒選／選了 |
|---|---|
| 派工信決定裝哪幾包 | 要在派工時改工人的 `info.tools`，這件事郵差（B 隊領地）或 aos-agent 的 tick 才做得到。而且同一個家前後輪的工具表會變，記憶裡舊的工具呼叫對不上。牽動太大，這一波不做 |
| 描述精簡 | base 七支的描述是 tools-base 真跑調過的，大家共用（coder、lead、reviewer 都裝）。改短有行為風險，省的也有限：最長的 grep 才 303 token |
| **模板拆兩種** ✔ | 照 catalog 共同規則 3「角色只裝用得到的」。只動我的領地（templates），一般 worker 照舊什麼都能做。代價：名冊要多一列 `importer-1`、門房的導入規則 `assignee` 要指它；閒著時多一個停車的 agent（停車不佔 cpu） |

**importer 裝什麼**：
- base 的 read、edit、ls
- wf 的 wf_doc、wf_init、wf_fill、wf_residue、wf_lint
- ask_human、team_say

不給 bash、write、grep、find、notes、files、compact_me、board、wf_table。

**量出來的**：

| 量什麼 | 改前（T5 的 worker） | 改後 worker（多了 wf_fill） | 改後 importer |
|---|---|---|---|
| 工具數 | 19 | 20 | 10 |
| 工具表字元（`aos-agent context` 同一算法） | 11,996 | 12,729 | 5,582 |
| 工具表 token 粗估 | 約 3,008 | 約 3,196 | 約 1,409（少 53%） |
| 第一問的 prompt_tokens（LiteLLM 回報的真數字：人格＋工具表＋派工信） | 4,247 | 4,466 | 2,442（少 43%） |
| 一件導入總 token（端點回報加總） | 21.8～33.7 萬 | 12.9 萬（1 次） | 3.0～3.6 萬 |

總 token 降得比每問的 prompt 多，因為兩件事相乘：每問少送約 1,800 token，而且問的次數從 17～25 降到 6～7。

## 4. 六軸自評（每支工具一列；照 axes.md §4 工具欄）

量法：
- 單支工具的秒數與 cpu 用 bash `time` 量。
- 描述 token 用 `aos-agent context` 同一算法。
- S 軸跑不到 10 次不給分：這裡的 10/10 指單元測試的固定輸入。崩潰恢復有測的才給 5。

| 工具 | L | S | R | F | H | B | 依據 |
|---|---|---|---|---|---|---|---|
| `tools new` | 5 | 4 | 5 | 5 | 5 | 5 | 不叫模型；0.04 秒、cpu 0.04 秒；錯誤都是 aos-agent 格式；暫存資料夾＋rename，但沒有 KILL 測試＝4；只寫 `--out` 底下的新資料夾 |
| `tools test` | 5 | 4 | 4 | 3 | 4 | 5（關牢）／3（`--no-jail`） | 88 條案例關牢 2.4 秒（cpu 0.9 秒）→ R4、F3；在拋棄式假家跑，關牢只掛拋棄式 workspace、網路關。H4：一條一行 PASS／FAIL，但自動案例的名字（`type:path`）要看規範才懂。拿它跑內建包會誤判幾條（§7） |
| `tools wrap-py`（產生） | 5 | 4 | 5 | 5 | 5 | 5 | 0.04 秒；不 import、不執行；拒收表逐條有測 |
| wrap-py 產的工具（跑） | 5 | 4 | 5 | 5 | 4 | 5（關牢） | 每次呼叫起一個 python，約 30 毫秒；`count_words` 描述約 97 token；牢裡只看得到專案。H4：模型看到的描述來自 docstring，寫得差描述就差 |
| `wf_fill` | 5 | 4 | 5 | 5 | 4 | 4 | 0.03 秒；描述約 188 token；再跑一次什麼都不動（有測）；只寫根目錄內的 `.md`、跳過符號連結、暫存＋rename、持專案鎖。B4：會改專案裡很多檔（這就是它的工作），不碰信任資料。H4：規則寫死在 `_fill.py` 開頭，要看 README 那節才知道為什麼沒填 |
| `route try` | 5 | 4 | 5 | 5 | 5 | 5 | 只讀，不寫任何檔（有測：route.log、outbox、input 都沒動） |
| `mail`（題目、落穿信） | 5 | 4 | 5 | 5 | 5 | 5 | 只讀；補了 T5 H 軸扣分的「反問在 mail 看不到」 |
| `importer` 模板（團隊，例子 1） | **3** | —（3/3 次過） | **4** | **5** | 4 | 3 | L：6～7 次，落在 6～15＝3（T5 是 2）。R：3.0～3.6 萬＝4（T5 是 2）。F：42～54 秒＝5（T5 是 4）。H、B 沿用 T5 的判斷：B 還是 3，逃逸測試是 B 隊的事 |

**團隊總評**（例子 1，不加總）：最低兩軸從 T5 的 L2、R2 升到 **L3、R4**。
L 要到 4（2～5 次）還差「寄完信後那句回話」和「先讀事實檔」這兩步，已經是模型本身的輪次，工具這邊能省的都省了。

## 5. 我代裁的（附預設，翻案就回這條）

1. **瘦身選「拆模板」**，而且 `worker` 不動、`examples/routes.json` 的導入規則仍派給 `worker-1`。importer 要人自己在名冊加一列、把規則改指它。理由：教程 08 的名冊只有三人，改預設會連帶改教程與新手流程。這題列成 §6 第 1 題。
2. **importer 不給 bash、write、grep、notes、compact_me**。導入用 wf 工具就夠。沒有 bash，模型就不會退回手抄檔案（T5 ex1-try2 的 51 次就是這樣來的）。
3. **wf_fill 的名字對應規則寫死三層**：一樣 → 同義詞表 → 包含。每層恰好一條才填，兩條以上一律不填。同義詞表只收 workflows 模板真的出現過的寫法。事實值寫「今天…」會換成今天的日期（照事實表的時區）。這是 facts.json 原本就這樣寫，機械換掉比叫模型查日期省一輪。
4. **wf_fill 的範本列一律不填**（第一格整格是佔位的表格列，例如 INDEX 的 `{{src/ 或主要產出目錄}}`），即使有事實對得上。理由：事實「其他頂層目錄＝沒有（佔位列刪掉）」會被當成值填進路徑格。要刪就帶 `drop_template_rows`。
5. **`drop_examples` 只刪認得出範圍的兩種**：上方表格裡「（範例）」開頭的列、「下面…」指的 `###` 小節。`## 時機分區` 標題留著、底下清空。其他〔導入判斷〕不動，列給模型。
6. **wf_fill 的〔模板說明〕一律刪**，沒有開關。IMPORT.md 第 4 步本來就是「讀過刪整段」。
7. **mail 搬到新檔 `aos_team_mail.py`**，`aos_team_post.cmd_mail` 沒刪。`aos_team_post.py` 是 B 隊領地，我不改它；分派表改指新檔。舊函式現在沒人叫，B 隊可以順手刪。
8. **mail 的 `--json` 多一種紀錄 `kind: "ask"`**（多帶 `question`、`answer`、`state`）。讀它的程式要略過不認得的 kind。
9. **派工信的驗收那行改寫**（全部工人都會看到，不只 importer）：「檔案在」「含某段字」不用先 read 確認。這一步本來就是驗收員做的，寫明省模型輪次。
10. 署名已照 repo 規定改為 Fable 5.1。
11. 隊員代裁（細節在 [tools-dev.md](../../../spec/aos-agent/tools-dev.md)）：
    - `tools test` 多一個 `--tool T`（只測一支）；包裡有好幾支時，`--args` 一定要配它。
    - 三個造工具指令給 `--target` 算用法錯。
    - `cases.json` 多一格 `files`：跑之前先把檔寫進拋棄式 workspace，讀檔的工具才測得到。
    - wrap-py 收 `typing.List`／`Dict`／`Optional`／`Union[X, None]` 和字串註解。
    - 產的 `run` 叫函式前先 cd 到工作根目錄；函式自己 print 的改走 stderr。
    - `aos-jail` 沒有 `--tool` 參數：程式寫在 `--` 後面。

## 6. 要使用者拍的（一題）

| # | 題目 | 預設 |
|---|---|---|
| 1 | 導入這種事要不要**預設**交給 `importer`？要的話：`examples/team.json` 與教程 08 的名冊加一列 `importer-1`、`examples/routes.json` 的導入規則改派給它。好處：例子 1 模型 6～7 次、3 萬 token，一般 worker 是 14 次、13 萬。代價：團隊多一個成員（閒著停車不佔 cpu），教程多一行 | **先不改**：importer 是選用的，教程照舊三人。你看過本報告的數字再決定 |

## 7. 給別隊

- **B 隊**：`aos_team_post.cmd_mail` 現在沒人叫（mail 改由 `aos_team_mail.py` 做），要刪就刪。
- **所有做工具包的**：拿 `tools test` 跑現有內建包，有幾支的自動案例會誤判：
  - `md_section`、`note`：必填跟著 `op` 變，自動正例只給 schema 的必填，會回 BadArguments。
  - `wf_init`、`wf_table`：先看專案狀態，型別錯回的不是 BadArguments。
  - `team_say`、task 包：沒 `aos-team init` 過一律 `ConfigInvalid`，蓋過參數檢查。

  這不是 tools test 壞了：自動案例假設「先驗參數、再做事」。要讓這些包也全過，可以給它們各放一份 `cases.json`，或把參數驗證挪到最前面。這一波沒動。
- **P 隊**：每輪模型與工具之間的排程等待還是約 3～4 秒（§2「其他」22 秒／6 步）。

## 8. README／索引加了的列

- proto5 README：
  - 指令表加 `tools new／test／wrap-py`、`route try`，mail 那列寫新功能。
  - templates 列加 importer；tools 列加 wf_fill。
- lib README：`aos_agent_tools_dev.py`、`aos_team_mail.py` 兩個模組；`test_team_w2a.py`、`test_tools_wf_fill.py`、`test_agent_tools_dev.py` 三個測試檔；總數改成 81 檔 2265 條。
- tools README：wf 那列、〈自己做一個工具包〉開頭一段。wf README：六支表、wf_fill 一節、錯誤代號。
- spec/aos-agent README：tools-dev.md 一列。spec/team：cli.md 兩列、route.md 一段、templates.md 一段。
- notes README：本報告一列。教程 08：route try、wrap-py 兩段，start 那行、反問那句各補幾個字。code-map：兩個模組。
- `wf/WAIT_USER.md`：第 34 條。

## 9. 數字

- **測試**：81 檔 2265 條全綠（第一波收尾 78 檔 2177 條；這隊新增 88 條）。最後一次全套 test_team_beat 偶發紅一條（已知，P／T2 在修），單跑 18 條全過。
  - `test_agent_tools_dev.py` 56 條
  - `test_tools_wf_fill.py` 17 條
  - `test_team_w2a.py` 15 條
  - `test_tools_wf.py` 改 2 處（工具名單、描述預算）
- **工具描述**：wf_fill 733 字元約 188 token；wf 包六支描述合計 1,093 字元（上限 1,500）。wrap-py 產的描述在 36～97 token 之間，`tools new` 範例約 80 token。
- **人格**：importer 約 572 字。
- **astra 審查**：見 [回報](review-astra.md)，必修修法見 §10。

## 10. astra 審查：必修 12 修 12

| # | 問題 | 怎麼修 |
|---|---|---|
| M1 | `tools test` 的 `cases.json` `files` 會沿著前一支工具在 workspace 建的符號連結，由牢外的測試器寫到主機別處 | 從 workspace 一層層開資料夾、不跟符號連結、最後的檔 `O_NOFOLLOW`、有硬連結也不寫；寫不進去那條記 FAIL（隊員修，下同） |
| M2 | `--force` 發布時新包 rename 失敗，舊包也被刪 | 新包就位才刪備份，失敗改回舊包；暫存名帶 pid，下次寫包前清掉死掉那次的殘渣（只剩備份就改回正式名），清了什麼印 stderr |
| M3 | 包名 `config`、`cases`、`wrap` 會讓必要檔互相蓋掉 | 建檔清單有重複路徑就 `BadName`，寫任何檔之前擋 |
| M4 | 工具輸出沒上限、逾時後收尾沒期限 | stdout／stderr 各只留最後 1 MB；逾時殺整個行程群組、最多再等 5 秒；背景子孫握著管子最多再收 2 秒；殺不掉照實寫；暫存家一定刪 |
| M5 | 「沒關牢」跑完才說 | 跑任何程式之前先印 stderr；表頭先印、每條跑完就印一行 |
| M6 | `if` 區塊裡的函式被當成頂層收 | 只收 `Module.body` 直接的函式；`if`／`for`／`try`／`with` 裡的拒收並說原因 |
| M7 | 函式丟 `KeyboardInterrupt` 還是噴 Traceback | 叫使用者函式的邊界接 `BaseException`，一律 `PythonError`；遞迴太深的回傳也算 `ResultNotJSON` |
| M8 | `drop_examples` 會一路刪到下一個 `##`，連後面的正式小節一起刪 | 只刪「下面 N 段」緊接的 N 個同級小節；沒寫段數、或小節不夠 N 個就不動 |
| M9 | 第一格 `{{甲}} {{乙}}` 被當成「整格一個佔位」的範本列 | 第一格要恰好一個 `{{…}}`、外面沒別的字 |
| M10 | 一個字完全一樣也不填；某層不只一條像它時，還會拿表格第一格去猜 | 兩個字的下限只給「包含」那層；某層不只一條就停。`wf.json` 描述改成 "only unambiguous name matches" |
| M11 | mail 的落穿信挑法跟 score 不同 | 抽成 `aos_team_score.lead_letter()`，score 的起點和 mail 共用 |
| M12 | 信的時間沒時區時 `mail --task` 會丟 TypeError | 時間一律走 score 的 `when()`（沒時區的當本機） |

建議做了 2 條：
- S3：`mail --follow` 題目答完會再印一次。
- S4：規範寫明 mail `--json` 題目那行的形狀。

S1（跑之前核對原檔 sha256）、S2（「包含」那層改成只列候選）記在這裡，沒改。
修完後再跑例子 1 一次（ex1-r7）：done 11/11，模型 6 次、29,792 token、42 秒，跟正式三次一致。
