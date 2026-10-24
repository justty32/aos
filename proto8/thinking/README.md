# proto8 討論紀錄

← [proto8](../README.md)

一天一份。只留三種內容：使用者原文（照原意整理）、決定（含使用者說「照建議」採納的 AI 建議）、跟 AI 討論後的結論；還沒定的列「未決」。AI 的分析過程、利弊表、被推翻的方案不留（規矩見 [user.md](../../wf/workflows/common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。

> **10-12 夜使用者定**：thinking 只留「使用者原文整理、決策結果、跟 AI 討論後的結論、未決」，其餘 AI 產出拿掉（「今天 10/12 產出的那些 thinking 也是，留結論」）。整份是 AI 產出的 13 份已刪（10-11 的六份審查／探針打撈、綜合、Fable 獨立抽概念、診斷、隊長想的、壓力測試、「件」與格、一天日記草稿）；其餘五份都已精簡。舊版：10-11 的與 tasks-ticktock 在 git（commit e4a7d345）；loop-daemon、inst-json、ctl-norms 三份**沒進過 git**，精簡前的原版要另外保存。

| 月份 | 份數 | 範圍 |
|---|---|---|
| [2026-10](months/2026-10.md) | 64 | 10-11 重來～10-19 資料夾＝程式（proto8-2 併入）、重寫順序；10-20 指示詞與 argv 第一個元素；10-21 aos-exec 收旗標、支援 `.env`；10-21 下午 loop／daemon／fsm／agent 搬到新 aos-exec 上的計畫；10-22 Python 版向 C++ 看齊、對 s6／runit 報告的回應；10-23 命名統合、命名方法、daemon 壓測後的六個問題、ctl 只寫變動與 `$ref` 切檔、aos-agent 做成範本、腦的工具呼叫；10-24 fsm 格的 exec 不寫死檔名；10-24 agent 當工具（agent-eve 叫 pyfix）；10-24 給人用的 say／listen；10-24 仿 pi 的基本工具組（pi-tools、agent-pip）；10-24 claude／codex CLI 當工具、人可以接進去（agent-fay）；10-24 `_metainfo` 函數的特性；10-24 給 AI 用的 aos 工具集（aos-ai）；10-24 記憶庫（agent-meg）；10-24 agent 之間寄信（demo/talk）；10-24 函數成長（六級、aos-grow 原型）；10-24 小念頭（agent-gus：先規劃 steps、每步 fork、只帶結論）；10-24 Janet 編成 aos（langs/janet）；10-24 改 JSON 的工具集（aos-json）；10-24 Lua 寫 aos、接進 nvim（langs/lua、editors/nvim）；10-24 按意圖組 context（agent-kai）；10-24 自我改進流程（self-improve）；10-24 LLM kernel 第一版（aos-gate、aos-kernel-llm）；10-24 工具＝函式庫（proto8/lib、agent-liv）；10-24 土法 compact（agent-hal）；10-24 Linux 權限與沙箱（aos-sandbox） |

> 10-15 晚按月份分層（使用者「都按照推薦」）：本檔只留月份索引，各月一份表放 `months/`；各天的討論檔留在原地（`thinking/2026-10-15-xxx.md`），舊連結都還能點。新增一份討論＝在那個月的表加一列。
