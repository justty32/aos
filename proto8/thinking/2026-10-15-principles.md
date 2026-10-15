# 2026-10-15 兩條總原則：巢狀只管自己這一層、錯誤只處理自己的

← [討論紀錄](README.md)｜落成：[C-52、C-53](../CONCEPTS/01-設計理念.md)｜先前的標準：[proto7 設計原則](../../proto7/notes/principles.md) 第 9、10 條（10-04）、[proto7-2 契約卡](../../proto7-2/notes/component-contracts.md)（職責／前置條件／保證／明確不管）

## 原文（10-15，照貼）

「都按照推薦。我這邊的原則是：盡量保持簡單，要考慮到在巢狀的情況下，進行乾淨的切分，也就是只管自己這一層，因爲後續複雜起來的時候，巢狀會很容易出現，我會希望當多層巢狀出現的時候，我可以用單一原則，或是單一概念，只去拿最上層的進行處理，下層的東西會被很乾淨的切割，在我處理上層的時候可以盡量不管下層的事情，或是要管的時候，心理有一把尺，有一個可以參照的原則，我可以相信這個原則會貫穿和在整個巢狀重複。然後一樣，關於錯誤處理那塊也是按照先前的標準，各功能單元僅處理自己的錯誤，對於別人的錯誤，我們可以分爲：你丟給我的時候就應該是正常的（之後可以延伸爲我不管(默認正常)，或是我會在入口處檢查並處理輸入），或是我交出去的時候我會保証不出錯，或是提前把可能的錯誤列出來。相關錯誤路徑處理也是盡量濃縮成少數幾個，讓整個程式的行爲(這裏說的和程式本身的功能有關，但更多是關於"在程式執行該功能時出了問題後"的行爲)複雜度減少，這塊後續也可以納入kernel評估中」

（開頭「都按照推薦」答的是前一輪的推薦，由主控另行處理，不在本檔。）

同晚補充（照貼）：

「都同意。」（答下面盤點的第 1、3、8、9 條）

「都按照推薦。」（答「正常退出」盤點的 S1～S5；同晚，經主控轉達）

「按照推薦」（答下面「新的待定」A～C，另加一條：被訊號停掉不用 128＋N、一律退 1；同晚，經主控轉達）

「喔剛剛那個我補一句：結束碼0代表正常退出，我這邊的定義(我希望盡量靠近unix傳統)，關於"正常退出"的定義，就是該功能單元中，其行爲有如當初的設計構想、功能介紹、文檔走(當然，走的是定義中正常退出的那條路)，並且是考慮過的狀況的一部分(有被預料到，且是正常的)，一個更簡單一些的定義是不會在stderr噴東西。」

「當然，不在stderr噴東西，不代表結束碼就必須爲0。你當然可以把錯誤輸出到別的地方。」

## 決定

- 兩條寫成設計理念 **C-52**（巢狀：只管自己這一層）、**C-53**（錯誤：只處理自己的錯；對別人的錯三種姿態；錯誤路徑濃縮）。
- 「先前的標準」＝proto7 設計原則 9、10：KISS、錯誤分類同類走同一分支（＝濃縮錯誤路徑）、很多東西默認正常、誤用不歸組件管、先定義組件功能（要求呼叫者保證什麼＝入口、它保證什麼＝出口、明確不管）。C-53 接著它寫，不另起爐灶；proto8 已有的 N-18（錯誤歸類）、N-20、N-29、N-43、N-38、「卡死不防護」都是它的實例，條文不動、只補指向。
- 盤點第 1、3、8、9 條照推薦（「都同意。」），10-15 晚照做完（程式＋lib 文件＋N-43）：
  - **1** 每層只退 0／非 0 說自己，下層的碼只放 stdout／stderr 的 JSON，不沿用下層的結束碼。做法：loop、daemon 只退 0／1（設定錯、窗缺原本 125、最後一次 aos_inst 出錯原本沿用它的 127 等，全改 1；stderr 一份自己的錯誤，代號照 `last_error` 的）；被訊號停掉 128＋N 照留（Unix 傳統，原盤點 N-43 第 7 條已判「合」）。寫進 N-43。fsm、閘門、inst、proto8-1 tasks 不在這次範圍（見下「新的待定」）。
  - **3** kernel2 判官錯濃縮成一條「判官這拍沒給合法答案＝這拍用規則」，連錯計數交給判官格自己，拿掉「等人歸零」。做法：`aos_kernel.py` 拿掉 `max_fails` 設定與 state 窗的 `judge_fails`、stdout 的 `fails`／`on_rules`；`judge_error` 留著（只記原因，答對清掉）；補位（backfill）不是錯誤路徑，照留。demo kernel2 第 2 段改成「每次都退回規則」。
  - **8** think 連錯時自己寫好要交的錯，done 格不讀 think 的 `work/think-fails.json`。做法：think 第 halt_after 次自己寫 cwd 的 `ret.json`＝`{"error"}`、回 `next: halted`；`halted` 從各表的 `states` 拿掉、只留在 `end`（N-40：next 不在表裡、在 end 裡＝fsm 結束），不經 done；done 只寫 `{"reply": 最後一句}`。demo 六張表（fsm、clerk、boss、judge、painter、brush）一起改。
  - **9** halted 時 loop 退 0 維持：照 C-52，loop 只說自己這一層（它照設計拍完、正常結束），agent 的錯在 `ret.json`；lib agent 寫明「看 ret.json」。
