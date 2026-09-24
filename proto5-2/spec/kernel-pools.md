# kernel 這邊怎麼增減 cpu

← [spec 導航](README.md)｜池表：[kernel-info](kernel-info.md)｜送給 daemon 的單：[protocol](protocol.md)｜在第幾步：[kernel-tick](kernel-tick.md) 第 7 步

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel.md) §1.1 末「改 info 之後」那段與 §3 第 7 步**。

一句話：**info 說要幾顆，kernel 算出「要哪幾號」，把這組號碼整份告訴 daemon（宣告式）；要收的號先等它手上那件做完再收。**
kernel 不記 pid、不問哪顆活著，只記 daemon 確認過的號碼（`sent`）。

## 1. 三組號碼

對池 P（M(x) ＝ `count`＋`skip` 算出的成員集合，[kernel-info §3](kernel-info.md)）：

| 名字 | 是什麼 |
|---|---|
| W | M(info 的 `count`／`skip`)——info 現在要的 |
| S | M(帳本 `sent`)——daemon 已經確認的 |
| T | W ∪ (S 裡還在 `busy` 的號)——**這一刻該告訴 daemon 的**：要的全部，加上縮小中還在做事的 |

**只在「有變化」時算集合**（O(池大小)）：info 的 `count`／`skip` 跟帳本 `want` 不同、或第 6 步標了「要重算」（縮小中的某號剛做完）。
平常每格只比 `want` 一下，O(1)。

## 2. 每格（`kernel-tick` 第 7 步）

對 info 裡與帳本裡的每一個池：

1. **收 scale 回音**：`pending` 不是 null → 照 proto5 §3 第 6 步的順序看 daemon 家：`D/requests/<pending.name>` 在＝還沒收，跳過；
   不在、`D/responses/<pending.name>` 在 → 讀：
   - 成功：舊 S 換成 `pending` 那組成為新 `sent`；**新增的號（新 S − 舊 S）** 裡是 W 成員的推進 `free`；被拿掉的號就此忘掉；`error` 清 null。
   - `Interrupted`：daemon 死在這張單上，結果不明——`pending` 清掉，本格下一步照常重算重送（scale 可重做）。
   - 其他錯（`NameTaken`、`TooMany`、`Stopping`…）：`pending` 清掉、`error` 記下、`want` 設成現在的 info（**不自動重試**，
     等 info 再變或 boot；免得每格打一次 daemon）。`Stopping` 例外：每 10 格重試一次（daemon 重開後自己會好）。
   - 這則回音的 ack 進 `acks`（`home` 是 daemon 家，同 proto5 對 daemon 回音的做法）。
   兩個都不在：還在 `sends` 裡＝還沒放出去；不在 `sends` 又兩個都不在不該發生，當 `Interrupted` 處理。
2. **算**：有變化才算 W、T，並重整 `free`＝S ∩ W 裡不在 `busy` 的號（O(池大小)，只在有變化時）。
   所以縮小時 `free` 裡被拿掉的號不會再被派；縮了又改回來（還沒送單）的號也會回到 `free`。
3. **送**：`pending` 是 null 且 T ≠ S → 新增的號（T − S）先建家（[kernel-home §3](kernel-home.md)），再排一張 scale 單
   （成員 T，寫成 `count`＋`skip`）進 `sends`、記 `pending`、`want`＝info。一池同時最多一張在路上；在路上時 info 又變，等回音後下一格再送。
4. **envs**：info 的 envs 摘要跟 `envs_digest` 不同 → 重寫 `K/pools/P/envs.json`、更新摘要。不送任何單（活著的 cpu 不換環境，[kernel-home §2](kernel-home.md)）。
5. **池從 info 消失**：當成 `count: 0`。`sent` 變空、`busy` 沒有它的號之後，帳本那格拿掉。排在它 `ready`／`delayed` 的行程照排（同 proto5：沒 cpu 就一直排隊）。

**kernel 池**不走這一段：它只在 boot 與停機時送 scale（[handoff](handoff.md)）。

## 3. 為什麼「先做完再收」

縮小時如果直接叫 daemon 收，那顆 cpu 可能手上有一件、或 `requests/` 裡剛被放了一件還沒開始：
- 溫和停會讓它做完手上那件，但**不會**做還沒開始的（[cpu.md §5.1](../../proto5/spec/cpu.md)），那張單就留在一個不會再有主人的家裡，
  那個行程永遠卡在 `running`。
- kernel 是外人，不能自己去刪那張單（規則一）。

所以縮小一律是：先不再派給它 → 等它的 `busy` 結清 → T 不含它了才送 scale。代價：手上那件沒設 `timeout_ms` 就可能等很久，
`cpu ls` 會印「收掉中 N 顆，等 <行程名>」。真的卡住就 `aos-daemon kill --pool <dpool> <i>`：那顆重生、開機對帳回 `Interrupted`、kernel 收掉那件，再收這顆。
要不要另外給一個 `--now`（不等、直接收），列在 [README 的要使用者拍的](../README.md)。

## 4. 長大時的順序

先建家、再送單、**回音成功才進 `free`**。理由：
- daemon 回錯（撞名、超過它能管的數量）時，那些號根本不會有 cpu；若先進 `free`，派過去的工作就永遠沒人做。
- scale 成功不代表 cpu 已經活著——daemon 照節流慢慢拉（[daemon-reconcile](daemon-reconcile.md)）。派到還沒起來的號沒關係，單在家裡等。
- 拉起來失敗（例如家壞了）的號，派過去的工作會卡著；`cpu ls --pool P` 對得出「busy 且 daemon 說 failed」的號。
  這是保證外（[scale](scale.md) §4），處理方法是 `cpu rm P/<i>`（退休那號）加 `rm` 那個行程。

## 5. 崩在哪都接得上

| 崩在 | 下一格看到 | 做什麼 |
|---|---|---|
| 建了一半的家 | 家缺檔 | 下次送單前「缺的補齊」 |
| 寫了 `pending`／`sends`、還沒放單 | `sends` 還有它 | 第 4 步出貨放單 |
| 放了單、daemon 還沒處理 | `D/requests/` 有它 | 等 |
| daemon 回了音、kernel 還沒寫帳本 | `D/responses/` 有它、`pending` 還在 | 重讀同一份回音、重判（冪等：新 `sent` 算出來一樣） |
| 寫了帳本、ack 還沒放 | ack 在 `acks` | 出貨補放 |
