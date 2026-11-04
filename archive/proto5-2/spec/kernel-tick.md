# kernel 一格做什麼：派工與回音通知

← [spec 導航](README.md)｜帳本：[kernel-ledger](kernel-ledger.md)｜通知從哪來：[cpu-notify](cpu-notify.md)｜池：[kernel-pools](kernel-pools.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel/README.md) §3**（第 1～3 步不變，第 4～10 步改寫）；§4 回音怎麼判、§2 syscall **不變**。

一句話：**每格只碰「有事的」cpu**——有通知的、上一格剛派的、輪到巡檢的那幾顆；派工從每池的閒號堆疊直接拿，不掃每一顆找閒的。

proto5 每格有三件事跟 cpu 總數 N 成比例：第 6 步每顆忙的都查兩個檔、第 7 步每顆都去 daemon 孩子表對一次、第 8 步每顆閒的都從佇列頭找。
這一版三件都拿掉或改成跟「有事的數量」成比例。

## 步驟

1. **讀** info、帳本；`--chain` 不對＝殘格，退 0。（同 proto5）
2. `phase=stopped` → 出貨、不接鏈、退 0。否則**放檔**下一格到 `K/pools/kernel/cpus/0/requests/k-<chain>-<N+1>.json`，
   **寫帳本** `last_seq`。先放後記。（同 proto5，只換了路徑）
3. 睡 `tick_ms`。（同 proto5）
4. **出貨**：`acks`／`replies`／`deletes`／`sends` 全部做一遍，**做完一次寫帳本**拿掉（[kernel-ledger §3](kernel-ledger.md)）。
   kernel cpu 的 `responses/` 全部 ack（同 proto5；那顆不發通知，所以只看它自己的一顆）。
5. **讀 `K/requests/`**，列一次目錄，照檔名前綴分：`ack-`（範式 §3.3）、`stop-`（改 `phase`）、`resp-`（回音通知，進第 6 步）、
   其他是 syscall（`add`／`rm`，照 proto5 §2 判；`rm` 一個 `running` 的行程用 `on` 找到那顆 cpu）。`.tmp` 結尾的略過。
   列目錄的成本是**目錄裡所有項目數**（含堆著沒處理的、`.tmp` 殘檔），不只是這格新來的（審查 R22）。
6. **收回音**。要查的 cpu＝下面三組的聯集：
   - `resp-` 通知指到的：通知的 `params.home` 換成 `P/<i>`（家路徑在 `K/pools/P/cpus/<i>`）；`params.name` 不等於那格 `busy.req` 的＝舊通知，只刪不查。
     **壞通知**（不是 JSON、帶 `id`、method 不是 `responded`、`home` 不在 `K/pools/*/cpus/` 底下、`busy` 沒那格）：進 `deletes`、log 一行，**絕不讓這格退 1**（審查 R27）。
   - `recent`：上一格派出去的每一顆。
   - **巡檢**：`busy` 的**前** `sweep` 顆；查完把它們搬到 `busy` 的尾巴（JSON 物件照插入順序，所以輪著查）。
   每一顆照 proto5 §3 第 6 步的三種情況查（原單在＝在途；原單不在、回音在＝判定；兩個都不在＝再放一次）。
   判完：`busy`、`on` 那格拿掉；這號符合 [kernel-pools §1](kernel-pools.md) 的可派條件就放回那池 `free` 的尾巴，
   不符合（縮小中）就不放回、那池 `draining` 減 1（歸 0 設 `dirty`）。
   處理過的 `resp-` 通知檔名進 `deletes`。**判定規則同 proto5 §4，一字不改。**
