# compact 細部契約

← [README](README.md)

## 契約卡

- **職責**：單 node 持鎖選舊段、摘要／忘掉、封存原文、替換檔案與留下 log。
- **前置條件**：node 可讀寫；檔案是 md／jsonl；watch 有任務環境；使用 llmcall 時帳任務已運行、grant 允許 holder 與 gateway。
- **保證**：先 archive 再換檔；now 不摘 open、最近 N 則與 files 第一個 md 的現役段（第一個 `## ` 到下一個 `## `，進行中的工作）；pending 原子保存，SIGKILL 後沿同 call 接續，已有 summary 不再叫摘要。只保證持 write.lock 的追加者：最後讀檔到 rename 持共同短鎖，摘要／llmcall 期間不持有；追加尾巴接回，其他改寫則放棄 pending、下次重規劃；未完成的段落觸發留到全部檔成功。events/ 已存在才發布 obs，沿同 event_id 重送。
- **明確不管**：不拿 write.lock 的追加在換檔瞬間可能丟，明確不管；斷電保證、摘要的語意正確性、封存保留期限；refs/、agent 的 prompt 組裝、events store 都不由本包管理。

合作的追加者先建 compact/，拿同一把鎖再追加（NODE 是 node 絕對路徑）：

```sh
mkdir -p "$NODE/compact"
export NODE
flock "$NODE/compact/write.lock" sh -c 'echo "{\"open\":true,\"text\":\"新待辦\"}" >> "$NODE/notes/journal.jsonl"'
```

資料都留在 `<node>/compact/`：lock、write.lock、state.json、pending.json、archive/、log.jsonl；req／result 在收尾清掉。本機摘要把每則壓成一行取前 60 字，以「；」串接後截短；llmcall 要求一段繁體中文，保留決定、數字、檔名與未解問題，避開 open 項；只輸出摘要本文。LiteLLM 不設 max_tokens；超過 summary_max_chars×1.5 字時截到 summary_max_chars，log／事件記 truncated: true。這裡整理的是記憶檔，事件只通知 `compact.done`／`compact.forget`。


段落觸發的 evidence（ended、similarity、threshold）寫入 log 與事件 payload；state 的 stage_evidence 隨 stage_due 保留到全部檔整理成功，abandoned pending 不會吃掉觸發；接完舊 pending 後同一次照樣重評該檔，舊 pending 不算新觸發完成。相似度保存原始浮點值，人看的原因顯示兩位小數。

真 AI 實跑（10-09，`examples/real_ai.sh`，`chatgpt-gpt-6-sol-high`，1 次呼叫）：65 則（60 舊＋5 open）→ 6 則，8968 → 2149 bytes（−76%），open 5 全留；usage 5429 tokens（prompt 4830、completion 599），約 12 秒，未截斷。
