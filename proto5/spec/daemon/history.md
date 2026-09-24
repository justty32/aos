← [daemon](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`daemon：所有 cpu 的父行程（第 1 版，2026-09-23 定稿）`

> 2026-09-23 重架構第三份；同日照 astra 第二輪 D 清單（18 題）與第三輪（D3／X3／C3）改過。
> 2026-09-23 定稿並已實作：[`aos_daemon.py`](../../lib/aos_daemon.py)（入口 `aos-daemon`）。舊 daemon-home.md／aos-daemon.md 已刪（副本在 [proto5.1/spec/](../../../proto5.1/spec)）。
> 已拍板的前提在 §8，我自己選的在 §9。
> 2026-09-24 實作補記：依實作審查回寫，見 impl-review-report.md；補進的句子標「（09-24 補）」，總表在檔尾〈實作補記〉。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> 2026-09-24 fix-r4：§6 命令列改成 `aos-daemon boot`／`halt [--target D]`（裸 `aos-daemon` 退 2、`--home` 拿掉），家的預設從 `~/.aos-daemon` 改成 `AOS_DAEMON_HOME`→目前資料夾。
> 2026-09-24 proto5-2 池式納入：§1 孩子表搬出 `state.json`、info 多退避與節流鍵；新增 §1.2 [pools.md](pools.md)（`pool.json`、kids 檔、摘要）；§2 只留 fd 0 一條 pipe、拿掉 `spawn`；§3 換成 `scale`／`kill`／`ls`；§4 改宣告式對帳、任何退出碼都重拉、退避、令牌桶、fd 預算；§5 批次階梯、`halt` 留 `pool.json`；§6.1 啟動照 `pool.json` 拉回來；新增 §6.3 [cli.md](cli.md)（`ls` 的 `running N（含 restarting M）`、`scale`、`kill`）；§8、§9 跟著改。草稿與審查在 proto5-2/spec、proto5-2/notes。
> 2026-09-24 one-boot（P 審查 daemon-split-review 後使用者改的，[審查](../../notes/2026-09-24-daemon-split-review/README.md)、[報告](../../notes/2026-09-24-one-boot/README.md)）：開機合一、家不合一。daemon 替 kernel 定時開 tick（新增 §10 [ticks.md](ticks.md)：`tick` method、`kernels/<id>.json` 登記、何時開、退出碼、退避、逾時、停機、被 kill -9、`ls`）；新增 §11 [up.md](up.md)（`aos up`／`aos down`）；§1 家多 `kernels/`、`daemon.log`；§3 加 `tick`、`ls` 多 `kernels`；§4 一圈多「開 tick」；§5、§6.1 跟著改；§6.3 `ls` 多印 kernel；§8 「daemon 不認識 kernel」改成「只認得 kernel 家在哪、多久開一格」；§9 加 23～28。
