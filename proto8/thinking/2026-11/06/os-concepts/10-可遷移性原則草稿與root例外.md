← [入口](README.md)｜涵蓋：使用者 11-06 確認「上位原則＝可遷移性、daemon 當介面是手段」與「root daemon 是矛盾集中點、使用者保底可拉扯」——原則草稿（寫哪層、怎麼寫，不改條文）、root 可放寬清單與邊界、搬家重建 root 的食譜、方向題 C（no-pid 已落地要不要放寬）｜上一份 [09-Linux原生機制與可遷移性](09-Linux原生機制與可遷移性.md)

# 可遷移性原則草稿與 root 例外

## 使用者原文（11-06，逐字，依先後）

> 先前之所以說這條，是因為那時候還沒凝聚出"可遷移性"這個概念，所以定死這條。但後來發現目標是可遷移性，所以其實就...（話沒講完）

（頂層解讀：真正的上位原則是**可遷移性**；「Linux 原生機制都以 daemon 為界面」是達成它的手段，11-05 定死是因為當時還沒有可遷移性這個概念，現在降成建議；判一項原生機制能不能用、要不要經 daemon，看「會不會破壞可遷移性」而不是「有沒有經過 daemon」。使用者：「是。」）

> 然後root daemon本身，因為他是最底層介面，所以他這邊是可遷移性在實現過程中的矛盾集中點，同時也因為契約中提到使用者必須關照root daemon，所以在使用者作為保底的情況下，實作上可以稍微拉扯一下。

## 定下的

1. **上位原則＝可遷移性**：一棵樹（root daemon 以下的定義＋stack＝一份 image）凍住後能搬到另一台 Linux 接著跑。daemon 當介面是**手段、建議**，不是原則。
2. **root daemon 以下**（子 daemon、proc）盡量守住：設定在樹裡、到新機器由那台的 daemon 重套。
3. **root daemon 是樹跟這台 Linux 的接觸面**：搬不走的東西刻意集中在它身上（systemd、s6、帳號、cgroup 根、boot_id、實際路徑）——矛盾集中點，不是缺陷。契約（no-pid 05）：根由使用者顧、aos 不做根的根；所以 root 可以綁這台、可以直接用原生機制、可以不完全可遷移；代價由使用者承擔，或由「搬家時重建 root」承擔。

## 原則草稿（只草稿、條號由 lift-to-norms 隊定；不改條文）

**概念層（CONCEPTS 01-設計理念，接在 C-75 後，暫稱 C-76）**：
> **C-76 可遷移性**（11-05 portable-flow、11-06 daemon-board 04、os-concepts 09／10）：一棵樹＝一份 image（定義＋root daemon 以下所有 stack），凍住（整樹 sleep）後能整個搬到另一台 Linux 再接著跑；暫停的目的就是遷移。Linux 原生特性（權限、setrlimit、cgroup、排程、命名空間…）可以用；**建議**把設定寫在樹裡、由 daemon 在起子行程時套用（daemon＝Linux 與 aos 之間的橋，C-04），Linux 行程身上的執行期狀態不是真相；直接用的要寫明搬不走什麼。**root 例外**：root daemon 是樹跟這台機器的接觸面，搬不走的東西集中在它身上，由使用者保底（no-pid 05 契約），實作上可以綁這台。

**規範層（NORMS 10-基礎設施-定義與工作區，接在 N-64 後，暫稱 N-65）**——把散在各處的已裁事項收成一條檢查單：
1. image 裡的位址一律相對 root daemon 的 stack（N-28 11-05；已實作）。
2. 期限用 tick、跨樹用毫秒（N-04 兩鐘規則、daemon-board 題 1；T 線）。
3. 原生機制：表列設定（`limits` 等）→ daemon 套；不經 daemon 直接用的程式在自己 README 寫「搬不走什麼」（09 偏離表）。
4. 行程狀態（pid、`started_at_ticks`、`boot_id`、鎖）不是真相：只給上一層 daemon 判活（N-17），搬過去對不上＝全當死＝正確。
5. **root 例外**：root 的這台綁定（systemd／s6、`prlimit`／scope、帳號、sudo 規則、人 export 的絕對變數、ctl 信箱擁有者）不進 image；搬家＝照食譜重建 root（下節）。
6. 檢驛法：睡著 → `cp -a`／git → 另一台 `aos-exec` 醒來接著跑（P8 試驗場就是這條的測試）。

