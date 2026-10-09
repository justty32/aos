# events 事件保存包

一個 `events/` 夾就是一本帳：`pub` 寫一筆、`read` 讀出來、`ack` 確認處理完。檔數固定，舊的自己清。

← [modules](../README.md)｜進階（讓 daemon 自動記、完整選項、檔案規則、契約卡）→ [ADVANCED.md](ADVANCED.md)

## 先懂這五個詞（照第一次跑出現的順序）

1. **events 夾**：放事件的資料夾，第一次 pub 加 `--create` 才建。
2. **seq**：每筆的編號（1、2、3…）。`read --text` 最後一行 `# next_cursor 2` 就是「下一個要讀的 seq」，不是新東西，想接著讀時帶給 `--cursor`，不接著讀就不用管。
3. **obs／must**：夾裡兩本帳。obs＝一般紀錄，滿了丟最舊的（預設寫這本）；must＝一定要有人處理完的，用 `--must` 寫、`--channel must` 讀。
4. **ack**：對 must 說「seq 到這裡都處理完了」。讀到不算，ack 了才算；沒 ack 的一直留著，滿了 must 就拒收新的。
5. **event_id**：一件事的身分。同 id 再 pub 一次不會多一筆（回 `dup true`），所以失敗了可以放心重送。不給 `--event-id` 就自動產生一個（印在結果裡，這種不防重複）。

## 第一次跑（不用 daemon，約 1 分鐘）

整段貼上就能跑（第一行先切到 repo 根目錄；`P`、`E` 自動帶好，不用改）。

**一、寫一筆、讀出來（obs）**

```sh
cd "$(git rev-parse --show-toplevel)"
P=$PWD/proto7-2; E=$(mktemp -d)/n1/events; EV=$P/modules/events/aos7-events
$EV pub  --events $E --create --kind hello --payload '{"msg": "hi"}'
$EV read --events $E --text
```

```text
{"ok": true, "seq": 1, "dup": false, "why": null, "event_id": "auto/3f0c…"}   # 存好了，編號 1；event_id 是自動給的（每次不同）
1 hello n1 {"msg": "hi"}      # 編號 種類 n1 內容（n1 只是路徑裡的資料夾名，自動帶，不用管）
# next_cursor 2               # 下一個要讀的 seq
```

**二、一定要處理的事（must）：寫、重送、讀、ack**

```sh
$EV pub  --events $E --kind job.done --payload '{"id": 7}' --event-id job/7 --must
$EV pub  --events $E --kind job.done --payload '{"id": 7}' --event-id job/7 --must
$EV read --events $E --channel must --text
$EV ack --events $E 1
ls $E
```

```text
{"ok": true, "seq": 1, "dup": false, "why": null}
{"ok": true, "seq": 1, "dup": true, "why": null}   # 同 event_id 重送：還是 seq 1，沒多寫
1 job.done n1 {"id": 7}
# next_cursor 2
{"acked_upto": 1}                                  # 1 號處理完了
must.active.jsonl  obs.active.jsonl  state.json  state.json.lock   # 兩本帳＋帳本自己的進度檔與鎖（別動）
```

看到兩本帳各一筆、重送 `dup true`、`acked_upto 1` 就成功了（10-09 實跑）。完整選項：`$EV pub --help`、`$EV read --help`、`$EV ack --help`。

## 想做更多

日常用不到；需要時看 [ADVANCED.md](ADVANCED.md)：讓 daemon 每回合自動記、`pub`／`read`／`ack` 全部選項、檔案與檔數、契約卡、已知限制、長跑。測試：`python3 proto7-2/tests/run_all.py modules/events/tests`。
