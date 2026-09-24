← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：boot 交接與停機

（2026-09-24 proto5-2 池式納入：交接改成「把 kernel 池縮到 0 → 等 → 寫帳本 → 拉 1」；停機改成「每池縮到 0」。）

## boot

```sh
aos-kernel boot [--target K] [--wait-ms N]
```

只做「交接、拉起來、放第 1 格」，不跑格；**兩個 boot 不能同時跑**（給人的規矩，不在保證內）。
boot 一開始就產生新 chain id；它送的單都帶 `decl`＝[新 chain 的 epoch ns, 0]，**比舊鏈任何一張單都新**——
舊鏈已經放進 daemon 家、還沒被處理的 scale 單，daemon 之後處理時會回 `Stale`、不生效（[daemon §3](../daemon/methods.md)）。

1. **驗**（不改任何東西）：K 轉絕對路徑、`aos-kernel` realpath、info 第 2 版讀驗；每個池都解得出 daemon（`NoDaemon`），每個 daemon 家都活著（flock 探測）。
   帳本是第 1 版（有 `cpus`、沒 `pools`）＝`LedgerVersion` 退 1，請人先 halt 舊版、移走帳本（實作 D-29）。
2. **交接 kernel 池**：「帳本裡的 kernel 池」與「info 的 kernel 池」（`daemon`／`dpool` 去重，最多兩個）各送 `scale {count: 0}`、等回音
   （池不在也算成功；`NameTaken`＝別人的池，退 1）；再**等 daemon 的 `summary.json` 確定不在，或 `running 0`、`killing 0`、`draining 0`**，
   最多 `--wait-ms`（預設 30 秒），逾時＝`AlreadyRunning`、退 1（單不撤回；訊息印出是哪池讀不到或哪格不是 0）。
   「也要等 draining 0」（09-24 裁定，實作 D-5）：縮到 0 之後 daemon 會先發布 `count 0、running 0、draining 1`，那顆舊 kernel cpu 其實還在收尾，只看 running 就寫新鏈會跟舊 tick 撞。
   帳本裡 kernel 池若有舊的 `pending`，它的回音在就讀掉、ack，`pending` 清掉。
   為什麼是「縮到 0」而不是 `kill`：宣告式下 kill＝砍掉重來，daemon 馬上再拉一顆，它會去跑舊鏈排好的下一格，
   而新鏈還沒寫進帳本——兩格就可能同時在改帳本。縮到 0 才真的「沒有任何一格在跑、也不會再有」。
   （cpu 被 KILL 硬砍時，另一個 process group 的 tick 子程式可能還活著，範式 §5.3 的保證外。）
3. **寫帳本**：確認舊主人退出後**重新讀一次帳本**（等待期間舊 tick 可能還提交過，實作 D-47），在新讀的帳本上改：
   `chain` 新 id、`kcpu`、`cli`、`last_seq` 0、`phase` running。`procs`／`ready`／`delayed`／`busy`／`on`／`acks`／`replies`／`deletes` 照舊；
   **`sends` 裡的 scale 單全部丟掉**（ack 類照留；boot 自己會重送宣告）。
   `pools` 每一格：`dirty`、`redeclare`、`boot_redeclare` 設 true（第一格重算並**整份重送**宣告——這就是 boot 時的池對帳，[§3.1](pools.md)）；
   `pending` 照舊（回音下一格照收；被丟掉、沒放出去的那張下一格當 `Interrupted`）。`recent`＝`busy` 全部（新鏈第一格把每顆忙的都查一次）。
   第一次 boot 沒有帳本＝全部從空開始。
4. **建家與模板**：每個池寫 `envs.json`、`inst.json` 模板；W 裡每一號「缺的補齊」（O(池大小)，只在 boot）。kernel 池 0 號的家也在這裡補。
5. **拉 kernel 池**：送 `scale {count: 1}`（帶 `target` 樣板）、等回音、ack。不等它活起來。
6. `link` 第 1 格 `k-<chain>-1.json` 到 `K/pools/kernel/cpus/0/requests/`。印一行 `booted <N> pools, <M> cpus`（N、M 算 info 的池數與 `count` 總和，含 kernel 池）、退 0。

