# KISS 審視：fsm 與格庫（N-20、N-36～N-41、N-44 的 fsm 半邊；lib aos_fsm.py、aos_methods.py、aos_agent_lib.py；fsm.md、agent_lib.md；demo/fsm；test_fsm、test_agent、test_agent_frame）

範圍：只審規範條文與程式／lib 說明／demo／測試；概念（C-49、C-52、C-53）只拿來當尺，不提刪改。另一個 agent 正在改「fsm 不讀格 stderr」與「巢狀規矩（那行帶 `next: null`）」、以及 inst-exec 第三版（TARGET 拿掉、格只收內嵌、`aos agent fsm` 與 frame.json 退場）——這些不重提，只在它們之上再看能不能更簡。每條直接給推薦。

## 砍

1. **下一狀態的錯誤分支**
   - 現況：格吐了東西但不是完整 JSON＝錯；格沒吐又沒表上 next＝錯；格沒吐但表上有 next＝照表走；吐了 `{}` 沒 next 沒表上 next＝留原狀態。四種情形、兩個 `ResultMissing`、一個 `cell_empty` 旗標。
   - KISS：一條——「最後一份完整 JSON 的 `next` ＞ 表上 `next` ＞ 留原狀態」；沒吐、吐了半份、吐了垃圾都＝「沒有結果」（N-12 已經這麼說），不報錯、不分辨。
   - 動：N-37、N-38、aos_fsm.py、aos_methods.py（`cell_empty` 刪）、fsm.md、test_fsm（刪 `test_no_result_is_error`、`test_non_json_output_with_static_next_is_error`、`test_empty_stdout_follows_static_next`、`test_empty_stdout_end_gives_nothing`）。
   - 風險：格退 0 又吐垃圾時 fsm 不叫，原地踏到 loop 的 `times` 用完——那是格的誤用，不歸 fsm 管（C-53）。

2. **fsm 那行轉述格的 N-30 結果**
   - 現況：fsm 每拍那行＝格的 aos_inst 結果七個欄位（`id`、`code`、`signal`、`timed_out`、`pid`、`ms`、`exit_file`；沒起成格全填 null、`ms` 還要自己回填）＋ `from`、`to`、`error`、`end`；`error.msg` 截 300 字。
   - KISS：那行只說 fsm 自己的事：`{"from", "to"}`，選填 `end`、`next`（另一 agent 正在加）、`error`。格的結束碼寫進 `error.msg` 一句就夠；id 也不替格推導（`#/states/<名>`）。
   - 動：N-38、N-40、aos_fsm.py（`line` 模板、`ERR_LIMIT`、`t0`）、aos_methods.py（`target_id`）、fsm.md、test_fsm（`test_first_tick` 的 key 集合、`test_cell_failure` 的 `code` 欄）。
   - 風險：除錯時少了 pid／ms；要就讓那張格 inst 自己寫 `stdout`／`stderr` 檔。

3. **結束那拍多吐一份「那格的結果」**
   - 現況：結束那拍 stdout 兩份：fsm 那行＋那格的結果原樣再吐一遍（那格沒輸出就不吐）——為了讓外層 fsm 讀到 `next`。
   - KISS：只吐那一行，行裡帶 `next`（那格回的）；外層照 N-37 看那行就夠（這是另一 agent「那行帶 `next: null`」的自然延伸：沒結束 null、結束帶名字）。
   - 動：N-40、aos_fsm.py（`give`）、fsm.md、test_fsm（`test_end_line_marked`、`test_end_in_table_runs_then_ends`、`test_end_not_in_table_ends_now`、`test_nested`）。
   - 風險：外層拿不到內層最後一格的 `data`——N-37 本來就說 fsm 不傳 data，格之間走檔。

4. **think 的連錯停住整套**
   - 現況：`halt_after`、`halt_state` 兩個 key、私檔 `work/think.json` 計數、到次數自己寫 `ret.json` 的錯並回 `halted`、`main` 特判 `SystemUnreadable` 不計、七張表的 `end` 都得列 `halted`。
   - KISS：全砍。連錯停住＝拍它的 loop 的 `times`；`ret.json` 沒有＝沒跑完（Q12 已定）。think 每次只報自己的錯、退 1。
   - 動：aos_agent_lib.py（`_think_failed`、`_fails_file`、`main` 的特判）、agent_lib.md、七張 fsm.json 的 `end`、demo/fsm README、test_agent（`test_no_tools_400_surfaces_and_stops`）、test_agent_frame。
   - 風險：腦壞掉時每拍叫一次腦直到 `times` 用完（demo 是 20 次）；真要省，是 loop 加一個通用的「連錯 N 次就停」key，不是 think 自己數。這翻掉盤點第 8 條的前提（第 8 條只定「done 不讀 think 私檔」，砍掉後自然成立）。

