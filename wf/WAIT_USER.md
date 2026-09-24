# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

### A. 等你一句話（其餘我都做得下去，卡的只有這幾條）

> 編號是固定的（別處用「WAIT_USER 第 N 條」引用），拍掉的號碼不回收，所以會跳號（1、2、7 已結；9 移到 C）。

3. **辯論場的四件轉交提案**：`deliver`／`aos enqueue` 要不要插進 T5 之前、「回合中途死掉
   的洞」歸不歸 roadmap 第六節、`k/`／`c/` 兩層命名進不進 `.aos` 標準、有限資源要不要
   獨立成 idea。**四件都是改規格文件，要人拍板。**
   → [pre-agent-loop-core](workflows/workshop/records/pre-agent-loop-core.md)
4. **hackathon 第一場（core-scope）的結論採不採用**：題目是「近期 core 要回撤到哪裡」，
   四個 persona 各實作一版、Torvalds persona 評分，**從白話導讀讀起**。
   → [records/core-scope](workflows/hackathon/records/core-scope/README.md)
5. **有限資源那場的衝突是不是已經自解**：你 2026-08-25 說「外部處理器自己監控一個資料夾、
   甚至不必引用 aos lib」之後，排隊就變成外部處理器的家務——**確認這一句就能收掉那場**。
   → [finite-resource-queue](workflows/workshop/records/finite-resource-queue.md)
6. **proto2：子 agent 會自動繼承 `spawn` 工具**，子孫一路都能生小孩（驗過三層）。要不要擋、要不要限深度？（使用者 09-06 說「之後再說」）→ [proto2/README](../proto2/README.md)
8. **proto2：agent 之間的交流（tell／hear，或子回話自動變父的信）**先不做，什麼時候做、走哪種？→ [proto2/README](../proto2/README.md)
10. **proto2：玩出來的 25 條效能與邊緣狀況、各包想要但沒有的接點**，要你看過說哪些現在要做。→ [notes/play/README.md](../proto2/notes/play/README.md)、[docs/packs-api.md](../proto2/docs/packs-api.md) 最後一節
11. **proto2 工作室：預算要不要對 cached token 打折**——claude-cli／anthropic 的 prompt_tokens 把 cache_read 也算進去（真實價格約 1/10），4d 帳面 841k 裡一半以上是 cache。選項：閘門只算 prompt−cached＋completion；或另開一個「真實成本」欄。→ [journey 第 10 節](../proto2/notes/2026-09-07-studio-journey.md)
12. **proto2 工作室：dev 的對話史**——haiku 一輪 10k 漲到 20k，一個任務 21 輪 325k。要不要每個任務開新對話史（做完就清、只留任務說明＋檔案清單）？→ 同上
13. **preset 的 `max_per_member`**——100k 對 claude-cli 太低（4d 手動抬到 500k）。改成 300k？還是照引擎不同給不同值？→ 同上
14. **proto5 重架構收線後的八題**（都不卡實作，agent 重寫照現況做）：(a) 跨代 stop——已送進 cpu 家的舊 stop 在 boot 後仍有效、新 kernel cpu 可能一開機就停，要不要讓 boot 去刪 cpu 家裡舊 chain 的 stop 檔（違反「不由外人刪 cpu 家的檔」）？(b) `kernel.log` 要不要輪替／限大小？(c) 硬砍 kernel cpu 時另一組的 tick 子程式可能還活著，要不要補 kill-tree？(d) agent 連敗暫停要不要改成明確 `fail` 狀態（[cleanup 筆記](../proto5/notes/2026-09-24-backlog-cleanup.md)）？(e) ~~`pause` 門關了還收不收結果~~——fix-r4 已做掉：暫停中 tick 直接退 0，連回音也不收（aos-agent.md §1.6，[fix-r4 筆記](../proto5/notes/play/fix-r4.md)），要翻案再說；(f) agent 要不要在 info 記自己屬於哪個 K（現在只在 tick.json 與 batch.kernel）？(g) 模型多回的欄位（`reasoning_content`）收回時要不要拿掉——現在原樣進記憶、下一問原樣送回，推理長的模型記憶會一起長大；(h) 封存檔 `*.<消費 id>.done` 誰清、何時清（每收一次輸入多一個，agent 不清）？→ [impl-fix-round1](../proto5/notes/2026-09-23-rearch/impl-fix-round1.md)、[agent-round2-changes](../proto5/notes/2026-09-23-rearch/agent-round2-changes.md)、[agent-impl-findings](../proto5/notes/2026-09-23-rearch/agent-impl-findings.md)
15. **daemon 崩潰窗口測試（C-2／C-3）挖出的兩題**（不卡實作）：(a) daemon 回完音、刪原單前被 KILL——回音裡的 `pid` 已被新任 daemon 弄死，規範沒說回音的 pid 可能過期，要不要在 daemon.md 補一句？(b) 舊孩子的 pid 若被別的使用者的程序重用，新任 daemon 送 TERM 失敗會直接退 1、不自救——要不要改成「發不出 TERM 就當它已消失」？→ [daemon-crash](../proto5/notes/2026-09-24-daemon-crash/README.md)
16. **問模型的 endpoint 壞掉要不要做自動換手**（原 backlog `llm-cpu-fallback`）：現在一個模型代號在 llm.json 只認一個 endpoint、不重試；要支援就要把 `models` 表一個代號改成一串。→ [cleanup 筆記](../proto5/notes/2026-09-24-backlog-cleanup.md)
17. **kernel 排隊要不要加期限**（原 backlog `kiss-holes` 第 2 條的 kernel 那半）：`queue` 裡等派工的行程沒有期限，只有 `timeout_ms` 管跑的時間；agent 那半（半批沒送完永遠等）已有手動 escape（stop 後把 `batch` 設 `null`）。→ [cleanup 筆記](../proto5/notes/2026-09-24-backlog-cleanup.md)
18. **once 工作綁在 `tick_ms` 的延遲算不算要處理**（原 backlog `review-leftovers` R11）：kernel 一格派、下一格才收，一次問答最快也要等一格；09-23 已判「算不算要做要人判」，agent 重寫沒碰這塊。→ [cleanup 筆記](../proto5/notes/2026-09-24-backlog-cleanup.md)
19. **proto5-2 規範草稿要拍的六題**（[proto5-2/README.md](../proto5-2/README.md) 的「要使用者拍的」一節第 4～9 條；前三條規模題 09-24 使用者說先不動，見下 C 段）：`cpu rm NAME` 的 `NAME`＝`P/<i>`、永久退休那個號，對不對；既有池的 `cpu add --env` 草稿直接拒絕，對不對；縮小要不要有 `--now`（現在一律等被收的那顆把手上工作做完）；拉不起來的號卡住的工作要不要訂「放棄」協定；daemon `halt` 後再 `boot` 要不要自動把池拉回來（草稿選「要」）；退休的 cpu 家永不刪，要不要清理指令。
20. **kernel C-7／C-8 崩潰窗口測試挖出的兩件**（[kernel-crash](../proto5/notes/2026-09-24-kernel-crash/README.md)）：(a) 出貨中被 KILL、cpu 已讀掉 stop 並退出後，下一格會照「EEXIST 當已放」重送一份同名 stop 到它家，下次 boot 這顆 cpu 起來就退 0、再下一格才拉起——astra 認為算重複投遞該修，隊長沒修因為會改規範行為（與 A.14(a) 跨代 stop 同一件事）；(b) kernel 拿到 daemon 的 spawn 回音、還沒記帳就崩潰，那則回音永遠沒人 ack，留在 `D/responses/`（只多一個檔，排程不受影響），修法要動 kernel↔daemon 對話。

