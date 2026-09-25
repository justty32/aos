# wait-user／proto2 — 辯論場／hackathon／proto2 舊題

← [WAIT_USER](../WAIT_USER.md)｜[wait-user/](README.md)

從 [WAIT_USER.md](../WAIT_USER.md) A 區搬出，編號沿用原號（3～13，7、9 已結/移出，見 hub）；逐字保留、不改寫不刪字。

3. **辯論場的四件轉交提案**：`deliver`／`aos enqueue` 要不要插進 T5 之前、「回合中途死掉
   的洞」歸不歸 roadmap 第六節、`k/`／`c/` 兩層命名進不進 `.aos` 標準、有限資源要不要
   獨立成 idea。**四件都是改規格文件，要人拍板。**
   → [pre-agent-loop-core](../workflows/workshop/records/pre-agent-loop-core.md)
4. **hackathon 第一場（core-scope）的結論採不採用**：題目是「近期 core 要回撤到哪裡」，
   四個 persona 各實作一版、Torvalds persona 評分，**從白話導讀讀起**。
   → [records/core-scope](../workflows/hackathon/records/core-scope/README.md)
5. **有限資源那場的衝突是不是已經自解**：你 2026-08-25 說「外部處理器自己監控一個資料夾、
   甚至不必引用 aos lib」之後，排隊就變成外部處理器的家務——**確認這一句就能收掉那場**。
   → [finite-resource-queue](../workflows/workshop/records/finite-resource-queue.md)
6. **proto2：子 agent 會自動繼承 `spawn` 工具**，子孫一路都能生小孩（驗過三層）。要不要擋、要不要限深度？（使用者 09-06 說「之後再說」）→ [proto2/README](../../proto2/README.md)
8. **proto2：agent 之間的交流（tell／hear，或子回話自動變父的信）**先不做，什麼時候做、走哪種？→ [proto2/README](../../proto2/README.md)
10. **proto2：玩出來的 25 條效能與邊緣狀況、各包想要但沒有的接點**，要你看過說哪些現在要做。→ [notes/play/README.md](../../proto2/notes/play/README.md)、[docs/packs-api.md](../../proto2/docs/packs-api.md) 最後一節
11. **proto2 工作室：預算要不要對 cached token 打折**——claude-cli／anthropic 的 prompt_tokens 把 cache_read 也算進去（真實價格約 1/10），4d 帳面 841k 裡一半以上是 cache。選項：閘門只算 prompt−cached＋completion；或另開一個「真實成本」欄。→ [journey 第 10 節](../../proto2/notes/2026-09-07-studio-journey.md)
12. **proto2 工作室：dev 的對話史**——haiku 一輪 10k 漲到 20k，一個任務 21 輪 325k。要不要每個任務開新對話史（做完就清、只留任務說明＋檔案清單）？→ 同上
13. **preset 的 `max_per_member`**——100k 對 claude-cli 太低（4d 手動抬到 500k）。改成 300k？還是照引擎不同給不同值？→ 同上
