# 子 daemon 包（subd）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)（第 2.7 節：守門檔）

**讓一個 node 的任務擁有一個子空間根，跑自己的 daemon**（S-21 路一）：子 daemon 是那個任務的子程序，父 node kill 它就帶走整棵；它的 stop 要擁有者允許。核心不知道「從屬」，只認通用守門檔 `.aosd/stop-guard.json`。

| 項目 | 內容 |
|---|---|
| 接法 | B 包裝程式：tasks.json 項目的 argv 寫成 `aos7-subd <subroot> [--allow-stop] -- <argv...>` |
| 預設 | 關（用到才寫） |
| 依賴 | 核心的守門檔（spec 2.7）、「路上有別的 daemon 根就不收那個 node」（spec 第 1 節） |
| 程式 | `aos7-subd`（可執行 Python） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/subd/tests`） |

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
- 通過後寫：
  - `<subroot>/.aosd/stop-guard.json`＝`{"allow": 有沒有 --allow-stop, "note": "這個 daemon 屬於 node X（任務 Y）…"}`——核心照它擋控制檔 `stop`；
  - `<subroot>/.aosd/owner.json`＝`{"owner": {"node", "tid", "allow_stop"}, "daemon": {"pid", "since"}}`——給人看。
- 設 `AOS7_SUBROOT`（子根絕對路徑）後把 argv 起成子程序（同一個程序群組），等它結束；退出碼照它（被訊號殺＝128＋訊號號）。
- argv 結束、**不是**因為包裝程式自己收到 SIGTERM（父 kill 時整個群組一起收到）、而且子根 `status.json` 是 `stopped: true` → 那是被允許的外部 stop：寫 `stopped.json`＝`{"by", "why", "at"}`（取 `ctl-done/` 裡最近一份成功的 stop 回條）。父 node 的 keep 項下一回合再起包裝程式時就被擋下（退出碼 1）。
- 父 kill 這個任務：SIGTERM 打到整個群組，子 daemon 照 SIGTERM＝stop＋kill 收自己的任務（核心 2.3），不看守門檔。

## 界線

- **繞過包裝**（argv 直接寫 `aos7-daemon <子根>`）：沒有守門檔、沒有 stopped.json、也沒有重複認領的擋法；重複認領時第二個 daemon 拿不到 daemon.lock、退出碼 1，keep 每回合重試，總結裡會一直看到失敗。stop 權限只靠守門檔，守門檔由這個包寫。
- **人手直接起子 daemon**：守門檔與 owner.json 照舊留著（核心不碰），stopped.json 也留著——刪不刪由人決定。
- 跟以前（核心 tick 做）的差別：被擋的情況以前是「tick 不起、記 tasks_error、總結 skipped」，現在是「包裝程式起了又馬上退出碼 1、總結 ended 看得到失敗、原因在 out.log」。
- 擁有者、守門檔、stopped.json 都是普通檔（合作式）：防失誤，不防惡意。
