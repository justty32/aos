# 主題：有限資源——CPU 是怎麼指揮 GPU 的，aos 該怎麼做？

← [workshop](../README.md)

| | |
|---|---|
| **開場** | 2026-08-24 |
| **已跑輪數** | R1（各自發想） |
| **狀態** | 進行中 |
| **參與身份** | 資深工程師 / 資深架構師 / 資深研究人員 / 資深獨立維運人員 / 資深獨立軟體開發者 |

**主題**：`aos exec` 是無窮的資源（要多跑一筆就 `fork` 一個 process）；LLM endpoint 是有限
資源（速率限制、併發上限、成本、429、而且多個資料夾可能搶同一個）。使用者的提法是：
**想想 CPU 和 GPU 是怎麼交流的、CPU 是怎麼指揮 GPU 的。**

---

## R1 想法池

### 成形的方向

1. **佇列必須在資料夾之外，落在「使用者層級」。五位獨立地都這樣放。**
   `$XDG_STATE_HOME/aos/llm/<endpoint>/` 或 `~/.local/state/aos/llm/<endpoint>/`。
   理由很簡單：**endpoint 是跨資料夾共享的東西**，把佇列放在某一個 `.aos/` 裡，第二個資料夾
   就看不到它。
   > ⚠ **這直接撞上 [`docs/roadmap.md`](../../../docs/roadmap.md) 第六節「不做全域 LLM daemon
   > 與跨資料夾排程」。** 五位沒有一個人是為了挑戰那條而挑戰——他們是從「endpoint 在哪」這個
   > 事實推出來的。這是本輪最該讓使用者知道的一件事。

2. **目錄狀態機（maildir 式）**：工作在目錄之間 `rename` 來表示狀態。五位給的分格幾乎同形：
   `ready`／`running`／`done`／`delayed`（或 `retry`／`delay`）／`unknown`／`bad`。
   `rename` 是**發布**，目錄名就是狀態，`ls` 一下就知道發生什麼事。

3. **fence 在 world 裡，工作在 spool 裡。** 資料夾只留 `.aos/k/llm/<id>.json` 當 fence，
   續體 poll 它；真正的工作內容在中央 spool。這樣**排程者不會變成資料夾的第二個 writer**
   （架構師的講法），資料夾的所有權保持單一。

4. **staging 不能省，而且有兩個獨立理由。**
   - 技術理由：**跨檔案系統 `rename` 會 `EXDEV`**，所以「投遞到中央 spool」必須是明確的複製
     步驟，不能靠一次 `rename` 同時承諾兩端。這正好對應硬體的 staging buffer／DMA。
   - 語意理由（維運的觀點）：輸入要**快照**，否則工作排隊期間 prompt 被改掉，跑出來的東西
     跟當初送的不是同一件事。

5. **「doorbell 可以漏，命令不能丟」**（工程師的一句話結論，四位講法一致）。
   `inotify`／Unix socket 只是**提示**，權威永遠是目錄；漏了鈴用定期重掃補回。
   所以門鈴是最佳努力的加速器，不是正確性的一部分。

6. **`unknown` 狀態與「不自動重送」。** 連線逾時但 provider 可能已經收件的情形要進 `unknown/`；
   **沒有 idempotency key 就絕不自動重送**，否則雙重扣款、tool call 被做兩次。
   維運給了配套的人工介面：`aos llm inspect <id>`、`resolve <id> --retry|--fail`。
   這跟 aos 現有的 `.runi` 拒絕啟動是同一個哲學——**留現場給人**。

7. **「同時幾筆」與「每分鐘幾筆」是兩種額度，不能混成一種 token。**
   研究人員借 GNU make 的 jobserver：併發額做成 `slots/ready/<n>` 檔，claim 時搬到
   `slots/held/<lease>`；速率另用 `rate.json` 的 token bucket。維運的 `limits.json` 則把
   五種上限一起列出：concurrency、RPM、TPM、max-pending、daily-cost。

