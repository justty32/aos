# KISS 審視彙整：8 份稿去重、衝突、總表、批次（10-15 深夜）

← [討論紀錄](../README.md)｜8 份稿（各稿不改）：[鳥瞰](overview.md)、[loop／daemon](loop-daemon.md)、[窗](windows.md)、[fsm](fsm.md)、[kernel](kernel.md)、[agent](agent.md)、[總則與共通](general.md)、[組合子](combinators.md)｜相關：[inst-exec 第四版](../2026-10-15-inst-exec-v4.md)（使用者答了第三版 A～L；第四版矛盾與未決 C～P 10-15 深夜已定：「C-50 選 a，其他都按照推薦」）、[原則稿](../2026-10-15-principles.md)（切乾淨＋KISS，已做）

> **⚠ 10-16 使用者撤回「都照推薦」、要重看**：「關於KISS大掃除那塊，我說都照推薦...那是我昨天在打遊戲懶得思考的情況下說的，我後悔惹QQ，等一下我想要重新看過。」所以：**批次 1 已做**（各列 commit 見總表）**可逐項翻案**；**批次 2～6 暫停**，等使用者重看再動。同日 C-56 本條改寫成「KISS 也是最後原則」（先滿足需求與其他原則，最後才做減法，[10-16 稿](../2026-10-16-kiss-last.md)），本檔的推薦是照舊說法「最乾淨、規則最少」給的，重看時要拿新說法再對一次。

> 使用者 10-15 深夜：「拿KISS原則重新去思考各種東西」「去思考現有的規範和實作。概念倒是不用。」KISS 是最高原則（C-56），層要徹底切割（C-52 加嚴：「想要看子層的東西請另外透過其他機制，沒機制就別碰」）。本檔只彙整，每條只給一個推薦。**10-15 深夜使用者拍板**：「C-50 選 a，其他都按照推薦」——總表與衝突表照推薦做（含 ★ 翻案）；6.10 PLAN 使用者另說「刪掉」。各條做完標「已做（commit）」。

## 摘要：砍完剩什麼

- **程式 13 支**（現在 lib 24 支＋proto8-1 6 支）：`aos_cli`（含指示詞）、`aos_inst`、`aos_exec`（人用的糖，形狀照第四版）、`aos_loop`、`aos_daemon`（不再繼承 loop、沒身體）、`aos_ctl_state`、`aos_proc`、`aos_fsm`（格庫方法併進來）、`aos_agent`（intake／think／tool／done 四格）、`aos_brain_openai`、`aos_gate`、`aos_kernel`（一支）、`aos_tick`；tasks 四支留著（使用者「少用 sh」、stdlib 地位）但瘦身成三支。
- **規範約 15 條**（現在 44 條，九個分檔）：一份 NORMS.md——總則 4 條（先暫存再改名；stdin／stdout／stderr 都是 JSON 串流、半份不算、stdout 最後一份帶 `"end": true`＝不必再叫；錯誤出口 0／1、stderr 一種形狀、每層只說自己；規範沒說的邊緣狀況預設不會發生）、inst 1 條、窗 3 條（窗是什麼、ctl、state）、loop 1 條、daemon 1 條、fsm 4 條、時鐘 1 條、kernel 1 條。
- **砍掉的**：第二支 kernel、第二顆腦、aos_tree、daemon 指令資料夾、frame.json、exit 檔、三個 `*_inherit`、fixed 節奏與三個 ms 旋鈕、ctl 的 `now`／`seq`、心跳三欄、七態、策略格、table 窗、route 格、think 連錯計數、aging／log／defer、`$at` 與相對指示詞、標準實作分級、條文裡的沿革句。
- **一句話**：inst 是唯一的東西，loop 讓它反覆，fsm 讓它分狀態，kernel 讓它排隊，tasks 把它們串起來；其他全是 JSON 本來就會的。

## 已做（另一位 agent，commit 1a5cd68c、ab1928e3、b629e128）

原則稿第 2、4、5、6 條＋KISS 寫進設計理念，都已 commit、ctest 全綠：

| 編號 | 做了什麼 | 對應本彙整 |
|---|---|---|
| 0.1 | C-56 KISS＝最高原則；C-52 加嚴（沒機制就別碰、上層不知道下層是什麼）；C-53 補「下層的錯不轉述」 | 全部的尺 |
| 0.2 | daemon 收子項裡面不驗（`_check_inst`、`aos_inst.parse`、loop `check_config` 拿掉，原樣灌 stdin；表上 `times` 欄拿掉） | 3.1～3.5 的前提 |
| 0.3 | fsm 不讀格 stderr（`cell_error` 拿掉）；`error.msg` 只說「格 X 結束碼 N」；think 也不讀腦 stderr | 4.2 做了一半 |
| 0.4 | 巢狀規矩：沒結束的拍自己那行帶 `next: null`＝留原狀態（N-37、N-40），外層不必知道格是 fsm | 4.1、4.3 的前提 |
| 0.5 | agent 只看到工具清單；`work/<n>/` 改稱「工具的工作資料夾」（要不要當 frame 是工具 inst 自己的事） | 2.8：`work/<n>/` 留 |

## 使用者對第三版的回覆怎麼影響本彙整

使用者 10-15 深夜回 inst-exec 第三版：**A** TARGET 必填；**D** inst 的 `stdin` 不收內嵌 JSON（要的話另開一個 key 明說，第四版推薦 `stdin_inline: true`）；**G** 不要 `sh`，工具 argv 直接 `aos loop`，「少用sh」（已記進 user.md）；**H**「不要濫用內嵌，指示詞只是用來拆檔用的」，再追加「後續都默認沒有指示詞能用，但不用擔心json太大」→ **N-45**；其餘照推薦。[第四版](../2026-10-15-inst-exec-v4.md)已寫好（一個 agent 的定義＝一張 inst、跑在哪 cwd 就是 frame、工具一律走 frame：`work/<n>/` 的 args.json 進、ret.json 出、agent 不碰工具的 stdin／stdout、agent 當工具＝argv 直接 `aos loop`），未決 C～P 10-15 深夜已定照推薦。所以：