5. **route 格**
   - 現況：think 不吐 next，另一格 route 看最後一則 assistant 有沒有 tool_calls 決定 `tool`／`done`，還帶 `--done 名` 旗標；每張表都要 thinking → route 兩格兩拍。
   - KISS：併進 think：叫完腦直接吐 `next`（有 tool_calls＝`tool`、沒有＝`done`，固定名）。刪 route 子命令、`--done`、五個 `cells/route.json`。
   - 動：aos_agent_lib.py、agent_lib.md、五張表、demo README、test_agent_frame。
   - 風險：只想叫腦不分流的表沒得用——demo 外層的內層 fsm（ask → review）就是這種，但它本身在第 9 條也要砍。

6. **tool 格的被殺防護**
   - 現況：每跑一個工具先寫 `work/.tool-running.json`、跑完刪；下一拍看到同 id＝回 `Interrupted` 不重跑。data 還同時給 `tool`／`result`（第一個）和 `tools`／`results`（全部）。
   - KISS：砍標記檔與 `Interrupted`：被殺中的那個重跑一次（已接進 history 的本來就不重跑）。data 只留 `tools`、`results`。
   - 動：aos_agent_lib.py（`act`、`INTERRUPTED`、`_rm`）、agent_lib.md 邊緣表、test_agent（`test_interrupted_in_middle_skips_only_that_one`、`test_interrupted_tool_not_rerun`、`test_multiple_tool_calls` 的 data 比對）。
   - 風險：有副作用的工具被殺後跑兩次——N-20 本來就不保證冪等。

7. **intake 的三種輸入**
   - 現況：`{"question"}`、`{"history"}` 整段換、沒有 args.json 但有 history＝照舊；還順手刪上一輪 `ret.json`。
   - KISS：只收 `{"question"}`，接進 history、改名 `args.taken.json`，沒了。要整段綁 history＝呼叫方自己把 `history.json` 放進 frame（C-46 綁定本來就是放檔）；每次呼叫都是新 frame，沒有「上一輪的 ret.json」。
   - 動：aos_agent_lib.py、agent_lib.md、test_agent_frame（「整段換掉」那個）。
   - 風險：同一個 frame 續聊時舊 `ret.json` 會留著——呼叫方看「沒跑完」靠的是自己先刪，一行。

8. **格庫設定的 `history`／`work` key 與 `need_brain`**
   - 現況：每格（含 intake、done）都走 `load_config` 找 brain、tools、system，`history`／`work` 可改路徑，`need_brain` 分 think 與其他。
   - KISS：`history.json`、`work/` 固定在 cwd（C-46 的 frame 慣例），不開 key；只有 think 讀設定（brain、tools、system），其他格不讀 stdin。
   - 動：aos_agent_lib.py、agent_lib.md、test_agent／test_gate 的 cfg dict（`h.json` → `history.json`）。
   - 風險：沒人改過這兩個路徑；測試要改檔名。

9. **demo/fsm 的兩層結構**
   - 現況：外層 idle／thinking／tool／done，thinking 格是內層 fsm（ask → review），`review.py` 用 `sys.path` 拼路徑 import `common.py`，`idle.py` 讀 inbox；旁邊 clerk 又是一張單層表。巢狀為了展示而存在。
   - KISS：demo/fsm 瘦成跟 clerk 同一張單層表（intake → thinking → tool → thinking … → done），刪 `think/`、`cells/idle.py`、`review.py`、`common.py`；run.py 寫一份 `args.json` 起 loop。巢狀只在 test_fsm 的 `test_nested` 驗。報時員當工具的例子留（它是「agent 當工具」唯一的示範）。
   - 動：demo/fsm 整個資料夾、README「裡面有什麼」「會看到什麼」、run.py、test_agent 整圈測試（`test_full_round_with_tool`、`test_empty_inbox_done_stops`）。
   - 風險：「兩層 state 窗怎麼變」的畫面沒了；想看巢狀跑 test_nested。

10. **brains/ 五份腦設定**
    - 現況：fake、openai、litellm、lmstudio、ollama×2；ollama 兩份指向已不准用的 146 主機「只留當範例」；openai.json 預設就是 LiteLLM，跟 litellm.json 重複。
    - KISS：留 fake、openai、lmstudio 三份；刪 `ollama/` 與 `litellm.json`。
    - 動：demo/fsm/brains、README「換成真的 LLM」。
    - 風險：無。

11. **舊 key 相容的話與測試**
    - 現況：aos_fsm.py 檔頭與 fsm.md 寫「舊設定的 ctl、lock、max_steps、max_fails 也忽略」，test_fsm 有 `test_old_keys_ignored` 專門驗。
    - KISS：全刪。「不認得的 key 忽略」是通則，不為舊 key 留話、留測試。
    - 動：aos_fsm.py、fsm.md、test_fsm。
    - 風險：無。

