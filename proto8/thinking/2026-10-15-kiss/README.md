# KISS 審視彙整：8 份稿去重、衝突、總表、批次（10-15 深夜）

← [討論紀錄](../README.md)｜8 份平行審稿（鳥瞰、loop／daemon、窗、fsm、kernel、agent、總則與共通、組合子）是 AI 審稿、結論都收在本檔，已刪（見 git 歷史 0b7758b7）｜相關：[inst-exec 第四版](../2026-10-15-inst-exec-v4.md)（使用者答了第三版 A～L；第四版矛盾與未決 C～P 10-15 深夜已定：「C-50 選 a，其他都按照推薦」）、[原則稿](../2026-10-15-principles.md)（切乾淨＋KISS，已做）、[10-16 撤回](../2026-10-16-kiss-last.md)、[10-16 重審](../2026-10-16-kiss-recheck.md)

> **⚠ 10-16 使用者撤回「都照推薦」、要重看**：「關於KISS大掃除那塊，我說都照推薦...那是我昨天在打遊戲懶得思考的情況下說的，我後悔惹QQ，等一下我想要重新看過。」所以：**批次 1 已做**（各列 commit 見總表）**可逐項翻案**；**批次 2～6 暫停**，等使用者重看再動。同日 C-56 本條改寫成「KISS 也是最後原則」（先滿足需求與其他原則，最後才做減法，[10-16 稿](../2026-10-16-kiss-last.md)），本檔的推薦是照舊說法「最乾淨、規則最少」給的，重看時要拿新說法再對一次。

> 使用者 10-15 深夜：「拿KISS原則重新去思考各種東西」「去思考現有的規範和實作。概念倒是不用。」KISS 是最高原則（C-56），層要徹底切割（C-52 加嚴：「想要看子層的東西請另外透過其他機制，沒機制就別碰」）。本檔只彙整，每條只給一個推薦。**10-15 深夜使用者拍板**：「C-50 選 a，其他都按照推薦」——總表與衝突表照推薦做（含 ★ 翻案）；6.10 PLAN 使用者另說「刪掉」。各條做完標「已做（commit）」。

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

使用者 10-15 深夜回 inst-exec 第三版：**A** TARGET 必填；**D** inst 的 `stdin` 不收內嵌 JSON（要的話另開一個 key 明說，第四版推薦 `stdin_inline: true`）；**G** 不要 `sh`，工具 argv 直接 `aos loop`，「少用sh」（已記進 user.md）；**H**「不要濫用內嵌，指示詞只是用來拆檔用的」，再追加「後續都默認沒有指示詞能用，但不用擔心json太大」→ **N-45**；其餘照推薦。

## 總表（依「先做會讓後面變簡單」分批；每批可獨立 ctest 全綠）

欄位：編號｜區｜現況 → KISS 版（一句）｜翻案？（★＝推翻使用者親定，附日期與原話出處）｜做了沒。

### 批次 1：純刪、彼此不相依、不碰第四版的形狀（**已做**，10-15 深夜四個 commit；自定點見 [10-15 session log](../../../wf/session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)）

