# 做 kernel 遇到的問題

← [proto7-1 spec](../spec.md) 第 9 節｜核心 spec：[core.md](../../proto7/spec/core.md)（條號 S-）

照核心 spec 做 `aos7-kernel`（`lib/aos7_kernel.py`、`lib/aos7_kernel_rules.py`）時碰到的問題。分級：〔要使用者決定〕＝方向、核心 spec 說不清或互相衝突；〔技術選型，先這樣〕；〔默認正常〕。

## K-1 kernel 寫 daemon ctl 超出 tick 給的資料夾〔要使用者決定〕

- 層：kernel ↔ daemon；S-10 vs S-18、S-21。
- 發生：S-10 說任務「理論上只碰 tick 給的資料夾」，kernel 的 birth.json `dirs` 只有自己的 node。但 S-18 要 kernel 下 daemon ctl，實作上就是寫 `$AOS7_ROOT/.aosd/ctl/`——在 node 之外，而且是 daemon 自己的地方。kernel 也要寫**成員 node** 底下任務的 `ctl.json`（`team/agents/amy/.aos/tasks/…`）。巢狀成員還算在自己 node 的子樹裡；但 kernel.json 若寫 `../other`，就跨到別的 node 去了。
- 繞過：不檢查，kernel 直接寫絕對路徑（沒有 FUSE，S-10 本來就只是宣告）。
- 待答：daemon ctl 目錄要不要算成「tick 一律給每個任務」的資料夾？成員在子樹外時算不算越權？（核心 spec 把權限列在「之後再說」，但 S-10 的限制和 S-18 的能力在這裡正面相撞。）

## K-2 「卡住 N 回合」數的是誰的回合〔技術選型，先這樣〕（隊長改級，歸入 problems.md 的 D-2）

- 層：kernel；S-08（回合數每條時間線各自數）、S-17（時間單位是 tick-tock）。
- 發生：kernel 被自己 node 的 tock 叫醒，但成員 node 是別的時間線，interval 可以不同。成員比 kernel 慢時，用 kernel 的回合數，成員根本還沒機會動就被判卡住；成員被 pause 時更是永遠「沒變」，會被誤 restart。
- 繞過：卡住改數**成員 node 的回合**（讀成員的 `round.json`，有前進才算一輪沒變）；成員被 pause（自己記的或 status.json 的 `paused`）時不數。預算的冷卻反過來用 **kernel 自己的回合**（被 pause 的 node 沒回合可數）。同一個 kernel 裡兩種時間並存。
- 待答：S-17「時間單位是 tick-tock」——kernel 管別的時間線上的任務時，時間單位是哪條時間線的？spec.md 第 9 節已改成上面的作法。

## K-3 kernel 怎麼看見別的 node 的任務〔技術選型，先這樣〕

- 層：kernel ↔ aos 時空；核心 spec「之後再說」那節明列「kernel 怎麼看見各 node 的任務」。
- 發生：沒有任何介面，kernel 只能直接去掃 `<成員>/.aos/tasks/*/`，自己判斷活不活（exit.json／pid.json＋`os.kill(pid,0)`／只有 birth.json）。這跟 tock 的判斷重複了一份（核心組的 `aos7_task.py`），兩邊判斷有一天會不一致。pid 判活還有 pid 重用的老問題。
- 繞過：kernel 自己寫一份最簡單的判斷（`aos7_kernel_rules.task_state`）；lost 也當「不活」，交給 tock 補 exit.json。
- 註：這份判斷要讀別人 node 的 `.aos/`，又回到 K-1 的範圍問題。

## K-4 pause 了的 node 收不到 ctl.json 的執行〔默認正常〕

- 層：kernel ↔ tick-tock；S-17（「在 tick-tock 時」做 kill、restart）、S-18。
- 發生：任務控制只在 tick／tock 時刻執行。kernel 同一輪對某 node 既判「卡住→restart」又判「超預算→pause」時，restart 的 ctl.json 會一直躺到 resume 之後才執行；被 pause 期間任務照跑（pause 不停任務），用量還可能繼續漲。
- 繞過：不處理。pause 期間用量照樣累計進基準，resume 時累計歸零（等於 pause 期間的用量不追究）。
- 註：如果要「立刻」kill，只能另開一條不經 tick-tock 的路，跟 S-17 衝突，先不做。

## K-5 kernel 不能 pause 自己的 node〔技術選型，先這樣〕

