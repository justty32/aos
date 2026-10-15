# KISS 審視：agent（格庫 aos_agent_lib.py、aos_frame.py、兩顆腦、agent.md／agent_lib.md／frame.md、demo/paint、對應測試、N-27）

← [討論紀錄](../README.md)｜前提：[原則稿](../2026-10-15-principles.md)（KISS 最高、C-52／C-53 在它底下）｜只審規範與實作，概念不審｜只寫稿，程式、規範、說明一字未改

跟 [inst-exec 第三版](../2026-10-15-inst-exec-v3.md) 重疊的（frame.json／parent 鏈退場、`aos agent fsm` 退場、cwd 的檔 ＞ stdin 定義、TARGET 字串改內嵌）這裡**不重提**，只看它落地之後還能再少什麼。另一個 agent 在做「tool 格不認得工具裡面是 agent」，本稿 #3 是它的延伸。

每條：現況 → KISS 版 → 要動哪 → 風險。直接給推薦。

## 格庫（aos_agent_lib.py）

**1. route 格併進 think。**
現況：think 叫完腦不吐 `next`，另一格 route 再讀一次 history 看有沒有 tool_calls，決定 `tool` 還是 `done`（還有 `--done 名` 旗標）。
KISS：think 自己吐 `next`：有 tool_calls＝`tool`、沒有＝`done`。route、`--done` 刪；表少一個狀態。
動：aos_agent_lib.py；五個定義資料夾的 fsm.json 與 cells/route.json（demo/fsm/clerk、paint/painter、paint/brush、kernels/llm/boss、kernels/general/judges/agent）；test_agent_frame 的 bob。
風險：think 寫死 `tool`／`done` 兩個狀態名；要別的名字就自己寫一格（N-41 本來就允許換格）。

**2. think 連錯計數整套刪。**
現況：`halt_after`（預設 3）、`halt_state`、私檔 `work/think.json` 計次、`_think_failed()`、main 裡 `SystemUnreadable` 不計次的特例。
KISS：腦出錯一次＝think 把 `{"error"}` 寫成 `ret.json`、吐 `{"next": "halted"}`，結束。不計次、沒私檔、沒設定 key。要重試是腦那張 inst 或呼叫方的事（C-53：各管自己的錯）。
動：aos_agent_lib.py、agent_lib.md。
風險：一次暫時性錯誤就收工；真要重試得在腦那層包。

**3. `work/<n>/` 整個拿掉：tool 格只用 stdin／stdout 跟工具說話。**
現況：每叫一個工具就 mkdir 搶號 `work/<n>/`、寫 `args.json`、接 `stdout.json`、把 cwd 切過去；設定多一個 `work` key。理由是「那裡就是被叫 agent 的 frame」——這正是 agent 偷知道工具裡面是 agent。
KISS：tool 格把 arguments 當那張工具 inst 的 stdin（內嵌 JSON，v3 的 D）、拿 stdout 最後一份當結果，在自己的 cwd 跑，不開資料夾、不落檔。工具要自己的資料夾自己開（`sh -c 'd=$(mktemp -d) && cd "$d" && cat > args.json && …'`），agent 零知情。
動：aos_agent_lib.py（`new_dir`、`_run_tool`、`work` key）、N-27 第二句刪、agent.md、三張 agent 當工具的 inst（demo/fsm/tools/clerk.json、paint/painter/tools/brush.json、kernels/llm/boss/tools/clerk.json）、test_agent 的 `test_each_call_in_new_numbered_folder`。
風險：反轉 10-15 收工後「工具呼叫預設 frame＝`work/<n>/`」那條決定；工具若寫檔會落在 agent 的 cwd——那是工具的事。
給 inst-exec 的一句：v3 的 G 把 brush 的 loop 設定放在工具 inst 的 `stdin`，但 tool 格會把 stdin 蓋成 arguments，兩個撞。照本條，工具 inst 自己 `cat > args.json` 再起 loop，loop 設定由工具自己指（`aos-exec <brush>`，路徑是工具的事）。

**4. `.tool-running.json`／`Interrupted` 刪。**
現況：跑每個工具前寫標記、跑完刪；下一拍看到同 id＝上一拍被殺一半、那個不重跑、回 `Interrupted`。
KISS：被殺就重跑（N-20 冪等不保證、N-38 半成品由格自己看——這裡「看」＝不看）。
動：aos_agent_lib.py、agent_lib.md 邊緣表一列、test_agent 兩個 interrupted 測試。
風險：有副作用的工具被殺後跑兩次。

