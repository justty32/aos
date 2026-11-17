← [入口](../2026-11-17-重構與tidy盤點.md)｜涵蓋：impls（C／C++）與 kernel 的重構拆檔清單｜下一份 [02-程式-Python](02-程式-Python.md)

## 程式重構拆檔：impls 與 kernel

總結：C／C++ 單檔都不大（最大 `aos-inst` 的 `inst_proc.c` 401 行），沒有一檔塞好幾件不相干的事；痛點是幾個函式太長、同一段程式各專案各寫一份、刪 aos-llm-kernel 留下的殘渣。單向分層守住了（沒人 include 別專案的 `src/`），程式裡沒有舊格式相容碼（只剩註解）。前 15 大：inst_proc.c 401、loop/window.cpp 396、daemon/reconcile.cpp 394、child/child.cpp 384、daemon/procs.cpp 377、aos/loop.hpp 366、tend.cpp 353、directive/ref.cpp 336、lock/lock.cpp 333、adopt.cpp 326，其餘 ≤292。

| # | 檔或夾 | 現況（證據） | 問題 | 建議做法 | 工作量 | 風險 | 已知／新 |
|---|---|---|---|---|---|---|---|
| C1 | `impls/aos-llm/include/aos/llm_kernel.hpp` | 檔頭寫「aos-llm-kernel 的公開介面」；`sender_alive`、`has_sender`、`priority_of`、`read_reply`（:74、75、84、87）只有宣告，全 repo 沒定義、沒人叫（頂層 grep 核過） | 刪 kernel 後的殘渣；檔名不合 `include/aos/<短名>.hpp` | 改名 `aos/llm.hpp`、namespace `aos::llm`，刪四個空宣告、改檔頭；`aos-post/include/aos/post.hpp:3、:92` 註解一起改 | 小 | 低（只有 aos-llm 自己 include） | 新 |
| C2 | 寫檔「暫存→改名」 | `aos-util/src/…/files.cpp:79 write_text`（不 fsync）、`:243 write_json`（fsync、建夾）、`aos-json/src/doc/file.cpp:125 save_file`（fchmod＋fsync）；「迴圈寫完整份」也三份（files.cpp:88、:228、file.cpp:138） | 三份行為不同，改一份會漏 | aos-util 留一支底層（可選 mode、fsync），另兩支改叫它 | 小 | 低 | 新 |
| C3 | JSON pointer 跳脫 | `loop/config.cpp:66 pointer_escape`（頂層核過，還被 `aos-fsm table.cpp:119` 叫）、`exec/find/classify.cpp:25 escape`、`directive/ref.cpp:199 token_of`（已在公開標頭 `directive.hpp:73`）、`json/doc/pointer.cpp:40 pointer_of`；切段另兩份 | 四份重複 | 全改用 aos-directive 的 `token_of`／`pointer_tokens` | 小 | 低 | 新 |
| C4 | 子命令解旗標包裝 | `llm/main.cpp:146`、`post/main.cpp:63`、`lock/main.cpp:97`、`json/main.cpp:79` 都是「parse_cli＋FlagUnknown 補 `(see X sub --help)`」；`fail()` 包裝三份 | 違反「輸出格式只在共用介面改」 | aos-util 加 `parse_sub_cli(prog, sub, …)` | 小 | 低 | 新 |
| C5 | 讀 `$AOS_STACK` | 五處：`util/proc.cpp:105`、`loop/config.cpp:265`、`loop/engine/stack.cpp:11`、`exec/env/env.cpp:41`、`fsm/main.cpp:64`；config.cpp:265 把空字串當有設 | 規則不一致 | aos-util 一支 `env_or_empty` 統一；先確認空字串該怎麼算 | 小 | 低 | 新 |
| C6 | `aos-daemon/src/child/limits.cpp:154`、`child.cpp:73` | :154 在 fork 前用 `fprintf(stderr,"aos-daemon: warning: …")`（頂層核過）；:73 把 `"LimitBad"` 寫成字面字串 | 該走 `aos::warn` 與 `code::LimitBad`（fork 之後那幾處用 fprintf 合理） | 兩處改用共用介面 | 小 | 低 | 新 |
| C7 | `aos-daemon` 長函式 | `Daemon::adopt()` 約 180 行（adopt.cpp:144）、建構子 177 行（daemon.cpp:66–243，依序做信箱、窗、limits、cgroup、stack…）、`start` 約 115 行、`reconcile` 129 行 | 檔不大，函式太長、難讀難單測 | 同檔內拆成幾個小函式，不必拆檔 | 中 | 中（有 11 個測試檔可回歸） | 新 |
| C8 | `aos-loop/include/aos/loop.hpp`（366 行） | 一個公開標頭裝窗 struct（51–110）、`Run`／`Target`（112–190）、雜項、`Loop` 類別（264–366）；impls/docs/02 的例子寫的是 `aos/loop/engine.hpp` | 跟自家文件對不上 | 拆 `aos/loop/{windows,run,engine}.hpp`，`loop.hpp` 只 include | 中 | 低（只有 fsm、daemon 用） | 新 |
| C9 | `aos-loop/src/run/signals.cpp`（24 行） | 三個函式都只轉叫 `aos::` 同名 | 多一層 | 呼叫端直接叫 `aos::`，刪檔 | 小 | 低 | 新 |
| C10 | 註解裡的舊名提示 | `daemon.hpp:27`、`daemon.cpp:76、:172`、`windows.cpp:4`、`child.cpp:15`、`child.hpp:102`：「舊名 loops／execs 不認」「11-04 改名」 | 照「當沒有舊版」與「沿革只留結論」 | 刪這些句子 | 小 | 無 | 新 |
| C11 | `aos-daemon/tests/test_lifecycle.py`（795 行） | 40 個測試混 adopt、finish、ack、stuck、StateRecovery | 想找某主題不好找 | 按主題拆 test_adopt／test_stuck／test_ack（共用的已在 support.py） | 中 | 低 | 新 |
| C12 | 各專案 `test_ref_hash.py`（6 份）、`test_stack_make.py`（3 份） | 每份開頭自寫 `BIN=`、去掉 `AOS_` 的 ENV | 樣板重複但每份幾行 | 可不做；要做就抽 impls 共用測試 helper | 小 | 低 | 新 |

不建議拆：json/splice.cpp、help.cpp（大半是說明字）、directive/ref.cpp、lock.cpp、tend.cpp、inst_proc.c 都是單一主題。`aos-directive/src/` 扁平放三個 .cpp、沒照 `src/<元素>/` 分夾，檔少可不動。

`proto8/kernel/`：只有設定（JSON、`_entry`、`.env`），唯一程式是 `llm-kernel/fake_slow/_entry`（54 行），沒東西要重構；`llm-kernel` 與 `llm-team` 的 `daemon.json` 只差 description，README 寫明各一份 `def/`，看起來是刻意的。

沒把握：`child.cpp:81–90` 在 fork 之後叫 `setenv`、`run_cli`（conventions 說 fork 後只能叫 async-signal-safe）——若 daemon 是單執行緒實際上無害，沒查 daemon 有沒有開執行緒，值得另查；`llm/tests/test_ls_kernel.py:108` 有一列叫 `legacy`、exec 指 `/bin/aos-llm-kernel`，可能只是借名字當測試資料。