## root daemon 可以放寬的（直接用、綁這台）

| 可直接用 | 為什麼可以 | 搬家時 |
|---|---|---|
| systemd unit／s6-supervise 顧 root | 根的根不在 aos 裡（契約） | 另一台重寫 unit |
| `prlimit`／`ulimit -H`／`systemd-run --scope`（cgroup 總額）包 root | 「daemon 自己被限＝起它的人包」（docs/09） | 重包 |
| root 跑在哪個 Linux 帳號、root 小程式切帳號、sudo 規則 | 「一個 agent 一個帳號」的根在這裡（no-pid 05 遠期） | 重建帳號、規則 |
| 人 export 的絕對變數（`AOS_LLM_KERNEL`、`AOS_KERNEL`、`AOS_DAEMON`）、`env.sh` | 已裁「跨樹算外接、搬後重設」（daemon-board 04 題 1） | 重 export |
| ctl 信箱的擁有者／mode（「唯一」第 2 級） | 使用者裁「沒設也行、自擔」 | 重設 chown／chmod |
| flock `DaemonRunning`、`boot_id`、/proc 判活 | 鎖與 boot_id 本來就是「此刻這台」 | 不搬、正好 |
| root 的 `.env` 寫這台的值 | 跳線是板子的 | **不建議**：`.env` 在定義裡會跟樹走；這台的值用 export 或指示詞 |

## 放寬的邊界（root 哪些仍要可搬）

- **可搬**：root 的 `daemon.json`（名單、`tick`、`limits` 預設）、root 的 stack（`procs_state.json`、ctl 信箱、`_tick` 時鐘檔、子 daemon 與 proc 的小格）——就是 image。
- **不搬**（上表右欄）：行程、鎖、pid／boot_id、unit、scope、帳號、sudo、export、擁有者。這些已在 portable-flow 02「不屬於 image」與 daemon-board 04 #11／#16～#19 列過，本節只是把它們歸到「root 的這台綁定」一個名字下。
- **子 daemon 不放寬**：它在樹裡，`limits.user` 等「這台的」仍走表→另一台沒有＝`LimitBad` 留 `stopped`（寫什麼做什麼）；要綁這台的東西往上推到 root。
- **重建 root 食譜（P8，四步）**：① 建帳號／權限（或略過、自擔）→ ② 包 root（systemd／scope／prlimit，或略過）→ ③ export 這台的變數（`env.sh` 從自己位置算）→ ④ `aos-exec --stack <image> <定義>`：adopt 接回整棵樹（`boot_id` 不同＝全當死、照起照醒）。前兩步可省＝「普通使用者行程、壞了就壞了」。

## 方向題 C（給頂層問；兩邊後果，本夾不判）

**no-pid 已經落地的那批（N-17「對 /proc 判活只剩 daemon」、其他人不碰 pid、ctl 改寄信、aos-lock 改檔案鎖 T2）要不要跟著「降成建議」放寬？**

- **不放寬**（頂層傾向）：後果——沙箱只要一個信箱就通（no-pid 04）、判官能長成「誰能對誰做什麼」的權限閘門（遠期）、搬家後 pid 本來就無意義（用可遷移性判準看，no-pid 每一條都通過：pid 搬不走）、P1～P5b 已實作不重做；代價——多一趟信（ping 3 秒）、daemon 睡著時沒人答（寄信不回＝呼叫失敗，已裁）。
- **放寬**：允許 daemon 以外讀 /proc 判活、ctl 直接寫檔不寄信、aos-lock 名牌留 pid；後果——少一趟信、工具脫離 daemon 也能判活；代價——沙箱 pid namespace 誤判回來、跨機 pid 無意義、判官管不到直接寫檔的人、T2 與 P1～P5b 部分回退、兩種語氣（pid 硬、其他軟）要讀的人自己分。
- 一句觀察（供判）：11-05 那條定死時雖沒有「可遷移性」這個詞，但它擋的正是「以行程狀態為真相」——跟今天的上位原則同向；放寬的理由只剩便利，沒有可遷移性上的理由。
