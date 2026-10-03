# 探針 gang：三個合作任務要一起起、一起取消

← [probes](../README.md)｜出處：[其他 OS 報告 §7.3](../../notes/research/2026-10-03-other-os-borrow.md)（coscheduling／gang，E-04）

**是什麼**：一組成員（a、b、judge；tickkill 是 20 個）用一個 `spawn {"batch": [...]}` 起。成員共用一個成組資料夾 `cohorts/<id>`，經掛載點 `mnt/cohort` 進去。每個成員每收到一個 tock 做一步「付費工作」（work），記在 `gang.jsonl`。約 6 秒，不打 LLM。

兩種做法，每個情境各自的 node、同時跑：

- **naive**：batch 起來就做。
- **proto**（合作式 prepare／commit，探針當協調者）：
  1. 成員用 `O_EXCL` 認領 `claims/<角色>`。已經有人佔了，就是重複起的，直接退出（dup-exit）。
  2. 寫 `ready/<角色>`，等 `commit.json`；看到 `abort.json` 就走。
  3. 協調者在全員 ready 時 commit；1.2 秒還沒到齊就 abort；commit 之後有成員結束，也 abort（整組取消）。

| 情境 | 做法 |
|---|---|
| bad | batch 裡 judge 的 argv 壞掉 |
| keepblock | node 上已有一個活的 keep「judge」，batch 的 judge 也是 keep |
| tickkill | 20 個成員；tick 起到第 8 個時，探針用 PID SIGKILL 那個 tick |
| crash | b 做兩步後在兩個 tock 之間 exit 1；naive 由探針當 kernel，對其餘成員寫 task kill |
| cross | a 在 x1（200 ms），b、judge 在 x2（450 ms），兩邊同時寫 spawn |

**量的是**：
- 成組不完整時做的 work（partial）；
- 同一角色兩份同時做的 work（dup）；
- 同組起動的時間差。

## 結果（8 個 check 全綠，連跑 4 次，數字穩定）

| 情境 | naive | proto |
|---|---|---|
| bad | 壞項只被跳過（`tasks_error`：argv 要是非空字串陣列），a、b 照起，36 步全是 partial | judge 沒到 → 逾時 abort，0 步 |
| keepblock | judge 被擋（`tasks_error`：judge 已有活的），a、b 照起，36 步全是 partial | 0 步 |
| tickkill | spawn 檔還在（起完才刪），下一個 tick 整批再起 → 7 個角色變兩份，140～154 步 dup，起動差約 330 ms | 7 個重複的認領失敗、自己退出，dup 0 |
| crash | 探針寫 kill 後 150～190 ms（下一個 tick）其餘才結束，期間 2 步 partial | abort 後 20 ms 內兩個都走，partial 0 |
| cross | 起動差約 300 ms（兩個 node 的回合不同步），2 步 partial | 所有 work 都在 commit 之後，partial 0 |

- proto 五個情境的 partial 都是 0。合作式的 prepare／commit 在任務層做得到「不放行半組」。代價：
  - 要一個協調者（這裡是探針，實際上是 kernel）；
  - 成員自己要守 claims／ready／commit 的約定；
  - 被跳過的那一份要等 1.2 秒逾時才知道。
- **被 tick 殺掉的那一批沒有留下永遠 born 的資料夾**：已寫 birth 的都起了 runner。
- 成員自己看不到「同一批還有誰被跳過」。原因寫在 round.json 與回合總結的 `tasks_error`，是給 node 看的字串，沒有對應到哪一批、哪一項。

## 逼出的 daemon／tick 需求

- **N-85（對應 E-04，可以；宣稱成組原子准入時必要）spawn batch 不是全有全無**。壞項，或被 keep／max_live 擋下的項，只跳過那一項，其餘照起。成員不知道少了誰，batch 沒有「整批起或整批不起」的選項（`atomic: true`：任一項驗不過就整批不起、spawn 照刪、回條說原因），也沒有逐項的回條。合作式 prepare／commit 補得起來，所以先不必做。
- **N-86（對應 D-02、N-19，應該）spawn 項目要能去重**。spawn「起完才刪」是至少一次（I-02）。tick 起到一半被殺，下一個 tick 整批再起，已經起了的角色變兩份；這裡 7/20 個角色各做了兩份付費工作。合作式的 `O_EXCL` 認領擋得住，但每個任務都要自己做。

  最小的補法：tick 起每一項後，在 spawn 檔旁記下「這個檔第幾項已起」（或在 birth.json 記 `spawn` 加項次）。重做時跳過已起的項，算是 N-19「統一請求 id」的一小步。
- **沒有逼出新需求的**：
  - 「一起取消」逐個寫 task ctl.json，下一個 tick 就收，150～190 ms，夠用。
  - 跨 node 的起動差是回合本來就不同步（S-08），prepare／commit 已經處理。
