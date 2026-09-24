← [kernel](README.md)｜[spec 總導航](../README.md)

# 3. 一格 tick 做什麼

```sh
aos-kernel tick [--target K]
```

平常不用人打：daemon 替登記過的 kernel 開一格——時間到（上一格開始後 `tick_ms`），或 `K/requests/` 出現新檔（新 syscall、`wake`、cpu 的回音通知）就開（[daemon §10](../daemon/ticks.md)）。人手跑一格也行，給 debug。

（2026-09-24 proto5-2 池式納入：第 4～10 步改寫。**2026-09-24 one-boot**：第 1～3 步改寫——不再接鏈、不再睡 `tick_ms`、不再 ack kernel cpu 的回音；一開始拿 `K/.tick.lock`；提交點改成 A／B／C。）一句話：**每格只碰「有事的」cpu**——有通知的、上一格剛派的、輪到巡檢的那幾顆；
派工從每池的閒號堆疊直接拿，不掃每一顆找閒的；**不再每格偷看 daemon**，cpu 死了由 daemon 自己照宣告補。

cpu 那邊的順序是「先發回音、再刪原單」（範式 §6.3），這裡查檔一律**先查原單、再查回音**，才不會看錯。
帳本什麼時候存見 [§1.2 的三個提交點](ledger.md)。

1. **讀、拿鎖**：帶了舊版的 `--chain`／`--seq`（舊 kernel cpu 裡還排著的舊格才會帶）→ 退 0、什麼都不做。
   讀 info；帳本還是舊的 `K/state.json`＝`LedgerVersion`、退 1；沒有帳本＝`NotBooted`、退 1（要先 `aos up` 或 boot）。
   然後**非阻塞**拿 `K/.tick.lock`：拿不到＝別的一格正在跑 → **退 75**、什麼都不做（daemon 不算失敗，[§7](no-overlap.md)）。
   拿到了就設鬧鐘 `tick_timeout_ms`（0＝不設）：這格跑太久會被 SIGALRM 結束，daemon 被殺後留下的孤兒 tick 也不會永遠卡著。再讀帳本。
2. 這格的序號 N＝帳本 `last_seq`＋1（記在記憶體，跟提交點 A 或 B 一起存）。`phase=stopped` → 只出貨（有出貨就存帳本）、退 0。
3. （第 2 版的「放下一格」「睡 `tick_ms`」都拿掉了：兩格之間隔多久由 daemon 管，[daemon §10](../daemon/ticks.md)。）
4. **出貨**：`acks`／`replies`／`deletes`／`sends` 全部做一遍（`link`，EEXIST 當已放；刪檔 ENOENT 當已刪），**做完存一次帳本**拿掉（提交點 A）。
   （09-24 停車）帶 `wake` 的回音，檔放好（或 EEXIST）就照 [§2 叫醒](syscall.md)，叫醒的結果跟拿掉出貨項同一次存帳本；崩在中間下一格重做，叫醒重做無害。
5. **讀 `K/requests/`**，列一次目錄，照檔名前綴分：`ack-`（範式 §3.3）、`stop-`（改 `phase`；檔名進 `deletes`）、`resp-`（回音通知，進第 6 步）、
   其他是 syscall（`add`／`rm`／`wake`（09-24 停車），照 §2 判；`rm` 一個 `running` 的行程用 `on` 找到那顆 cpu）。`.tmp` 結尾的略過。
   列目錄的成本是**目錄裡所有項目數**（含堆著沒處理的、`.tmp` 殘檔），不只是這格新來的。
6. **收回音**。要查的 cpu＝下面三組的聯集：
   - `resp-` 通知指到的：通知的 `params.home` 換成 `P/<i>`（家路徑在 `K/pools/P/cpus/<i>`；字面比不上再用 realpath 比，K 經過 symlink 也認）；
     `params.name` 不等於那格 `busy.req` 的＝舊通知，只刪不查。
     **壞通知**（不是 JSON、帶 `id`、method 不是 `responded`、`home` 不在 `K/pools/*/cpus/` 底下或解析出錯、`busy` 沒那格）：進 `deletes`、log 一行，**絕不讓這格退 1**。
   - `recent`：上一格派出去的每一顆。
   - **巡檢**：`busy` 的**前** `sweep` 顆；查完把它們搬到 `busy` 的尾巴（JSON 物件照插入順序，所以輪著查）。
   每一顆照三種情況查：
   - 原單 `cpus/<i>/requests/<req>` 在：在途，跳過。
   - 原單不在、回音 `cpus/<i>/responses/<req>` 在：判定（§4），結果（計數、status、排隊、pending 的回音進 `replies`、這則的 ack 進 `acks`）進提交點 B。
   - 兩個都不在：從沒放出去（上格崩在記帳之後、放檔之前）→ **再放一次**。`discard` 的就直接取消（拿掉行程、放回號碼）。
   判完：`busy`、`on` 那格拿掉；這號符合 [§3.1](pools.md) 的可派條件就放回那池 `free` 的尾巴，
   不符合（縮小中）就不放回、那池 `draining` 減 1（歸 0 設 `dirty`）。處理過的 `resp-` 通知檔名進 `deletes`。
