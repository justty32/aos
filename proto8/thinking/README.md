# proto8 討論紀錄

← [proto8](../README.md)

一天一份。只留三種內容：使用者原文（照原意整理）、決定（含使用者說「照建議」採納的 AI 建議）、跟 AI 討論後的結論；還沒定的列「未決」。AI 的分析過程、利弊表、被推翻的方案不留（規矩見 [user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。

> **10-12 夜使用者定**：thinking 只留「使用者原文整理、決策結果、跟 AI 討論後的結論、未決」，其餘 AI 產出拿掉（「今天 10/12 產出的那些 thinking 也是，留結論」）；整份都是 AI 產出的檔整份刪。

> **10-30 改名**：aos-kernel-llm 改名 aos-llm-kernel（`demo/kernel-llm/` → `demo/llm-kernel/`、標頭 `aos/kernel_llm.hpp` → `aos/llm_kernel.hpp`、`tests/test_kernel_llm.py` → `tests/test_llm_kernel.py`；[map-review 第 9 點](2026-10-30-map-review.md#決定10-30)）；aos-gate 改名 aos-llm-send（[第 11 點](2026-10-30-map-review.md#決定10-30)）。舊紀錄照舊名。

> **10-30 夜改名**：aos-hub 改做 aos-eca-hub（`extras/cli_hub/` → `extras/eca_hub/`、`bin/aos-hub` → `bin/aos-eca-hub`；`aos-hub-kernel` 與 `AOS_HUB` 退場，`aos-hub` 這個名字留給以後；[eca](2026-10-30-eca.md#決定10-30) 衝突 2、4，[map-review 第 5 點](2026-10-30-map-review.md#決定10-30)）。舊紀錄照舊名。

| 月份 | 份數 | 範圍 |
|---|---|---|
| [2026-10](months/2026-10.md) | 79 | 10-11 重來～10-28 介質概念討論（納入管理透過介質、daemon 手把與狀態窗拆兩個、投遞／鎖／請求格式要正規化）與 10-29 的後續規劃（投遞格式與佈局、有順序的投遞、daemon 兩個手把、鎖的用法、父子交代；衝突與方向題等使用者看）、aos-hub 常駐 kernel 與實作（say／listen 協議、適配表）、aos-tools 工具註冊檔、10-29 playground（agent 輸入是對話簿、看信箱是 tool；看完後改成兩個使用場景：射後不理／射後有理，跑完結不結束寫死在定義裡；兩隻 agent-bob 實跑、塞話看回覆共用 aos-say／listen、aos-hub 對照；10-30 agent-lifecycle 規劃：queue、外部 agent 生命週期、session 檔接管）；10-30 使用者看現況地圖後的五點：plan 9 式檔案串流、round 的定位、外部 agent 與 aos agent 平級、aos-hub 通用化；10-30 夜 eca 規劃：外部 coding agent 平級、aos-eca-hub＝daemon＋畫面／session 檔）、agent 函數的常用操作都要是 aos 函數、agent 一輪（round）的細節設計：inst／loop／daemon／fsm、JSON 入口與指示詞、kernel、命名、aos-exec 與 `.env`、agent 範本與 10-24 的各種嘗試 |

按月份分層（使用者「都按照推薦」）：本檔只留月份索引，各月一份表放 `months/`，各天的討論檔放在本資料夾（`thinking/2026-10-15-xxx.md`）。新增一份討論＝在那個月的表加一列。
