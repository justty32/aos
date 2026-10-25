# 2026-10-15 兩條總原則：巢狀只管自己這一層、錯誤只處理自己的（深夜加：KISS 最高原則）

← [討論紀錄](README.md)｜落成：[C-56、C-52、C-53](../docs/CONCEPTS/01-設計理念.md)｜先前的標準：[proto7 設計原則](../../proto7/notes/principles.md) 第 9、10 條（10-04）、[proto7-2 契約卡](../../proto7-2/notes/component-contracts.md)（職責／前置條件／保證／明確不管）

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
  - **9** halted 時 loop 退 0 維持：照 C-52，loop 只說自己這一層（它照設計拍完、正常結束），agent 的錯在 `ret.json`；lib agent 寫明「看 ret.json」。照第 8 條改完後查證：halted 那拍 think 自己寫 `ret.json` 的錯、退 0、不寫 stderr，fsm 結束、loop 的 `stop_on_end` 停、退 0、stderr 空——符合「正常退出」的定義。
- 「正常退出」的定義寫進 N-43：照設計、文檔走正常那條路、是預料到的狀況；簡化判準＝不在 stderr 噴東西。反向不成立：退非 0 時錯誤可以寫到別處（文件說好的地方）。
- 「納入 kernel 評估」記成待定（[NORMS 待定 【kernel】](../docs/NORMS/08-待定.md)）。
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

- **只管自己這一層**：fsm 只管「狀態→inst」（C-49、N-36）、不讀格的 stderr（N-38）、沒結束就回 `next: null` 所以外層不必知道它是 fsm（N-37、N-40）；內層 fsm 不繼承外層設定（N-40）；inst 的結果只說子程式、自己不開窗（N-30）；暫停、停止、拍數交給拍它的 loop（N-39）；daemon 只靠兩扇窗管子 loop、子項裡面不驗（N-28、lib daemon）；frame 找名字照 `parent` 往上找，綁定只到那一層，agent 不知道工具內部（C-46；畫家 demo 自定點 2）。
- **錯誤三姿態**：(a) 入口默認正常＝N-18、N-20、卡死不防護、誤用不處理；入口檢查＝N-08（ctl 壞檔維持上一次）、N-29 `ExtraInput`、N-19（窗缺就不跑）。(b) 出口保證＝N-05（先寫暫存再改名）、N-12 半份不算。(c) 事先列出＝N-38 列出 fsm 出錯的幾種、lib 各頁的錯誤代號表。
- **濃縮**：N-43 結束碼只 0／非 0；N-29 錯誤只有一種形狀；N-38 出錯一律 phase 不動、原樣往外報、下層的錯不轉述。

## 10-15 深夜使用者拍板：切乾淨＋KISS

原文（照貼，答下面「未決」的第 2、4、5、6 條，**跟推薦相反**）：

「我希望能盡量乾淨。2.不留　4.不能接受，拜託切乾淨，想要看子層的東西請另外透過其他機制，沒機制就別碰。5.不，fsm就是他那一層，拜託，乾淨點，我要的是徹底的純淨簡潔，KISS。把KISS納進最高原則。 6.agent他就是看到自己的工具，工具在幹嘛他就不管，拜託，乾淨，完全切割，徹底切割，不得有任何殘留。」

### 決定

