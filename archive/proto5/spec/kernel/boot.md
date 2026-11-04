← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：boot 與停機

（2026-09-24 proto5-2 池式納入：交接改成「把 kernel 池縮到 0 → 等 → 寫帳本 → 拉 1」；停機改成「每池縮到 0」。）
（**2026-09-24 one-boot**：交接拿掉——沒有 kernel cpu、沒有鏈。boot 改成「驗 → 拿 tick 鎖 → 寫帳本 → 向 daemon 登記開 tick」；停好那格請 daemon 撤登記；每天開機改用 `aos up`。）

## boot

```sh
aos-kernel boot [--target K] [--wait-ms N]
```

平常不用直接打：`aos up` 會先把 daemon 開好、再叫 boot、再等第 1 格跑完（[daemon §11](../daemon/up.md)）。
boot 只寫帳本、登記，**不跑格**；第 1 格由 daemon 收到登記當下就開。**兩個 boot 不能同時跑**（給人的規矩，不在保證內）。
boot 一開始就產生新的 boot 編號（`chain`）；它送的單都帶 `decl`＝[新 chain 的 epoch ns, 0]，**比以前任何一張單都新**——
以前放進 daemon 家、還沒被處理的 scale 單，daemon 之後處理時會回 `Stale`、不生效（[daemon §3](../daemon/methods.md)）。

1. **驗**（不改任何東西）：K 轉絕對路徑、`aos-kernel` 有執行位、info 讀驗；
   解得出**開 tick 的 daemon**（info 頂層 `daemon`；舊 info 的 `pools.kernel.daemon` 有寫就用它）與每個工作池的 daemon（解不出＝`NoDaemon`），
   這些 daemon 家都活著（flock 探測；不活＝`NotRunning`，提示 `aos up`）。
   帳本是第 1 版（`state.json` 有 `cpus`、沒 `pools`）＝`LedgerVersion` 退 1，請人先 halt 舊版、移走帳本（實作 D-29）。缺 `requests/`、`responses/`、`pools/` 就補。
2. **拿 tick 鎖**：阻塞拿 `K/.tick.lock`，最多 `--wait-ms`（預設 30 秒）；拿不到＝有一格跑太久＝`AlreadyRunning`、退 1。
   拿到了就不會有一格在改帳本（[§3](tick.md)）。鎖拿到第 5 步做完。
3. **（只有舊的第 2 版帳本）收掉舊 kernel cpu**：帳本裡的 kernel 池送一張 `scale {count: 0}`（`k-<chain>-boot-scale-kernel-down.json`）、等回音
   （回錯＝退 1）；再**等 daemon 的 `summary.json` 確定不在，或 `count 0`、`running 0`、`killing 0`、`draining 0`**，最多 `--wait-ms`，
   逾時＝`AlreadyRunning`、退 1（單不撤回）。kernel 池舊的 `pending` 回音在就一起 ack。舊 kernel cpu 裡還排著的舊格帶 `--chain`，跑到了也直接退 0。
   （cpu 被 KILL 硬砍時，另一個 process group 的舊 tick 子程式可能還活著：範式 §5.3 的保證外；它要改帳本也得先拿 tick 鎖。）
4. **寫帳本（一筆交易）**：沒帳本＝從空開始；有 sqlite 帳本就讀它；舊的 `state.json` 就整份匯入。在讀到的帳本上改：
   `chain` 新編號、`cli`、`ticker`（開 tick 的 daemon）、`last_seq` 0、`last_tick_at` 現在、`phase` running、`halting` false；拿掉 `kcpu`、`pools.kernel`。
   `procs`／`ready`／`delayed`／`busy`／`acks`／`replies`／`deletes` 照舊；**`sends` 裡的 scale 單與 tick 單全部丟掉**（ack 類照留；宣告下一格會重送）。
   `pools` 每一格：`dirty`、`redeclare`、`boot_redeclare` 設 true、`retry_at` 清掉（第一格重算並**整份重送**宣告——這就是 boot 時的池對帳，[§3.1](pools.md)）；
   `pending` 照舊（回音下一格照收；被丟掉、沒放出去的那張下一格當 `Interrupted`）。`recent`＝`busy` 全部（第一格把每顆忙的都查一次）。
   存之前先**建家與模板**：每個工作池寫 `envs.json`、`inst.json` 模板；W 裡每一號「缺的補齊」（O(池大小)，只在 boot）。
   是匯入的話，交易提交之後把 `state.json` 改名 `state.json.v2-old`。
5. **登記**：放鎖之前，往開 tick 的 daemon 放一張 `tick` 單（`k-<chain>-boot-tick.json`；params `home`＝K、`cli`、`every_ms`＝`tick_ms`、`timeout_ms`＝`tick_timeout_ms`，
   [daemon §3](../daemon/methods.md)）、等回音、當場 ack。daemon 一收到就開第 1 格——那格可能撞到 boot 還拿著的鎖、退 75，daemon 不算失敗、`tick_ms` 後再開。
   回錯（例如 daemon 在停機，`Stopping`）＝退 1。成功就印一行 `booted <N> pools, <M> cpus`（N、M 算工作池數與 `count` 總和）、退 0。