| 編號 | 區 | 現況 → KISS 版 | 翻案？ | 做了沒 |
|---|---|---|---|---|
| 1.1 | inst | `exit`／`exit_append`／`exit_mkdir`、`read_exit()`、N-30／N-12「exit 檔出現也算」、demo once／tick、test_tick 的 exit 檔 → 全刪，子程式的碼只在結果的 `code` | ★ 10-12「子程式的碼進 exit 檔」（[inst 進 json](../2026-10-12-inst-json.md)）、10-14 深夜「exit 檔出現也算跑完」（N-12） | **已做** cb20249a |
| 1.2 | inst | 12 個布林 → **只砍 `stdin_inherit`／`stdout_inherit`／`stderr_inherit`**（寫 `/dev/stdin`／`/dev/stdout`／`/dev/stderr` 路徑就是繼承；N-26 整條與三條 Conflict 檢查消失，第四版 D 說的「`stdin_inline` 與 `stdin_inherit` 同時寫＝Conflict」也跟著不用）；`*_append`、`*_mkdir`、`cwd_mkdir`、`stderr_merge`、`envs_clear` **留**，第四版的 `stdin_inline` 加進來。風險：原稿要全砍換 `>>`／`2>&1`／`mkdir -p`，使用者偏好少用 sh，不採 | — | **已做** cb20249a；**10-16 使用者翻案、已還原** b815a213（「不要用這種方式添加規則，不直觀，這等同於埋雷……所以還是把inherit帶回來。」→ C-56 補「寫什麼就做什麼」、N-26 還原，[10-16 稿](../2026-10-16-kiss-last.md#原文寫什麼就做什麼10-16)） |
| 1.3 | loop | `interval_mode: fixed`＋`skipped`、`error_wait_ms`、`ctl_poll_ms`、loop 自己的 `grace_ms` → 只留 `interval_ms`：跑完隔一段再起、ctl 每圈讀、出錯不另算、收身體＝SIGTERM 後等 aos_inst 自己收（它保證過 `grace_ms`） | — | **已做** cb20249a |
| 1.4 | ctl | `paused`／`stop` 的 `{"val", "now"}` 雙形 → 只收布林；當場停＝送訊號 | ★ N-07 10-12（[ctl 規範](../2026-10-12-ctl-norms.md)） | **已做** cb20249a |
| 1.5 | agent | `aos_brain_ollama.py`、`brain ollama`、7 個測試、demo/fsm/brains/ollama → 刪，只留 OpenAI 相容一顆 | — | **已做** fa6629ee |
| 1.6 | agent | 腦自己的 HTTP `timeout_ms` → 刪，只留 inst 的 `timeout_ms` | — | **已做** fa6629ee |
| 1.7 | agent | `LIMIT` 截 8000 字、`.tool-running.json`／`Interrupted`、tool stdout 四格、intake 兩形＋`args.taken.json`、設定 key `history`／`work`／`halt_*`、11 個代號、`AgentError`、`need_brain` → 不截；被殺就重跑；stdout 一格 `{"data": {"tools": […]}}`；intake 只收 `question`、吃完刪 `args.json`；設定只剩 `brain`／`tools`／`system`（`history.json`、`work/` 固定在 cwd）；代號 6 個；直接丟 `CliError` | — | **已做** fa6629ee（halt_after／halt_state 留到批次 4、FsmMissing 留到批次 2） |
| 1.8 | kernel | 閘門 `wait_ms`／`poll_ms`／`QueueTimeout`、`_metainfo.resource` 沒寫＝直接跑、只有一封直接跑、判官 `defer`、`JUDGE_TIMEOUT_MS` 預設 30 秒、`log` jsonl、`slots` 純值糖、三個空錯誤類別、閘門驗 priority、三處刪旁檔、ask_judge 五種代號 → 全刪或收成一條（資源沒寫＝`ResourceUnknown`；有信有空格就問判官；判官只回 `{run, reject}`；任何失敗一律 `JudgeFailed`） | ★ `defer`：10-15 使用者「隨意」定三種話（[通用 kernel](../2026-10-15-general-kernel.md)）——跑、不跑、沒說三種還在，少一個 key | **已做** 7d833687（defer 刪＝三種話還在、少一個 key） |
| 1.9 | kernel | 閘門讀 `AOS_KERNEL`／`AOS_PRIORITY`、kernel 替判官清 `AOS_KERNEL`、`aos-demo` export `AOS_DEMO` → 閘門不認環境變數（`mailbox`／`priority` 寫在 gate.json）；kernel 跑判官一個 key 都不碰；`aos-demo` 只留「`.py` 轉指令名」那一招 | — | **已做** 7d833687（`aos-demo` 的 AOS_DEMO 那招留到批次 2：三張 sh -c 工具 inst 還靠它，2.7 本來就隨 v4 退場） |
| 1.10 | 共通 | `$at`、位置相對寫法 `./`／`../`／空檔名、`~0`／`~1`、7 個代號、`DirectiveError`、`aos_directives.py`、`expand(key=)`、`directives.md` → `$ref` 只收「檔#/從根算的位置」；一個 `DirectiveBad`；併進 `aos_cli.py` 一檔；檔頭就是說明 | — | **已做** cb20249a |
| 1.11 | 共通 | `aos_tree.py`＋`test_tree.py`（含自製 schema 驗證器）→ 刪（第三版已定 6；`schema.json` 留當資料） | — | **已做** cb20249a |
| 1.12 | fsm | 檔頭與 fsm.md「舊 key `ctl`／`lock`／`max_steps` 也忽略」＋`test_old_keys_ignored` → 刪（不認得的 key 忽略是通則） | — | **已做** cb20249a |
| 1.13 | loop | `aos_loop` 把 `aos_ctl_state`／`aos_proc` 再 export 一遍 → 刪，誰用誰直接 import | — | **已做** cb20249a |
| 1.14 | 共通 | `write_json` 只建一層、不 `-p` → `makedirs(exist_ok=True)` 一句 | ★ 10-15 晚盤點 P3「都按照推薦」（小） | **已做** cb20249a |
| 1.15 | demo | kernels/llm demo 在 clerk 的 frame 放 boss 的 `brain.json`、paint 的 `--keep`／換腦靠在下層 frame 放檔 → demo 不示範「上層伸手進下層的 frame」；要換 clerk 的腦改 clerk 自己的定義 | — | **已做** fa6629ee |
| 1.16 | demo | `demo/tick` 印 `date`、跟 aos-tick 同名不同事 → 改成真的 `aos tick clock`，README 改看 clock 檔 1→5 | — | **已做** a0c7214d |
| 1.17 | tasks | 四支（316 行、14 測試、12 張 inst 的 demo）→ **不砍**（原稿換 sh；使用者「少用 sh」＋「地位等同 C 的 stdlib」）。改瘦身：`aos-not` 刪（反過來寫 `aos-if X 失敗格 成功格`；N-43 述詞例外、N-34 述詞句跟著刪）、「先全部驗過才跑」砍（跑到哪讀到哪）、proto8-1 整個併進 proto8/lib（一個 lib、一個 bin、`aos seq|par|if|tick`） | ★ 述詞例外 10-15 晚「都按照推薦」（S5）；tick 搬家只改路徑 | **已做** a0c7214d（proto8-1 整個併進 proto8：lib、tests、demo/tasks；述詞例外隨 aos-not 刪） |
| 1.18 | 待定 | 08 待定 §28「回合數格式算不算規範」→ 結案＝不是（aos-tick 是糖，格式寫在它檔頭） | 替他結案，一句可翻 | **已做** cb20249a（替他結案，一句可翻） |

批次 1 改的是舊 lib；10-19 proto8-2 併入時舊 lib 整套刪了（使用者「都按照建議」，見 git 歷史 aa2fec1f），這些已做的結果留在 git。

另外批次 6 的 6.10（`proto8/README.md` 精簡、`PLAN.md`＋`PLAN/` 刪；★ PLAN 10-11「留著當樣本」）使用者另說「刪掉」，**已做** cb20249a。

### 批次 2～6（暫停）

10-16 使用者撤回「都照推薦」後暫停，逐項現況（10-16 新設計取代的、重審推薦、使用者拍板的五件、還沒定的）收在 [10-16 重審](../2026-10-16-kiss-recheck.md)。
