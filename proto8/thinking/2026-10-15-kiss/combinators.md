# KISS 審：組合子與 proto8-1

範圍：NORMS 07（N-34、N-20、N-36～N-41）、N-43／N-44 跟它們相關的句子、proto8-1 整個資料夾（aos_tasks.py、seq／par／if／not、aos-tick、demo、tests、README）、proto8/demo/once、demo/tick、proto8/bin/aos。只審規範與實作，概念不審（CONCEPTS 只拿來理解）。另一個 agent 在做的（inst-exec-v3 的 TARGET→stdin、fsm 讀格 stderr、巢狀 next 那幾條）不重提。

> 稿，只寫推薦，沒改任何檔。每條：現況 → KISS 版 → 動到哪 → 風險。

## 砍

**1. tasks 四支（seq／par／if／not）全砍，控制流交給 sh。**
- 現況：proto8-1 用 Python 重做了 sh 早就有的四個字：`&&`（seq）、`& wait`（par）、`if`（if）、`!`（not）。為此多了：自己接訊號轉訊號（`Signals`）、自己解 aos-inst 的 stdout 往回找帶 `code` 的那行（`_code`、`ResultUnreadable`、`stdout_inherit` 的特例）、5 個 lib 檔、5 個 bin 殼、14 個測試、一棵 12 張 inst 的 demo，還在 N-43 挖了兩種例外（透明轉交、述詞）。demo 自己的結論第 3 條：「整棵樹 12 個 inst 檔，換成 sh 大概 10 行」；使用者 10-12 也說過「控制流原語多半不必要，到後續搞不好大家就乾脆一個程式跑下去，控制流都在 argv[0] 的那個程式裡」。v3 現在還打算把這四支再改一次（argv → stdin）。
- KISS 版：刪。要串就在 argv[0] 寫 sh：`sh -c 'aos-exec a && aos-exec b'`、`aos-exec a & aos-exec b & wait`、`if aos-exec c; then aos-exec t; fi`、`! aos-exec x`。aos 不提供流程控制程式，只提供「一張 inst 怎麼跑」。
- 動到：proto8-1/lib/aos_tasks.py、aos_seq／par／if／not.py、bin/aos-seq／par／if／not、tests/test_tasks.py、demo/ 整個（含 README 兩份）、proto8-1/README；N-34（見第 5 條）；N-43 例外 (1) 只剩閘門、(2) 述詞整段刪；N-12「例：tasks 報 ResultUnreadable」那句；proto8/lib/README 第 28 列「proto8-1 也借 error()」；code map；inst-exec-v3「proto8-1 tasks 改吃 stdin」那行作廢。
- 風險：使用者 10-15 說過 tasks「地位等同 C 的 stdlib」，這是翻案；sh 沒有「先全部驗過才跑」（demo 第 13 條已證明那只驗一層，沒差）；被訊號停時 sh 自己先死、子程式靠 loop 整群收（現況測試 `test_loop_stop_now_clears_children` 本來就是這樣收的）。

**2.（tasks 留才做）aos-not 砍。**
- 現況：aos-not 只為了拼 or／retry。demo 第 1 條：`if (not X)` 會把「X 根本起不來」吞成「X 不成立」、流程照走。它是 N-43「述詞例外」的唯一主角（aos-if 的條件是子程式的碼、不是 aos-if 自己的退出碼，本來就不是例外）。
- KISS 版：刪 aos-not；N-43 例外 (2)、N-34 述詞那句一起刪。要反過來就 `aos-if X 失敗格 成功格`。
- 動到：aos_not.py、bin/aos-not、test_tasks 的 `test_not` 與各 subTest 的 NOT 列、demo/pipeline/not-check、N-34、N-43。
- 風險：反過來要多寫一張空的 inst。

**3.（tasks 留才做）「先全部讀好驗過才跑」砍。**
- 現況：`load_all` 先讀全部 TARGET、個數不對 `Usage`、一個壞就一個都不跑。demo 第 13 條：只驗一層，巢狀一樣要跑到才知道。
- KISS 版：跟 sh 一樣，跑到哪讀到哪，壞了那一步就 stderr 一份、退 1。
- 動到：aos_tasks.load_all、四支 main、`test_bad_target_runs_nothing`、proto8-1/README 共同規矩那條。
- 風險：壞的排第三時前兩步已跑，跟 sh 一樣。

