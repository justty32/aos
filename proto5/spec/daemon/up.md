← [daemon](README.md)｜[spec 總導航](../README.md)

# 11. `aos up`／`aos down`：一條指令開機、一條指令停機

（2026-09-24 one-boot 新節。使用者拍板「開機合一、家不合一」，見 [§8](README.md)。入口 `cli/aos`，實作在 `lib/aos_up.py`。）

程式不合一，只是包起來：`aos up` 替你依序叫 `aos-daemon boot`、`aos-kernel boot`；`aos down` 替你叫 `aos-kernel halt`、`aos-daemon halt`。
那些子命令都還在，給人 debug。

```text
aos up   [--target K] [--wait-ms N]
aos down [--target K] [--wait-ms N] [--keep-daemon]
```

K 的找法跟 `aos-kernel` 一樣：`--target K`，其次 `AOS_KERNEL_HOME`，再其次目前資料夾。`--wait-ms` 是每一步最多等多久（預設 30000）。

## `aos up`

1. 讀 K 的 `info.json`，找出要用的 daemon 家：**開 tick 的那個**（info 頂層 `daemon`）排第一，再來各工作池的。解不出＝`NoDaemon`、退 1。
2. 每個 daemon 沒在跑就開：`aos-daemon boot --target D`，放到背景、跟終端脫鉤（新 session），stdin 接 `/dev/null`，
   **stdout、stderr 都附加到 `D/daemon.log`**；環境照目前的，但 `PATH` 前面補上 `proto5/cli`（daemon 拉的 cpu、開的 tick 都靠 PATH 找 `aos-*`）。
   等到它拿到鎖（flock 探測活著）；它先退出了＝`DaemonFailed`、逾時＝`Timeout`，都叫你看 `D/daemon.log`。已經在跑的不動。
3. `aos-kernel boot`（[kernel §6 boot](../kernel/boot.md)）：寫帳本、向 daemon 登記開 tick。
4. 等 daemon 開的**第一格跑完**（帳本 `last_seq` ≥ 1），這時 kernel 已經能收單了。逾時＝`Timeout`，叫你看 `aos-kernel ls` 與 `D/daemon.log`。
5. 再等各工作池的第一張宣告有回音（講好了、或出錯），最多 5 秒——池名撞了（`NameTaken`）這類錯要等 daemon 回音的下一格才看得到。
6. 印 `up K=<K>  daemon <D>（新開｜本來就在）  N 個池、M 顆 cpu`；還有別的 daemon 的，一個一行 `  另一個 daemon <D>（新開｜本來就在）`；
   最後一行 `health <訊息>`（同 `aos-kernel ls` 第一行）。health 是池出錯、daemon 沒在跑、沒人開 tick、舊帳本、家讀不到＝退 1，其他退 0。

**已經開著再跑一次也行**：daemon 都在就不動，只是重 boot 一次（換 boot 編號、整份重送宣告、重新登記、連敗歸零）。
所以**每天重開機就是 `aos up`**，不用先看 health 決定要不要 boot。

## `aos down`

1. `aos-kernel halt`（[kernel §6 停機](../kernel/boot.md)）：等 kernel 停好、每個池收乾淨。停好那格 kernel 自己向 daemon 撤登記。halt 失敗就照它的退出碼退。
2. 等撤登記生效（`D/kernels/` 那檔不見），最多 5 秒（也不超過 `--wait-ms`）。等不到照樣往下（後果見下）。
3. `--keep-daemon`：到這裡就退 0，daemon 留著。
4. 否則每個用到的 daemon：還有**別的 kernel 登記著**、或還有池（`D/pools/` 底下有資料夾）＝不停，印
   `daemon <D> 沒停：還有 別的 kernel：…；池：…（要停就 aos-daemon halt --target <D>）`；沒有＝`aos-daemon halt`。退 0。

（試玩 one-boot 追加）`aos down` 自己印摘要，分得出這次做了什麼：
- kernel 一行，照 `aos-kernel halt` 自己回報的結果印：`kernel <K> 剛停`／`本來就停了`／`沒 boot 過`／
  `沒在跑：帳本還寫 running，但替它開 tick 的 daemon 不在（上次沒停好就崩了）；…下次 aos up 會接上`／`沒在跑：…daemon 沒登記替它開 tick…`
  （後兩種 `aos down` 不去改帳本）。
- 每個 daemon 一行：`daemon <D> 剛停`／`本來就沒在跑`／`留著（--keep-daemon）`／`沒停：還有 …`。

第 2 步等不到時：撤登記的單還在 daemon 家沒處理；那個 daemon 如果在第 4 步被停掉，登記檔會留著、單也留在 `D/requests/`。
下次開 daemon 會先照登記開一格、再處理那張撤登記單——kernel 已經 `stopped`，那格只出貨、退 0，不會派工。沒有害處。

halt 只等「這個 kernel 在 daemon 那邊真的有的池」：從沒被 daemon 確認過的池位置（例如一開始就撞 `NameTaken`、那池其實是別人的）不等，
所以撞名的 K 也停得掉（P 隊真跑挖到）。

## 退出碼

0 成功；1 錯（stderr 一行 `aos: <代號>: <白話>`，尾巴附 K 從哪來）；2 用法錯（`--target ""`、`--wait-ms` 負數）。
