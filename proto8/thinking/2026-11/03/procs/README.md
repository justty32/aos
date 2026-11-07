# 2026-11-03 execs／loops 統稱 procs：名單合一成 `procs`、看寫法決定怎麼起（沒有 `kind`）、每項可指定 `stack`、四態與名詞表（add／rm／start／stop／pause／resume）

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜出發點：[11-02 晚 ctl-state-names § 方向題 1](../../02/ctl-state-names/01-使用者原文-11-02-晚-逐字.md#方向題的答案11-02-晚使用者逐字)（使用者下班通勤時的想法）｜被本條推翻的：[11-02 state 窗 § 決定（晚）](../../02/state-window/01-使用者原文-11-02-逐字.md#決定11-02-晚使用者實作中陸續裁的)「loops_state 的 `loops`／`execs` 仍分開」「喔等等，那還是不要合併了」（「子項結束後不留名單」**沒**被推翻：衝突 2 使用者「照舊拿掉」）、[10-29 medium-plan § 四 1](../../../2026-10/29/medium-plan/03-四-aos-daemon-的兩個手把-兩扇狀態窗.md) 的窗名 `loops_ctl.json`／`loops_state.json`、[10-30 agent-lifecycle](../../../2026-10/30/agent-lifecycle/README.md) 的 `execs` 這個 key 與「表上的種類跟期望表不一樣＝收掉重起」｜條文：[N-28、N-54](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-06、N-07、N-09、N-13、N-14](../../../../docs/NORMS/05-基礎設施-窗.md)、[C-48、C-52、C-54、C-55、C-56](../../../../docs/CONCEPTS/01-設計理念.md)、[C-54 命名方法 R4、R7](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)、[C-75](../../../../docs/CONCEPTS/03-基礎設施.md)、[縮寫表 proc](../../../../docs/CONCEPTS/abbr.json)｜程式：[aos-loop](../../../../impls/aos-loop/README.md)、[aos-daemon](../../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../../cmd/README.md)、aos-eca（11-04 已刪，併進 aos-agent，見 [11-04 aos-agent](../../04/aos-agent/README.md)）、[ai_tools](../../../../cmd/aos-mcp/README.md)、[lua](../../../../extras/langs/lua/README.md)、[demo](../../../../templates/README.md)｜場地 `~/code/playground/`（不在 git）

本檔記使用者原文（逐字）、決定、fable 照原則定的細節（代定、可翻案）、實作時代定（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。11-03 已實作。

## 分檔目錄

<!-- wf-nav -->
| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-02-晚起-逐字-依先](01-使用者原文-11-02-晚起-逐字-依先.md) | 使用者原文（11-02 晚起，逐字，依先後）；決定（11-03，使用者） |
| [03-規劃-fable-照原則定的細節-可翻案](03-規劃-fable-照原則定的細節-可翻案.md) | 0. 名詞表（代定）、1. 名字總表（改前 → 改後）、2. 看寫法決定怎麼起與每項的 `stack`（代定） |
| [05-2c-起-停-暫停-代定](05-2c-起-停-暫停-代定.md) | 2c. 起、停、暫停（代定） |
| [07-4-舊名怎麼辦-遷移-當沒看到](07-4-舊名怎麼辦-遷移-當沒看到.md) | 4. 舊名怎麼辦（「當沒看到」） |
| [09-實作步驟表-不實作-給隊長](09-實作步驟表-不實作-給隊長.md) | 試驗場親手試（待使用者） |
| [10-實作時代定-11-03-實作者照原則定的](10-實作時代定-11-03-實作者照原則定的.md) | 實作時代定（11-03，可翻案）；8. 收工時改寫成休息中：sleep／wake（11-03 晚）› 使用者原文、決定、頂層代定、使用者回覆 |
| [11-實作時代定-11-03-晚-實作者照原則](11-實作時代定-11-03-晚-實作者照原則.md) | 8. sleep／wake › 實作時代定（11-03 晚，可翻案）、試驗場發現的問題（11-03 晚） |

## 使用者裁定（11-07，sol 審查；以下取代同題舊代定）

11-07 使用者裁定 sol 審查 #15-2：「15-2B*」——start 不清 ctl；舊 state 同 seq 可去重，尚未套用的首拍照做。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）