- 凡是碰 inst／aos-exec／TARGET／frame／「定義在哪」的條目，本檔標「**隨 v4**」＝跟第四版一起做、形狀照它，這裡不另定。
- 凡是原稿推薦「用 `sh -c` 取代程式」的，風險欄加「使用者偏好少用 sh」並**重判**。重判後翻掉的有四條：tasks 四支換 sh（不砍，改瘦身）、inst 布林換 `>>`／`2>&1`／`mkdir -p`（只砍三個 `*_inherit`，其餘留）、agent 的 `work/<n>/` 換工具自己 `mktemp`（不砍）、`檔#/位置` 退出 aos-exec（不退：設計假設沒有指示詞，一份檔放多張 inst 要有路可指，C-48）。
- 「設計一律假設沒有指示詞」：本檔每條推薦都不靠 `$ref`／`$env` 才成立；demo 用 `$env` 省字是便利，不是機制。

## 衝突（份與份之間、或與第三版之間；每題一個推薦）

| 題目 | 兩邊 | 推薦 |
|---|---|---|
| agent 的 `work/<n>/` | agent 稿 #3 拿掉、工具自己開資料夾 vs 第三版 G 工具 stdin 放 brush 的 loop 設定 | **都不採，照第四版 G**。使用者「不要 sh」＋「stdin 不收內嵌」兩邊都死：工具自己開資料夾要 sh，stdin 內嵌沒了。第四版：`work/<n>/` 留，但比現況更少——tool 格對每張工具只做「開 `work/<n>/`、寫 args.json、以它為 cwd 跑、讀 `work/<n>/ret.json` 當結果」，不碰工具的 stdin／stdout、不接 stdout.json；agent 當工具＝工具 inst 的 argv 直接 `aos loop`，brush 的 intake 讀 args.json、done 寫 ret.json，就是它自己的 frame |
| daemon 要不要是 loop | 鳥瞰 #3 daemon 併進 loop（設定有 `children` 就多管子項） vs loop／daemon 稿 D5、窗稿 #11 daemon 不繼承 loop、沒身體 | **D5**：兩支小程式（loop 約 150 行、daemon 約 80 行），只共用 ctl／state 與 aos_proc。併進 loop 會讓 loop 認得 daemon 的 key（跨層）。翻 N-28「daemon.json 是 loop.json 嚴格超集」（10-14 候選 g）；C-36「daemon 自己也是一個 loop」是概念、不動——反覆看表也是 loop |
| `檔#/位置` 住哪 | 總則稿 #1 只活在 `$ref`、aos-exec 不接 vs 第三版步驟 1／C 留在 aos-exec、id＝`abspath#/位置` | **留在 aos-exec**（第三版，使用者「其餘照推薦」）。總則稿的理由是「只有測試在用」，但 C-48 要求設計假設沒有指示詞，拿掉後一份檔裡的第二張 inst 就指不到了；H 不濫用內嵌也需要它。第四版 P 說「本稿不動」，所以本檔定：留 |
| 排序政策放哪 | 鳥瞰 #2 政策全搬判官、kernel 身體零政策 vs kernel 稿 #2／#3 規則一份在 kernel、判官可有可無 | **kernel 稿**：判官錯時 kernel 本來就要有規則；全搬判官＝每拍多起一張 inst。規則只剩「級數→deadline→先來後到」 |
| ctl 認哪些 key | loop 稿 L3 只剩 `paused`／`stop` 兩布林 vs 窗稿 #19 還認 `times`、`interval_ms` | **L3**：改節奏＝停了重起（N-11 對位置類本來就這麼說，節奏類跟著走）；daemon 多一個 `children`。翻 N-11「節奏類可蓋」（10-12） |
| 窗必填還是選填 | loop 稿 D4 children 每項自己寫好窗（必填） vs 窗稿 #12 窗一律選填、N-19 刪 | **選填**（一條規則沒有例外）＋ daemon 不替子項補路徑：子項沒 ctl＝收工送 SIGTERM、沒 state＝只看結束碼；fsm 的 `state` 改列在 fsm 設定的必填項，不用窗的規則管。翻 N-19（10-14 夜） |
| table 窗 | 窗稿留一列 `{id, ctl, state, pid, code}` 給人看 vs loop 稿 D2 併進 daemon 自己的 state 窗 | **D2**：少一扇窗、`kind` 跟著消失 |
| 心跳留多少 | 鳥瞰 #14／loop 稿 L9 留 `pid`、`beat` vs 窗稿 #3 全刪、state 只在變了才寫、活著看 pid | **窗稿**：全 repo 沒人讀 `beat`；`kill -0` 是 Unix 本來的做法。翻 N-17、N-32 |
| state 幾態 | 鳥瞰／loop 稿三態 vs 窗稿五態 | **三態** `running`／`paused`／`stopped`（跑滿沒跑滿看 `runs`／`times`） |
| think 連錯 | agent 稿 #2 腦錯一次＝寫 `ret.json` 錯、回 `halted` vs fsm 稿 #4 全砍、think 退 1、停住靠 loop 的 `times` | **fsm 稿**：零計數、零私檔、零 `halted` 狀態，重試＝loop 本來就會的；`ret.json` 沒有＝沒跑完（Q12 已定）。翻 10-15 晚盤點第 8 條、LiteLLM 實跑拍板「腦連錯 halted」 |
| `stop_on_end` | 鳥瞰 #6 旗標刪、永遠生效 vs loop 稿 L4／組合子稿 #12 留 key；L4「最後一份」vs #12「任一份」 | **旗標刪、最後一份**：寫成 N-12 通則「stdout 最後一份帶 `"end": true`＝不必再叫我」，loop 只認這句、不知道 fsm |
| aos_methods 併不併 | fsm 稿 #14 併進 aos_fsm vs 組合子稿「看過不動」 | **併**：一檔一種錯誤；`run_cell(args)` 那個分支留（D 不做，think 還要把請求落暫存檔當 stdin） |
| NORMS 併回幾份 | 總則稿 #10 全併一份 vs 鳥瞰 #24 只併 02、09 兩個小檔 | **全併一份**，但排在條文瘦身之後、量過再併（估 12 KB）。翻 10-15「按主題分」——主題留當 `##` 標題 |
| ollama 腦 | 鳥瞰 #8 搬去 demo vs agent 稿 #11 刪 | **刪**（146 已禁用；context 長度在伺服器端設） |
| brains 留幾份 | agent 稿 #16 litellm＋lmstudio vs fsm 稿 #10 fake＋openai＋lmstudio | **fake、litellm、lmstudio**（openai.json 跟 litellm 重複、ollama 已禁） |
| intake 的 `args.json` | agent 稿 #7 吃完刪 vs fsm 稿 #7 改名 `args.taken.json` | **刪**（history.json 裡有） |
| 閘門的 `AOS_KERNEL` | 鳥瞰 #17 `mailbox` 必填 vs kernel 稿 #5 gate.json 寫 `$env` | 閘門程式不認任何環境變數，`mailbox`／`priority` 寫在 gate.json；demo 要省字用 `$env`（只是便利，C-48） |
| `signal` 欄 | loop 稿 L5 刪（訊號＝stop 當場版、退 0） vs 窗稿最小核心留 | **刪**：loop、daemon 同一條。翻 10-15 晚待定 A～C「loop 退 1 記 signal」 |
| `last_error` 形狀 | 總則稿 #13 物件 `{code, msg}` vs 窗稿 #21「代號: 白話」字串 | **物件**（跟 stderr 同一形） |
| tasks 要不要砍 | 鳥瞰 #5／組合子稿 #1 刪四支換 sh vs 使用者「少用 sh」、「地位等同 C 的 stdlib」 | **留**，改瘦身（1.19）。換 sh 的推薦不成立 |
| 第三版 H「tasks 從 stdin 收」 | 第四版 H 表「argv → stdin，或照鳥瞰 5 整個刪」 vs 1.17 留 | tasks 留（1.17），所以照第四版 H 表改從 stdin 收（seq／par＝一串 inst、if＝`{"cond", "then", "else"}`） |