- 「正常退出」的定義寫進 N-43：照設計、文檔走正常那條路、是預料到的狀況；簡化判準＝不在 stderr 噴東西。反向不成立：退非 0 時錯誤可以寫到別處（文件說好的地方）。
- 「納入 kernel 評估」記成待定（[NORMS 待定 【kernel】](../NORMS/08-待定.md)）。
- 「正常退出」盤點 S1～S5 照推薦（「都按照推薦。」），10-15 晚照做完：
  - **S1 警告不開例外**：stderr 不放警告（N-29 改寫，`aos_cli.warn()` 拿掉）。逐一處理：ctl 窗壞檔／不見了／讀不了（`CtlBad`／`CtlMissing`／`CtlReadFailed`）→ loop、daemon 的 state 窗 `last_warning`（讀到好的清掉；N-08 改寫）；daemon 的 `PolicyFailed`／`RestartFailed`／`TableWriteFailed`／收工寫不了子項 ctl 的 `WriteFailed` → daemon state 窗 `last_warning`；`ScanFailed`／`ReplyFailed`（控制資料夾）原本就記 `last_error`，拿掉 stderr；信箱回信寫不進去 `ReplyFailed` → kernel（兩種）state 窗 `last_warning`；`aos_tree` 的 `TreeCycle`／`TreeDepth` 沒窗→寫在輸出（停住的 ref node 帶 `stop`、print 行尾標出），退 0；`ExtraInput`（aos_cli、兩顆腦）→ 入口錯、退非 0；**`StateWriteFailed`** 沒地方記（就是窗本身壞了）→ 改成錯：loop／daemon 收工、stderr 一份、退 1（同 N-19 窗缺）。`ToolCallsSkipped` 確認已不存在（10-15 tool 格一拍跑完全部 tool_calls 時已拿掉）。
  - **S2** loop 不再把 aos_inst 的 stderr 轉到自己的 stderr（`_Tail` 不 echo），只記 state 窗 `last_error`；daemon 的子 loop stderr 本來就落 `work_dir/N/err.json`。
  - **S3** 閘門維持轉交 target 的 stderr 與碼，`aos_gate.py` 檔頭、lib kernel.md、N-43 寫明「閘門透明」。
  - **S4** `stderr_inherit` 維持，aos_inst 檔頭、lib inst.md、N-26、N-43 寫明是寫單子的人自選、那時 stderr 是子程式的。
  - **S5** 述詞（`aos-not`、`aos-if` 的條件）在 N-34 寫明是 N-43 的 Unix 式例外（同 `test`／`false`／`grep`），N-43 也列進例外。
- 驗證：proto8 lib 測試 168 → 171 個全過（新增 state 窗寫不了＝錯、策略格錯記 `last_warning` 不寫 stderr、回信寫不進去記 kernel state 窗；判官連錯改成「每次都問、每次退回規則」）；ctest 全綠；fsm、kernel、kernel2、paint demo 假腦實跑正常。
- 新的待定 A～C 照推薦（「按照推薦」），同晚照做完：
  - **結束碼只剩 0／1**（N-43 改寫：「0 正常、非 0 有錯，沒了」，aos 的程式說自己的錯一律 1，不再用數字分種類，是哪種錯看 stderr 的 `code`）：aos-inst 自己的 127／126／125 → 1（`exit_code()` 拿掉，信箱回信也不再帶 `exit`）；fsm 自己的 125 → 1；閘門自己的錯（含 kernel 回錯、kernel 那邊 aos_inst 起不來）→ 1；兩種 kernel、aos_tree、`aos agent fsm` 的 125、格庫用法錯的 2 → 1；proto8-1 tasks 自己的錯（Usage、TARGET 不對、aos_inst 起不來、結果讀不到）→ 1。
  - **被訊號停掉一律 1**（原 128＋N）：loop 退 1、哪個訊號記在 state 窗與結束那份的 `signal`（新欄位，沒有＝null）；閘門、tasks 沒窗＝stderr 一份 `Signaled`（msg 帶號碼）、退 1。**daemon 收到 SIGTERM／SIGINT 照舊退 0**：那是它照設計的收工路（文件寫明），原本就不是 128＋N；`signal` 一樣記在 state 窗與結束那份。
  - **例外只有兩種，寫進 N-43**：透明轉交別人的碼（閘門＝target 的碼；tasks 的 seq／par／if 回子程式的碼，同 sh 的 `&&`）、述詞（aos-not、aos-if 的條件）。aos-inst 結果與 exit 檔的 `code`（被訊號停掉的子程式是 128＋N）是子程式的碼、是資料，不是退出碼，照留並在 N-30 寫明。
  - B（state 窗寫不了就收工）、C（`last_warning` 只留最近一件）維持。
  - 驗證：proto8 lib 171 個、proto8-1 22 個測試全過；ctest 全綠；fsm、kernel、kernel2、paint、proto8-1 demo 假腦實跑正常（proto8-1 demo README 的樣本輸出 125 → 1）。