7. **池**：[kernel-pools](kernel-pools.md) 的每格步驟（收 scale 回音、info 變了沒、要不要送下一張 scale 單、envs 變了沒）。O(池數＋有變化的號碼)。
8. **派工**（`phase=running` 才做）：
   1. `delayed` 是堆積：堆頂到期就彈出、接到它池的 `ready` 尾巴，直到堆頂沒到期。每彈一個 O(log 排隊數)。
   2. 每個池：`ready` 不空、`free` 不空 → 兩邊各拿一個配對：行程 `status=running`、`busy[P/i]`＝`{req: k-<chain>-<N>-<P>-<i>.json, proc, discard:false}`、`on[NAME]`、號碼進 `recent`。一直做到其中一邊空。
      `ready` 在記憶體裡當 deque 用（從頭拿不搬整條）。拿到的格若是舊格（[kernel-ledger §2](kernel-ledger.md) 的判法），丟掉再拿下一個。
   3. 派完進提交點 3，之後逐一放檔（先記後放）。崩在中間＝下一格靠 `recent` 補放。
   回 queue（proto5 §4）的行程：`not_before` 已到的接 `ready` 尾巴，沒到的推進 `delayed` 堆積（O(log 排隊數)）。
   成本另外要算**丟掉的舊格數**；舊格由壓縮規則攤還（kernel-ledger §2）。
9. **停機**（`phase=stopping`）：同 proto5 §3 第 9 步的前半——`ready`／`delayed` 裡的 `once` 全部拿掉、各回 `Stopping`；
   `busy` 空、出貨箱空、沒有 `pending`（`procs` 的與池的都算）→ 帳本記 `halting: true` 進「縮池」：之後第 7 步把每個工作池的 W 當空集合（等於每池排一張 `count: 0` 的 scale 單），
   **等它們全部回成功**（照 [kernel-pools §2](kernel-pools.md) 第 1 步收）才 `phase=stopped`，同一次提交再排 kernel 池的 `count: 0`。
   詳見 [handoff §3](handoff.md)。**取代** proto5 的 `stops`：不再往每顆 cpu 放 `stop-` 檔。
   注意 `stopping` 期間**只**在剛進入時掃一次 `ready`／`delayed` 找 once（O(排隊數)），之後新 add 的 once 當場回 `Stopping`。
10. **出貨**（同第 4 步）、**寫帳本**、有事件才 append `kernel.log`（同 proto5）、退 0。

一格出錯（磁碟、daemon 家不在…）：stderr 一行、退 1，帳本＋出貨箱讓下一格接上（同 proto5）。

## 為什麼通知漏了也不會卡死

通知只是「提早告訴你」，不是唯一的路：

| 情況 | 誰補 |
|---|---|
| cpu 崩在「刪原單」之後、「丟通知」之前 | cpu 重生後開機時對 `responses/` 裡每一份補丟通知（[cpu-notify](cpu-notify.md) §3） |
| cpu 被縮掉、不會重生，手上有回音沒通知 | 巡檢：每格查 `sweep` 顆，最慢 ⌈忙的數 ÷ sweep⌉ 格一定輪到 |
| kernel 記了派工、還沒放檔就崩 | `recent`：下一格一定查，兩個檔都不在就補放 |
| 通知檔寫失敗（磁碟滿、權限） | cpu 只記一行 stderr，由巡檢補 |
| 舊通知（回音早就收過了） | `params.name` 對不上 `busy.req`，只刪 |

## 每格的成本

O(`K/requests/` 項目數＋`recent`＋`sweep`＋池數＋`skip` 長度＋派工數×log＋丟掉的舊格＋出貨數)，**加上讀一次、寫最多四次整份帳本**（帳本大小仍跟 N 有關，[scale](scale.md) §2）。
所以這一版做到的是「**不再逐顆查檔、不再逐顆找閒的**」；帳本本身仍是 O(N)，這點沒做到使用者 (f) 的全部，列在 README 要使用者拍的。

## 跟 proto5 的其他差別

- **不再每格偷看 daemon 孩子表**（proto5 第 7 步）。cpu 死了是 daemon 自己補（宣告式，[daemon-reconcile](daemon-reconcile.md)）；
  kernel 只在 `ls` 時讀 daemon 的池摘要。所以 proto5 的 `NameTaken`（每格發現 cpu 被別的 kernel 佔）改成在 scale 單的回音裡發現（[protocol](protocol.md)）。
- **派到還沒起來的 cpu 沒關係**：單放在那顆的家裡，等 daemon 拉起來就做（同 proto5 對「剛死、等重拉」的 cpu 的態度）。
  只有 scale 單回成功的號才會被派（[kernel-pools](kernel-pools.md)），所以不會派到 daemon 根本不打算拉的號。
