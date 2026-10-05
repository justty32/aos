# 子 daemon 包（subd）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)（第 2.7 節：守門檔）

**讓一個 node 的任務擁有一個子空間根，跑自己的 daemon**（S-21 路一）：子 daemon 是那個任務的子程序，父 node kill 它就帶走整棵；它的 stop 要擁有者允許。核心不知道「從屬」，只認通用守門檔 `.aosd/stop-guard.json`。

| 項目 | 內容 |
|---|---|
| 接法 | B 包裝程式：tasks.json 項目的 argv 寫成 `aos7-subd <subroot> [--allow-stop] -- <argv...>` |
| 預設 | 關（用到才寫） |
| 依賴 | 核心的守門檔（spec 2.7）、「路上有別的 daemon 根就不收那個 node」（spec 第 1 節）、核心程序工具 `lib/aos7_proc.py`（身分掃描、收群組；重開前回收用） |
| 程式 | `aos7-subd`（可執行 Python） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/subd/tests`） |

## 契約卡

- **職責**：讓一個 node 的任務擁有子空間根、跑自己的 daemon：起之前檢查位置與認領，**收掉前代留下的程序**，寫守門檔與 `owner.json`，被允許的 stop 之後寫 `stopped.json` 擋下一次重起（下面規則節）。
- **前置條件**：以任務身分起（`AOS7_ROOT`、`AOS7_NODE_ID`、`AOS7_TID`）；argv 經這個包裝程式起子 daemon，不繞過；子根只由這個包認領；父的 `nodes.json` 只有父 daemon 寫。
- **保證**：
  - 位置不合、子根已被認領、有 `stopped.json`、父 nodes.json 讀不到＝印原因、退出碼 1、什麼都不起。
  - 守門檔照 `--allow-stop` 寫，核心照它擋控制檔 stop（核心 spec §2.7）；SIGTERM 不看守門檔。
  - 父 kill 這個任務＝整個群組收到 SIGTERM，子 daemon 照 stop＋kill 收自己的任務（核心 §2.3、§6）。父 kill 回 `ok:true` 只表示父那個任務收掉了（核心 §6），**不代表子空間已空**。
  - **重開前回收**：下一次起 argv 之前，包自己收子根裡前代的 launcher、runner、任務（含 paused node），一次掃描確定沒有才起新代；所以新代子 daemon 起來時，前代的任務已經不在。查不清、收不掉、記錄壞掉＝不起（退出碼 1），下一次接著收。被允許的 stop 之後不回收（見規則）。
  - 被允許的外部 stop 留 `stopped.json`，父 node 的 keep 項之後再起就被擋。「被允許的 stop」**以核心停止事實（子根 status＋stop 回條）判定**，起點與收尾同一個判定；提交（stopped.json、生命週期）中途被殺，下一次起包時補完、不回收（A6-01）。stop 生效了但回條沒寫成（核心 §2.3 的處理例外）＝不知道，**不轉成可回收**，照被允許的 stop 擋著（A8-09）；刪 stopped.json 重接、新代 daemon 起來之前被打斷，下一次仍不回收（MC-01）。
- **明確不管**：繞過包裝或人手起的子 daemon（界線）；擁有者檔被手改；惡意任務（合作式：改掉環境身分、換 uid 的程序掃不到）；父 kill 之後、下一次起包之前那段時間裡前代任務還在跑（父不再起它就一直不收，見界線）。

## 用法

```json
{"name": "sub", "mode": "keep",
 "argv": ["aos7-subd", "team/sub", "--", "sh", "-c",
          "aos7-ctl daemon \"$AOS7_SUBROOT\" register n1 && exec aos7-daemon \"$AOS7_SUBROOT\""]}