## 總表（依「先做會讓後面變簡單」分批；每批可獨立 ctest 全綠）

欄位：編號｜區｜現況 → KISS 版（一句）｜翻案？（★＝推翻使用者親定，附日期與原話出處）｜來源稿。「隨 v4」＝跟第四版綁在一起、形狀照它。

### 批次 1：純刪、彼此不相依、不碰第四版的形狀（**已做**，10-15 深夜四個 commit；自定點見 [10-15 session log](../../../wf/session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)）

| 編號 | 區 | 現況 → KISS 版 | 翻案？ | 來源 |
|---|---|---|---|---|
| 1.1 | inst | `exit`／`exit_append`／`exit_mkdir`、`read_exit()`、N-30／N-12「exit 檔出現也算」、demo once／tick、test_tick 的 exit 檔 → 全刪，子程式的碼只在結果的 `code` | ★ 10-12「子程式的碼進 exit 檔」（[inst 進 json](../2026-10-12-inst-json.md)）、10-14 深夜「exit 檔出現也算跑完」（N-12） | 鳥瞰 9、組合子 7、總則 5 ｜ **已做** cb20249a |
| 1.2 | inst | 12 個布林 → **只砍 `stdin_inherit`／`stdout_inherit`／`stderr_inherit`**（寫 `/dev/stdin`／`/dev/stdout`／`/dev/stderr` 路徑就是繼承；N-26 整條與三條 Conflict 檢查消失，第四版 D 說的「`stdin_inline` 與 `stdin_inherit` 同時寫＝Conflict」也跟著不用）；`*_append`、`*_mkdir`、`cwd_mkdir`、`stderr_merge`、`envs_clear` **留**，第四版的 `stdin_inline` 加進來。風險：原稿要全砍換 `>>`／`2>&1`／`mkdir -p`，使用者偏好少用 sh，不採 | — | 鳥瞰 10（重判）、第四版 D ｜ **已做** cb20249a |
| 1.3 | loop | `interval_mode: fixed`＋`skipped`、`error_wait_ms`、`ctl_poll_ms`、loop 自己的 `grace_ms` → 只留 `interval_ms`：跑完隔一段再起、ctl 每圈讀、出錯不另算、收身體＝SIGTERM 後等 aos_inst 自己收（它保證過 `grace_ms`） | — | 鳥瞰 11、loop L1 L2、窗 5 6 7 ｜ **已做** cb20249a |
| 1.4 | ctl | `paused`／`stop` 的 `{"val", "now"}` 雙形 → 只收布林；當場停＝送訊號 | ★ N-07 10-12（[ctl 規範](../2026-10-12-ctl-norms.md)） | 鳥瞰 12、loop L3、窗 1 ｜ **已做** cb20249a |
| 1.5 | agent | `aos_brain_ollama.py`、`brain ollama`、7 個測試、demo/fsm/brains/ollama → 刪，只留 OpenAI 相容一顆 | — | 鳥瞰 8、agent 11 ｜ **已做** fa6629ee |
| 1.6 | agent | 腦自己的 HTTP `timeout_ms` → 刪，只留 inst 的 `timeout_ms` | — | agent 12 ｜ **已做** fa6629ee |
| 1.7 | agent | `LIMIT` 截 8000 字、`.tool-running.json`／`Interrupted`、tool stdout 四格、intake 兩形＋`args.taken.json`、設定 key `history`／`work`／`halt_*`、11 個代號、`AgentError`、`need_brain` → 不截；被殺就重跑；stdout 一格 `{"data": {"tools": […]}}`；intake 只收 `question`、吃完刪 `args.json`；設定只剩 `brain`／`tools`／`system`（`history.json`、`work/` 固定在 cwd）；代號 6 個；直接丟 `CliError` | — | agent 4～10、fsm 6～8 ｜ **已做** fa6629ee（halt_after／halt_state 留到批次 4、FsmMissing 留到批次 2） |
| 1.8 | kernel | 閘門 `wait_ms`／`poll_ms`／`QueueTimeout`、`_metainfo.resource` 沒寫＝直接跑、只有一封直接跑、判官 `defer`、`JUDGE_TIMEOUT_MS` 預設 30 秒、`log` jsonl、`slots` 純值糖、三個空錯誤類別、閘門驗 priority、三處刪旁檔、ask_judge 五種代號 → 全刪或收成一條（資源沒寫＝`ResourceUnknown`；有信有空格就問判官；判官只回 `{run, reject}`；任何失敗一律 `JudgeFailed`） | ★ `defer`：10-15 使用者「隨意」定三種話（[通用 kernel](../2026-10-15-general-kernel.md)）——跑、不跑、沒說三種還在，少一個 key | kernel 4 7 8 9 10 11 14 15 18 20 22 ｜ **已做** 7d833687（defer 刪＝三種話還在、少一個 key） |
| 1.9 | kernel | 閘門讀 `AOS_KERNEL`／`AOS_PRIORITY`、kernel 替判官清 `AOS_KERNEL`、`aos-demo` export `AOS_DEMO` → 閘門不認環境變數（`mailbox`／`priority` 寫在 gate.json）；kernel 跑判官一個 key 都不碰；`aos-demo` 只留「`.py` 轉指令名」那一招 | — | 鳥瞰 17 20、kernel 5 6 ｜ **已做** 7d833687（`aos-demo` 的 AOS_DEMO 那招留到批次 2：三張 sh -c 工具 inst 還靠它，2.7 本來就隨 v4 退場） |
| 1.10 | 共通 | `$at`、位置相對寫法 `./`／`../`／空檔名、`~0`／`~1`、7 個代號、`DirectiveError`、`aos_directives.py`、`expand(key=)`、`directives.md` → `$ref` 只收「檔#/從根算的位置」；一個 `DirectiveBad`；併進 `aos_cli.py` 一檔；檔頭就是說明 | — | 總則 14～19 22 ｜ **已做** cb20249a |
| 1.11 | 共通 | `aos_tree.py`＋`test_tree.py`（含自製 schema 驗證器）→ 刪（第三版已定 6；`schema.json` 留當資料） | — | 總則 21 ｜ **已做** cb20249a |
| 1.12 | fsm | 檔頭與 fsm.md「舊 key `ctl`／`lock`／`max_steps` 也忽略」＋`test_old_keys_ignored` → 刪（不認得的 key 忽略是通則） | — | fsm 11 ｜ **已做** cb20249a |
| 1.13 | loop | `aos_loop` 把 `aos_ctl_state`／`aos_proc` 再 export 一遍 → 刪，誰用誰直接 import | — | loop M1、窗 18 ｜ **已做** cb20249a |
| 1.14 | 共通 | `write_json` 只建一層、不 `-p` → `makedirs(exist_ok=True)` 一句 | ★ 10-15 晚盤點 P3「都按照推薦」（小） | 窗 23 ｜ **已做** cb20249a |
| 1.15 | demo | kernels/llm demo 在 clerk 的 frame 放 boss 的 `brain.json`、paint 的 `--keep`／換腦靠在下層 frame 放檔 → demo 不示範「上層伸手進下層的 frame」；要換 clerk 的腦改 clerk 自己的定義 | — | 鳥瞰 16 ｜ **已做** fa6629ee |
| 1.16 | demo | `demo/tick` 印 `date`、跟 aos-tick 同名不同事 → 改成真的 `aos tick clock`，README 改看 clock 檔 1→5 | — | 組合子 8 ｜ **已做** a0c7214d |
| 1.17 | tasks | 四支（316 行、14 測試、12 張 inst 的 demo）→ **不砍**（原稿換 sh；使用者「少用 sh」＋「地位等同 C 的 stdlib」）。改瘦身：`aos-not` 刪（反過來寫 `aos-if X 失敗格 成功格`；N-43 述詞例外、N-34 述詞句跟著刪）、「先全部驗過才跑」砍（跑到哪讀到哪）、proto8-1 整個併進 proto8/lib（一個 lib、一個 bin、`aos seq|par|if|tick`） | ★ 述詞例外 10-15 晚「都按照推薦」（S5）；tick 搬家只改路徑 | 組合子 1～4（重判） ｜ **已做** a0c7214d（proto8-1 整個併進 proto8：lib、tests、demo/tasks；述詞例外隨 aos-not 刪） |
| 1.18 | 待定 | 08 待定 §28「回合數格式算不算規範」→ 結案＝不是（aos-tick 是糖，格式寫在它檔頭） | 替他結案，一句可翻 | 組合子 6 ｜ **已做** cb20249a（替他結案，一句可翻） |