- 層：kernel ↔ daemon；S-18、S-22（控制成環不管）。
- 發生：kernel 被 pause 的 node 收不到 tock，而 kernel 靠 tock 才會跑規則、才會 resume——自己 pause 自己＝永遠停。S-22 說成環不管，但這個環是一步就鎖死。
- 繞過：預算規則遇到成員就是自己的 node 時跳過。其他 kernel／人互相 pause 成環照 S-22 不管。

## K-6 kernel 被 restart 後狀態在別的資料夾〔技術選型，先這樣〕

- 層：kernel ↔ 任務；S-01、S-11、spec.md 第 5 節（tid＝`<name>-r<回合>`）。
- 發生：restart 會起**新的任務資料夾**（新 tid），舊的 `$AOS7_TASK/kernel-state.json` 不在新資料夾。`keep` 任務掛掉被 tick 重起時連 `restart_of` 都沒有。
- 繞過：新資料夾裡沒有狀態時，先接 birth.json 的 `restart_of`，否則接同名任務裡 birth round 最大的那份。狀態裡記 `round`（已處理到第幾回合），啟動時跳過 ≤ 它的 tock。
- 連帶：一開始我用「啟動時 tock.json 已有的回合不重跑」，結果 tick 剛起任務、tock 在程序讀檔前就寫進來時，那次 tock 會被吞掉（整合測一開始就踩到）。改成看狀態檔的 `round`。也就是：**「任務還沒準備好時 tock 先到」是常態**，每個收 tock 的任務都要自己處理。

## K-7 「進度」「用量」是誰定義的協議〔技術選型，先這樣〕（隊長改級：S-17 已說資源隨意定義）

- 層：kernel ↔ agent；S-16、S-17（資源可以無限定義）。
- 發生：kernel 讀 `progress.json`、`usage.json`，agent 寫，格式只在 proto7-1 spec 第 9、10 節約定。agent 組的 progress 內容含 `round`，每收一次 tock 就變——所以「卡住」實際上等於「沒在處理 tock」（心跳），不是「事情沒進展」（agent 在 idle 空等也不算卡）。兩種意思差很多；kernel 看不出來是哪一種。
- 繞過：照現況，progress 內容不變＝卡住，意思由寫的一方決定。
- 待答：資源與進度的協議由誰定——kernel 定、任務照寫；還是任務各自宣告（例如 birth 或 tasks.json 寫「我的進度檔在哪、怎麼判斷」）？S-17 說資源無限定義，但沒說定義放在哪。

## K-8 用量要不要算已結束任務、第一次看到怎麼算〔默認正常〕

- 層：kernel；spec.md 第 9 節。
- 發生：usage.json 留在任務資料夾裡，任務結束後還在；任務資料夾被清掉時總和會變小。kernel 第一次看到某 node（或剛重起沒接到狀態）時，現有用量全算是「新增」會立刻誤 pause。
- 繞過：加總含已結束的任務；增量小於 0 當 0；第一次看到用現值當基準、不算舊帳。

## K-9 restart 一個 keep 任務可能起兩份〔默認正常，給 tick 組看〕

- 層：tick；spec.md 第 4、6 節。
- 發生：kernel 對 `keep` 任務（例如 agent）下 restart → tick 執行時 kill 掉並寫 `spawn/restart-<tid>.json`，下一個 tick 先起 spawn、再看 tasks.json 的 keep。spec 寫「keep 的檢查會算進剛起的」所以應該不重複；但如果 kill 和 spawn 不在同一個 tick 裡（tock 執行 ctl、下個 tick 起 spawn），中間沒有活的同名任務。目前流程 spawn 在 keep 前所以沒事；記下來，順序一換就會起兩份。
- 繞過：kernel 不管，靠 tick 的順序。

## K-10 決定與執行之間沒有回饋〔默認正常〕

- 層：kernel ↔ daemon；S-18、S-01。
- 發生：kernel 寫完 daemon ctl 就當作 pause 了，不看 `ctl-done/` 的 `result.ok`。daemon 沒在跑或讀不懂時，kernel 自己的狀態（「已 pause、某回合 resume」）跟實際不符。任務 ctl.json 也一樣只寫不查。
- 繞過：不查，下一輪照自己的狀態走；resume 一樣照時寫。對同一任務只下一次指令，目標已有 ctl.json（別人先下）就不蓋。
