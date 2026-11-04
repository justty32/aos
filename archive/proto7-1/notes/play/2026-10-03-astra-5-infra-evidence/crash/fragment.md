# 崩潰回歸與補驗

重跑 `python3 .../crash/probe.py`，再跑 `python3 .../crash/extended.py`。原 astra-4 harness 七案都保留結果，只有暫存前綴換 astra5；sitecustomize 保留舊 hook 並另加 flock/append_jsonl hook 供補验。extended 九案均沒有 probe_error，cleanup.remaining_children 都空、root_exists 都 false。所有故障在自有目錄，subreaper 只為實驗控制器收尾。

## 原腳本不再適用的等待條件

- stale-tick/stale-tock 原流程要求「新 daemon 先到 r2，再放行仍持鎖的舊動作」。新版整段鎖使 r2 無法出現，原 harness 5 秒 TimeoutError；這**不是證明倒寫仍在**，也不能直接當通過，須看 extended 的交接實驗。
- readonly/enospc 原流程等 daemon 5 秒內崩潰；現在它不退出，因此原 harness TimeoutExpired。extended 改為確認持續運轉、錯誤可見、解除故障後恢復與正常 stop。
- runner-exit 原 hook 比對 `/exit.json`，新版 runner 用 dir_fd＋相對目的 `exit.json`，hook 未觸發而 timeout。extended 的 runner-exit-fd 改比對檔名，其餘故障窗口相同。

## 結果

| 案例 | 實測／判定 |
|---|---|
| spawn-loss 原刪檔後 kill tick | at_fault 已有 once-r1 birth；工作已啟動，原 I-02 無痕失蹤不再重現。這是至少一次，不是 exactly-once |
| ended-loss 原寫 ended 後 kill tock | at_fault 已有 r1 rounds.jsonl 的 ended 事件，原 I-03 消費標記超前已修 |
| 舊 tick/tock 在 flock 前停住→kill daemon→重開 | 新 gen2 分別到 r12/r13；放行舊動作後未倒退，舊動作已Z／不再執行。舊 tick 輸出管線在 daemon 死後不可作可靠回條來源；磁碟實測無倒寫 |
| 舊 tick/tock **持鎖**→kill daemon→重開 | gen2 已落盤，action_timeout_s=.25；1.15 秒窗 round 一直1，新動作連續 timeout -9。放行舊動作後才到 r4。新 daemon 只 kill 正在等鎖的新 action，沒有識別／收掉舊持有者。未永久等待；「持有者不退出則無法接管」另由 flock/timeout 程式路徑支持 |
| 真 chmod .aosd 0555，稍後恢復 | daemon 活著，io_errors 增加，解除後 status 恢復；正常 stop rc0 |
| status rename 注入一次 ENOSPC | daemon 活著，status.io_errors=1，正常 stop rc0；沒有真的填滿磁碟 |
| tock append 完 summary 後停住，讓 .25s action timeout 殺它 | r1 與 r2 兩行都報同一 one-r1 ended。r1 summary 無 incomplete；daemon log 對 r1 tock 記 incomplete:true/rc:-9。接著繼續 r3/r4。不是資料被抹掉，是兩份完成／失敗視角不在同一提交邊界 |
| append 完 summary 後 kill tock，**同回合再 tock** | rounds.jsonl 有兩行 round:1、同一 done-r1 ended。open:false 只在最後寫成，不能防中斷後重放重複。N-20「不重複總結」尚未完成；細部 spec 明示可能重報 ended，不能誤讀為 exactly-once 已承諾 |
| runner 寫完 exit tmp 未 replace，kill runner | 正式 exit lost:true/code:null，保留 tmp 的 code23；P-07/N-23 舊限制仍在 |

## 分類／需求

I-01 原「新進度被舊動作倒寫」已擋；N-18 原防倒寫安全性通過，接管可用性缺口另併 N-23 並連 N-54 的管理範圍。舊鎖持有者的回收是〔bug〕S-03/S-06/S-08，不需改每動作一個程序。需要可驗身分的 action owner 記錄（PID加啟動身分／世代）與重開時有界回收，不能直接 unlink lock：那會造兩個 inode、失去互斥。

N-20 從「已做」改部分；已修「永久漏掉」的原窗口，沒有重放冪等與跨檔提交。N-54 timeout 殺動作與 log incomplete 符合現行 spec；tock 的 summary 可能已正常寫成，需有 attempt／提交結果可判讀，這是 N-20／N-12 的擴充驗收，不是現行 spec 已要求 tock summary 的 incomplete 欄位。持鎖案例先放行舊動作才 stop，未直接驗持鎖中停機上界。S-01/S-06/S-08/S-11，〔bug〕相對需求不重複承諾；提交方案是技術選型。

I-07 原主迴圈 OSError 退出修好，N-22仍部分；不涵蓋 daemon.run 啟動階段、掃描內被吞掉的錯誤、滿碟降級策略及斷電 fsync 保證。這些不能從兩案通過推論全有。