## 結論：已有的實例

- **只管自己這一層**：fsm 只管「狀態→inst」（C-49、N-36）；內層 fsm 不繼承外層設定（N-40）；inst 的結果只說子程式、自己不開窗（N-30）；暫停、停止、拍數交給拍它的 loop（N-39）；daemon 只靠兩扇窗管子 loop（N-28、lib daemon）；frame 找名字照 `parent` 往上找，綁定只到那一層（C-46；畫家 demo 自定點 2）。
- **錯誤三姿態**：(a) 入口默認正常＝N-18、N-20、卡死不防護、誤用不處理；入口檢查＝N-08（ctl 壞檔維持上一次）、N-29 `ExtraInput`、N-19（窗缺就不跑）。(b) 出口保證＝N-05（先寫暫存再改名）、N-12 半份不算。(c) 事先列出＝N-38 列出 fsm 出錯的幾種、lib 各頁的錯誤代號表。
- **濃縮**：N-43 結束碼只 0／非 0；N-29 錯誤只有一種形狀；N-38 出錯一律 phase 不動、原樣往外報。

## 未決：跟兩條原則不完全合的地方（AI 盤點，附推薦，等使用者看）

（第 1、3、8、9 條已定、已做，移到上面「決定」。）

2. **daemon `add` 先驗 inst**（原 h15）：daemon 替兩層下的 inst 做入口檢查。推薦：維持（入口檢查是姿態 (a) 的一種），但說明寫成「daemon 驗的是它收的那份 loop 設定」，驗不到的交給子 loop 自己報。
4. **fsm 讀格的 stderr**（N-38 把格 stderr 最後一份錯誤放進自己的 stdout）：fsm 往下看了一層。推薦：可接受（只轉述、不處理），寫明「轉述不解讀」。（loop 這次改成不轉 aos_inst 的 stderr；fsm 是把錯放進自己的 stdout 行、不是 stderr，跟 S2 不同件。）
5. **巢狀格不宜寫表上靜態 next**（N-40）：上層得知道那格是不是另一個 fsm。推薦：維持，當成格作者的責任寫在 lib fsm.md 即可。
6. **綁定不往子 agent 傳**（[LiteLLM 實跑](2026-10-15-litellm-live.md) 問題 1）：照 C-52 推薦「子 agent 一律用自己的定義，要換就由呼叫方在工具綁定裡明給」，不訂繼承。
7. **`ask_judge.py` 寫死 `parent`**（同上問題 2）：一層寫死另一層的位置。推薦：照 boss 靠 frame 綁定。（10-15 已改成收定義資料夾當引數。）
10. **文件小矛盾**：NORMS 總則檔頭寫「之後可能併」，已對齊「維持分開」（本次修）。lib `ctl-state.md` 的 fsm 列、`directives.md` 的 exit 檔說法另一個 agent 同晚已照 N-39、N-30 修好。

## 「正常退出」（N-43）盤點的查證（已照 S1～S5 處理完，留紀錄）

- 退非 0、沒寫 stderr、錯誤在文件說好的地方：fsm 格出錯（退 1，錯在這拍 stdout 行的 `error`，N-38）——合；收到訊號 128＋N（loop、閘門、tasks）——Unix 傳統，合；loop／daemon 最後一次 aos_inst 出錯——照第 1 條改成退 1＋stderr 一份自己的錯。
- **halted（第 9 條）查證**（照第 8 條改完後重看）：think 第 3 次連錯時自己寫 `ret.json` 的錯、回 `{"next": "halted"}`、退 0、不寫 stderr；halted 只在 `end`＝fsm 結束那拍、退 0；loop 的 `stop_on_end` 看到就停、退 0、stderr 空——**符合新定義**。前兩次連錯：think 退 1＋stderr（合）、fsm 退 1、錯在 stdout 行（合）、loop 只記 `last_code`、不寫 stderr。

## 新的待定（這次做的時候發現）

A～C 已定（見「決定」）。daemon 收到訊號照舊退 0（照設計的收工路）——若使用者要連 daemon 也一律 1，改一行加測試即可。