新的 kernel cpu 會先做家裡剩下的單：舊鏈留下的殘格（帶舊 chain，自滅）、然後第 1 格。檔名照字典序，舊 chain 的 epoch 較小、排前面。
第 2 步回錯或逾時時帳本還沒碰，已收到的回音當場 ack；第 5 步回錯時帳本已寫，退 1，再 boot 即可（實作 D-30）。

| 崩在 | 狀態 | 怎麼辦 |
|---|---|---|
| 第 2 步之後、第 3 步之前 | kernel 池 0 顆、帳本還是舊鏈 | 再跑一次 boot |
| 第 3 步之後、第 5 步之前 | 新鏈寫了、kernel 池 0 顆 | 再跑一次 boot（第 2 步縮到 0 是冪等的） |
| 第 5 步之後、第 6 步之前 | kernel cpu 活著但沒有第 1 格 | `ls` 報 `tick 停住`；再跑一次 boot |

**daemon 重開過**：daemon 照 `pool.json` 把孩子拉回來（[daemon §6.1](../daemon/lifecycle.md)），kernel 的鏈多半**自己接得上**——
每格在第 2 步就把下一格放進 kernel cpu 的家了，新主人起來就會跑它。只有 daemon 剛好死在「那格已開始、下一格還沒放」的窗口，
鏈才會斷，`ls` 報 `tick 停住`，這時才要 boot。所以「每天重開機」是：`aos-daemon boot` 就好；`aos-kernel ls` 的 health 不是 ok 再 boot。
工作 cpu 上一任在做的那件，新主人開機對帳回 `Interrupted`、再補丟通知，kernel 照常收。

## 停機（`aos-kernel halt`）

1. 放 `stop` syscall → `phase=stopping` → 收完在途（§3 第 9 步）。
2. 每個**工作池**排 `count: 0` 的 scale 單；照 §3.1 第 1 步收回音。回錯（例如 daemon 在 `Stopping`）就照規則重試，**一直停在這一步**，`ls` 印原因。
3. 全部工作池都回成功 → `phase=stopped`，同一次提交排 kernel 池的 `count: 0`、出貨。正在跑的那一格被溫和停、跑完才退；
   已排好的下一格留在家裡，下次 boot 換了 chain 自滅。kernel 池這張的回音留在 daemon 家，下次 boot 第 2 步讀掉。
4. CLI 等的是：`phase=stopped`，而且這個 kernel 帳本裡的**每個池**（含 kernel 池、搬池中的舊位置）在 daemon 那邊都確定消失（`summary.json` 不在）
   或 `count 0`、`running 0`、`killing 0`、`draining 0`。只看 `running 0` 不夠——宣告還是 N、孩子都在等重拉時也是 0。

不再往每顆 cpu 放 `stop-` 檔：上萬顆就是上萬個檔；縮到 0 讓 daemon 用批次階梯收，一池一張單。CLI 的細節（`not running`、`--no-wait`、逾時）在 [cli-ops.md](cli-ops.md)。

**跟 daemon `halt` 的順序**：daemon halt 用批次階梯收全部孩子，`pool.json` 留著（[daemon §5](../daemon/shutdown.md)）。
建議先 kernel、後 daemon：先 kernel 的話池都是 0、已消失，daemon 停完下次開也不會拉任何東西，等 `aos-kernel boot` 重新宣告。
反過來先停 daemon：下次開 daemon 會把所有池拉回來，kernel 的鏈多半接得上。兩種都能用。
kernel `halt` 卡在第 2 步時才去停 daemon，會留下非 0 的宣告，下次開 daemon 會拉回來——`aos-kernel halt` 逾時的訊息要講這件事。

**kernel 改綁另一個 daemon**：照 [§1.1](info.md) 的搬池流程（改池的 `daemon`），下一格就開始搬，不用 boot。