### 批次 2：隨 v4（inst／aos-exec／TARGET／frame，跟第四版一起做）

| 編號 | 區 | 現況 → KISS 版 | 翻案？ | 來源 |
|---|---|---|---|---|
| 2.1 | inst | aos-inst 吃 TARGET、旗標、`-` → **隨 v4**：aos-inst 零引數只吃 stdin；`aos-exec TARGET [--key 值] [-- argv]`（TARGET 必填，A）；旗標與 `-` 只在 aos-exec；NORMS/06 三條變成 aos-exec 檔頭的用法、整檔刪 | — | 第三版 3 4 I、總則 3 |
| 2.2 | 總則 | N-35 `檔#/位置`、資料夾找 inst.json、id → **留在 aos-exec**（總則稿「退出規範」不採，見衝突表）；id＝`abspath#/位置`（第三版 C） | — | 總則 1（重判） |
| 2.3 | agent | `frame.json`／`parent` 鏈、`aos_frame.py`（`chain`、`MAX_CHAIN`、繞圈） → **隨 v4**：退場（E 照推薦）；綁定一句「每個名字 cwd 有就用 cwd 的，否則用定義的」（F 照推薦）；「整份取代不支援」句刪 | — | agent 13 14、第三版 E F |
| 2.4 | agent | `aos agent fsm` 子命令（用 frame 找 fsm.json 再叫 aos_fsm） → **隨 v4**：刪，loop 直接 `aos fsm`（第四版 P） | — | 鳥瞰 7 |
| 2.5 | 各處 | JSON 裡的 TARGET 字串（daemon `children`、閘門 `target`、kernel judges、fsm 格、agent 的 `brain`／`tools`、tasks）→ **隨 v4** H 表：原本放 TARGET 字串的地方放那份 JSON 本身（資料形，N-45 JSON 大沒關係；children `id` 必填）；N-36「格從設定檔所在資料夾算」句、fsm 的 `FLAGS`／`base_of`／`ident`、`aos_cli.load_target` 一串刪 | — | 第四版 H、fsm 16 |
| 2.6 | 共通 | `run(x)` 收路徑或 dict、loop 六層入口（`run`／`load_config`／`check_config(ident, doc, defaults, need_inst, err)`／`main`／`Loop.run`／`serve`） → **隨 v4**：`aos_inst.run(dict)` 只收 dict（J）；loop 剩 `main()`（stdin→dict）與 `Loop(cfg).run()`，驗證表只列 loop 自己的 key | — | loop M2、第三版 J |
| 2.7 | agent | agent 當工具：三張 `sh -c` 三步的工具 inst；tool 格把 args.json 同時當 stdin、接 stdout.json → **隨 v4** G：工具一律走 frame（`work/<n>/` 的 args.json 進、ret.json 出），tool 格不碰工具的 stdin／stdout；agent 當工具＝工具 inst 的 argv 直接 `aos loop`；`AOS_DEMO` 退場。agent 稿 #3「拿掉 `work/<n>/`」不採（要 sh） | — | agent 3（重判）、第四版 G |
| 2.8 | agent | 五個定義資料夾 `fsm.json` md5 全同、`cells/` 幾乎全同 → **隨 v4** P：lib 放一張預設 inst，demo 各自只換 brain／system／tools（第四版 M：`system` 直接寫字串） | — | 鳥瞰 18 |

