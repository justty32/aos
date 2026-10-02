# 第三段之三：daemon 的五個模組

← [plan 入口](README.md)｜**接在 [m3 核心](m3-daemon-core.md)、[m3n 控制模組](m3n-control-module.md) 之後。**｜spec 正本：[B-640 核心](../spec/settled/daemon/core.md)、[B-641 控制](../spec/settled/daemon/control.md)、格式 [P-120](../spec/settled/protocol/daemon/core.md)、[P-121](../spec/settled/protocol/daemon/control.md)｜舊規劃（暫緩區）：[總表](../spec/settled/deferred/readme/02-總表-daemon與helper.md#daemon-與-helper)

**狀態（2026-10-01 第十二批裁定後）**：

| 模組 | 狀態 | spec |
|---|---|---|
| 一、重讀設定 `reload` | **已做**（R1～R4 照建議，R3 改成 stdout 警告） | [B-642](../spec/settled/daemon/reload.md)、[P-122](../spec/settled/protocol/daemon/reload.md) |
| 二、收屍／cgroup `cgroup` | **已做**（第十二批：C1～C4 照建議） | [B-644](../spec/settled/daemon/cgroup.md)、[P-124](../spec/settled/protocol/daemon/cgroup.md) |
| 三、記住狀態 `state` | **已做**（S1～S3 照建議，設定改成 `$ref`） | [B-643](../spec/settled/daemon/state.md)、[P-123](../spec/settled/protocol/daemon/state.md) |
| 四、訊息 `mq` | **已做**（第十二批：M1～M4 照建議） | [B-645](../spec/settled/daemon/mq.md)、[P-125](../spec/settled/protocol/daemon/mq.md) |
| 五、帳號 `account`（原草稿叫 helper） | **已做**（第十二批：拆 root 端、主程式降權；第十三批：A1～A7 照建議、白名單／黑名單） | [B-646](../spec/settled/daemon/account.md)、[P-126](../spec/settled/protocol/daemon/account.md) |

做了什麼、自己定的細節見篇末[做完了沒](m3m-daemon-modules/09-做完了沒.md#做完了沒)；裁定見 [verdicts 11 第十一批](../notes/verdicts/11-tick-as-unit/13-1001-第十十一批.md#2026-10-01-第十一批daemon-模組)、[第十二批](../notes/verdicts/11-tick-as-unit/14-1001-第十二批.md#2026-10-01-第十二批cgroup-與帳號)。下面各節保留原本的草稿，裁定處就地標註。

> **使用者方向（2026-10-01，原話）**：「node這塊不要動，我有預感，node相關概念以後會不存在。剩下這些都值得做成模組。」「剩下這些」＝重讀設定、收屍／cgroup、記住狀態、訊息、helper／跨帳號五個。所以：**不做 node 模組**（[verdicts 11「node 模組方向」](../notes/verdicts/11-tick-as-unit/08-1001-node模組與統一更新.md#node-模組方向2026-10-01記錄用未排程)照留、不排程），**五個模組一律以「daemon 設定檔 `insts` 裡的一項」為單位**，不認得資料夾、任務表、上下層。

> **POC 總原則**（[plan 入口](README.md)）：默認一切正常，不為異常寫處理，出事自然丟錯、回 1。結束碼 0＝預料之中、非 0＝要額外處理、1＝通用錯誤。

## 分檔目錄

> 2026-10-02 整理：原檔約 56 KB 超過 8 KB 門檻，按標題逐字拆進 `m3m-daemon-modules/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-現況與原則.md](m3m-daemon-modules/01-現況與原則.md) | 先講現在的 daemon；模組怎麼掛；本檔原則 |
| 2 | [02-模組一-重讀設定.md](m3m-daemon-modules/02-模組一-重讀設定.md) | 模組一：重讀設定（`modules.reload`） |
| 3 | [03-模組二-收屍與資源上限.md](m3m-daemon-modules/03-模組二-收屍與資源上限.md) | 模組二：收屍與資源上限（`modules.cgroup`） |
| 4 | [04-模組三-記住狀態.md](m3m-daemon-modules/04-模組三-記住狀態.md) | 模組三：記住狀態（`modules.state`） |
| 5 | [05-模組四-訊息.md](m3m-daemon-modules/05-模組四-訊息.md) | 模組四：訊息（`modules.mq`） |
| 6 | [06-模組五-帳號.md](m3m-daemon-modules/06-模組五-帳號.md) | 模組五：帳號（`modules.account`） |
| 7 | [07-模組五裁定驗收與實作順序.md](m3m-daemon-modules/07-模組五裁定驗收與實作順序.md) | 建議的實作順序；跨模組的待問 |
| 8 | [08-待問總表.md](m3m-daemon-modules/08-待問總表.md) | 待問總表 |
| 9 | [09-做完了沒.md](m3m-daemon-modules/09-做完了沒.md)<a id="做完了沒"></a> | 做完了沒 |
