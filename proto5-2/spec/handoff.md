# 開機交接：kernel boot、daemon 重開、停機

← [spec 導航](README.md)｜kernel 池怎麼增減：[kernel-pools](kernel-pools.md)｜daemon 對帳：[daemon-reconcile](daemon-reconcile.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel/README.md) §6 boot 五步、§3 第 9 步的 `stops`**，
> 以及 [proto5/spec/daemon.md](../../proto5/spec/daemon/README.md) §6.1 第 5 步「孩子表從空開始」與 §5 末「daemon 重啟過 kernel 要重 boot」。

## 1. `aos-kernel boot`

跟 proto5 一樣只做「交接、拉起來、放第 1 格」，不跑格；兩個 boot 同時跑仍是保證外。
boot 一開始就產生新 chain id；它送的單都帶 `decl`＝[新 chain 的 epoch ns, 0]，**比舊鏈任何一張單都新**——
舊鏈已經放進 daemon 家、還沒被處理的 scale 單，daemon 之後處理時會回 `Stale`、不生效（[protocol §1](protocol.md)，審查 R6）。

1. **驗**（不改任何東西）：K 轉絕對路徑、`aos-kernel` realpath、info 第 2 版讀驗；每個池都解得出 daemon（`NoDaemon`），每個 daemon 家都活著（flock 探測）。
2. **交接 kernel 池**：「帳本裡的 kernel 池」與「info 的 kernel 池」（`daemon`／`dpool` 去重，最多兩個）各送 `scale {count: 0}`、等回音
   （池不在也算成功，[protocol §1](protocol.md)；`NameTaken`＝別人的池，退 1）；再**等 daemon 的 `summary.json` 不在、或 `running 0`、`killing 0`**，
   最多 `--wait-ms`（預設 30 秒），逾時＝`AlreadyRunning`、退 1（單不撤回，同 proto5）。
   帳本裡 kernel 池若有舊的 `pending`，它的回音在就讀掉、ack，`pending` 清掉。
   為什麼是「縮到 0」而不是 proto5 的 `kill`：宣告式下 kill＝砍掉重來，daemon 馬上再拉一顆，它會去跑舊鏈排好的下一格，
   而新鏈還沒寫進帳本——兩格就可能同時在改帳本。縮到 0 才真的「沒有任何一格在跑、也不會再有」。
   （硬砍時另一個 process group 的 tick 子程式可能還活著，同 proto5 的保證外。）
3. **寫帳本**：`chain` 新 id、`kcpu`、`cli`、`last_seq` 0、`phase` running。`procs`／`ready`／`delayed`／`busy`／`on`／`acks`／`replies`／`deletes` 照舊；
   **`sends` 裡的 scale 單全部丟掉**（ack 類照留；boot 自己會重送宣告）。
   `pools` 每一格：`dirty`、`redeclare` 設 true（第一格重算並**整份重送**宣告——這就是 boot 時的池對帳，[kernel-pools §2](kernel-pools.md)）；
   `pending` 照舊（回音下一格照收；被丟掉、沒放出去的那張下一格當 `Interrupted`）。`recent`＝`busy` 全部（新鏈第一格把每顆忙的都查一次）。
   第一次 boot 沒有帳本＝全部從空開始。
4. **建家與模板**：每個池寫 `envs.json`、`inst.json` 模板；W 裡每一號「缺的補齊」（O(池大小)，只在 boot）。kernel 池 0 號的家也在這裡補。
5. **拉 kernel 池**：送 `scale {count: 1}`（帶 `target` 樣板）、等回音、ack。不等它活起來。
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
  舊版（proto5）的家：`state.json` 還有 `children` 的，那些 pid 一併殺掉，之後 `children` 拿掉（審查 R25）。
- 殺完：每個 kids 檔改成 `pending`（`pid` null；`gen`、`exits` 照留，`streak` 歸 0），不是成員的刪掉；重算 `summary.json`。
- **照 `pool.json` 把孩子拉回來**：每池的成員全部進 `pending`，照節流慢慢拉（[daemon-reconcile §4](daemon-reconcile.md)）。
  proto5 的「孩子表從空開始、等客戶再 spawn」**拿掉**。

對 kernel 的影響：
- 工作 cpu：上一任在做的那件，新主人開機對帳回 `Interrupted`、再補丟通知（[cpu-notify §3](cpu-notify.md)），kernel 照常收。
- kernel cpu：鏈多半**自己接得上**——每格在第 2 步就把下一格放進 kernel cpu 的家了，新主人起來就會跑它。
  只有 daemon 剛好死在「那格已開始、下一格還沒放」的窗口，鏈才會斷，`ls` 會報 `tick 停住`，這時才要 `aos-kernel boot`。
- 所以「每天重開機」變成：`aos-daemon boot` 就好；`aos-kernel ls` 的 health 不是 ok 再 boot。

## 3. 停機

**kernel `halt`**（審查 R5）：
1. `phase=stopping` → 收完在途（同 proto5）。
2. 每個**工作池**排 `count: 0` 的 scale 單；照 kernel-pools §2 第 1 步收回音。回錯（例如 daemon 在 `Stopping`）就照規則重試，**一直停在這一步**，`ls` 印原因。
3. 全部工作池都回成功 → `phase=stopped`，同一次提交排 kernel 池的 `count: 0`、出貨。正在跑的那一格被溫和停、跑完才退；
   已排好的下一格留在家裡，下次 boot 換了 chain 自滅。kernel 池這張的回音留在 daemon 家，下次 boot 第 2 步讀掉。
4. `aos-kernel halt` CLI 等的是：`phase=stopped`，而且這個 kernel 的**每個池**在 daemon 那邊都消失（`summary.json` 不在）或 `count 0`、`running 0`、`killing 0`。
   只看 `running 0` 不夠——宣告還是 N、孩子都在等重拉時也是 0。
- 不再往每顆 cpu 放 `stop-` 檔（proto5 的 `stops` 拿掉）：上萬顆就是上萬個檔；縮到 0 讓 daemon 用批次階梯收，一池一張單。
  [cpu.md §5.4](../../proto5/spec/cpu/stop.md)「kernel 往每顆 cpu 放 stop」這句因此作廢。

**daemon `halt`**：批次階梯收全部孩子，`pool.json` 留著（[daemon-reconcile §7](daemon-reconcile.md)）。
順序仍建議先 kernel、後 daemon：先 kernel 的話池都是 0、已消失，daemon 停完下次開也不會拉任何東西，等 `aos-kernel boot` 重新宣告。
反過來先停 daemon：下次開 daemon 會把所有池拉回來，kernel 的鏈多半接得上（§2）。兩種都能用。
kernel `halt` 卡在第 2 步時才去停 daemon，會留下非 0 的宣告，下次開 daemon 會拉回來——`aos-kernel halt` 逾時的訊息要講這件事。

**kernel 改綁另一個 daemon**：照 [kernel-info §4](kernel-info.md) 的搬池流程；proto5 的「不支援交接」由那段取代。
