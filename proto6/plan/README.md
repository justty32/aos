# proto6 實作規劃

← [proto6](../README.md)｜[spec 入口](../spec/README.md)｜[現行程式](../src/py/README.md)

2026-09-30 起的實作順序表。**現行行為與格式以 [spec](../spec/README.md) 加 [程式與測試](../src/py/README.md) 為準**（第二十七批，2026-10-02）。這裡只記哪段做完、哪段暫緩、哪段還沒做；各段細部檔是當時的施工紀錄，**屬於歷史**，裡面的旗標、檔名、結束碼很多後來改過，不再當驗收正本。

**分工（09-30 晚定）**：先用 Python 3.9（只用標準庫）把整條 POC 做通，POC 由 AI 隊寫，使用者看結果、做裁定；C++11 改寫放最後，由使用者親手寫。POC 總原則「默認一切正常」與結束碼慣例，現行寫法見 [spec tick](../spec/tick.md) 與 [慣例 C-08](../spec/conventions.md)。

## 各段狀態

| 段 | 狀態 | 現行正本 | 當時的細部檔（歷史） |
|---|---|---|---|
| 一、tick 核心 | **已完成** | [tick](../spec/tick.md) | [m1](m1-tick-core.md) |
| 一之二、hooks | **已完成**（後來從 `after_all` 擴成四個掛點） | [hooks B-635](../spec/tick/hooks.md) | [m1h](m1h-hooks-module.md) |
| 一之三、tasks-blocked 模組、`kind` | **已完成**（沒有獨立 plan 檔） | [tasks-blocked B-636](../spec/tick/tasks-blocked.md)、[tick](../spec/tick.md) | — |
| 二、系統級任務與普通程式 | **暫緩**：`aos-git`、`aos-clean`、範本、`aos-tick-check-task`、`aos-publish`、`aos-config-add` 全搬暫緩區，現行沒有系統級任務 | [暫緩區](../spec/deferred/README.md) | [m2（草稿，沒開工）](m2-system-tasks.md) |
| 三、daemon 核心 | **已完成**（砍到最核心：定期叫 `aos-exec`） | [daemon](../spec/daemon/README.md) | [m3](m3-daemon-core.md) |
| 三之二、控制模組 | **已完成** | [控制 B-641](../spec/daemon/control.md) | [m3n](m3n-control-module.md) |
| 三之三、五個 daemon 模組 | **已完成**（重讀設定、記住狀態、收屍／cgroup、訊息、帳號） | [daemon](../spec/daemon/README.md) | [m3m](m3m-daemon-modules.md) |
| 四、訊息與 cgroup | **已由三之三的模組取代**；舊的 `node.send`／`take`、`aos-mq get`／`post`、`aos-cg` 暫緩 | [訊息 B-645](../spec/daemon/mq.md)、[收屍 B-644](../spec/daemon/cgroup.md) | [原規劃](readme/02-四至六段順序與待問.md#第四段daemon-部件訊息與-cgroup) |
| 五、helper 與跨帳號 | **已由帳號模組取代**；`aos-as` 暫緩。真 root 驗收等使用者（見 [WAIT_USER](../../wf/WAIT_USER.md)） | [帳號 B-646](../spec/daemon/account.md) | [原規劃](readme/02-四至六段順序與待問.md#第五段helper-與跨帳號) |
| 六、C++11 改寫 | **未開始**：等 Python POC 玩過再說 | — | [原規劃](readme/02-四至六段順序與待問.md#第六段c11-改寫) |

還沒排進哪一段、使用者說先不做或還在想的：node 模組（使用者預感 node 概念會消失）、`peers`、系統級任務怎麼改用 hooks（[整理清單](../notes/2026-10-01-tick-system-tasks.md)）。裁定都在 [verdicts 11](../notes/verdicts/11-tick-as-unit.md)。

## 原本的六段總覽（歷史）

> 2026-10-02 整理：原檔約 15 KB 超過 8 KB 門檻，按標題逐字拆進 `readme/`。內容是 09-30～10-01 的規劃原文，**歷史，現行以 spec 為準**。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-六段總覽-一至三段.md](readme/01-六段總覽-一至三段.md) | 六段總覽 |
| 2 | [02-四至六段順序與待問.md](readme/02-四至六段順序與待問.md) | 順序上的調整；跨段待問 |