8. **公平性靠持久的 cursor 與輪轉。** 每個資料夾一次只取一件，`cursor.json` 記「輪到誰」，
   避免高產資料夾吃掉整條 endpoint；或者要求 claim 者必須拿**全域最小 ticket**。

9. **前一場沒解決的「公平性需不需要常駐者」，這輪被切開了。**
   架構師：**「公平性是耐久選擇；活性是可替換喚醒。」** daemon 只是喚醒器——沒有 daemon
   仍然可以保證公平（因為順序寫在磁碟上），但**不能保證延遲的工作會醒來**。
   研究人員的同一句話：**「檔案系統能保存排隊事實，卻不會自己產生公平與時間。」**

10. **可以馬上跑通的最小版本**（獨立開發者）：一支**前景** worker
    `aos llm work main --loop 200` ＋ `submit`／`collect` 兩支命令，**不必先有 daemon**。
    未完成時 `collect` 回**退出碼 75**（`EX_TEMPFAIL`），完成才 `temp→rename` 帶回。
    另加一個 `fake` profile 用 shell 假裝 endpoint，好讓整條路先跑通。

### 還在生長的想法

- **`aos llm submit`／`collect`／`work`／`inspect`／`resolve` 這組動詞**已經被四位不約而同地
  用了，但**分工還沒對齊**：submit 是「複製到 spool 並發布」還是「連投遞帶配號」？collect 是
  「搬回結果」還是「同時投遞續體」？
- **ticket 怎麼配號**：`submit.lock` 鎖著配序（工程師）、`cursor.json` 選票（架構師）、
  全域最小 ticket（研究人員）——三種都能定序，但耐久性與競爭成本不同。
- **429 的擺法**：`delayed/<not-before>-<id>.json`——把「什麼時候能再試」編進檔名，所以
  **不會堵住 queue 頭**，而且 `ls` 就看得出來誰在等。醒來時「只放一筆探路」（維運）。
- **每個模型要不要各自一條 lane**（獨立開發者標為不確定）：`limits` 是綁 endpoint 還是綁
  model？
- **收據（receipt）**：token 數、費用、嘗試次數、provider 的 request-id。維運要它，其他人
  沒提——但它是「成本看得見」的唯一辦法。

### 大家問出來的問題

1. **`<endpoint>` 的身分到底按什麼分**——provider？credential／key？帳號？model？
   quota project？**四位都問了這一題**，而且它決定了整個目錄結構的第一層。
2. **公平的單位是什麼**——request 數、token 數、金額、資料夾，還是 OS 使用者？
3. **誰喚醒無人值守的延遲工作**？（沒有 daemon 的話，`delayed/` 裡的東西靠誰醒）
4. **日額用完怎麼辦**——暫停、拒收，還是允許 instruction 明示降級到更便宜的 model？
5. **worker 沒開的時候**，submit 該安靜排隊還是當場警告？
6. 結果在中央 spool 要保留多久？如果那個資料夾被搬走或刪掉了呢？

### 明顯的坑

- **`EXDEV`**：跨檔案系統一次 `rename` 不可能同時承諾兩端，一定要有冪等的修復步驟。
- **供應商的現實不一致**：限額範圍、`Retry-After`、idempotency 支援、實際費用資料，各家都
  不一樣；「動態限額只靠 429 學」可能學不夠準。
- **網路斷線後是否已計費，通常不可判定**——這是 `unknown/` 存在的根本原因，不是實作偷懶。
- **兩個先例都不能直接搬**（研究人員自己點出）：maildir 只解決了原子投遞；make 的 jobserver
  成立的前提是**所有子行程繼承同一個 pipe**。跨無親緣關係的資料夾、又要嚴格公平與準時 retry
  的話，**最小正解可能真的是一支 per-user scheduler**。
- **不要搬的東西**（三位分別點名）：固定大小 ring、覆寫 slot、共享 head／tail 指標、
  只靠 PID 的 lease、多優先權佇列、semaphore。這些在硬體裡成立是因為有共享記憶體與中斷。
- **`fsync` 要到什麼程度**（工程師標為不確定）：要求斷電級耐久，協定會重很多；容許少量重算，
  協定可以輕很多。