### B. 要你親自做的（環境／帳號，我跨不過去）

（目前沒有。）

### C. 你已明說先不決定的（不催，只記「什麼時候會被迫要答」）

放這裡是為了**別再拿它們去煩你**，不是待辦：

- **proto5-2 規模三題**（kernel 帳本仍整份讀寫、aos-agent 每格偷看整份帳本、一顆 cpu＝一支 Python 程序）——09-24 使用者說「規模這塊先不動」；什麼時候會被迫要答：proto5-2 要實作，或 cpu 上千顆時。→ [proto5-2/README.md](../proto5-2/README.md) 的「要使用者拍的」1～3

- **pi 當介面層**（2026-08-30「先擱置」）——接法與代價在 [pi-interface](../core/agent/docs/pi-interface.md)，要投資時從那裡起。

- **B12 判準／loop 分支的形式／版面知識放哪**（2026-08-30 三題都「先不決定」）——
  會撞上的時機：要動 `exec_loop` 時（分支）、要寫第一支 CLI 小程式時（版面 lib）。
  → verdicts B12、core-layering
- **workshop 那四個設計選擇**（World 抽象、`kernel.json` 分層合成、子行程拓樸、親緣綁
  路徑還是 UUID）——你明講「窩不想看惹」，方向是**用實測取代拍板**，所以不列 A 區。
- **top-down-cli 的 14 條**——已裁「實作時順便解決」。
- （原 A.9）**proto2：拍板題 T-01～T-77 全照建議做了（使用者 09-06 說「都 OK」）**；要翻案就回編號。→ [notes/tools/README.md](../proto2/notes/tools/README.md)

> 設計上還沒答完、但不卡你的細節不放這裡——記在 [`roadmap`](workflows/roadmap.md) 與各 idea 文件的開放問題。
