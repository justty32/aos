# 開機交接：kernel boot、daemon 重開、停機

← [spec 導航](README.md)｜kernel 池怎麼增減：[kernel-pools](kernel-pools.md)｜daemon 對帳：[daemon-reconcile](daemon-reconcile.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel.md) §6 boot 五步、§3 第 9 步的 `stops`**，
> 以及 [proto5/spec/daemon.md](../../proto5/spec/daemon.md) §6.1 第 5 步「孩子表從空開始」與 §5 末「daemon 重啟過 kernel 要重 boot」。

## 1. `aos-kernel boot`

跟 proto5 一樣只做「交接、拉起來、放第 1 格」，不跑格；兩個 boot 同時跑仍是保證外。

1. **驗**（不改任何東西）：K 轉絕對路徑、`aos-kernel` realpath、info 第 2 版讀驗；池表提到的每個 daemon 家都要是 daemon 家、活著（flock 探測）。
2. **交接 kernel 池**：要交接的是「帳本裡的 kernel 池」與「info 的 kernel 池」（`daemon`／`dpool` 去重，最多兩個）。對每一個：
   送 `scale {count: 0}`、等回音（`NameTaken`＝別人的池，退 1）；再**等 daemon 的 `summary.json` 顯示 `running 0`、`killing 0`**（或整個池已被拿掉），
   最多 `--wait-ms`（預設 30 秒），逾時＝`AlreadyRunning`、退 1（單不撤回，同 proto5）。
   為什麼是「縮到 0」而不是 proto5 的 `kill`：宣告式下 kill＝砍掉重來，daemon 會馬上再拉一顆，那顆會去跑舊鏈排好的下一格，
   而新鏈還沒寫進帳本——兩格就可能同時在改帳本。縮到 0 才真的「沒有任何一格在跑、也不會再有」。
   （硬砍時另一個 process group 的 tick 子程式可能還活著，同 proto5 的保證外。）
3. **寫帳本**：`chain` 新 id、`kcpu`、`cli`、`last_seq` 0、`phase` running。`procs`／`ready`／`delayed`／`busy`／`acks`／`replies`／`deletes`／`sends` **照舊**。
   `pools` 每一格：`want` 設 null（逼第一格重算、把宣告整份重送給 daemon——這就是 boot 時的池對帳）；`free` 重建為 S ∩ W 減 `busy`（O(池大小)，只在 boot）；
   `pending` 照舊（它的回音下一格照收）。`recent`＝`busy` 全部（新鏈第一格把每顆忙的都查一次，O(忙的數)）。
   第一次 boot 沒有帳本＝全部從空開始。
4. **建家與模板**：每個池寫 `envs.json`、`inst.json` 模板；W 裡每一號「缺的補齊」（O(池大小)，只在 boot）。kernel 池 0 號的家也在這裡補。
5. **拉 kernel 池**：送 `scale {count: 1}`（帶 `target` 樣板）、等回音。不等它活起來。
6. `link` 第 1 格 `k-<chain>-1.json` 到 `K/pools/kernel/cpus/0/requests/`。退 0。

新的 kernel cpu 會先做家裡剩下的單：舊鏈留下的殘格（帶舊 chain，自滅）、然後第 1 格。檔名照字典序，舊 chain 的 epoch 較小、排前面。

| 崩在 | 狀態 | 怎麼辦 |
|---|---|---|
| 第 2 步之後、第 3 步之前 | kernel 池 0 顆、帳本還是舊鏈 | 再跑一次 boot |
| 第 3 步之後、第 5 步之前 | 新鏈寫了、kernel 池 0 顆 | 再跑一次 boot（第 2 步縮到 0 是冪等的） |
| 第 5 步之後、第 6 步之前 | kernel cpu 活著但沒有第 1 格 | `ls` 報 `tick 停住`；再跑一次 boot |

## 2. daemon 重開（`aos-daemon boot`）

啟動前幾步同 proto5 §6.1（建家、拿鎖、等上一任的孩子死透、對帳自己的 `current`），差在：

- **找上一任的孩子**：讀每個 `pools/*/kids/*.json` 的 pid（O(孩子數)，只在啟動），用 proto5 §6.1 第 3 步的方法殺乾淨，**整批一起**送 TERM、一起等、一起 KILL。
- 殺完把 `kids/` 清空、重算 `summary.json`。
- **照 `pool.json` 把孩子拉回來**：每池的成員全部進 `pending`，照節流慢慢拉（[daemon-reconcile §4](daemon-reconcile.md)）。
  proto5 的「孩子表從空開始、等客戶再 spawn」**拿掉**。

對 kernel 的影響：
- 工作 cpu：上一任在做的那件，新主人開機對帳回 `Interrupted`、再補丟通知（[cpu-notify §3](cpu-notify.md)），kernel 照常收。
- kernel cpu：鏈多半**自己接得上**——每格在第 2 步就把下一格放進 kernel cpu 的家了，新主人起來就會跑它。
  只有 daemon 剛好死在「那格已開始、下一格還沒放」的窗口，鏈才會斷，`ls` 會報 `tick 停住`，這時才要 `aos-kernel boot`。
- 所以「每天重開機」變成：`aos-daemon boot` 就好；`aos-kernel ls` 的 health 不是 ok 再 boot。

## 3. 停機

**kernel `halt`**：`phase=stopping` → 收完在途（同 proto5）→ `phase=stopped`，同一次寫帳本時對**每個池（含 kernel 池）**排一張 `count: 0` 的 scale 單進 `sends`，出貨。
- 不再往每顆 cpu 放 `stop-` 檔（proto5 的 `stops` 拿掉）：上萬顆就是上萬個檔；縮到 0 讓 daemon 用批次階梯收，一池一張單。
- kernel 池縮到 0 時，正在跑的那一格是被溫和停的——它會跑完（包括把這些單出貨完）才退。已經排好的下一格留在家裡不會被跑，
  下次 boot 換了 chain 它自滅（同 proto5）。
- 崩在寫帳本之後、出貨之前：下一格若還跑得到，第 2 步 `stopped` 分支會出貨補放；跑不到（kernel cpu 已被收）就剩在 `sends`，
  下次 boot 會照舊出貨——**這幾張縮到 0 的單在 boot 第 3 步前要丟掉**，不然 boot 剛拉起來的池又被縮回 0。
  規則：boot 第 3 步把 `sends` 裡**所有 scale 單**丟掉（boot 自己會重送宣告），ack 類照留。
- 這幾張單照常記進各池的 `pending`。停機後沒有格去收回音，回音就留在 daemon 家；下次 boot 後的第一格照 [kernel-pools §2](kernel-pools.md) 第 1 步收（成功＝`sent` 變空，接著重送 info 的宣告）。
  被 boot 丟掉、沒放出去的那張：兩個檔都不在、也不在 `sends`，照同一步當 `Interrupted`、重算重送。kernel 池那張由 boot 第 2 步順手讀掉、ack（它自己的回音）。

**daemon `halt`**：批次階梯收全部孩子，`pool.json` 留著（[daemon-reconcile §7](daemon-reconcile.md)）。
順序仍建議先 kernel、後 daemon：先 kernel 的話池已經是 0，daemon 停完、下次開也不會拉任何東西，等 `aos-kernel boot` 重新宣告。
反過來先停 daemon：下次開 daemon 會把所有池拉回來，kernel 的鏈多半接得上（§2）。兩種都能用。

**kernel 改綁另一個 daemon**：照 [kernel-info §4](kernel-info.md) 先縮到 0、再改。proto5 的「不支援交接」仍成立，只是現在有明確的做法。