### 批次 3：loop／daemon／窗重做（一次做完，因為 ctl／state 的形狀牽一髮動全身）

| 編號 | 區 | 現況 → KISS 版 | 翻案？ | 來源 |
|---|---|---|---|---|
| 3.1 | daemon | N-10 指令資料夾：`aos_daemon_folder.py`、九條指令、`.done` 一問一答、`ScanFailed`／`ReplyFailed`／`given_up` 三層補救、`ctl_dir` 衝突檢查 → 全刪；daemon 的 ctl 多一個 `children` key＝「我要表上有誰」（整份就是全部期望，N-06 本意）；暫停某個子 loop＝直接寫它的 ctl；看它＝讀它的 state | ★ N-10 10-12「daemon 這塊才是資料夾」（[ctl 規範](../2026-10-12-ctl-norms.md)、[loop／daemon](../2026-10-12-loop-daemon.md)） | 鳥瞰 4、loop D1 D6、窗 10 |
| 3.2 | daemon | `Daemon(Loop)` 六個掛鉤、有身體有 `times`、「daemon.json 是 loop.json 嚴格超集」 → daemon 不繼承 loop、沒身體：設定 `{children, interval_ms, ctl, state}`，約 80 行小迴圈；要每拍做一件事＝children 裡放一個 loop；loop 的驗證表不再混 daemon 的 key | ★ N-28 10-14 夜末候選 g「loop.json 直接丟給 aos-daemon 也要能跑」；10-12「自己也是一個 loop」（概念 C-36 不動） | loop D5、窗 11（鳥瞰 3 不採） |
| 3.3 | daemon | table 窗、`load: true` 接回、/proc 認領孤兒（`proc_started`、`boot_id`）、子項六態 `phase`、`kind` → 全刪；children 列進 daemon 自己的 state 窗 `[{id, pid, state(alive|exited), last_code}]`；daemon 被 -9 的孤兒自己 `pkill` | ★ 10-14 暫定 d（table＝save 檔、`--load`）、b（六態撞名不改）10-15「全定」（[七題回覆 §33](../2026-10-14-json-entry/12-七題回覆.md)） | loop D2、窗 4 9 15、鳥瞰 15 |
| 3.4 | daemon | `policies.child_exit` 策略格、退避、`MAX_EXITS`、`policy.in/out.json`、把子項 state 整份塞給策略格 → 刪；子 loop 結束＝表上記 `last_code`；要重來＝loop 自己的 `times` | ★ 10-15 暫定 f「全定」（同上） | loop D3、窗 8 |
| 3.5 | 窗 | N-19 窗必填（`require()`、`WindowMissing`）、daemon 替子項在 `work_dir/N/` 補 ctl／state、接 `err.json` → 窗一律選填（一條規則沒例外）：loop 沒 ctl＝只能訊號停、沒 state＝結果在 stdout；`work_dir` 刪，daemon 不替下層發明路徑；子項 stdout／stderr 丟掉；fsm 的 `state` 列在 fsm 設定必填項 | ★ N-19 10-14 夜；`work_dir/N/err.json` 10-14 深夜「隨你」方案 B | loop D4、窗 12 |
| 3.6 | 窗 | ctl 認 `times`／`interval_ms`／`interval_mode`、`initial`＋`want()` 回初始值、`stopping` 閂鎖、「stop 壓過 paused」、檔不見＝維持上一次（`CtlMissing`） → ctl＝`{"paused", "stop"}` 兩布林（daemon 多 `children`）；改節奏＝停了重起；ctl 純宣告沒記憶；檔不見＝全部初始值（壞檔仍維持上一次） | ★ N-07／N-11 10-12（節奏類可蓋）、N-08 10-12（檔不見維持上一次） | loop L3、窗 16 17 19 |
| 3.7 | 窗 | ctl `seq`／state `ctl_seq` 回音（N-33、N-14 半句） → 刪（只有 3.1 的回執在用） | ★ 暫定 c 10-15「全定」 | 鳥瞰 13、loop L3、窗 2 |
| 3.8 | 窗 | 心跳 `beat`／`started`／`boot_id`、每秒碰一下（N-17、N-32） → 全刪；state 只在內容變了才寫；活著看 `pid` | ★ N-17 10-14、N-32 10-14 深夜 | 鳥瞰 14、loop L9、窗 3 |
| 3.9 | 窗 | state 七態 → 三態 `running`／`paused`／`stopped` | — | 鳥瞰 15、loop L7（窗 22 五態不採） |
| 3.10 | loop | loop 收訊號退 1 記 `signal`、daemon 退 0、`LoopError.exit` → loop 同 daemon：SIGTERM／SIGINT＝`stop` 當場版（收身體、寫最後 state、退 0）；`signal` 欄刪；SIGHUP 不接 | ★ 10-15 晚待定 A～C「按照推薦」（loop 退 1、訊號記 `signal`，[原則稿](../2026-10-15-principles.md)） | loop L5 |
| 3.11 | loop | 退出碼看最後一次 aos_inst 有沒有錯（`inst_exit`）、`last_warning`（`CtlBad`／`CtlMissing`／`CtlReadFailed`＋daemon 四種）、`error_now`／`warning_now` 兩個掛鉤 → loop 退 1 只有「起不來」「state 寫不了」；state 一格 `last_error`，物件形 `{code, msg}`（跟 stderr 同形）；ctl 壞檔＝維持上一次、不記 | ★ N-08 `last_warning` 10-15 晚 S1「都按照推薦」 | loop L6、窗 21、總則 13 |
| 3.12 | loop | stdout 每拍 `{run, code, ms}`＋結束總結（N-31） → 只在結束吐一份＝最後那份 state 的內容 | — | loop L8 |
| 3.13 | loop | N-44 `stop_on_end` 旗標、`_saw_end` 認 `from`／`to`、讀 stdout 記 offset → 旗標刪、永遠生效：身體 stdout **最後一份**帶 `"end": true`＝不再起下一次；loop 不知道 fsm；N-44 併進 N-12 通則；讀法一條：有 stdout 檔就讀整份取最後一份 | N-44 10-15 收工後「都按照推薦」（主控推薦，非使用者原話） | 鳥瞰 6、loop L4、fsm 17、組合子 12 |
| 3.14 | daemon | `shutdown(now, grace_ms, got)` 兩條路、`aos_proc` 四個函數 → 收工一條：替活著的子項寫 `stop: true`、等它們；當場＝對子項送訊號；`aos_proc` 只剩 `stop(proc)`、`reap(proc)` | — | loop M3 M4 |
| 3.15 | demo | `demo/daemon.json`＋`run.py` 主角是 12 條指令 → children 兩個 loop、起 daemon、寫 tick 的 ctl 暫停／放行／停、SIGTERM 退 0；loop 測試 23→約 9、daemon 20→約 6 | — | loop T1 T2 |