**5. tool 格的 stdout 四格 → 一格。**
現況：`{"tool", "result", "tools", "results"}`（第一個＋全部各一份）。
KISS：`{"data": {"tools": [名…]}}`。結果在 history 裡，沒人讀 stdout 的 result。
動：aos_agent_lib.py、agent_lib.md。風險：無。

**6. 工具結果截 8000 字（`LIMIT`）刪。**
現況：回給模型的 JSON 字串硬截，截完不是合法 JSON。
KISS：不截；工具吐多少是工具的事（C-53 誤用不歸組件管）。
動：aos_agent_lib.py。風險：工具狂吐會撐爆 context——由工具或 system 提示管。

**7. intake 只收 `{"question"}`；`args.json` 吃完就刪。**
現況：`args.json` 兩形（`question`／`history` 整段換）；接完改名 `args.taken.json`（常數 `TAKEN`）。綁一段 history 已有另一條路＝frame 放 `history.json`。
KISS：只收 `question`；接完 `rm args.json`。
動：aos_agent_lib.py、agent_lib.md、frame.md、test_agent_frame 的 `test_intake_continues_same_frame` 後半、paint/run.py `show_frame`。
風險：失去「這次問了什麼」的旁證——history.json 裡有。

**8. 設定 key 只剩 brain、tools、system。**
現況：stdin 設定還有 `history`、`work`、`halt_after`、`halt_state`。
KISS：`history.json` 固定在 cwd、`work` 隨 #3 消失、兩個 halt 隨 #2 消失。
動：aos_agent_lib.py `load_config`、agent_lib.md、test_agent 各處 `self.cfg`。風險：無。

**9. 錯誤代號 11 個 → 6 個。**
現況：ConfigMissing、FieldType、SystemUnreadable、ReadFailed、BrainFailed、ReplyBad、HistoryMissing、ArgumentsBad、ToolUnknown、Interrupted、FsmMissing。
KISS：ConfigMissing→FieldType、SystemUnreadable→ReadFailed、ReplyBad→BrainFailed（腦沒給合法答案都算一種）、Interrupted 隨 #4、FsmMissing 隨 v3。留 FieldType、ReadFailed、BrainFailed、HistoryMissing、ArgumentsBad、ToolUnknown。
動：aos_agent_lib.py、agent_lib.md、test_agent 三處斷言。風險：無。

**10. 小零碎一起收。** `AgentError` 類改直接丟 `CliError`；`__all__` 不再 re-export frame 的函數（隨 #12）；`load_config(need_brain=)` 參數拿掉（think 之外的格不看 brain，就不驗）。動：aos_agent_lib.py。

## 腦

**11. `aos_brain_ollama.py` 刪，只留一顆 openai 腦。**
現況：140 行第二顆腦，存在理由只有 `num_ctx`（ollama 的 `/v1` 設不了），外加 `keep_alive`、兩邊形狀互翻、編 id。146 已不准用。
KISS：對 ollama 一律走它的 OpenAI 相容 `/v1`，context 長度在 ollama 那邊設（`OLLAMA_CONTEXT_LENGTH` 或 Modelfile `num_ctx`）——腦不替模型伺服器管記憶體。
動：刪 lib/aos_brain_ollama.py、bin/aos 的 `brain ollama`、test_agent 的 `BrainOllamaTest`（7 個）、demo/fsm/brains/ollama/ 兩份、agent.md 第三顆腦那段。
風險：想精準控 num_ctx 得在伺服器端設，不能每張 inst 不同。

**12. 腦的 `timeout_ms` 刪。**
現況：腦自己有 HTTP timeout，外面那張 inst 又有 `timeout_ms`，一次呼叫兩把尺。
KISS：只留 inst 的 `timeout_ms`，腦不設 timeout（被 inst 殺掉即可）。
動：aos_brain_openai.py、agent.md。風險：無。

看過、留著：`usage` 腦加／think 拿掉（LLM kernel 要用）；system.md 每拍現讀、不進 history；think「最後一則已是 assistant 就不再叫腦」（省錢）；`api_key_env`。

## frame／binding

**13. `aos_frame.py` 整檔刪。**
現況：`chain()`（parent 鏈、`MAX_CHAIN` 16、繞圈偵測）、`lookup()`、`lookup_dir()`。v3 的 E 讓 parent 鏈退場後，剩下的只是「cwd 有這個檔嗎」。
KISS：併回 aos_agent_lib.py 一個 `os.path.exists` 判斷；MAX_CHAIN、繞圈都不需要。
動：刪 lib/aos_frame.py，test_agent_frame 的 `test_lookup_chain_and_dir_merge`，code map。風險：無（前提是 v3 E 落地）。

