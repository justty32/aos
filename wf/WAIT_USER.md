# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

### A. 等你一句話（其餘我都做得下去，卡的只有這幾條）

1. **`aos/inst.hpp` 這個 include 路徑跟不跟著改？** `core/inst` → `core/exec` 已拍板
   （2026-08-30），但公開標頭算「專案的門面」（改成 `aos/exec.hpp`）還是「那個資料格式
   的標頭」（留著）沒答——**不答就動不了工**。
   → [core-layering 落差區](workflows/ideas/core-layering.md)
2. **T5 驗收條件與 `.aos` 規格第六節互相矛盾，要改哪一邊？** 單次 `aos exec` 真被 SIGINT
   中止會留 `.runi`、下次固定退出 3，人工搬回去只能**重播整批**，而外部作用可能已經做過。
   → [t5-agent-loop](workflows/experiments/t5-agent-loop.md)
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

6. **自我投遞要不要埋進 loop**：隊 B 提了方案 A（`.aos/every/` 目錄，loop 每回合自動投遞）與方案 B，
   建議 A；文末另有五條待拍板。→ [self-delivery-in-loop](workflows/ideas/self-delivery-in-loop.md)
7. **pi 當介面層要不要投資**：三種接法與代價已寫好，需一句話選一種或先不做。
   → [pi-interface](../core/agent/docs/pi-interface.md)

### B. 要你親自做的（環境／帳號，我跨不過去）

8. **真模型的 T5 實測還沒跑通**（**2026-08-30 補**：新原型已用 LM Studio 跑通，這條大概可以收掉，等你確認）：當時三條路全斷——codex 被沙盒擋、Claude OAuth 過期、
   WSL 沒裝 pi。→ [t5-agent-loop](workflows/experiments/t5-agent-loop.md)
   > **這條可能已經不必等你了，但要你確認兩件事**：(a) SESSION-LOG 記的建置環境是
   > WSL ＋ `/mnt/c`，而現在這台是 Manjaro、repo 在 `~/repo`，那些筆記可能已過期；
   > (b) 你手上有本機 LM Studio（`localhost:1234`）——**如果它可以當那顆「真模型」，
   > 我自己就跑得動，不用等帳號。**

### C. 你已明說先不決定的（不催，只記「什麼時候會被迫要答」）

放這裡是為了**別再拿它們去煩你**，不是待辦：

- **B12 判準／loop 分支的形式／版面知識放哪**（2026-08-30 三題都「先不決定」）——
  會撞上的時機：要動 `exec_loop` 時（分支）、要寫第一支 CLI 小程式時（版面 lib）。
  → [verdicts B12](workflows/ideas/verdicts.md)、[core-layering](workflows/ideas/core-layering.md)
- **workshop 那四個設計選擇**（World 抽象、`kernel.json` 分層合成、子行程拓樸、親緣綁
  路徑還是 UUID）——你明講「窩不想看惹」，方向是**用實測取代拍板**，所以不列 A 區。
- **[top-down-cli](workflows/ideas/top-down-cli.md) 的 14 條**——已裁「實作時順便解決」。

> 2026-08-24：原本卡著的「移植 S2 的決策 A（`core/tooljson` 的 exec 引擎自己寫還是動
> `core/inst`）」已經整條解掉——使用者批准解凍 `core/inst`，並拍板 `stderr` 併流用
> `{"$opt": "merge"}` 由 `inst` 自己支援（見
> [`docs/inst-directives.md`](../docs/inst-directives.md)）；`core/tooljson` 本身則
> 先不動、排在 agent loop 之後。設計上還沒答完的細節不放這裡——它們不卡使用者，記在
> [`docs/roadmap.md`](../docs/roadmap.md) 與各 idea 文件的開放問題。