### 批次 4：fsm／agent 收攏（在批次 3 之後，因為 3.13 定了 `end` 的通則）

| 編號 | 區 | 現況 → KISS 版 | 翻案？ | 來源 |
|---|---|---|---|---|
| 4.1 | fsm | 下一狀態四種情形、兩個 `ResultMissing`、`cell_empty` 旗標（N-37、N-38） → 一條：最後一份完整 JSON 的 `next`（`null`＝留，已做 0.4）＞ 表上 `next` ＞ 留原狀態；沒吐、半份、垃圾＝沒有結果，不報錯 | — | fsm 1、組合子 10 |
| 4.2 | fsm | 那行轉述格的 N-30 七欄（`id`、`code`、`signal`、`pid`、`ms`、`exit_file`…）、`ERR_LIMIT` 300 字、替格推 id `#/states/<名>` → 那行只說自己：`{"from", "to"}`＋選填 `end`／`next`／`error`（`error.msg` 只說結束碼，已做 0.3） | — | fsm 2 |
| 4.3 | fsm | 結束那拍多吐一份「那格的結果」（N-40） → 只吐那一行、行裡帶 `next`（那格回的） | ★ N-40 10-15「把那格的結果原樣當最後一份交出去」（[意見 1～4](../2026-10-15-opinions-1-4.md)；end 四情形本身不動） | fsm 3 |
| 4.4 | agent | route 格（讀 history 看有沒有 tool_calls、`--done` 旗標） → 併進 think：叫完腦直接吐 `next`（有 tool_calls＝`tool`、沒有＝`done`）；五張表少一個狀態 | — | agent 1、fsm 5 |
| 4.5 | agent | think 連錯計數：`halt_after`、`halt_state`、私檔 `work/think.json`、`_think_failed()`、`SystemUnreadable` 特判、七張表的 `halted` → 全刪：腦錯＝think 退 1，fsm phase 不動，重試＝拍它的 loop 的 `times`；`ret.json` 沒有＝沒跑完 | ★ 10-15 晚盤點第 8 條「都按照推薦」、[LiteLLM 實跑](../2026-10-15-litellm-live.md)拍板「腦連錯 halted」 | fsm 4（agent 2 不採） |
| 4.6 | fsm | `aos_methods.py`＋`aos_fsm.py` 兩檔、`MethodsError` 包成 `FsmError` → 併一檔一種錯誤（`run_cell(args)` 分支留，D 不做） | — | fsm 14 |
| 4.7 | demo | 八條跑法＋`runpy` 轉派、demo/fsm 兩層（`review.py` 拼 `sys.path`、`idle.py` 讀 inbox）、paint run.py 三段（`--keep`、`find_brain`、`tree_hash`、`bind_brain`、`fake_alt.json`）、brains 五份 → 三個 demo（`demo/loop`、`demo/agent`＝paint 吞掉 fsm demo、`demo/kernel`）各自 run.py；paint 只做一件事（建 frame、放 args、跑、印 ret）；巢狀只在 `test_nested` 驗；brains 留 fake、litellm、lmstudio | — | 鳥瞰 19、fsm 9 10、agent 15 16 |
| 4.8 | 測試／說明 | test_paint_demo 3 個、agent.md＋agent_lib.md＋frame.md 三檔 → 只留 `test_run_script`（行為測試集中在 bob）；一份 agent.md（思考介面、定義資料夾、四格各一行、邊緣表三列；146／qwen 實驗記錄只留連結） | — | agent 17 18 |

