← [spec](spec.md)｜[README](README.md)

# 取樣器規則（ev1）

保存端（append／recover／derive）規則見 [spec.md](spec.md)。

## 取樣 keep 任務

aos7-events 是可執行 Python 腳本，使用 task_env、resolver(task)、wait_tock；首參數 `read`／`pub` 時改分派 aos7_events_read／aos7_events_pub 的 main，選項同原腳本（見 [README 工具](README.md#工具)）。`--src` 可重複、預設自身 node_id；來源先走掛載，否則 `<root>/<nid>/.aos/last-round.json`。`--status` 取最近 daemon 事件、`--daemon-log` 續讀 log；`--out` 預設 `<me.node>/events`；`--rounds N`（0 持續）；`--keep`、`--segment-bytes` 明確指定才傳 config。每次 tock 先 recover；None 則 stderr 一行、跳過。無自身落盤 state。

來源 dict、round 真整數才收。未見則寫快照 round.observed／sample，source={node,round}、payload={last_round:來源}；同 round 不寫。跳號先寫 gap，source.round=r−1，payload={from:prev+1,to:r−1,why:round_skip}；倒退改 {from:prev,to:r,why:source_reset_unknown}。gap 成功後寫快照，重啟不重記 gap。快照 too_large 改 {last_round:{round:r},truncated:true} 再試。not ok 停此來源，下回合重試。

status 只取 `<root>/.aosd/status.json` 的 dict last_event，與記憶體上次成功值不同才寫 daemon.status、capture=sample、source.node=.aosd、payload.last_event=事件。只記憶體去重，重起可能重記一筆。

測試：`TestSampler.test_300_rounds`、`TestSampler.test_gaps_and_reset`

## daemon log 續讀

只讀 `<root>/.aosd/log.jsonl`，不存在跳過，不裁不改。同一開檔 fd 的 fstat 取得 dev／ino／大小；舊進度身分不同或大小小於 offset，先寫 source_log gap：source={log_dev,log_ino,off_from:0,off_to:0}、payload={from:舊offset,to:0,why:source_reset_unknown}，成功後從 0 讀；無舊進度也從 0 讀。

完整行寫 daemon.log、capture=source_log，source={log_dev,log_ino,off_from,off_to}（byte 位置）。payload 為 parse 值或 {unparsed:前1000字}；壞 UTF-8 替代字。too_large 改 {too_large:true,bytes:原行bytes} 再試；not ok 停，下次從 state.offset 續。無換行尾端留待下次。

測試：`TestSampler.test_log_offsets`、`TestSampler.test_crash_log`
