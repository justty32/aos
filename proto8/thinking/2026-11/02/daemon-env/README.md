# 2026-11-02 daemon 的環境變數：`AOS_DAEMON` 指 stack 不對勁——三個名字（定義／stack／ws）還是一個名字（溝通入口）

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜出發點：[11-02 試驗場 daemon](../playground-daemon.md)（指令要 `export AOS_DAEMON=$PWD/.stack`）｜前情：[11-01 環境變數盤點](../../01/playground-bob/01-環境變數盤點.md)、[要使用者裁的問題](../../01/playground-bob/02-環境變數要使用者裁的問題.md)（第 1 題「hub 型不用改」）、[10-30 map-review 第 10 點](../../../2026-10/30/map-review/01-使用者原文.md#決定10-30)（`AOS_DAEMON` 的來歷）｜條文：[N-63 hub 型變數、N-64 父子交代、N-57 六個變數、N-55](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-28 daemon、N-54](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[C-54 命名、C-69](../../../../docs/CONCEPTS/01-設計理念.md)、[C-65／C-67 stack 與工作區](../../../../docs/CONCEPTS/03-基礎設施.md)、[P-39](../../../../docs/CONVENTION/06-巢狀.md)｜程式：[aos-daemon-ctl](../../../../bin/README.md)、aos-eca-hub、[aos-daemon](../../../../impls/aos-daemon/README.md)

本檔只記使用者原文（逐字）、決定、照原則定的規劃與它撞到的原則（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

**結論**：一個變數、值＝daemon 的 stack，不定三個名字、不切控制口；daemon 起子項時設給子項。11-02 定名 `AOS_DAEMON_STACK`／`--daemon-stack`，11-04 晚改回 `AOS_DAEMON`／`--daemon`（使用者「AOS_DAEMON_STACK實在太醜，還是直接簡化成AOS_DAEMON就好了」）。細節在 [01 決定](01-使用者原文-11-02-逐字.md#決定11-02使用者)。

## 分檔目錄

> 依 [STRUCTURE](../../../../../wf/STRUCTURE.md#拆檔做法) 按 `##` 標題拆開；本檔留前言與表，各段在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-02-逐字](01-使用者原文-11-02-逐字.md) | 使用者原文（11-02，逐字）；決定（11-02，使用者） |
| [02-AOS-DAEMON-現況-查清的-不是](02-AOS-DAEMON-現況-查清的-不是.md) | `AOS_DAEMON` 現況（查清的，不是規劃）；規劃 › 共同的底、方案 A（不採用） |
| [03-方案-B-一個名字-使用者第二句-只要投](03-方案-B-一個名字-使用者第二句-只要投.md) | 規劃 › 方案 B：一個名字（採用） |
| [04-方案-C-daemon-自己也讀-控制口](04-方案-C-daemon-自己也讀-控制口.md) | 規劃 › 方案 C：把對外的切出 stack（現在不切；要切時怎麼做） |
| [05-方案-A-B-C-怎麼選-fable-的](05-方案-A-B-C-怎麼選-fable-的.md) | 規劃 › 方案怎麼選；衝突 1～4、方向題 1～2 各自的定案 |
| [06-實作步驟表-給隊長-每步都要先-pull](06-實作步驟表-給隊長-每步都要先-pull.md) | 做到哪；工人提的三點（11-02，使用者）；aos-daemon-ctl 的定位（11-02，使用者） |

<a id="使用者原文11-02逐字"></a>
<a id="決定11-02使用者"></a>
<a id="aos_daemon-現況查清的不是規劃"></a>
<a id="規劃fable照原則定的細節可翻案"></a>
<a id="要使用者看的衝突與方向題"></a>
<a id="實作步驟表給隊長每步都要先-pull"></a>
<a id="工人提的三點11-02使用者"></a>
<a id="aos-daemon-ctl-的定位11-02使用者"></a>
