# 名詞表：行程拓樸與控制平面
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### root（根管理者／唯一提交者）

**白話**：大家可以同時算，但最後只有一個人可以把結果算進公用世界。
**嚴格**：對建立、claim、排程、能力授予、收割與跨 lane commit 持有唯一寫權的控制主體；這是所有權協定，不自動是安全隔離。
**在 aos 裡具體是什麼**：目前不存在這個通用管理者，是提案；現存 `aos exec` 只會推進一個 world，不知道父子行程樹。
**為什麼會冒出這個詞**：使用者在[核心行程場](../records/core-process-and-subprocess.md) 說「多核學 Linux」；[四個選擇場](../records/four-open-choices-tradeoffs.md) 後收窄成扁平 `exec`、階層 `aos core` 的候選邊界。

### control plane（控制平面）

**白話**：不是幫忙做具體工作的那條路，而是負責「誰先做、誰能做、結果算不算數」的管理那層。
**嚴格**：管理工作身分、生命週期、排程、授權、join、commit 與恢復的機制集，與真正執行 instruction 的 data plane 相對。
**在 aos 裡具體是什麼**：目前不存在，是 lane、proc-table、capability、promotion、join 的合稱提案；現有 `aos exec` 不承擔這整層。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 想解決多工作共享世界的提交權；[回頭審視](../records/step-back-review.md) 認為這套在第一條 agent loop 之前太早。

### capability（能力憑證／可用權限描述）

**白話**：不只說「你可以做事」，而是把「你可以碰哪裡、做哪些事」連同一個難以偽造的憑據交給你。
**嚴格**：以可持有且可驗證的 authority 表示對某資源的特定操作權；若只是 JSON 中的路徑提示或排程標籤，就不是真正安全邊界。
**在 aos 裡具體是什麼**：目前不存在，是 `World` root fd、可寫路徑、root 授權等提案；同 UID 且允許任意 POSIX 指令時，只靠檔案欄位無法強制。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 想限制 lane 寫入範圍；[四個選擇場](../records/four-open-choices-tradeoffs.md) 四位又追問它究竟是安全邊界還是路由資料。

### proc-table（行程表／manager manifest）

**白話**：一張記「現在有哪些工作、放在哪裡、誰在等它們」的管理清單。
**嚴格**：由管理者維護的耐久 registry/manifest，候選欄位包含 handle、location、generation、lifecycle、owner、ready/join 狀態；它是真源還是可重建索引尚未定。
**在 aos 裡具體是什麼**：目前不存在，`.aos/procs/<id>.json` 與 `proc-table.json` 只是提案名字。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) R2 把子 world 的實體資料與父端管理狀態拆開；[回頭審視](../records/step-back-review.md) 後整體延後。

### join、barrier 與 completion event

**白話**：join 是「我要等這些工作都回來」；barrier 是「大家都到這條線才能往下」；completion event 是「我不原地等，你好了就留訊息」。
**嚴格**：join 聚合一組 asynchronous child/effect handles 的完成；barrier 禁止任一參與者越過共同同步點；completion event/receipt 以耐久消息取代持續阻塞。
**在 aos 裡具體是什麼**：目前沒有跨回合 join handle 或 event；現存 `parallel:true` 只會在同一 `aos exec` 回合末等所有 thread，不是待答題的持久 join。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 問父如何等子工作；[agent loop 場](../records/agent-loop-architecture.md) 又問平行 tools 何時收齊才可以提交下一回。

### handle 與 generation

**白話**：handle 是以後找回某件工作的拉環；generation 再多記一個「這是同名位置的第幾代」，避免舊結果丟給後來的新工作。
**嚴格**：handle 是指向耐久實體或未完成操作的穩定參照；generation 是在名稱／slot 重用時單調變化的 incarnation tag，使 `(name,generation)` 不會將 stale receipt 誤配到新實體。
**在 aos 裡具體是什麼**：目前都不存在公開契約；相對路徑與 `(name,generation)` 是慢想區的候選，[回頭審視](../records/step-back-review.md) 已延後 generation。
**為什麼會冒出這個詞**：[四個選擇場](../records/four-open-choices-tradeoffs.md) 不想使用 UUID，卻又要防止同名資料夾刪掉重建後誤收上一代的 receipt。

