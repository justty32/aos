# 待答問題：完成史、template 與定時喚醒
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)｜[白話導讀](../background/questions-workflow-policy.md)

第 15–17 題：完成史留不留、安裝後的 template 追不追上游、哪些 workflow 需要自動喚醒。

## 擋住事情的

### 15. SESSION-LOG／WAIT_USER 要不要保留完成史？

**問題｜**現在留下的完成事項是刻意的歷史，還是應恢復 open-only？  
**為什麼卡著｜**若完成史是需求，`done` 不能只刪除；若不是，現況就是要被 runtime 修掉的 drift。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位獨立地問了。  
**候選答案｜**

- **嚴格 open-only**——完成即從 SESSION-LOG／WAIT_USER 移除，不保留已解項。
- **原檔保留完成史**——`done` 改成標記完成，不刪除原項。
- **open-only＋另存 archive**——活 view 只列 open，完成項移到獨立歷史／done 區。

### 16. template 安裝後還追不追上游？

**問題｜**既有專案要持續吸收 template 更新、只做診斷，還是安裝後永久分叉？  
**為什麼卡著｜**是否需要 source version／base hash、三方 diff、doctor 與 upgrade 命令，全取決於這個答案。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位獨立地問了。  
**候選答案｜**

- **安裝後永久分叉**——不做 upgrade；上游版本最多只作追溯。
- **來源鎖＋人工三方合併**——保存 base hash，upgrade 只產舊基底／新基底／本地差異。
- **自動換未修改檔**——未改檔自動升級，客製檔只顯示 diff，不覆蓋。
- **只做 doctor**——先掃 placeholder、壞連結與孤兒路由，不替人合併政策。

### 17. 哪些 workflow 需要自動喚醒？

**問題｜**schedule／tick 是普遍 runtime 能力、少數專案特例，還是暫時維持人工喚醒？  
**為什麼卡著｜**若是普遍能力，task 狀態要收 `next_at`、Deliver 與 cursor；若不是，先做 scheduler 會放錯 scope。  
**在哪問過｜**〈用 aos 實現 workflows〉；3 位獨立地問了。  
**候選答案｜**

- **人工喚醒**——不做 runtime scheduler，沿用現在的 tick／cron 外部觸發。
- **只收 `next_at`**——人或 cron 到點呼叫，成功 Deliver 後才更新時間／cursor。
- **納入 `aos wf` runtime**——ready、schedule 與 wake 都由 task 狀態機管理。

