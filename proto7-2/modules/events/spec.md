← [modules](../README.md)｜藍圖 [blueprint-ev1](../../notes/blueprint-ev1.md)

# 事件保存端與取樣契約（ev1）

## 目錄與紀錄

每 node 一個 events/：只有 obs.active.jsonl、must.active.jsonl、各通道 `<ch>.%012d.jsonl` 封存段（數字＝段首 seq）、state.json、state.json.lock。預設每通道四個封存，清理完成後最多 `2(N+1)+2`＝12 檔；原子寫時另有 `.state.json.tmp.<pid>`。持鎖恢復刪所有 `.state.json.tmp.` 前綴殘留，不看 pid；不可刪鎖檔。

UTF-8 JSONL、ensure_ascii=False，完整換行才算一筆。鍵序為 v=1、stream=`<node>/<channel>`、seq、kind、capture、可選 event_id、source、at、payload，再補 rec 其他鍵。seq 每通道從 1 起只增不重用；at 沿用 rec 或用 now()。capture 是 sample（最新檔取樣，可能漏）、source_log（續讀來源 log）、published（合作來源逐件發布，必帶非空字串 event_id）。

單筆含換行限 65536 bytes；超限不輪替、不寫、不耗 seq。flush、不 fsync；保存確認只抗程序 SIGKILL，不承諾斷電。state 用 write_json 原子替換。寫者拿 `locked(<dir>/state.json, timeout=5)`。

測試：`TestStore.test_append_basic`

## state 與設定

state 是 `{v:1,node,config,channels,sample,daemon_log}`。DEFAULTS：keep_segments=4、segment_bytes=1048576、max_record_bytes=65536。新建只合併三個設定，值須真正正整數（bool 不算），keep_segments ≤ 4（MAX_KEEP，守 12 檔），否則 ValueError。已有 state 以原設定為準；傳入 config 任一鍵不同，append 加 config_ignored=true；node 不符回 unknown。

channels 的 obs／must 各有 next_seq=1、active_first=1、active_bytes=0（存 state 時活躍段 bytes）、segments=[]（封存首 seq 遞增）、dropped_upto=0、torn=0；must 加 acked_upto=0、refused=0。sample={} 存來源末 round；daemon_log=null 或 `{offset,dev,ino}`。

state 存在但 fact 非 OK、非 dict 或缺必要欄位／型別不合，append 回 unknown、ack 丟 Unknown、recover 回 None，絕不覆蓋。不存在才建，並恢復既有段。state 遺失只能推回留存的 seq、來源進度、淘汰下界，不能重建舊 ack 與計數。

測試：`TestStore.test_bad_state`

## 持鎖恢復與唯讀

append／ack／recover 持鎖先恢復。列 `<ch>.(12位數字).jsonl`，升序取代 segments，忽略其他名。新段掃完整行的 dict、真整數 seq；按檔內順序 derive seq ≥ 掃描前 next_seq 者，next_seq=max(seq)+1。

活躍段不存在：active_first=next_seq、active_bytes=0。大小等於 active_bytes 且無新段時不掃；其餘整檔讀。尾無換行截到最後換行後（無换行截 0），torn 加一；active_first 取第一筆有效 seq，空則 next_seq；同樣補尾端進度，active_bytes 更新為截後大小。最後 dropped_upto 推到最早封存首 seq−1，無封存則 active_first−1，只增不減；obs 封存多於 keep_segments（rename 後清段前被殺）就當場刪最舊。恢復只改記憶體，呼叫端寫回。

共用 derive：sample 的 source.node 字串、round 真整數，推 sample[node]（含 gap）；source_log 的 log_dev、log_ino、off_to 真整數，推 daemon_log 的 dev、ino、offset。

`recover(events_dir, *, node, config=None)` 鎖內建檔／恢復／保存，回 state；逾時、OSError、壞 state、node 不符回 None。`load_state(events_dir)` 唯讀、不鎖、不恢復，fact OK 且 dict 回內容，其餘 None。

測試：`TestRecovery.test_missing_state`、`TestRecovery.test_torn_and_tmp`

## append 與去重

`append(events_dir, channel, rec, *, node, config=None)` 回 `{ok:bool,seq:int|null,dup:bool,why:null|"full"|"too_large"|"unknown"}`，可加 config_ignored。同通道 event_id 重複回成功、原 seq、dup=true，不另寫。輪替前掃留存全部完整行；窗口外重送成新紀錄。

channel 非 obs／must、rec 非 dict、node 非非空字串、published 缺非空字串 event_id、rec 帶 seq／stream／v，鎖外丟 ValueError。執行期 LockTimeout、Unknown、任何 OSError 回 unknown；可能已寫入，發布者照同 id 重送，不推進自己的進度。失敗均 seq=null、dup=false。dup、too_large、full 保存恢復後 state。

