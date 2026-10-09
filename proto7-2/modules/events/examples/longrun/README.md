← [events](../../README.md)

# 長跑：真 daemon 300 回合，events/ 檔數不長、垃圾會清

`longrun.py` 開一個新 root、登記 node `n1`，掛三個 keep 任務，起**真的** `aos7-daemon` 跑到指定回合，再照正規途徑 `aos7-ctl daemon … stop --kill` 收掉：

| 任務 | 做什麼 |
|---|---|
| `aos7-events --status --daemon-log` | 取樣器：每回合記 last-round、daemon status 變化、續讀 `.aosd/log.jsonl`（放了 `log.on`） |
| `pub_task.py` | 發布者：每個 tock 發一件 obs、一件 must（同 event_id 重送冪等），保存確認後才推進 `<node>/longrun/pub.json` |
| `reader_task.py` | 讀者：每個 tock 讀完 must、核對連號、先存游標 `<node>/longrun/reader.json` 再 ack |

段大小開小（預設 8 KiB，keep 4），十幾回合就輪替一次，才看得到刪舊段。主程式每 20 ms 列一次 `events/`（取最大檔數、記看過的段名），每 25 回合與最後一回合取 daemon 與三個任務的 pid／starttime／RSS／開檔數，收掉後再列一次檔、從頭讀 obs 與 must 核對，印摘要並存 `<root>-summary.json`（含全部樣本）。

```sh
P=<proto7-2>
systemd-run --user --scope -q -p TasksMax=300 python3 $P/modules/events/examples/longrun/longrun.py --root /tmp/ev-long
systemd-run --user --scope -q -p TasksMax=300 python3 $P/modules/events/examples/longrun/longrun.py --root /tmp/ev-long-nr --no-reader
```

`--root` 要空或不存在。選項：`--rounds`（300）、`--interval-ms`（100）、`--segment-bytes`（8192）、`--keep`（4）、`--pad`（200）、`--timeout`（600 秒）。退出碼 0＝判準全過、1＝有判準沒過（看摘要的 `checks`）、2＝用法錯。

## 判準（`checks`，全過才退出 0）

- 兩種都要：到回合數；`events/` 檔數最大值 ≤12（不算原子寫瞬間的 `.state.json.tmp.<pid>`，另記 `max_files_incl_tmp`。12 是 spec 說的「清理完成後」上限：obs 輪替是先 rename 再刪最舊，中間瞬間會多一段，20 ms 取樣不保證抓得到，也不算違規）；只出現規定的檔名；收掉後的最終列檔也合規（每通道封存 ≤ keep）；obs 舊段真的被刪（看過的 obs 段名事後不在、`dropped_upto` > 0）；obs 從頭讀沒有錯；每次取樣每個角色恰一個程序、全程 pid＋starttime 不變（沒重起、沒雙開）；發布者活到最後；RSS 漲幅 <2 MB、開檔數不漲過 2；daemon 退出 0、收掉後沒有殘留程序。
- 有讀者：must 已 ack 的段被刪（`dropped_upto` > 0 且看過的 must 段名事後不在）、從沒拒收；讀者連號、0 錯 0 缺 0 重；讀者游標只推過處理成功的連號紀錄，停機時差的最後幾件由主程式從讀者游標逐筆補讀核對，合計等於發布件數且 ≥ 九成回合數。
- `--no-reader`：must 沒人 ack → 一段都沒刪、已接受的 must 從 1 起全部還讀得到、滿了拒收（`refused` > 0）、發布者停在容量上不推進；obs 照常輪替清理。

## 10-09 實跑結果（家機 Manjaro，scope TasksMax=300，審查修正後重跑）

| 項目 | 有讀者 | `--no-reader` |
|---|---|---|
| 回合／牆鐘 | 300／43 s | 300／43 s |
| events/ 檔數最大（含 tmp） | 9（9） | 12（13） |
| 看過的封存段／事後不在 | 34／obs 29＋must 1 | 26／obs 18＋must 0 |
| obs `next_seq`／`dropped_upto` | 606／524 | 404／326 |
| must `next_seq`／`dropped_upto`／`acked_upto`／`refused` | 301／293／299／0 | 96／0／0／205 |
| 發布者 `done_upto` | 300（讀者 299＋停機後補讀 1，0 錯 0 缺 0 重） | 95（之後 205 次 full 不推進；1～95 全在） |
| 收掉後 events/ | obs 封存 4＋兩個 active＋state＋鎖＝8 | obs 4＋must 4＋兩個 active＋state＋鎖＝12 |
| RSS（第 51→300 回合，KB） | daemon 20440→20476、取樣器 21956→22008、發布者 21416→21456、讀者 18460→18536 | daemon 20456→20492、取樣器 21876→21940、發布者 21356→21400 |
| 開檔數（第 51→300 回合） | daemon 7→7、取樣器 3→3、發布者 3→3、讀者 3→4 | daemon 7→7、取樣器 5→3、發布者 3→3 |
| root 下總項目數（第 51→300 回合） | 50→50 | 46→48 |
| daemon 退出碼／殘留程序 | 0／0 | 0／0 |
| `checks` | 16 條全過，退出 0 | 16 條全過，退出 0 |

must 段名「事後不在」只看到 1 段，是因為有讀者時 must 封存段在**同一次輪替**裡就因已 ack 被刪，只存在幾毫秒，20 ms 列檔多半看不到；刪除的證據是 `dropped_upto` 推到 293（spec：unlink 成功後才推）。開檔數 3→4、5→3 是取樣那一刻任務正開著段檔或鎖檔，不是累積。

結論：每回合都在寫，但 `events/` 檔數有上限、不會每回合多檔或多夾；obs 舊段由寫的人（取樣器、發布者）輪替時刪掉；must 只在 ack 後才刪，沒人 ack 時停收而不是刪。記憶體 250 回合內漲 36～76 KB（沒有隨回合線性長）、開檔數不累積。
