# must 需求收件（已實跑）

← [author 包](../../README.md)｜需求沿用 [CSV request](../csv-request/request.json)

命令在 node 目錄跑。`P`／`A` 用絕對路徑；send 自動傳 node 目錄名（此例 n1），不用 `--node`，events 不存在也可建立。寫者只送需求，data.csv 的驗證由作者 intake 做。

```sh
P=<proto7-2>; A=$P/packs/author
mkdir -p <root>/n1 && cd <root>/n1
cp $P/packs/step/examples/csv/data.csv data.csv
python3 $A/bin/aos7-author send $A/examples/csv-request/request.json --events events
python3 $A/bin/aos7-author send $A/examples/csv-request/request.json --events events
python3 $A/bin/aos7-author intake --events events
python3 $A/bin/aos7-author intake --events events
python3 $P/modules/events/aos7-events read --events events --channel must --ack 1
python3 $A/bin/aos7-author propose csv1 --candidate $A/examples/csv-request/valid.json
python3 $A/bin/aos7-author publish csv1
```

實跑輸出（10-09，JSON 縮排壓成單行；路徑換成佔位符）：

```text
{"seq": 1, "dup": false, "ok": true, "why": null}
{"seq": 1, "dup": true, "ok": true, "why": null}
{"handled": [{"seq": 1, "rid": "csv1", "result": "registered"}], "cursor": 2, "acked_upto": 1, "ok": true, "why": null}
{"handled": [], "cursor": 2, "acked_upto": 1, "ok": true, "why": null}
{"acked_upto": 1}
{"rid": "csv1", "candidate_sha": "32ac171d8cb870db672da20829e0300f19b33b033e44ff40b031493a8900b76c", "job": "csv1_32ac171d", "payload_sha": "1ccea2a285404289dd107f18f30852c5a3308407af0b5f5103c854073f322b43", "issues": [], "ok": true, "why": null}
{"rid": "csv1", "receipt": {"v": 1, "rid": "csv1", "request_sha": "57aa2b8c17356aa7f1cee15aa64f6c0b91e8bf1706ec7bc244d79d9aade1e2be", "candidate_sha": "32ac171d8cb870db672da20829e0300f19b33b033e44ff40b031493a8900b76c", "payload_sha": "1ccea2a285404289dd107f18f30852c5a3308407af0b5f5103c854073f322b43", "job": "csv1_32ac171d", "task_name": "author-csv1_32ac171d", "registered": true, "evidence": "table", "closed": false}, "ok": true, "why": null}
```

intake 已 ack；read 的 `--ack 1` 是同值重送，可看確認值，不另推進。再 intake 的 handled 空，回條仍是第一次 registered。propose／publish 之後的執行、answer／close 照 [進階流程](../../ADVANCED.md)。full（退出 1）不算送出；unknown（退出 3）照同 rid 重送。