**4. aos-tick 搬進 proto8/lib，proto8-1 資料夾收掉。**
- 現況：tasks 砍完 proto8-1 只剩 aos_tick.py（60 行）＋ test_tick.py，卻獨占一個頂層資料夾、自己的 bin/、README，還 `sys.path.insert` 去借 proto8/lib 的 `error()`。
- KISS 版：`proto8/lib/aos_tick.py`、`proto8/lib/tests/test_tick.py`、`proto8/bin/aos` 加 `tick`；proto8-1 整個刪。aos-tick 本身不動（讀 n 寫 n＋1、先寫暫存再改名，這是 sh 一行做不乾淨的地方，留著有理由）。
- 動到：搬兩個檔、bin/aos、lib README、NORMS 07 檔頭「實作在 proto8-1」、CONCEPTS 02 檔頭的連結（只改連結）、code map、wf/INDEX repo-layout、testing.md。
- 風險：連結多，wf-lint 跑一次就抓得到。

**5. N-34 整條刪。**
- 現況：N-34 一段寫完 tasks 怎麼拿碼、tasks 與 aos-tick stdout 不吐、錯照 N-29 退 1、述詞例外、三次修訂史。
- KISS 版：tasks 沒了；aos-tick 的規矩全是 N-12／N-29／N-43 的通則，它是語法糖（C-45），不需要專條。07 檔標題改「組合子（fsm）」，「tasks」小節刪。
- 動到：NORMS 07、NORMS.md 索引、N-43 引 N-34 的兩處。
- 風險：無。

**6. 待定 §28「回合數格式算不算規範」結案＝不是。**
- 現況：掛在 08-待定，使用者說「晚點再說」。
- KISS 版：aos-tick 是糖，檔案格式是它自己的檔頭說明，不進 NORMS。結案。
- 動到：08-待定。
- 風險：是替他結案，一句話可翻。

**7. demo once／tick 與 test_tick 的 exit 檔拿掉。**
- 現況：proto8/demo/once、tick 的 inst 寫 `exit`／`exit_append`，run.py 印 once.exit／tick.exit，README 說「last_code 讀它的 exit 檔」（已過時：loop 讀 stdout 結果）；test_tick 的 loop 測試也靠 `tick.exit` 數三個 0。N-30 已定 exit 檔「只當過渡」。
- KISS 版：兩張 inst 刪 `exit*`；run.py 只印 once.out、tick.out；README 改「last_code＝stdout 結果的 code」；test_tick 只看 clock 檔＝3。
- 動到：proto8/demo/once/inst.json、tick/inst.json、demo/run.py、demo/README.md、test_tick.py。
- 風險：無。順便是把 inst 的 `exit`／`exit_append`／`exit_mkdir` 三個 key 整個拿掉的好時機（inst 範圍，一句帶過）。

**8. proto8/demo/tick 改成真的 tick。**
- 現況：demo/tick 印 `date`，跟 aos-tick（時鐘）同名不同事，一詞兩義（C-54）。proto8-1 demo 砍掉之後 aos-tick 反而沒 demo。
- KISS 版：demo/tick 的 inst 改成 `aos tick clock`，loop 照舊 5 次隔 1 秒；README「會看到什麼」改成 clock 檔 1→5、暫停那段不變。
- 動到：proto8/demo/tick/inst.json、demo/run.py、demo/README.md。
- 風險：README 範例輸出重抓一次。

**9. N-20 刪。**
- 現況：N-20 只說「重跑的冪等不保證、算使用者的事」，N-38 末尾已經再說一次並指回 N-20。
- KISS 版：刪 N-20，N-38 那句留著、不指號。
- 動到：NORMS 07、08-待定與 fsm.md、aos_fsm.py 檔頭引 N-20 處。
- 風險：無。

**10. N-38「格沒輸出又沒表上 next＝錯」改成「留原狀態」。**
- 現況：格吐了 JSON 但沒 `next` → 留原狀態（N-37）；格什麼都沒吐又沒表上 next → 錯 `ResultMissing`（N-38）。同一件事（沒人說 next）兩種結局，多一個錯誤代號、`cell_empty` 旗標、一條特例、兩個測試。
- KISS 版：一律「沒人說 next＝留原狀態」；`ResultMissing` 刪、`cell_empty` 刪。
- 動到：N-37、N-38、aos_fsm.py、aos_methods.run_cell、fsm.md、test_fsm 的 `test_no_output_no_next_is_error`、`test_empty_stdout_follows_static_next` 改名。
- 風險：格忘了說 next 會每拍重跑同一格而不報錯；loop 的 `times` 擋得住，而且吐 `{}` 的格現在就已經是這樣。