12. **N-41**
    - 現況：整條在說「一格怎麼跑 fsm 不管」（同步／非同步都合規）＋一條禁令（格不自己 setsid／fork）＋「格裡放 loop 不禁止也不鼓勵」。
    - KISS：刪。「inst 內部的事 fsm 不管」N-36 已講；setsid／fork 是 argv[0] 程式的通則（待定裡擱置那條），不是 fsm 的事。同步／非同步例子留 fsm.md 一句。
    - 動：NORMS 07、NORMS.md 條號表（N-41 標「併入 N-36」）、fsm.md。
    - 風險：條號空一個。

13. **N-20**
    - 現況：獨立一條說「巢狀重跑的冪等性不保證、不在規範範圍」。
    - KISS：併進 N-38 一句「被殺＝下一拍重跑同一格，半成品格自己認，冪等不保證」；規範不保證的事不值一條。
    - 動：NORMS 07、NORMS.md 條號表。
    - 風險：條號空一個。

## 合

14. **aos_methods.py 與 aos_fsm.py 兩檔、兩種錯誤類別**
    - 現況：方法表 lib 獨立一檔（`check_table`、`cell`、`run_cell`、`last_json`、`MethodsError`），fsm 抓到 `MethodsError` 再包成 `FsmError`；`run_cell` 多一個 `args` 分支給 think 叫腦用（stdin 蓋成暫存檔）。
    - KISS：併成一檔 aos_fsm.py、一種 `FsmError`。`run_cell(args)` 等 v3「inst 的 `stdin` 收內嵌 JSON」落地後，think 直接 `aos_inst.run(dict(inst, stdin=req))`，那個分支跟暫存檔一起消失。
    - 動：lib（刪 aos_methods.py）、fsm.md 標題、agent_lib.md、lib README、wf code map、test_fsm（`test_methods_cell_forms` 併進 fsm 測試）。
    - 風險：v3 沒落地前 think 還要 `run_cell(args)`——先把那個分支搬去 agent_lib，等 v3 再刪。

15. **N-36～N-40 的歷史括號與「不做什麼」清單**
    - 現況：每條帶「（原為…、10-15 收工後依 Q 幾改）」；N-39 大半在列不做的（不開 ctl／lock、不計 step、心跳不適用、不寫時間 pid、遞迴不擋、原本還記 data／step／running…）。
    - KISS：條文只寫現行規則。N-39 一句：「state 窗必填、只記 `phase`、只有 fsm 寫。」歷史與「原本有什麼」留 thinking，每條末尾一個連結。
    - 動：NORMS 07。
    - 風險：讀條文的人少了「為什麼」——點連結。

16. **跟 v3 一起消失、別留尾巴**（v3 已定，這裡只列清單）
    - `FLAGS`／`--start`／`--state`、`base_of`、`check_config` 的 `base`／`ident`、`cell()` 的 `ident`／`base`、`aos_cli.load_target` 在 `cell` 裡、`run()` 只收 dict；fsm.md「格放哪：慣例 `cells/`」段；N-36「格的名字從設定檔所在資料夾算」句；test_fsm `test_cell_names_from_config_folder`。
    - 動：aos_fsm.py、aos_methods.py、fsm.md、N-36、test_fsm。
    - 風險：無。

## 跨層殘留

17. **loop 的 `stop_on_end` 認得 fsm**（跨到 loop 那章，一行）
    - 現況：N-44 寫「包的是 aos-fsm 時」，`_saw_end` 檢查 `end: true` 還要有 `from`、`to`。loop 知道 fsm 那行長什麼樣。
    - KISS：loop 只看子程式 stdout 最後一份有沒有 `"end": true`，條文不提 fsm。
    - 動：N-44、aos_loop.py `_saw_end`、loop.md。
    - 風險：任何子程式吐 `end: true` 都會停——這個 key 本來就是這個意思。

## 最小核心

從零只留這些：

- **fsm**：一張表 `{"start", "states": {名: inst 或 {"val": inst, "next"}}, "end": [名], "state"}`。一拍＝讀 `phase`（沒檔＝start）→ 跑那格 → 最後一份 JSON 的 `next`（＞表上 `next` ＞ 不動）→ 寫 `phase` → 吐一行 `{"from", "to"}`（結束多 `end: true` 與 `next`；錯多 `error`）。錯只有四種：表不對、窗不對、格結束碼非 0、`next` 不認得。退 0／1。一檔、一種錯誤、約 80 行。
- **格庫**：think（讀 history、叫腦、接回覆、吐 `next` tool／done）、tool（跑還沒回的 tool_calls，各開 `work/<n>/`）、intake（`args.json` 的 `question` → history）、done（寫 `ret.json`）。設定只有 think 讀（brain、tools、system）。
- **demo**：一個單層 agent 定義資料夾＋一個「agent 當工具」的例子。
- **測試**：fsm 十個上下（第一拍、靜態 next、stdout 蓋表上、留原狀態、end 兩種、錯四種、巢狀、被殺重跑、窗缺）；格庫十個上下。

不在範圍：概念條（C-49、C-52、C-53）不審、不提刪改。