```

`aos7-subd` 不在任務的 `PATH` 上，argv 寫它的路徑（`proto7-2/modules/subd/aos7-subd`，或 `python3 <路徑>`）。子 daemon 起來時 nodes.json 是空的：先往 `$AOS7_SUBROOT/.aosd/ctl/` 寫 `register`（子 daemon 還沒起也行，起來就處理）。

## 規則

- `<subroot>` 是空間路徑（相對空間根）。包裝程式以任務身分起（要有 `AOS7_ROOT`、`AOS7_NODE_ID`、`AOS7_TID`），起之前檢查，**不合就印原因（進 out.log）、退出碼 1、什麼都不起**：
  - 子根要在自己的 node 底下、不能是 node 本身、不能包住父 daemon 已登記的 node（讀 `$AOS7_ROOT/.aosd/nodes.json`；讀不到或壞掉＝不知道＝不起）；
  - `<subroot>/.aosd/stopped.json` 存在（被允許的 stop 停過）→ 不起，刪掉它下一次才起；
  - 已有別的 `aos7-subd` 認領這個子根（它全程拿著 `<subroot>/.aosd/subd.lock`），或子根的 `daemon.lock` 有人拿著（例如人手起的）→ 不起。
  - 前代沒收乾淨、或不知道收乾淨沒有（見「重開前回收」）→ 不起。
- 通過後寫：
  - `<subroot>/.aosd/stop-guard.json`＝`{"allow": 有沒有 --allow-stop, "note": "這個 daemon 屬於 node X（任務 Y）…"}`——核心照它擋控制檔 `stop`；
  - `<subroot>/.aosd/owner.json`＝`{"owner": {"node", "tid", "allow_stop"}, "daemon": {"pid", "since"}}`——給人看。
- 設 `AOS7_SUBROOT`（子根絕對路徑）後把 argv 起成子程序（同一個程序群組），等它結束；退出碼照它（被訊號殺＝128＋訊號號）。
- argv 結束後判定是不是**被允許的外部 stop**（`allowed_stop`，以核心停止事實判定）：子根 `status.json` 是 `stopped: true`，**且** `ctl-done/` 有 `op: stop`、`result.ok: true`、`result.at` 不早於本代 `running` 記錄的 `since` 的回條。控制檔 stop 一定留回條，SIGTERM（父 kill、或有人直接 TERM 子 daemon）不留（核心 2.3），這就是兩者的區別；舊於 `since` 的回條是上一代的 stop，不算。成立就提交：先寫 `stopped.json`＝`{"by", "why", "at"}`（那份回條），再寫生命週期 `stopped`。父 node 的 keep 項下一回合再起包裝程式時就被擋下（退出碼 1）。（時間比較用牆鐘字串：**前置是主機牆鐘不倒退**；倒退超過一代時，本代成功 stop 的回條可能早於 `since` 而被當成沒停，重開會回收原任務——astra-6 實測，照原則 9 不另防。）
  - **回條沒寫成（A8-09）**：核心處理控制檔丟例外時（例如 `ctl-done/` 寫不進去）效果可能已生效、請求被刪、只記 status 的 `last_ctl_error`（核心 §2.3）——那件可能就是 stop。所以 status `stopped: true`、沒有合格回條、但有 `last_ctl_error.at ≥ since`，且這代是 `--allow-stop`（記錄的 `allow_stop` 不是 `false`）＝不知道，**照被允許的 stop 提交**：`stopped.json` 多 `"unconfirmed": true`，`why` 寫明；人確認後刪掉它就照核心接回。不解析錯誤文字。代價：同一代有別件控制檔出錯、又被父 kill 而子 daemon 在寬限內收完（status 寫成 stopped）時，也會被擋一次——那時任務已被子 daemon 收掉，擋下不毀東西，刪掉 stopped.json 就再起。
- 父 kill 這個任務：SIGTERM 打到整個群組，子 daemon 照 SIGTERM＝stop＋kill 收自己的任務（核心 2.3），不看守門檔。父 kill 的 1 秒寬限（核心 §6）內收不完的，留給下一次起包時的回收。

## 重開前回收（A5-01）

核心 daemon 重開時，任務或 runner 還活著就當活接回（核心 §5.4），不會收前代；這是一般 daemon 的契約，包不改它。子 daemon 被父 kill 時常收不完（逐槽各等 1 秒，父 1 秒後就 SIGKILL），所以由包在起新代之前自己收。

- **生命週期記錄** `<subroot>/.aosd/subd-life.json`（包自有，核心不讀）＝`{"state", "subroot", "owner": {"node", "tid", "run", "pid"}, …}`，`state`：
  - `running`：起 argv **之前**原子寫好（不靠 SIGTERM handler），帶 `since`、`allow_stop`；之後不管 argv 怎麼結束（父 kill、子 daemon 掛了）都留著＝「前代可能沒收乾淨」。從 `stopped` 跳過回收而寫的另帶 `kept`（接回中，見第 2 步）。
  - `recovering`：正在收前代（`prev` 是最初那份前代記錄、`attempt` 是第幾次收）；收到一半被殺就留著，下一次接著收，`prev` 沿用、不一層包一層（R8-18）。
  - `stopped`：被允許的外部 stop 結束（緊接 `stopped.json` 之後寫）。只是快取：`running` 不代表沒被允許 stop 過（見第 2 步）。
- **步驟**（拿到 `subd.lock` 之後，它全程拿著）：
  1. 拿子根的 `daemon.lock`（拿不到＝有 daemon 在跑，不起），回收期間一直拿著：其他 daemon 起不來，舊 daemon 也確定不在。
  2. 讀記錄：讀不到或內容不合＝不知道，不起（確認子根裡沒有前代程序後修好或刪掉它）。`running` → 先問 `allowed_stop`（同收尾那個判定，起點用記錄的 `since`）：成立＝前代被允許的 stop 的提交被中斷（status 已 stopped 還沒寫 stopped.json、stopped.json 寫了生命週期還沒寫、暫存檔沒 rename），**補完提交**（沒有才寫 `stopped.json`、生命週期 `stopped`）、印「被允許的 stop 停過」、退出碼 1、不回收；status／回條讀不到＝不知道，不收、不起（退出碼 1）。`stopped` → 跳過回收。`running` 帶 `kept` 且本代還沒有 daemon 起來過（子根 `gen.json` 的 `at` 早於 `since`；讀不到＝不知道，不收、不起）→ 保留的任務還沒被接回，同 `stopped` 跳過回收，新 `running` 照帶 `kept`（MC-01）；本代 daemon 起來過，任務已照核心接回，之後照一般前代處理。其他（`running` 且判定不成立、`recovering`、**沒有記錄**）→ 回收：沒有記錄不當全新空間（例如舊版包起過、記錄被刪），一樣先掃。
     - `stopped.json` 還在而被擋時（規則節起之前的檢查），拿得到兩把鎖就順手做同一個補完（只寫生命週期），所以人刪掉 `stopped.json` 再起時直接接回；若人在任何一次被擋之前就刪掉，第一次再起會補寫 `stopped.json` 擋一次，再刪一次就接回（任務一直不收）。
  3. 回收：寫 `recovering`，照環境身分掃子根（核心 §5.2 的身分，經核心 `aos7_proc`）：`AOS7_NODE` 是子根或在它底下、有 `AOS7_TID` 的是任務或 runner（巢狀子空間也在內；paused node 照樣掃到，不 resume、不改 pause）；`AOS7_SUBROOT` 正好是這個子根的是 launcher（前代子 daemon、tick、tock）。不含自己與祖先；sibling 子根路徑不同（比到 `/`），不算。每輪先打 launcher（TERM 後立刻 KILL：tick 收到 TERM 會做完動作、可能再起 runner），再照核心 kill 的寬限收任務的群組（TERM、等 1 秒、KILL），等 runner 寫完 `exit.json` 自己退出（最多 0.5 秒），還在的再收；然後重掃。**一次掃描確定沒有才算乾淨**；最多 5 輪、掃描讀不完整＝不起，記錄留著。
  4. 乾淨了：寫本代 `running` → 放掉 `daemon.lock` → 寫守門檔、起 argv。
- 不寫核心的 birth／exit／round、不改 pause；被收掉的槽由新代 daemon 照核心判定（runner 寫了 `exit.json` 就是結束，沒寫就照 §5.4 判 lost），keep 照常重起。
- **被允許的 stop 不回收**：那是擁有者要的結束；不帶 `--kill` 的 stop 留下的任務，刪掉 `stopped.json` 再起時照核心接回（跟一般 daemon 重開一樣）。接回的新代 daemon 起來之前包被殺（例如 argv 前），再起照樣不回收（`kept`，MC-01）。
- 起 argv 前就收到 SIGTERM（父 kill）＝不起、退出，`running` 記錄留著。

## 界線（方案 6.1 第 2 點）

- **繞過包裝**（argv 直接寫 `aos7-daemon <子根>`）：沒有守門檔、沒有 stopped.json、也沒有重複認領的擋法；重複認領時第二個 daemon 拿不到 daemon.lock、退出碼 1，keep 每回合重試，總結裡會一直看到失敗。stop 權限只靠守門檔，守門檔由這個包寫。
- **人手直接起子 daemon**：守門檔與 owner.json 照舊留著（核心不碰），stopped.json 也留著——刪不刪由人決定。
- 跟以前（核心 tick 做）的差別：被擋的情況以前是「tick 不起、記 tasks_error、總結 skipped」，現在是「包裝程式起了又馬上退出碼 1、總結 ended 看得到失敗、原因在 out.log」。
- 擁有者、守門檔、stopped.json 都是普通檔（合作式）：防失誤，不防惡意。
- **父 kill 的 1 秒**是核心 kill 的通用寬限（核心 spec §6），不是這包的設定：子 daemon 在寬限內收不完的子任務，由**下一次起這個包**時的重開前回收收（上一節），不靠核心 §5.4（任務還活就當活接回）。父 node 不再起這項（拿掉 tasks.json 那項、pause 父 node）時，前代任務就一直留著，要收就再起一次包，或照環境身分人手收。
- **繞過包裝起過的子 daemon** 留下的任務：下一次經包起時，記錄不是 `stopped` 就一樣被收（子根只由這個包認領，前置條件）。
- **要永久拿掉子空間**：先對子 daemon 下允許的 stop（`--allow-stop` 的才收）、等 `<subroot>/.aosd/stopped.json` 出現，再拿掉父 tasks.json 那項。
