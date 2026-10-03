# 探針 holds：多個控制者 pause 同一條線

← [probes](../README.md)｜出處：[Linux 報告 §10.4](../../notes/research/2026-10-03-linux-kernel-borrow.md)（D-12、D-13）

**是什麼**：預算 kernel、凍結 kernel、人、不走協定的舊腳本、維運 CLI，五方都會 pause／resume 同一條線（line，interval 100 ms，工作每個 tock 用量 +10）。用現有的單一 paused 狀態湊，有兩種湊法，在同一個 daemon 裡並排跑同一份劇本。時鐘是各自 ctrl node 的回合。約 6 秒，不打 LLM。

- **naive**：每個控制者直接寫 daemon 控制檔 pause／resume。
- **holds**：預算、凍結、人只寫或刪自己的 hold 檔 `ctrl/holds/<owner>.json`。另有一個常駐的 arbiter 每 20 ms 對帳：有任何 hold 就 pause，沒有就 resume。它**只解自己停的**：翻 daemon `log.jsonl` 的尾端，看最後一筆 pause 是誰下的；別人下的 pause 當成一個外部 hold，不去解。

劇本（ctrl 的回合）：

| 回合 | 誰 | 做什麼 |
|---|---|---|
| 10～22 | 人 | 要停 |
| 15～35 | 凍結 kernel | 要停 |
| 自己判斷 | 預算 kernel | 用量比基準多 60 就停 5 回合 |
| 28 | 舊腳本 | 直接寫 resume |
| 31 | 探針 | 對 line 的工作下 task kill |
| 40～45 | 維運 CLI | 直接 pause／resume |

**量的是**：每個控制者「要停」的期間，line 還開了幾回合（扣掉 0.35 秒的生效延遲），以及是誰的 resume 把它放掉的。

## 結果（5 個 check 全綠，連跑 3 次）

- **naive：被放掉的回合合計 14～17**。
  - 凍結窗口被放掉約 10 回合：人 22 回合 resume 時，凍結還沒結束。
  - 預算 kernel 冷卻到期的 resume 一次放掉 9 回合，是別人還要停的回合。
  - 維運 CLI 的 pause 也會被別人的 resume 解掉。
- **holds：被放掉的回合合計 1**，只有 old-script 的那一次。
  - arbiter 的 resume 都是在沒有任何 hold 時下的。
  - old-script 的 resume 被 arbiter 在下一次對帳就補 pause，記錄是 `fix_external_resume`。
  - 維運 CLI 直接下的 pause，arbiter 認出不是自己下的，當外部 hold、沒去解，等 CLI 自己 resume。
  - 寫給 daemon 的控制檔比 naive 少，約 9 對 15。
- **pause 中的 task kill（D-13）**：
  - holds 等了約 0.45 秒，等凍結結束才執行。
  - naive 只等 0.05 秒，因為線早就被別人放開了。
  - 「停著也要收掉一個任務」只能放開整條線。
- **arbiter 認 pause 是誰下的只能翻 log.jsonl**。4 條線時 log 每秒約 63 行，尾端 400 行只涵蓋約 6 秒。外部 pause 比這久，arbiter 就會把它當成自己的，去 resume 它。保留政策輪替 log（astra-7 H-08）也一樣會讓它看不到。

## 逼出的 daemon／tick 需求

- **N-81（對應 D-12，應該；多控制者時必要）pause 要能帶 owner，各解各的**。
  - daemon 只有一個 paused 位元：誰的 resume 都放掉所有人的 pause（naive 14～17 回合）。
  - 合作式的 hold 檔加 arbiter 做得到，但要另外常駐一個 20 ms 輪詢的任務。這個 arbiter 自己不能被 pause。不走協定的人照樣能放掉一兩回合。
  - 判斷「這個 pause 是誰下的」要翻 log 尾端，log 被輪替或量大時就判錯。

  最小的補法：paused.json 改成 `{node: [owner...]}`，resume 只拿掉自己的 owner，`status` 列出 holds。
- **N-82（對應 D-13，可以）pause 中要能做任務控制，不必放開整條線**。現在 task ctl 只在 tick／tock 執行，pause 時要等所有 hold 放開。合作式的變通是 `resume rounds 1`，但那一回合會照樣起 spawn／keep、發 tock，不是「只收尾」的維護回合。
