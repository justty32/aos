> 封存 2026-11-04：沒有取代者。常駐 bob 使用者 11-03「B5.封存吧，eca是他的全面強化版，真的沒必要了。」；11-04 晚收斂報告 05 問「整個資料夾要不要封存」，使用者回「封存」。原在 `proto8/thinking/2026-11/02/resident-bob/`；同晚整份 AI 產出的 03、07、08、09、11、12、13 先刪掉（使用者「刪掉」）。

# 2026-11-02 常駐版 bob：一個 exec（一直跑的 bob）＋一個 loop（外部控制器），掛在 daemon 底下

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜前情：[11-01 試驗場 bob](../../01/playground-bob/README.md)、[11-02 試驗場 daemon](../playground-daemon.md)（方向題「常駐的掛法」就是本題）、[10-29 agent-bob 決定 33～35](../../../2026-10/29/agent-bob/04-頂層對八題的再想.md#決定10-30)、[10-30 agent-lifecycle](../../../2026-10/30/agent-lifecycle/README.md)｜同日：[state 窗](../state-window/README.md)、[loop-stdio](../loop-stdio.md)、[daemon-env](../daemon-env/README.md)、[exec 像繼承](../exec-inheritance.md)、[ctl-state-names](../ctl-state-names/README.md)｜條文：[N-28、N-54](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-63、N-64](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[P-17、P-20](../../../../docs/CONVENTION/02-題目stack停錯腦.md)、[C-52、C-56、C-75](../../../../docs/CONCEPTS.md)｜場地 `~/code/playground/`（不在 git）

本檔只記使用者原文（逐字）、決定、實測結論、照建議定案的規劃與代定（可翻案）（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

> **11-03 晚使用者封存**（頂層列開著的事，逐字）：「B5.封存吧，eca是他的全面強化版，真的沒必要了。」→ 常駐 bob 不再追、不做第二版。git 裡沒有它專用的程式（試驗場 `~/code/playground/agents/resident_bob` 不在 git、不動）；它帶出來的「daemon 起子項時把自己的 stack 設給子項」是通用機制，留著。

**現況**：daemon 給子項變數（步驟 1）在 repo；試驗場 `agents/resident_bob/` 第一版（不含睡／醒）寫好、實跑過；睡／醒（第二版）與 `relay` 升 bin 不做。

**讀法**（本資料夾寫的是 11-02 的名字，之後改成）：控制器的窗 `loop_ctl.json`／`loop_state.json` → `ctl.json`／`state.json`（11-02 晚 [ctl-state-names](../ctl-state-names/README.md)）；daemon 的 `loops_state.json`、`execs` 表、小格 `loops/<名字>/` → `procs_state.json`、`procs` 表、列上的 `stack`（[11-03 procs](../../03/procs/README.md)）；loop 的 ctl `{"stopped": true}` → `{"cmd": "stop"}`（[11-03 ctl-commands](../../03/ctl-commands/README.md)）；`AOS_DAEMON_STACK` → `AOS_DAEMON`（11-04 晚，使用者「AOS_DAEMON_STACK實在太醜，還是直接簡化成AOS_DAEMON就好了」，[11-04 aos-agent](../../04/aos-agent/06-衝突與方向題.md)）。

## 分檔目錄

> 依 [STRUCTURE](../../../../../wf/STRUCTURE.md#拆檔做法) 按 `##` 標題拆開；本檔留前言與表，各段在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-02-逐字](01-使用者原文-11-02-逐字.md) | 使用者原文（11-02，逐字）；決定（11-02，使用者） |
| [02-衝突與方向題的裁定-11-02-晚-使用](02-衝突與方向題的裁定-11-02-晚-使用.md) | 衝突與方向題的裁定（11-02 晚，使用者「照建議走」）與頂層代定 |
| [03-現況-查清的-不是規劃](03-現況-查清的-不是規劃.md) | 做這類東西要知道的；規劃 › 0. 一句話 |
| [04-1-誰當父-daemon-當父-控制器經](04-1-誰當父-daemon-當父-控制器經.md) | 規劃 › 1. daemon 當父、同生共死；2. bob 怎麼一直跑 |
| [05-3-loop-那半-控制器](05-3-loop-那半-控制器.md) | 規劃 › 3. 控制器與 `relay` 每輪 |
| [06-4-資料夾程式長什麼樣-怎麼請-daem](06-4-資料夾程式長什麼樣-怎麼請-daem.md) | 規劃 › 4. 資料夾程式與 install；5. 使用者怎麼用 |
| [07-6-要動的程式與步驟表-不實作](07-6-要動的程式與步驟表-不實作.md) | 規劃 › 6. 做到哪；結論（11-02 實測） › 輸入形狀 |
| [08-實測到的行為](08-實測到的行為.md) | 結論（11-02 實測） › claude 一直跑模式的行為 ①～⑫ |
| [09-規劃要跟著改的地方-實測當下列的-11](09-規劃要跟著改的地方-實測當下列的-11.md) | 結論（11-02 實測） › 沒測的 |
| [10-實作時代定-11-02](10-實作時代定-11-02.md) | 實作時代定（11-02） |
| [11-實作結論-11-02](11-實作結論-11-02.md) | 實作結論（11-02） |
| [12-要使用者看的衝突與方向題-11-02-晚](12-要使用者看的衝突與方向題-11-02-晚.md) | 衝突與方向題（11-02 晚第二版） › 衝突 1～6 |
| [13-衝突-7-控制器建-bob-小格裡的-F](13-衝突-7-控制器建-bob-小格裡的-F.md) | 衝突與方向題 › 衝突 7、8，方向題 1～5 |

<a id="使用者原文11-02逐字"></a>
<a id="決定11-02使用者"></a>
<a id="現況查清的不是規劃"></a>
<a id="規劃fable-11-02-晚第二版照使用者決定與實測改寫可翻案"></a>
<a id="結論11-02-實測"></a>
<a id="實作時代定11-02"></a>
<a id="實作結論11-02"></a>
<a id="要使用者看的衝突與方向題11-02-晚第二版"></a>