7. **池**：[§3.1](pools.md) 的每格步驟（收 scale 回音、info 變了沒、要不要送下一張 scale 單、envs 變了沒）。O(池數＋有變化的號碼)。
8. **派工**（`phase=running` 才做）：
   1. `delayed` 是堆積：堆頂到期就彈出、接到它池的 `ready` 尾巴，直到堆頂沒到期。每彈一個 O(log 排隊數)。
   2. 每個池：`ready` 不空、`free` 不空 → 兩邊各拿一個配對：行程 `status=running`、`busy[P/i]`＝`{req: k-<chain>-<N>-<P>-<i>.json, proc, discard:false}`、`on[NAME]`、號碼進 `recent`。一直做到其中一邊空。
      拿到的格若是舊格（[§1.2](ledger.md) 的判法），丟掉再拿下一個。
   3. 派完進提交點 B，之後逐一放檔（`aos-exec`，params 照行程紀錄：`target`／`dir_target`／`args`（有才放）／`timeout_ms`）。**先記後放**，所以永遠不會同一行程派兩顆；崩在中間＝下一格靠 `recent` 補放。
   回 queue（§4）的行程：`not_before` 已到的接 `ready` 尾巴，沒到的推進 `delayed` 堆積。
9. **停機**（`phase=stopping`）：剛進入時把 `ready`／`delayed` 裡的 `once` 全部拿掉、各回 `-32000`／`Stopping`（進 `replies`；只掃這一次，之後新 add 的 once 當場回 `Stopping`）。
   `busy` 空、出貨箱空、沒有 `pending`（`procs` 的與池的都算）→ 帳本記 `halting: true` 進「縮池」：之後第 7 步把每個工作池的 W 當空集合（等於每池排一張 `count: 0` 的 scale 單），
   **等它們全部回成功**才 `phase=stopped`，同一次提交在 `sends` 排一張 `tick {home: K, off: true}` notification 給帳本 `ticker` 那個 daemon（撤登記，請它別再開 tick）。詳見 [§6 停機](boot.md)。
   不再往每顆 cpu 放 `stop-` 檔（第 1 版的 `stops` 拿掉）。`stopped` 之後再來的 syscall／ack 留在 `K/requests/`，下次 boot 的第 1 格會收。
10. **出貨**（同第 4 步）、**存帳本**（提交點 C）、有事件才 append `kernel.log`、退 0。`kernel.log` 每格記：派了誰去哪顆（行程名、`P/<i>`、request 檔名）、
    收到的每則回音（`result` 或 `error` 整段）、退件時的門檻、池的事件（`scale_send`、`scale_echo`、`pool_new`、`pool_envs`、`pool_gone`、`bad_notify`、`halting`、`stopped`…）。
    沒有事件的格**不寫**。kernel.log 在出貨、寫帳本之後才 append，所以**不保證涵蓋崩潰中途已結帳的回音**。

一格出錯（磁碟、daemon 家不在…）：stderr 一行、退 1，帳本＋出貨箱讓下一格接上。daemon 把退 1、被鬧鐘結束、逾時被 KILL 都記一次失敗，退避後再開（[daemon §10](../daemon/ticks.md)）。
退出碼：0 做完（含舊格、`stopped`）；75 鎖被佔；1 出錯；2 用法錯。

**派到還沒起來的 cpu 沒關係**：單放在那顆的家裡，等 daemon 拉起來就做。只有 scale 單回成功的號才會被派（§3.1），所以不會派到 daemon 根本不打算拉的號。
通知漏了誰補、每格的成本，見 [§11](scale.md)。
