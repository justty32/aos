# kernel 這邊怎麼增減 cpu

← [spec 導航](README.md)｜池表：[kernel-info](kernel-info.md)｜送給 daemon 的單：[protocol](protocol.md)｜在第幾步：[kernel-tick](kernel-tick.md) 第 7 步

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel.md) §1.1 末「改 info 之後」那段與 §3 第 7 步**。

一句話：**info 說要幾顆，kernel 算出「要哪幾號」，把這組號碼整份告訴 daemon（宣告式）；要收的號先等它手上那件做完再收。**
kernel 不記 pid、不問哪顆活著，只記 daemon 確認過的號碼（`sent`）。

## 1. 幾組號碼

對池 P（M(x) ＝ `count`＋`skip` 算出的成員集合，[kernel-info §3](kernel-info.md)）：

| 名字 | 是什麼 |
|---|---|
| W | M(info 的 `count`／`skip`)——info 現在要的 |
| S | M(帳本 `sent`)——daemon 已經確認的 |
| Q | M(帳本 `pending`)——已送出、還沒確認的；沒有在途單時 Q＝S |
| T | W ∪ (S 裡還在 `busy` 的號)——**該告訴 daemon 的**：要的全部，加上縮小中還在做事的 |

**哪些號可以派（進 `free`）**＝ S ∩ Q ∩ W，再扣掉 `busy`。三個條件缺一不可：
daemon 確認過（S）、在途的單沒有要拿掉它（Q）、info 還要它（W）。（審查 R4：縮小單在途時又改回來，那號要等下一張單確認才回 `free`。）

**什麼時候重算**（O(池大小)）：帳本那池標了 `dirty`。會設 `dirty` 的：info 的 `count`／`skip` 跟 `want` 不同（處理完當場把 `want` 更新成 info，審查 R19）、
在途單結清（成功或失敗）、`draining` 從非 0 變成 0。平常每格只比 `want`、看 `dirty`，O(1)＋O(`skip` 長度)。
`draining`＝S 裡、不在 W、還在 `busy` 的號數；在第 6 步收回音時遞減，不用重掃。**縮一萬顆只在最後一顆做完時重算一次**，不是每做完一顆重算一次。

## 2. 每格（`kernel-tick` 第 7 步）

對 info 與帳本裡的每一個池：

0. **新池**（帳本沒這格，審查 R13）：建帳本格（`sent` 空、`pending` null、`free` 空、`dirty` true、`redeclare` true）→ 寫 `envs.json`、`inst.json` 模板。
   這些都是「缺的補齊」，崩了下一格重做。
1. **收 scale 回音**：`pending` 不是 null → `D/requests/<pending.name>` 在＝還沒收，跳過；不在、`D/responses/<pending.name>` 在 → 讀：
   - 成功：`sent`＝`pending` 那組；`redeclare` 清掉；`error` 清 null。
   - `Interrupted`、`Stale`：結果不明或被較新的單蓋過——設 `redeclare`（下一步照常重送）。
   - 其他錯：`error` 存 **`data.code`＋`message`**（審查 R26）；`Stopping` 另記 `retry_at`＝本格序號＋10，到了設 `redeclare`；其他錯不自動重試，等 info 再變或 boot。
   - 不管哪種：`pending` 清 null、`dirty` 設起來；這則回音的 ack 進 `acks`（`home` 是 daemon 家）。
   兩個檔都不在、也不在 `sends`（例如被 boot 丟掉）：當 `Interrupted`。
2. **算**（`dirty` 才做）：算 W、T，重整 `free`＝S ∩ Q ∩ W − `busy`，重算 `draining`；`dirty` 清掉。
3. **送**：`pending` 是 null，而且（T ≠ S 或 `redeclare`）→ 新增的號（T − S）先建家（[kernel-home §3](kernel-home.md)），再排一張 scale 單
   （成員 T、`decl`＝[chain 的 epoch ns, 本格序號]，[protocol §1](protocol.md)）進 `sends`、記 `pending`。**一池同時最多一張在路上**；在路上時 info 又變，只設 `dirty`，等結清後再送。
   `redeclare` 的用途（審查 R3）：`sent` 只是「上次確認過的」，不能當「daemon 現在一定還有」的證據；boot、`Interrupted` 之後一律整份重送一次，就算集合一樣。