### 批次 5：kernel 併一（在批次 1、2 之後；judges 怎麼指看 2.5）

| 編號 | 區 | 現況 → KISS 版 | 翻案？ | 來源 |
|---|---|---|---|---|
| 5.1 | kernel | `aos_kernel_llm.py`（218 行）＋`aos_kernel_general.py`（254 行）、`aos kernel llm|general`、兩份說明、兩份 demo、兩份測試 → 一支 `aos_kernel.py`：`judge` 沒寫＝內建規則＝「管 LLM 的那種」；`aos kernel`；一份 kernel.md、一份 demo（三段）、一份 test_kernel.py；N-42 一句 | ★ N-42 10-15「先做兩種」（[LLM kernel](../2026-10-15-llm-kernel.md)）——兩種是用途不是兩支程式；通用 kernel 自定點 6 本來就寫「跑順再併」 | 鳥瞰 1、kernel 1 |
| 5.2 | kernel | 三套排序規則（`order` 五層 key、`decide_rules`、獨立 `aos_kernel_judge_rules.py` 規則還不一樣）、`aging_ticks`／`near_ms`／`_metainfo.cost`／`seen`／`waited` → 規則一份在 kernel：級數→deadline→先來後到；獨立腳本、`judges/rules.json`、`schema.json` 刪，demo 第 1 段改「不設判官」 | aging／near_ms／cost 是 AI 自定（使用者只定「誰先來誰先上」「priority 和 deadline」） | kernel 2 3（鳥瞰 2 不採） |
| 5.3 | kernel | 判官答案五種 `ValueError`（多 key、型別、重複 id、reject 少 msg…）跟 C-48「只處理認得的 key」打架 → 判官錯只一種（不是物件、非 0、逾時）；是物件就只拿 `run`（認得的 id、去重）與 `reject`，其他忽略 | — | kernel 17 |
| 5.4 | kernel | 閘門 `letter()` 把 target 的 `stdout`／`stderr`／`exit` 抄進信、kernel 再用八個 `False` 蓋掉 → 閘門不抄；kernel 跑信時去掉所有 `std*`／`exit` 開頭的 key 再填自己的旁檔；kernel.md 一句「被包的 inst 串流由 kernel 決定」 | — | kernel 19 |
| 5.5 | kernel | 六檔五層相依（gate、mailbox、kernel_llm、kernel_general、judge、judge_rules） → `aos_gate.py`（閘門＋信箱讀寫，「信長什麼樣」只在這裡定）＋`aos_kernel.py`（身體＋規則＋問判官） | — | kernel 16 |
| 5.6 | kernel | state 窗抄 loop 骨架（`state: waiting`、`pid`、`beat`、永遠 null 的 `last_error`）＋`served`／`seen`／`judge_asked`；stdout 摘要帶 `judge: {asked, fallback, direct, skipped}` → 單次程式 state 只放自己的：`runs`、`queue`（每封只留 `priority`、`_metainfo`、`waited_ms`）、`running`、`slots`、`budget`、`judge_error`；stdout `{runs, served[], dropped[], waiting, budget}` | — | kernel 12 13、窗 24 |
| 5.7 | kernel | kernel 讀 target 的 stdout 旁檔取 `usage.total_tokens` → **留**，kernel.md 寫明這是唯一一處往下看、只認這一個 key、沒有＝0 | — | kernel 21 |

### 批次 6：文件與布局（不動程式；排最後免得改兩次）