測試：`TestStore.test_dup`、`TestStore.test_value_errors`

## 輪替、滿載與確認

append 前 active_bytes ≥ segment_bytes 才輪替，一筆可讓段超過門檻。先判目的檔已存在或有段首 ≥ active_first（範圍重疊）→ unknown，任何刪段之前。再判容量：must 封存數 ≥ keep_segments，先從最舊刪整段已確認者，遇未確認立即停；仍滿則 refused 加一、存 state、回 full，段配置不動。段末 seq＝下一段首 seq−1，最後封存的下一段是 active_first；末 seq ≤ acked_upto 才可刪。

可收才 rename 活躍段到段首 seq 封存名，絕不覆蓋。rename 後加入 segments，active_first=next_seq、active_bytes=0。obs 刪最舊到剩 keep_segments；must 清全部整段已確認者，含剛輪替段。unlink 後才移除清單、推 dropped_upto（**must 刪已確認段同樣推 dropped_upto**）。輪替與清段完成後先存一次 state 再寫新筆，恢復的大小快速路徑才不會把新活躍段誤認為舊的。垃圾由寫者清。

保存確認＝append 成功（含 dup）；消費確認＝ack，讀到或 LLM 看過不算。`ack(events_dir, upto)` 須真整數，否則 ValueError；鎖內恢復，推 `max(acked_upto,min(upto,next_seq−1))`、保存、回新值，倒退忽略。state 不存在回 0、不建 state。ack 不刪段，下次輪替才清；壞 state、LockTimeout 往外丟 Unknown，OSError 包成 Unknown。

測試：`TestRotation.test_must_full_ack`

## 取樣 keep 任務

aos7-events 是可執行 Python 腳本，使用 task_env、resolver(task)、wait_tock。`--src` 可重複、預設自身 node_id；來源先走掛載，否則 `<root>/<nid>/.aos/last-round.json`。`--status` 取最近 daemon 事件、`--daemon-log` 續讀 log；`--out` 預設 `<me.node>/events`；`--rounds N`（0 持續）；`--keep`、`--segment-bytes` 明確指定才傳 config。每次 tock 先 recover；None 則 stderr 一行、跳過。無自身落盤 state。

來源 dict、round 真整數才收。未見則寫快照 round.observed／sample，source={node,round}、payload={last_round:來源}；同 round 不寫。跳號先寫 gap，source.round=r−1，payload={from:prev+1,to:r−1,why:round_skip}；倒退改 {from:prev,to:r,why:source_reset_unknown}。gap 成功後寫快照，重啟不重記 gap。快照 too_large 改 {last_round:{round:r},truncated:true} 再試。not ok 停此來源，下回合重試。

status 只取 `<root>/.aosd/status.json` 的 dict last_event，與記憶體上次成功值不同才寫 daemon.status、capture=sample、source.node=.aosd、payload.last_event=事件。只記憶體去重，重起可能重記一筆。

測試：`TestSampler.test_300_rounds`、`TestSampler.test_gaps_and_reset`

## daemon log 續讀

只讀 `<root>/.aosd/log.jsonl`，不存在跳過，不裁不改。同一開檔 fd 的 fstat 取得 dev／ino／大小；舊進度身分不同或大小小於 offset，先寫 source_log gap：source={log_dev,log_ino,off_from:0,off_to:0}、payload={from:舊offset,to:0,why:source_reset_unknown}，成功後從 0 讀；無舊進度也從 0 讀。

完整行寫 daemon.log、capture=source_log，source={log_dev,log_ino,off_from,off_to}（byte 位置）。payload 為 parse 值或 {unparsed:前1000字}；壞 UTF-8 替代字。too_large 改 {too_large:true,bytes:原行bytes} 再試；not ok 停，下次從 state.offset 續。無換行尾端留待下次。

測試：`TestSampler.test_log_offsets`、`TestSampler.test_crash_log`

## 測試點與限制

測試點 `events:` 前綴：after-partial（半行 flush 後）、after-append（整行 flush 後、存 state 前）、after-rename（rename 後）、after-unlink（unlink 後）、sample-after-gap（gap 保存後）。state 沿用 `tmp:state.json`。

限制：一個 events/ 只能有一個取樣器（進度在 recover 後離鎖使用）；截尾後存 state 前被殺 torn 少記一次（紀錄不受影響）；status 記憶體去重；event_id 留存窗口、逐次掃描成本；單消費者；取樣無法補漏；log 同 inode 截短又長回舊 offset 無法辨識。不做集中收集、fsync／斷電保證、三包接線、history 合併、核心出口、多消費者確認、跨 node 查詢。

測試：`TestCrash.test_after_partial`、`TestCrash.test_after_rename`、`TestReviewRegressions.test_rotation_then_kill_does_not_reuse_seq`
