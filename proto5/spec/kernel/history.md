← [kernel](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`kernel：排程也是一格一格的 aos-exec（第 1 版，2026-09-23 定稿）`

> 2026-09-23 重架構第二份；同日照 astra 三輪審查改過（K／X／R、K2／X2／R2、K3／X3／R3）。
> 2026-09-23 定稿並已實作：[`aos_kernel.py`](../../lib/aos_kernel.py)（入口 `aos-kernel`）。舊 kernel-home.md／aos-kernel.md 已刪（副本在 [proto5.1/spec/](../../../proto5.1/spec)）。
> 已拍板的前提在 §9，我自己選的在 §10。
> 2026-09-24 實作補記：依實作審查回寫，見 impl-review-report.md；補進的句子標「（09-24 補）」，總表在檔尾〈實作補記〉。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> 2026-09-24 fix-r4：§6 命令列全改 `--target K`（省略找 `AOS_KERNEL_HOME`→目前資料夾，錯誤行講來源）、`stop` 改名 `halt`、`init` 改讀 `--config FILE`、`--daemon` 改名 `--daemon-target`；§3 tick 的 args 同步。
> 2026-09-24 fix-r5（試玩 r4 兩份報告的共同痛點）：boot 成功印 `booted <N> cpus`；check 加 `--probe`、結尾印總結行；ls 的 health 多 `恢復中`（cpu dead、daemon 重拉中），kernel 正常時再看 agent 的暫停／重試，行程行尾標出來；daemon 沒在跑時 cpu 行印 `dead（daemon 沒在跑）`（§6）。
> 2026-09-24 advice-r1（使用者兩條建議）：`check --agent` 搬到 `aos-agent check`（舊用法＝用法錯 2、指到新指令）；`ls` 改成按池分組的對齊表、長名字砍中間、長路徑移到 `-v`，`--json` 改成欄位穩定的 `aos_kernel_ls` 第 1 版（不再原樣吐帳本）；第一行 health 不變（[cli-ls.md](cli-ls.md)）。
> 2026-09-24 proto5-2 池式納入：§1 目錄改 `K/pools/<P>/cpus/<i>/`、池模板；§1.1 換成池表（新檔 [info.md](info.md)）；§1.2 帳本第 2 版；§1.3 搬到 [names.md](names.md)；§2 pool 驗法；§3 改寫（通知、巡檢、`recent`、閒號堆疊）；新增 §3.1 [pools.md](pools.md)；§5 只剩 `scale`＋崩潰窗口＋保證外；§6 boot 改縮 kernel 池、停機改每池縮 0、新增 [cli-cpu.md](cli-cpu.md)、health 搬到 [health.md](health.md)、`ls --json` 升第 2 版（09-24 納入：第 2 版）；§7 交接句；§10 加 12～30；新增 §11 [scale.md](scale.md)。同日裁定：退休號只增不減、boot 等 draining 0、舊鏈晚到的 scale 單保證外、cpu add 後一兩秒「下一格確認」是接受的延遲。草稿與審查在 proto5-2/spec、proto5-2/notes。
> 2026-09-24 one-boot（P 審查 daemon-split-review 後使用者改的，[審查](../../notes/2026-09-24-daemon-split-review/README.md)、[報告](../../notes/2026-09-24-one-boot/README.md)）：開機合一、家不合一。kernel cpu、kernel 池、tick 鏈、開機交接拿掉，daemon 替 kernel 開 tick（[daemon §10](../daemon/ticks.md)），同時只准一格（daemon 只開一格＋`K/.tick.lock`）；帳本 `K/state.json`（第 2 版）換成 `K/ledger.sqlite`（第 3 版：四張表、只寫變了的列、三個提交點 A／B／C）；§0 名詞改寫；§1 家加 `.tick.lock`；§1.1 `kernel` 變保留名、加 `tick_timeout_ms`；§1.3 加登記／撤登記單；§3 第 1～3 步改寫；§5 多 `tick` 單；§6 boot 改五步＋崩潰表、每天開機改 `aos up`、停好那格撤登記、新增 `proc`、`ls --json` 第 3 版、health 加 `legacy`／`tick`；§7 改成兩道關；§9 改三條前提；§10 加 31～38；§11 帳本與 agent 那兩條改了。
