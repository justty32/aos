# compact 細部契約

← [ADVANCED.md（進階與契約卡）](ADVANCED.md)

合作的追加者先建 compact/，拿同一把鎖再追加（NODE 是 node 絕對路徑）：

```sh
mkdir -p "$NODE/compact"
export NODE
flock "$NODE/compact/write.lock" sh -c 'echo "{\"open\":true,\"text\":\"新待辦\"}" >> "$NODE/notes/journal.jsonl"'
```

資料都留在 `<node>/compact/`：lock、write.lock、state.json、pending.json、archive/、log.jsonl；req／result 在收尾清掉。本機摘要把舊則按「誰」分段（jsonl 的 `re`／`id`，md 行裡的信 id，都沒有就歸「其他」），每段寫「信 <寄件人>-…<尾碼> N 則（第 a～b 回合）：做了什麼 → … → 做了什麼」，做了什麼取 jsonl 的 `text`（`｜` 前那段）或 md 項去掉時間與信 id；開頭標總則數與時間範圍，舊摘要併成「更早：」；長度上限是舊則 bytes 的六分之一（至少 200 字、不超過 summary_max_chars），放不下先縮短每項、再省略中段只留第一項與最後幾項；llmcall 要求一段繁體中文，保留決定、數字、檔名與未解問題，避開 open 項；只輸出摘要本文。LiteLLM 不設 max_tokens；超過 summary_max_chars×1.5 字時截到 summary_max_chars，log／事件記 truncated: true。這裡整理的是記憶檔，事件只通知 `compact.done`／`compact.forget`。


段落觸發的 evidence（ended、similarity、threshold）寫入 log 與事件 payload；state 的 stage_evidence 隨 stage_due 保留到全部檔整理成功，abandoned pending 不會吃掉觸發；接完舊 pending 後同一次照樣重評該檔，舊 pending 不算新觸發完成。相似度保存原始浮點值，人看的原因顯示兩位小數。

真 AI 實跑（10-09，`examples/real_ai.sh`，`chatgpt-gpt-6-sol-high`，1 次呼叫）：65 則（60 舊＋5 open）→ 6 則，8968 → 2149 bytes（−76%），open 5 全留；usage 5429 tokens（prompt 4830、completion 599），約 12 秒，未截斷。