| 編號 | 區 | 現況 → KISS 版 | 翻案？ | 來源 |
|---|---|---|---|---|
| 6.1 | NORMS | 幾乎每條帶「原為…」「10-15 晚使用者『都按照推薦』」「推翻 10-14…」、33 個「草稿」、20 個日期標、臨時號（D-、h、S、A～L）、使用者引文；N-43 一條 3 KB → 條文只留現行規定一到三句，沿革一律條尾一個連結指 thinking；規範裡只認 N- 號 | — | 鳥瞰 21、總則 7 11、fsm 15 |
| 6.2 | NORMS | N-29＋N-43 兩條互指 1.9 KB、N-18 分基礎／標準兩級（標準一行程式都沒有卻生出兩條待定）、lib 約 50 個代號（`FieldType` 一個用 55 次） → 一條「錯誤出口」五句（0／1、stderr 一形、不放警告、每層只說自己、例外＝透明轉交與述詞）；N-18 剩一句併進去「規範沒說的邊緣狀況預設不會發生」；代號通則一句「只在有人要分支時才開、一支不超過五個、設定不對 `ConfigBad`、輸入不對 `InputBad`」 | ★ N-18 分級 10-14 使用者親定 | 總則 4 6 12 |
| 6.3 | NORMS | N-12 1.4 KB（「以函數來看」、橋樑、出處連結） → 三句：stdin＝參數、stdout／stderr＝結果、exit 輔助；三者 JSON 串流；只認完整的、半份當沒有；加 3.13 的 `end: true` 一句 | — | 總則 5 |
| 6.4 | NORMS | ctl 四條（N-06～08、N-11）互引、窗三條（N-09、13、14）、N-15 鎖（沒實作）、N-16 兩形（只做 Maildir）、N-14 的 fsync／inotify／FUSE 叮嚀 → ctl 一條、窗一條、N-15 刪、N-16 一句「信箱＝Maildir」、N-14 一句 | — | 窗 13 19 20、鳥瞰 14 |
| 6.5 | NORMS | N-01「大家都要看時鐘」（沒程式看、跟 C-37「可看可不看」打架）、N-02「資料夾別亂弄」（口號）、N-03 打包 → 02 檔只留一條「時鐘＝一個檔裡的回合數，aos-tick 加一，要看就讀」；N-02 併 N-05；N-03 原文併待定【kernel】公告 | ★ 10-12 原文三條（[tasks-ticktock](../2026-10-12-tasks-ticktock.md)）——刪條文不刪原文 | 窗 14 |
| 6.6 | NORMS | N-39（不開 ctl／lock、不心跳、不寫時間、遞迴不擋…）＋N-41（格怎麼跑、不 setsid、格裡放 loop）、N-20（冪等不保證） → 一條 N-39「fsm 只寫 `phase`；暫停、停止、重疊、心跳、時間、格內部、遞迴一律不管」；N-41、N-20 刪（N-38 留一句「被殺＝重跑同一格，冪等不保證」） | — | 組合子 9 11、fsm 12 13 |
| 6.7 | NORMS | 08 待定 11 條裡 6 條整條劃掉附原文、「argv[0] 規矩」四小點、`grace_ms` 慣例住在待定 → 劃掉的刪（user.md「被推翻的直接刪」同一把尺）、剩 5 條 open；`grace_ms` 建議值搬 lib loop.md 一行 | — | 總則 8、鳥瞰 23 |
| 6.8 | NORMS | NORMS.md 三張表（主題、條號→檔 44 列、各批出處 10 段）＋ 9 個分檔＋62 bytes 的 README → 只留主題表；6.1～6.7 做完約 12 KB，併回一份 NORMS.md（主題當 `##`，條號不重編），NORMS/ 資料夾刪 | ★ 10-15「按主題分」——主題留當標題，只是不一主題一檔 | 總則 9 10、鳥瞰 22（鳥瞰 24 只併小檔不採） |
| 6.9 | lib 說明 | 一支程式三處說明（檔頭、`lib/x.md` 重講＋沿革、`lib/README.md` 11 KB 每檔一長句＋相依圖＋十二個測試檔各在測什麼）、fsm.md「格放哪：慣例 cells/」段 → 檔頭＝唯一出處；`lib/x.md` 只留 JSON 形狀與一個例子；`lib/README.md` 一檔一行＋怎麼跑測試（目標 3 KB）；「格放哪」段刪 | — | 鳥瞰 25 26、總則 20、組合子 13 |
| 6.10 | proto8 | `proto8/README.md`（artifact 連結、restart §3g、「PLAN 擱置」…）、`PLAN.md`＋`PLAN/`（12 KB，AI 提案，檔頭自己說「高度錯」） → README 只留一段話＋四行；PLAN 刪 | ★ PLAN 10-11「留著當樣本」，10-12 夜規矩在後（整份 AI 產出就刪）——刪前問一句 | 鳥瞰 27 28 ｜ **已做** cb20249a（使用者「刪掉」） |
| 6.11 | repo | C++ `core/` 與 proto8 同一疊東西、執行檔都叫 `aos`、誰先在 PATH 誰贏 → 根 README 與 `core/README.md` 寫明 C++ 那套封存（只維持 ctest 綠、不收新功能）；proto8 的 `aos` 是日常唯一入口；真要刪 C++ 另拍板 | — | 鳥瞰 29 |
| 6.12 | bin | `bin/aos` 手寫 case 表（`inst|loop|daemon|fsm|gate|tree`、kernel 兩種、brain 兩種、agent 特例對到 `aos_agent_lib.py`） → 子命令＝lib 裡有 `aos_<名>.py` 就能跑（`$1 $2` 底線接起來找），沒有就 Usage 錯；`aos_agent_lib.py` 改名 `aos_agent.py`（C-54 程式名⇄檔名） | — | 組合子 14 |

## 審過、推薦不動的

- **tasks 四支當 stdlib**：留（1.17 只瘦身）。使用者「少用 sh」之後，流程控制要有程式，tasks 就是那些程式。
- **inst 的 `*_append`、`*_mkdir`、`cwd_mkdir`、`stderr_merge`、`envs_clear`**：留，砍了只能靠 sh 補。
- **agent 的 `work/<n>/`**：留（已做 0.5 的說法：工具的工作資料夾，每張工具一視同仁）。
- **N-35 `檔#/位置`、資料夾找 inst.json、`AOS_DIRNAME`**：留。`AOS_DIRNAME` 是 C-51 概念定的（隱藏資料夾例外），概念不審；總則稿 #2「刪」不採。
- **閘門把呼叫者 stdin 寫成旁檔 `reply/<名>.stdin`**（第四版 K 照推薦「這輪不動」）：留。
- **kernel 讀 `usage.total_tokens`**：留，寫明（5.7）。
- **N-36 表上靜態 `next`、N-37、N-38 phase 不動、N-40 `end` 四種情形**：使用者親拍，已是最短寫法；4.3 只改結束那拍吐什麼，不改四情形。
- **`demo/kernels/general/judges/agent/ask_judge.py` 當一支程式**：留（少用 sh 之下反而該是程式，kernel 稿「用 G 的 sh 寫法取代」不採）；只收代號（1.8）。
- **C++ `core/`**：封存不刪（6.11）。

## 批次之間的相依（一句）

1 先做會把 2～5 要改的面積縮小（布林、旋鈕、環境變數、指示詞、tree、第二顆腦都先不在了）；2 跟第四版一起做（未決 C～P 使用者答了就動）；3 定了 ctl／state／`end` 的形狀，4 才能照它收 fsm 與 agent；5 只靠 1、2（judges 怎麼指）；6 全是文件，最後一次寫完。每批做完都要從 repo 根跑 `cmake --build --preset default && ctest --preset default` 全綠。
