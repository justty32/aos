← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 9. 連敗暫停

§7 那次寫把 `errors` 加到 3 時：同一次寫改成 `errors: 0`、`waits` 表尾加 `{"$opt": "consume", "$val": "continue-<B>.json"}`（B＝這批的批 id，所以每次暫停的訊號檔名都不同，不會有舊檔先在），
stderr 一行 `aos-agent: stuck: 問模型連敗 3 次，修好原因後 aos-agent continue --target <agent 絕對路徑>`（09-24 試玩 r1 補；09-24 fix-r5 改：不再叫人 `touch` 訊號檔，檔名看 `status -v` 或 `state.json` 的 `waits`）。人也可以直接看 `state.json` 的 `waits` 找到檔名。（09-24 試玩 r2 補）日常用 `aos-agent continue`（§1.4）就好，不用抄檔名；`aos-agent status` 也會印出這道門。
本次退 0，之後門沒開就 101。設定讀驗、I/O 錯、`HistoryChanged` 不算連敗（它們退 1，由 kernel 的 `bad_after` 管）；工具失敗也不算（那是給模型看的結果）。

# 10. 清工作檔

每次 `tick` 第 3 步，對 `sweep` 的每一筆 `{kernel: K, name: N}`：`K/requests/N.json` 不在、**而且**偷看 `K/state.json` 的 `procs` 沒有 `N`
→ 刪 `work/N.inst.json`、`work/N.in`、`work/N.out`（ENOENT＝已刪）→ 把這筆拿掉。全部看完一次寫 state。

依據：kernel 對一件派出去的工作，`procs.N` 一直留到那顆 cpu 的回音收回來才拿掉——被 `rm` 的也一樣（標 `discard`，[kernel.md §2](../kernel/syscall.md)）。
所以 `procs` 沒有 `N`＝它已經不在任何 cpu 上（或根本沒送出去），檔可以刪；有 `N`＝可能還在讀 `.in`、寫 `.out`，先留著。
`K/state.json` 讀不到就整段跳過，下次再看。（cpu 被 KILL、子程式還活著這種情況在 [cpu.md §5.3](../cpu/stop.md) 的保證外。）