- **KISS 納進最高原則**＝新條 **C-56**，放在設計理念「最高原則」段、C-52／C-53 之上；接 proto7 設計原則第 9 條。C-52 加嚴：想看子層要另有機制、沒機制就不碰；上層不該知道下層是什麼。C-53 補一句：下層的錯不轉述。
- **2 不留**：daemon `add` 不再替子 loop 驗 inst（`_check_inst` 與包 inst.json 時的 `aos_inst.parse` 都拿掉），也不再用 loop 的 `check_config` 驗子項的 loop key、不填預設——daemon 收子項只看它自己需要的：是物件、沒 `inst` 有 `argv` 就包成跑一次、`ctl`／`state` 沒寫就放 `work_dir/N/`；設定原樣灌給子 loop，寫錯了子 loop 自己退 1、錯在 `err.json`，daemon 只看到它結束。N-28、lib daemon.md 改寫；測試 `test_add_checks_inst_up_front` 改成 `test_add_does_not_check_inside`。
- **4 切乾淨**：fsm 不讀格的 stderr（`aos_methods.run_cell` 的 `cell_error`、`_stderr_error`、「沒寫 stderr 的格改接暫存檔撿錯」全拿掉；stderr 照那張 inst 自己的，沒寫＝/dev/null）。格的結果＝N-12／N-36 的最小那份：**結束碼＋stdout 最後一份 JSON**；fsm 那行的 `error.msg` 只寫「格 X 結束碼 N」。想看格的錯＝在那張 inst 寫 `stderr` 檔（N-26 本來就有的機制）、去讀那個檔。N-38、lib fsm.md 改寫。
- **5 fsm 就是它那一層**：拿掉 N-40「巢狀格不宜寫表上靜態 next」；**N-37 多一種值 `next: null`＝留原狀態**（格說「我還沒完」，表上有靜態 next 也不走），fsm 沒結束的拍自己那行就帶 `next: null`；結束那拍照舊交出那格的結果。這樣外層不必知道那格是什麼，表上要不要寫靜態 next隨意。程式本來就把 `null` 當留原狀態，只是沒寫進規範、fsm 那行沒吐；現在兩邊都補上。測試 `test_nested` 改成外層寫了靜態 next 也不會被帶走、新增 `test_next_null_stays`。
- **6 徹底切割**：agent 只看到自己的工具清單（名字、`_tool` 的說明與參數），工具裡面是不是另一個 agent、它的 frame 放哪、綁什麼腦，agent 這層不知道、不傳、不繼承。lib 程式本來就沒有「agent 知道工具是 agent」的機制（`chain()` 只看自己的 frame.json；tool 格只是在 `work/<n>/` 跑一張 inst），殘留的是**說法**：`aos_agent_lib.py`、agent.md 把 `work/<n>/` 叫「工具呼叫的 frame」——改成「工具的工作資料夾」，把它當 frame 是那張工具 inst 自己的事。C-46 補一段、frame.md「當工具」「換腦只換那一層」改寫。**留給 inst-exec 稿**：工具叫 agent 的寫法（`sh -c` 三步還是 aos-exec）由那邊定，這裡只定「agent 這層不知道」。
- 同一原則往下再套一層（C-52「同一個原則在每一層重複」）：**think 也不讀腦的 stderr**——`BrainFailed` 只寫「腦 X 結束碼 N」（原本把腦 stderr 的 `HttpError: …` 接進來）。要看 proxy 回的原話＝在 `brain.json` 寫 `"stderr": "…"`。
- 盤點時查到的殘留（NORMS、CONCEPTS、lib 程式與說明、demo fsm README、測試、wf conventions 與 code map）都已清。demo 的 JSON 與 `paint/run.py` 沒動（`bind_brain()` 改寫的是工具 inst，是呼叫方的事，不是 agent 這層）。

- 使用者同晚另定「少用 sh」「設計一律假設沒有指示詞」（條文由另一位加進 NORMS）：這次改的程式與規範都沒用到 `sh -c`、也不靠 `$ref` 才成立；唯一碰到 sh 的是**既有的** demo 工具 inst（`tools/clerk.json`、`tools/brush.json` 的 `sh -c` 三步叫另一個 agent）——沒動，怎麼改法留給 [inst-exec 稿](2026-10-15-inst-exec.md)（工具叫 agent 的呼叫機制）。測試裡用 sh 當假格子是測試自己的事。

### 自定的小地方（等使用者看）

- daemon 表上的 `times` 欄拿掉（不再記子項的 loop key）；`add_times` 讀子項的 ctl 窗、沒有就讀它的 state 窗，子 loop 還沒報 state 就回 `Conflict`。
- daemon 子項的 `ctl`／`state` 寫了但不是路徑字串＝`FieldType`（daemon 自己要用的窗才驗）；null 當沒寫、放 `work_dir/N/`。
- fsm 出錯那拍（phase 不動、退 1）那行也帶 `next: null`——它確實沒結束；外層靠結束碼非 0 知道格出錯。
- `next: null` 只在規範層定義成「留原狀態」，fsm 的 `NextBad` 照舊只擋非字串非 null。

（10-20 註：這四條碰的舊 lib daemon／fsm 程式 10-19 已整套刪，見 git 歷史 5546be29；daemon 現無實作，照「資料夾＝程式」重寫時再對。）

### 驗證

- proto8 lib 測試 172 → 173 個全過；ctest 全綠；fsm、kernels/llm、kernels/general、paint demo 假腦實跑正常；wf-lint 不變。

## 盤點其餘兩條（已處理）

第 1、3、8、9 條見上面「決定」；第 2、4、5、6 條見上面「10-15 深夜使用者拍板」。

7. **`ask_judge.py` 寫死 `parent`**：照 [LiteLLM 實跑 § 拍板](2026-10-15-litellm-live.md#拍板10-15) 第 2 條（使用者「都按照推薦」）改成收定義資料夾當引數。
10. **文件小矛盾**：NORMS 總則檔頭寫「之後可能併」，已對齊「維持分開」；lib `ctl-state.md` 的 fsm 列、`directives.md` 的 exit 檔說法已照 N-39、N-30 修好。

## 新的待定（這次做的時候發現）

A～C 已定（見「決定」）。daemon 收到訊號照舊退 0（照設計的收工路）——若使用者要連 daemon 也一律 1，改一行加測試即可。（10-20 註：後來 10-16 定的 N-52「SIGTERM＝優雅收工、退 0」已在 10-19 作廢，依 CONVENTION P-36：收到 SIGTERM 先收好子程式、寫好狀態再結束，但結束碼非 0，loop／fsm 以 128＋N 結束；daemon 現無實作，重寫時照 P-36。）
