# aos-cg：每項一框

← [通用 tick 核心](../tick.md)｜[tick 子篇入口](README.md)｜格式：[tick 協議](protocol/tick.md)

> **這篇整篇在暫緩區**（2026-10-02 第二十三批）〔使用者 2026-10-02 第二十三批：「aos-cg搬進暫緩區。」〕原檔 `tick/cg.md` 整篇搬來，原文照留、條號保留不重用（B-634、撤回的 B-631 一起）。暫緩理由：每項一框、跑完收殘留現在由 daemon 收屍模組做（[B-644](../daemon/cgroup.md)，每項一框 `i-<h>`、`aos-exec` 結束後清空）；`aos-cg` 要的工作資料夾框是舊 daemon 的（暫緩區 B-605），從沒寫過程式。下面的「停格檔」現在叫 tasks-blocked（[B-620](../tick.md)）。

**狀態：待實作。`aos-cg` 還沒有程式。「有 cgroup」那欄要靠舊 daemon 開的工作資料夾框與資源上限（暫緩區）；現行不論誰跑，都只會走「沒 cgroup」那欄。**條號不變，2026-10-01 從 [tick.md](../tick.md) 拆出。

## B-634：aos-cg：每項一框

〔使用者方向 2026-09-30，第二十批追答 8〕每項任務一框做成普通程式 `aos-cg`，要的任務自己在 argv 包：`aos-cg -- 原指令`（argv、代碼與結束碼見 [P-211](protocol/tick.md)）。它不是系統級任務。框的樹與命名見 [B-605](daemon/cgroup.md)。**放棄「沒包的任務一結束就清殘留」**：沒包的任務留下的程序，等格後由 daemon 收（[B-601](daemon/runtime.md)；daemon 那側在暫緩區，現行 daemon 核心不收）。

| | 有 cgroup | 沒 cgroup |
|---|---|---|
| 什麼時候 | 自己在本工作資料夾的框 `n-<h>/tick` 裡（看 `/proc/self/cgroup`；暫緩區 B-605 叫 node 框，只有舊 daemon 會開） | 不在工作資料夾的框、沒有 cgroup v2，或框寫不進。人手、cron 與現行 daemon 跑的格一律是這種〔astra 報告必修 1〕 |
| 開框 | 在 `n-<h>` 下開 `task-<seq>-<pid>`（跟 `tick` 並列），把自己搬進去，再 fork＋exec 原指令、wait 主程序 | 不開框；stderr 印 `cgroup_unavailable`，設 `PR_SET_CHILD_SUBREAPER`，原指令另開程序群組 |
| 主程序結束後 | 框裡還有程序就直接寫 `cgroup.kill`（不先 TERM），看 `cgroup.events` 的 populated 變 0，再 rmdir | 對那個程序群組送 SIGKILL，再反覆收掛回自己的孤兒、逐一 SIGKILL 並 wait，到沒有為止 |
| 清不到的 | 經外部服務（`systemd-run --user`、`at`、cron）開的程序，會跑出 `n-<h>` | 同左，加上換成別的帳號的；也沒有上限、量測與 OOM 證據 |

- **清不空**：框一直不空時，stderr 印 `frame_not_empty`，建停格檔（[B-620](../tick.md)）、回 1，不讓後面的項在還有人寫檔時開跑。
- **結束碼**照原指令；原指令被訊號結束時，`aos-cg` 用同一個訊號結束自己。
- **不放在 `tick` 底下**：cgroup v2 規定開了 controller 的那層不能同時放程序和子層。每項多約 0.1 毫秒（[實測](../../../notes/probes/per-task-cgroup-cost.md)）。
- **〔暫緩〕跟 `aos-as` 一起用**（`aos-as` 2026-10-01 第十三批搬暫緩區）：寫成 `aos-cg -- aos-as <帳號> -- 原指令`；`aos-as` 把自己所在的 `task-*` 框帶給 helper，別的帳號的程序也放進同一框（[B-303](helper.md)、[B-609](daemon/helper-actions.md)）。反過來寫開不了框，因為框不歸那個帳號。
- **不清上一格留下的 `task-*`**：只有舊 daemon 開的格才有 `task-*`，舊 daemon 每格格後與重啟時都會收（[B-601](daemon/runtime.md)、[B-603](daemon/lifecycle.md)）。
- **跑出框的**：`setsid`、double fork 逃不出 cgroup；只有經外部服務開的逃得出。aos 不擋這條路（管轄權是約定，B-626），經外部服務開的不歸 aos 管。
- 〔暫定，第二十批疑-9 照 a〕沒 cgroup 時退回 subreaper 加程序群組，跟 daemon「沒有就退回」一致。

依據：第十七批（任務層框）；第二十批追答 8（改成普通程式 `aos-cg`、放棄沒包的任務一結束就清殘留）；第二十批疑-9（沒 cgroup 時的退回，暫定）；納入 cgroup 與 git 改寫計畫（拿掉開框前清舊 `task-*`；經外部服務開的不歸 aos 管）。

**驗收：**有 cgroup 時，包了 `aos-cg` 的項用 `setsid` 加 double fork 留下的程序，在它的 `task-*` 框被 `cgroup.kill`，下一項開跑時已經沒有；`aos-cg -- aos-as <帳號> --` 時別的帳號的程序也在同一框；框清不空時 `frame_not_empty`、建停格檔。沒 cgroup 時包了 `aos-cg` 的項留下、掛回 aos-cg 的後代也被清掉，stderr 有 `cgroup_unavailable`；沒包的任務留下的程序在舊 daemon 格後收尾時被清（暫緩區）。

## B-631：（撤）cgroup 框的備援

〔使用者方向 2026-09-30，第二十批追答 8〕撤：tick 側的 cgroup 備援（開格設 subreaper、每項後殺程序群組並掃孤兒、`RLIMIT_AS`／`RLIMIT_CPU`、getrusage）與完整／備援對照表。每項一框改成普通程式 `aos-cg`（B-634）；daemon 側的收尾見 [B-604](daemon/lifecycle.md)。
