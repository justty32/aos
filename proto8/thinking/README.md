# proto8 討論紀錄

← [proto8](../README.md)

一天一份。只留三種內容：使用者原文（照原意整理）、決定（含使用者說「照建議」採納的 AI 建議）、跟 AI 討論後的結論；還沒定的列「未決」。AI 的分析過程、利弊表、被推翻的方案不留（規矩見 [user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。

> **10-12 夜使用者定**：thinking 只留「使用者原文整理、決策結果、跟 AI 討論後的結論、未決」，其餘 AI 產出拿掉（「今天 10/12 產出的那些 thinking 也是，留結論」）；整份都是 AI 產出的檔整份刪。

> **10-30 改名**：aos-kernel-llm 改名 aos-llm-kernel（`demo/kernel-llm/` → `demo/llm-kernel/`、標頭 `aos/kernel_llm.hpp` → `aos/llm_kernel.hpp`、`tests/test_kernel_llm.py` → `tests/test_llm_kernel.py`；[map-review 第 9 點](2026-10-30-map-review/01-使用者原文.md#決定10-30)）；aos-gate 改名 aos-llm-send（[第 11 點](2026-10-30-map-review/01-使用者原文.md#決定10-30)）。舊紀錄照舊名。

> **10-30 夜改名**：aos-hub 改做 aos-eca-hub（`extras/cli_hub/` → `extras/eca_hub/`、`bin/aos-hub` → `bin/aos-eca-hub`；`aos-hub-kernel` 與 `AOS_HUB` 退場，`aos-hub` 這個名字留給以後；[eca](2026-10-30-eca/09-方向題.md#決定10-30) 衝突 2、4，[map-review 第 5 點](2026-10-30-map-review/01-使用者原文.md#決定10-30)）。舊紀錄照舊名。

> **11-03 改名**（同日再改名 aos-eca：`extras/eca_ctl/` → `extras/eca/`、`bin/aos-eca`、`tests/test_eca_cmd.py`，使用者「好像也不用aos-eca-ctl，改成aos-eca就好。」，[eca 16](2026-10-30-eca/16-11-03-改名-aos-eca-ctl.md#11-03-再改名aos-eca-ctl--aos-eca)）：aos-eca-hub 改名 aos-eca-ctl（`extras/eca_hub/` → `extras/eca_ctl/`、`bin/aos-eca-hub` → `bin/aos-eca-ctl`、`tests/test_eca_hub.py` → `tests/test_eca_ctl.py`；使用者 11-03「aos-eca-hub應該改名為aos-eca-ctl」，[eca 16](2026-10-30-eca/16-11-03-改名-aos-eca-ctl.md)）。舊紀錄照舊名，連到資料夾的連結改指新路徑。

| 月份 | 份數 | 範圍 |
|---|---|---|
| [2026-11](months/2026-11.md) | 14 | 11-01 試驗場現場（agents/bob、環境變數要謹慎）；11-02 試驗場 [bob 串 aos-mcp／aos-tools、資料夾工具 cathy](2026-11-02-playground-cathy.md)（使用者 CPU 類比原文）、stack-tools、daemon 試驗場、daemon-env、exec 像繼承、state 窗、loop-stdio、常駐 bob、[晚 loop 這一系的窗檔名](2026-11-02-ctl-state-names.md)（控制自身的 ctl／state 就叫 `ctl.json`／`state.json`，推翻白天的 `daemon_*`／`loop_*`）；[11-03 execs／loops 統稱 procs](2026-11-03-procs.md)（名單合一成 `procs`、沒有 `kind`、看寫法決定跑一次或包成 loop，每項可用 `stack` 指定自己的 stack，四態 running／paused／stopped／拔掉與動作 add／rm／start／stop／pause／resume 的名詞表，手把／窗／信箱／小格全改 `procs_*`、舊 key 照 C-48 忽略；衝突 2〔loop 型自己退了留不留表上〕使用者「照舊拿掉」；只規劃）；[11-03 ctl 改成下指令](2026-11-03-ctl-commands.md)（loop 的 ctl.json 寫一道 `{"cmd": pause／resume／stop, "max", "interval_ms", "seq"}`，不用信箱、誰能寫就能控制、比內容判新舊、起來第一次讀的當基準線——殘留 stopped 的坑拿掉；daemon 的 `procs_ctl` 照舊宣告；只規劃）；[11-03 trace 拿掉](2026-11-03-trace.md)（fsm、aos-eca-turn 不寫 `trace.jsonl`，讀它的 listen `--status`／`--trace` 等拿掉；topdown 量測待使用者挑）；[11-03 aos-agent](2026-11-03-aos-agent.md)（say／listen 等以後併進 `aos-agent xxx` 通用介面；只記原文、未規劃） |
| [2026-10](months/2026-10.md) | 82 | 10-11 重來～10-28 介質概念討論（納入管理透過介質、daemon 手把與狀態窗拆兩個、投遞／鎖／請求格式要正規化）與 10-29 的後續規劃（投遞格式與佈局、有順序的投遞、daemon 兩個手把、鎖的用法、父子交代；衝突與方向題等使用者看）、aos-hub 常駐 kernel 與實作（say／listen 協議、適配表）、aos-tools 工具註冊檔、10-29 playground（agent 輸入是對話簿、看信箱是 tool；看完後改成兩個使用場景：射後不理／射後有理，跑完結不結束寫死在定義裡；兩隻 agent-bob 實跑、塞話看回覆共用 aos-say／listen、aos-hub 對照；10-30 agent-lifecycle 規劃：queue、外部 agent 生命週期、session 檔接管）；10-30 使用者看現況地圖後的五點：plan 9 式檔案串流、round 的定位、外部 agent 與 aos agent 平級、aos-hub 通用化；10-30 夜 eca 規劃：外部 coding agent 平級、aos-eca-hub＝daemon＋畫面／session 檔；10-30 aos-round 規劃：round 化作 loop／fsm 薄殼、fsm 的 next 照結束碼分岔）；10-31 傍晚 aos-var 提了又收回（`$ref`／`$env` 已夠），改待議 parts 能否用 aos-exec＋`$ref`／`$env` 組出來（＋round 重切草圖，待議）、10-31 傍晚 fable 收斂（parts 退成 aos-exec 格式的約定＋`which`／`run` 薄殼、round 不重切；衝突 3 條與方向題 2 題待使用者）、agent 函數的常用操作都要是 aos 函數、agent 一輪（round）的細節設計：inst／loop／daemon／fsm、JSON 入口與指示詞、kernel、命名、aos-exec 與 `.env`、agent 範本與 10-24 的各種嘗試 |

按月份分層（使用者「都按照推薦」）：本檔只留月份索引，各月一份表放 `months/`，各天的討論檔放在本資料夾（`thinking/2026-10-15-xxx.md`）。新增一份討論＝在那個月的表加一列。