**11. N-39＋N-41 合成一條「fsm 不管的」。**
- 現況：N-39（不開 ctl／lock、不心跳、不寫時間 pid、遞迴不擋）與 N-41（格怎麼跑是格的事、不 setsid、格裡放 loop 不禁不勸）都是「fsm 明確不管」的清單，分兩條、各帶一段修訂史。
- KISS 版：一條 N-39：「fsm 只寫 state 窗的 `phase`；暫停、停止、重疊、心跳、時間、格內部怎麼跑、遞迴，一律不管，交給拍它的 loop 或格自己。」
- 動到：NORMS 07、08-待定「標準實作要不要每拍記時間」的引用、fsm.md「不做的」那列。
- 風險：無。

**12. N-44 loop 認 fsm「那一行」改成通用的 `"end": true`。**
- 現況：loop 的 `stop_on_end` 只認「帶 `from`、`to` 的那行」、「格自己的結果帶 `end` 不算」——loop 認得 fsm 那行長什麼樣，是 loop 往下看了一層。而且那個排除是死的：非結束拍 fsm 只吐自己那行，格的結果只在結束拍才轉出來，排不到任何東西。
- KISS 版：N-44 改成「這次 stdout 任一份完整 JSON 最上層有 `"end": true`＝不再起下一次」，不提 from／to、不提 fsm；loop 不知道包的是什麼。
- 動到：N-44（04 檔）、aos_loop.py 的結束判斷與檔頭、loop.md；N-40、fsm.md 只改引用字句。
- 風險：任何 inst 都能吐 `{"end": true}` 叫 loop 停——這是好處（不用靠 ctl）。

**13. fsm.md「格放哪」慣例段刪。**
- 現況：fsm.md 寫「慣例是格放 FSM.json 旁的 cells/」，下一句又說「表一定明寫路徑，不靠這個慣例找」——說了一個程式不用的慣例；v3 之後格是內嵌或 `$ref`，更沒意義。
- KISS 版：刪那段。demo 的 cells/ 資料夾照留，那只是布局。
- 動到：proto8/lib/fsm.md。
- 風險：無。

**14. proto8/bin/aos 不手寫子命令清單。**
- 現況：case 表列 `inst|loop|daemon|fsm|gate|tree`、kernel 兩種、brain 兩種、agent 一個特例（對到 aos_agent_lib.py 不是 aos_agent.py）；v3 要刪 tree、加 exec，第 4 條要加 tick，每次都得改入口。
- KISS 版：子命令＝lib 裡有 `aos_<名>.py` 就能跑：把 `$1`（兩層的連 `$2`）底線接起來找 `$lib/aos_X.py`，有就 exec、沒有就 Usage 錯。aos_agent_lib.py 改名 aos_agent.py（C-54 程式名⇄檔名）。入口剩 8 行。
- 動到：proto8/bin/aos、aos_agent_lib.py 改名（連 agent_lib.md、import 它的地方、code map）。
- 風險：改名動到的引用多；`aos agent` 的 import 要跟著改。

## 看過、不動

- N-36 表上靜態 `next`（`{"val", "next"}`）：七張 agent 表全在用（intake→thinking、thinking→route、tool→thinking）。不說 next 的格本來就不該知道表長什麼樣，表上寫才是對的；留。
- N-40 結束的四種情形與 `end` 可在表裡可不在：使用者 10-15 親自拍的，七張表兩種寫法都在用（`done` 在表裡、`halted` 只在 end）；留。
- N-37 fsm 不碰格的 stdin、不存 data；N-38 出錯 phase 不動：已經是最短的寫法；留。
- aos_fsm.py／aos_methods.py 分兩檔：agent_lib 也用 aos_methods，併回去不會更簡單；留。
- proto8/bin/aos 跟 C++ 的 `aos` 同名：是不是要改名由使用者定，不在這份。

## 最小核心（從零重寫只留這些）

- **fsm 一支**：表＝`start`、`states`（格＝一張 inst，可帶表上 `next`）、`end`、`state` 窗。一拍一格；下一狀態＝格 stdout 的 `next` ＞ 表上 `next` ＞ 留原地；進了 `end` 就那行多 `"end": true`、phase 歸 `start`；錯＝phase 不動、退 1。規範 N-36～N-40 四條（N-36 表、N-37 下一狀態、N-38 出錯、N-39 不管的＋結束併進 N-40）。
- **aos tick 一支**：讀 n 寫 n＋1。沒有規範條。
- 串、並、條件、反向：都是 argv[0] 裡的 sh。組合子沒有第二支程式。

## 不在範圍

- CONCEPTS（C-41、C-44、C-49、C-52／53 的例子）不審；上面提到的概念檔只改連結。
- fsm 把格的 stderr 放進自己 stdout（N-38 後半）、巢狀格的靜態 next（principles 未決 4、5）、TARGET→stdin（v3）另有人處理；本稿第 1、14 條與 v3 相接的地方已標。