4. **envs**：info 的 envs 摘要跟 `envs_digest` 不同 → 重寫 `K/pools/P/envs.json`、更新摘要。不送單（活著的 cpu 不換環境，[kernel-home §2](kernel-home.md)）。
5. **池從 info 消失、或搬池**：舊位置當成 `count: 0` 照上面走。`sent` 空、沒有 `pending`、`busy` 沒它的號之後，再等**舊 daemon 那池的 `summary.json` 不在了**
   （daemon 收完孩子才刪池，[protocol §1](protocol.md)），帳本那格才拿掉或換成新位置（[kernel-info §4](kernel-info.md)）。這一步每格只 stat 一個檔。
   排在它 `ready`／`delayed` 的行程照排（同 proto5：沒 cpu 就一直排隊）。

**kernel 池**不走這一段：它只在 boot 與停機時送 scale（[handoff](handoff.md)）。

## 3. 為什麼「先做完再收」

縮小時如果直接叫 daemon 收，那顆 cpu 可能手上有一件、或 `requests/` 裡剛被放了一件還沒開始：
- 溫和停會讓它做完手上那件，但**不會**做還沒開始的（[cpu.md §5.1](../../proto5/spec/cpu.md)），那張單就留在一個不會再有主人的家裡，
  那個行程永遠卡在 `running`。
- kernel 是外人，不能自己去刪那張單（規則一）。

所以縮小一律是：先不再派給它 → 等它的 `busy` 結清 → T 不含它了才送 scale。代價：手上那件沒設 `timeout_ms` 就可能等很久，
`cpu ls` 會印「收掉中 N 顆，等 <行程名>」。卡住就 `aos-daemon kill --pool <dpool> <i>`：那顆重生，
溫和停做完手上那件（或階梯砍掉回 `stopped:true`），kernel 收掉，再收這顆。要不要另外給一個 `--now`，列在 [README 的要使用者拍的](../README.md)。

## 4. 長大時的順序

先建家、再送單、**回音成功才進 `free`**。理由：
- daemon 回錯（撞名、超過它能管的數量）時，那些號根本不會有 cpu；若先進 `free`，派過去的工作就永遠沒人做。
- scale 成功不代表 cpu 已經活著——daemon 照節流慢慢拉（[daemon-reconcile](daemon-reconcile.md)）。派到還沒起來的號沒關係，單在家裡等。
- **拉不起來**（家壞了）的號，派過去的工作會卡在 `running`，`cpu ls --pool P` 對得出「busy 且 daemon 說 failed」。
  這時 `rm` 那個行程只會標 `discard`、`cpu rm` 也要等 busy 結清，兩個都解不開（審查 R12）。**唯一的解法是把那個家修好**：
  cpu 起得來之後會照範式開機對帳、跑或回 `Interrupted`，kernel 收掉，才能退休它。要不要訂「放棄一張沒人跑的單」的協定，列在 README 要使用者拍的。

## 5. 崩在哪都接得上

| 崩在 | 下一格看到 | 做什麼 |
|---|---|---|
| 建了一半的家、一半的模板 | 缺檔 | 下次送單前「缺的補齊」 |
| 寫了 `pending`／`sends`、還沒放單 | `sends` 還有它 | 第 4 步出貨放單 |
| 放了單、daemon 還沒處理 | `D/requests/` 有它 | 等 |
| daemon 回了音、kernel 還沒寫帳本 | `D/responses/` 有它、`pending` 還在 | 重讀同一份回音、重判（冪等） |
| 寫了帳本、ack 還沒放 | ack 在 `acks` | 出貨補放 |