**14. 綁定只留一句規則。**
現況：brain 一條規則、tools「逐項合併＝追加＋同名蓋過，整份取代先不支援」另一條、system 又一條。
KISS：一句：**每個名字（`brain.json`、`system.md`、`tools/<x>.json`），cwd 有就用 cwd 的，否則用定義的。** 「整份取代不支援」那句刪（不是功能，不用宣告沒有）。
動：agent.md／frame.md。風險：無。

## demo/paint

**15. run.py 三段 → 一段。**
現況：154 行：叫畫家、同 frame 續聊、換腦；`--keep`、`find_brain()` 三處找腦、`tree_hash()` 驗定義沒被改、`bind_brain()` 改寫工具 inst 多一步 cp、`brains/fake_alt.json`＋假腦 `--name` 旗標。
KISS：只做一件事——建 frame、放 `args.json`、跑畫家、印 ret.json 和資料夾樹，刪 frame。續聊、換腦、定義沒被改都已是測試。`fake_alt.json`、`--name`、`--keep`、`find_brain`、`tree_hash`、`bind_brain` 全刪；腦設定照給的路徑用。
動：demo/paint/run.py、brains/fake.py、刪 brains/fake_alt.json、README.md。
風險：demo 看不到換腦——README 一行說「cwd 放 brain.json」即可。

**16. demo/fsm/brains 5 份 → 2 份。**
現況：openai.json、litellm.json（兩份都指 LiteLLM）、lmstudio.json、ollama/×2（146 已禁）。
KISS：留 litellm.json、lmstudio.json。
動：demo/fsm/brains/、demo/fsm/README.md、paint/README.md 提到的名字。風險：無。

## 測試

**17. test_paint_demo 3 個 → 1 個。**
現況：巢狀＋續聊、換腦只到自己的 frame、跑 run.py；前兩個跟 test_agent_frame 的 bob（續聊、綁定、agent 當工具）重複，第二個的語意又會被 v3 F 改掉。
KISS：只留 `test_run_script`（demo 會跑）；行為測試集中在 bob。
動：lib/tests/test_paint_demo.py。風險：無。
連帶：#2 刪 halt 計數後 bob 的 `test_halted_writes_error_ret` 改成「腦錯一次就 halted」；#4 刪兩個 interrupted；#11 刪 7 個 ollama；#13、v3 刪 lookup 與 fsm 子命令兩個。test_agent＋test_agent_frame＋test_paint_demo 共 41 個，估剩約 26 個。

## 說明

**18. 三檔併一檔。**
現況：agent.md（65 行）＋agent_lib.md（33）＋frame.md（52），拆檔理由只是超過 8 KB；agent.md 裡一半是 146／qwen／LM Studio 實驗記錄、「為什麼不走 ollama /v1」、查過 boss 用哪顆腦。
KISS：一份 agent.md：思考介面（一段 JSON）、定義資料夾與 frame（一棵樹＋一行呼叫）、三格做什麼（各一行）、邊緣表（三列）。實驗記錄只留連結到 thinking。做完 #1～#16 內容本來就不到 8 KB。
動：lib/agent.md、刪 agent_lib.md、frame.md、lib/README.md 連結、demo 兩份 README 的連結。風險：無。

## 規範

**19. N-27 的 agent 那句刪。**
現況：「agent 的工具每次在一個新資料夾裡跑（frame，預設呼叫者 `work/<n>/`），arguments 落成那裡的 `args.json`，也照本條當 stdin」。
KISS：隨 #3，只剩本條原句「參數走 stdin」；agent 不是特例。
動：NORMS/03-基礎設施-inst.md。風險：無。

NORMS 其他沒有 agent 專屬的條（agent 是實作慣例），不用再動。

## 最小核心（從零重寫只留這些）

- **腦介面**：stdin `{"messages", "tools"}` → stdout 一份 assistant 訊息。一顆 `aos brain openai`（base_url、model、api_key_env）。
- **三格＋一格收尾**：`intake`（`args.json` → history）、`think`（叫腦、接 history、吐 `next: tool|done`；腦錯＝寫 `ret.json` 錯、`next: halted`）、`tool`（還沒回的 tool_calls → stdin 餵工具 inst → tool 訊息）、`done`（`ret.json`＝最後一句）。設定三個 key：brain、tools、system。
- **定義資料夾**：`inst.json`（v3）、`brain.json`、`system.md`、`tools/*.json`。**frame＝cwd**：`args.json`、`history.json`、`ret.json`、兩扇窗；cwd 同名檔蓋定義。
- **一份 agent.md、一個 demo（paint，一段）、一份行為測試（bob）＋一個 demo smoke。**

不在範圍：CONCEPTS（C-46 的 frame／parent 文字會隨 v3 改，概念本身不審）。
