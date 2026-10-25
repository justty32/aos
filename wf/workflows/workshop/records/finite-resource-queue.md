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

1. **佇列在資料夾之外，落在使用者層級**：`$XDG_STATE_HOME/aos/llm/<endpoint>/` 或
   `~/.local/state/aos/llm/<endpoint>/`。endpoint 是跨資料夾共享的，佇列放在某一個 `.aos/` 裡，
   第二個資料夾就看不到。
   > ⚠ **這直接撞上 `roadmap` 第六節「不做全域 LLM daemon 與跨資料夾排程」。** 是從「endpoint 在哪」
   > 推出來的，不是刻意挑戰那條。

2. **目錄狀態機（maildir 式）**：工作在目錄之間 `rename` 表示狀態：`ready`／`running`／`done`／
   `delayed`（或 `retry`／`delay`）／`unknown`／`bad`。`rename` 是發布，目錄名就是狀態，`ls` 就看得到。

3. **fence 在 world 裡，工作在 spool 裡。** 資料夾只留 `.aos/k/llm/<id>.json` 當 fence，續體 poll 它；
   工作內容在中央 spool。排程者不變成資料夾的第二個 writer，所有權保持單一。

4. **staging 不能省**：跨檔案系統 `rename` 會 `EXDEV`，投遞到中央 spool 必須是明確的複製步驟（對應
   硬體的 staging buffer／DMA）；輸入要**快照**，否則排隊期間 prompt 被改，跑出來的跟送的不是同一件事。

5. **「doorbell 可以漏，命令不能丟」。** `inotify`／Unix socket 只是提示，權威永遠是目錄；漏了鈴用
   定期重掃補回。門鈴是最佳努力的加速器，不是正確性的一部分。

6. **`unknown` 狀態與「不自動重送」。** 連線逾時但 provider 可能已收件 → 進 `unknown/`；**沒有
   idempotency key 就絕不自動重送**（否則雙重扣款、tool call 做兩次）。人工介面：`aos llm inspect <id>`、
   `resolve <id> --retry|--fail`。跟 `.runi` 拒絕啟動同一個哲學——留現場給人。

7. **「同時幾筆」與「每分鐘幾筆」是兩種額度。** 併發額學 GNU make jobserver：`slots/ready/<n>` 檔，
   claim 時搬到 `slots/held/<lease>`；速率另用 `rate.json` 的 token bucket。`limits.json` 列五種上限：
   concurrency、RPM、TPM、max-pending、daily-cost。

8. **公平性靠持久的 cursor 與輪轉。** 每個資料夾一次只取一件，`cursor.json` 記「輪到誰」；或要求 claim
   者必須拿全域最小 ticket。

9. **公平性與活性分開**：「公平性是耐久選擇；活性是可替換喚醒。」沒有 daemon 仍可保證公平（順序寫在
   磁碟上），但不能保證延遲的工作會醒來。

10. **可以馬上跑通的最小版本**：一支前景 worker `aos llm work main --loop 200` ＋ `submit`／`collect`，
    不必先有 daemon。未完成時 `collect` 回退出碼 75（`EX_TEMPFAIL`），完成才 `temp→rename` 帶回。另加
    一個 `fake` profile 用 shell 假裝 endpoint，讓整條路先跑通。

### 還在生長的想法

- **`aos llm submit`／`collect`／`work`／`inspect`／`resolve` 動詞的分工未對齊**：submit 是「複製到 spool
  並發布」還是「連投遞帶配號」？collect 是「搬回結果」還是「同時投遞續體」？
- **ticket 配號**：`submit.lock` 鎖著配序、`cursor.json` 選票、全域最小 ticket——都能定序，耐久性與競爭成本不同。
- **429 的擺法**：`delayed/<not-before>-<id>.json`，「什麼時候能再試」編進檔名，不堵 queue 頭，`ls` 看得出
  誰在等。醒來時只放一筆探路。
- **`limits` 綁 endpoint 還是綁 model**（每個模型要不要各自一條 lane）未定。
- **收據（receipt）**：token 數、費用、嘗試次數、provider 的 request-id——成本看得見的唯一辦法。

### 大家問出來的問題

1. **`<endpoint>` 的身分按什麼分**——provider？credential／key？帳號？model？quota project？它決定目錄結構的第一層。
2. 公平的單位是什麼——request 數、token 數、金額、資料夾，還是 OS 使用者？
3. 沒有 daemon 的話，誰喚醒 `delayed/` 裡無人值守的延遲工作？
4. 日額用完怎麼辦——暫停、拒收，還是允許 instruction 明示降級到更便宜的 model？
5. worker 沒開的時候，submit 該安靜排隊還是當場警告？
6. 結果在中央 spool 要保留多久？那個資料夾被搬走或刪掉了呢？

### 明顯的坑

- **`EXDEV`**：跨檔案系統一次 `rename` 不能同時承諾兩端，一定要有冪等的修復步驟。
- **供應商的現實不一致**：限額範圍、`Retry-After`、idempotency 支援、實際費用資料各家不同；只靠 429 學動態限額可能不準。
- **網路斷線後是否已計費通常不可判定**——這是 `unknown/` 存在的根本原因。
- **兩個先例都不能直接搬**：maildir 只解決原子投遞；make jobserver 的前提是所有子行程繼承同一個 pipe。
  跨無親緣的資料夾、又要嚴格公平與準時 retry，最小正解可能是一支 per-user scheduler。
- **不要搬的東西**：固定大小 ring、覆寫 slot、共享 head／tail 指標、只靠 PID 的 lease、多優先權佇列、
  semaphore（硬體裡成立是因為有共享記憶體與中斷）。
- **`fsync` 要到什麼程度**未定：要求斷電級耐久協定會重很多；容許少量重算可以輕很多。