第 3 步回錯或逾時時帳本還沒碰，已收到的回音當場 ack；第 5 步回錯時帳本已寫，退 1，再 boot 即可（實作 D-30）。
已經在跑的 kernel 再 boot 一次也行（換 boot 編號、整份重送宣告、重新登記、連敗歸零）。

| 崩在 | 狀態 | 怎麼辦 |
|---|---|---|
| 第 2 步之後、第 4 步的交易提交之前 | 帳本沒變（交易整筆沒發生）；舊版時舊 kernel 池可能已縮到 0 | 再跑一次 boot（或 `aos up`；第 3 步縮到 0 是冪等的） |
| 第 4 步提交之後、舊 `state.json` 改名之前 | sqlite 帳本已在，舊的 `state.json` 也還在 | **只要 `state.json` 還在就算舊帳本**：tick／agent 拒絕（`LedgerVersion`），health 報 `legacy`；再跑一次 boot（或 `aos up`）會拿 `state.json` 整份重匯、蓋掉 sqlite 裡的半成品，再改名。不能只看 `ledger.sqlite` 在不在就當匯入完成（astra 必修 5） |
| 第 4 步之後、第 5 步登記之前 | 帳本是新的，daemon 沒登記這個 kernel，沒人開 tick | `ls` 的 health 報 `tick`（daemon 沒在替這個 kernel 開 tick）；再跑一次 boot 或 `aos up` |
| 第 5 步 daemon 收了單、boot 還沒讀回音 | daemon 已登記、開始開 tick | 沒事；回音留在 `D/responses/` 沒人 ack（無害） |

**daemon 重開過**：daemon 照 `pool.json` 把 cpu 拉回來、照 `D/kernels/` 的登記接著開 tick（[daemon §6.1](../daemon/lifecycle.md)、[§10](../daemon/ticks.md)），
kernel **不用重 boot**。工作 cpu 上一任在做的那件，新主人開機對帳回 `Interrupted`、再補丟通知，kernel 照常收。
daemon 被 kill -9 的情況見 [daemon §10](../daemon/ticks.md)。
**每天重開機**：`aos up` 就好（[daemon §11](../daemon/up.md)）——daemon 沒在跑就開、再 boot、等第 1 格跑完。不用先看 health 決定要不要 boot。

## 停機（`aos-kernel halt`）

平常用 `aos down`：它先叫這個 halt，再停沒別人要用的 daemon（[daemon §11](../daemon/up.md)）。

1. 放 `stop` syscall → `phase=stopping` → 收完在途（§3 第 9 步）。
2. 每個**工作池**排 `count: 0` 的 scale 單；照 §3.1 第 1 步收回音。回錯（例如 daemon 在 `Stopping`）就照規則重試，**一直停在這一步**，`ls` 印原因。
3. 全部工作池都回成功 → `phase=stopped`，同一次提交在 `sends` 排一張 `tick {home: K, off: true}`（撤登記，notification）給開 tick 的 daemon、出貨。
   daemon 收到就不再開這個 kernel 的 tick（正在跑的那格照樣跑完），直到下次 boot。
4. CLI 等的是：`phase=stopped`，而且這個 kernel 帳本裡的**每個池**（含搬池中的舊位置）在 daemon 那邊都確定消失（`summary.json` 不在）
   或 `count 0`、`running 0`、`killing 0`、`draining 0`。只看 `running 0` 不夠——宣告還是 N、孩子都在等重拉時也是 0。
   （one-boot 真跑挖到）帳本裡**從沒被 daemon 確認過**的池位置（`acquired` 是 false，例如一開始就撞 `NameTaken`、那池其實是別人的）不等。

不往每顆 cpu 放 `stop-` 檔，縮到 0 讓 daemon 用批次階梯收、一池一張單。CLI 的細節（`not running`、`--no-wait`、逾時）在 [cli-ops.md](cli-ops.md)。

**跟 daemon `halt` 的順序**：daemon halt 用批次階梯收全部孩子，`pool.json` 與 `kernels/` 的登記都留著（[daemon §5](../daemon/shutdown.md)）。
`aos down` 就是先 kernel、後 daemon：池都是 0、已消失，登記也撤了，daemon 停完下次開也不會拉任何東西、不會開 tick，等 `aos up` 重新 boot。
反過來先停 daemon：下次開 daemon 會把所有池拉回來、接著開 tick，kernel 不用重 boot。兩種都能用。
kernel `halt` 卡在第 2 步時才去停 daemon，會留下非 0 的宣告，下次開 daemon 會拉回來——`aos-kernel halt` 逾時的訊息要講這件事。

**kernel 改綁另一個 daemon**：工作池照 [§1.1](info.md) 的搬池流程（改池的 `daemon`），下一格就開始搬，不用 boot；開 tick 的 daemon（頂層 `daemon`）要重 boot（或 `aos up`）才換。
