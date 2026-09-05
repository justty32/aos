# 08 daemon 與登記表
← [入口](README.md)

daemon 是一支常駐程式，住在家（`$AOS_HOME`，預設 `~`）。它只做兩件事：替每塊登記的地起一支 `aos run` 子行程，然後看管它們。所有時鐘記在同一份登記表 `$AOS_HOME/.aos/registry.json`。對帳、巡邏、清理、一次全停、`aos mv` 在 [08b](08b-daemon-reconcile.md)。

## daemon 是什麼

- **S-08-01** daemon 必須是常駐程式，家是 `$AOS_HOME`（預設 `~`）；登記表、使用者層設定、帳簿都住那的 `.aos/`。〔主編補〕
- **S-08-02** daemon 必須由 shell 手動 `aos daemon start` 起，第一版禁止做 systemd。〔裁決 2026-08-30〕
- **S-08-03** 頂層地必須由使用者開或由 daemon 代開，禁止任何地自己醒過來。〔裁決 2026-09-03〕
- **S-08-04** daemon 起來必須用 O_EXCL 建 `$AOS_HOME/.aos/daemon.pid`；建不出來就是已有一支，直接退出。〔主編補〕
- **S-08-05** daemon 必須把行程編號同時寫進 `daemon.pid` 與登記表的 `daemon_pid`，收工改回 `null`。〔主編補〕

## 走時鐘＝起一支子行程

- **S-08-06** 走時鐘必須是替每塊登記的地起一支 `aos run <地> --register …` 子行程；daemon 禁止自己逐一走。〔裁決 2026-09-05〕
- **S-08-07** 旗標必須照那筆登記換算：`steps`→`--steps N`、`every`→`--every <ms>`、`until`→`--until <值>`、`once`→`--steps 1`；有 `budget` 再加 `--budget N`。〔主編補〕
- **S-08-08** daemon 掛了各地時鐘必須照走；子行程禁止被 daemon 的死拖著死。〔裁決 2026-09-05〕
- **S-08-09** 代價必須明寫：daemon 不在時沒人能一次全停，只能等它重啟後對帳收拾。〔裁決 2026-09-05〕
- **S-08-10** 父的時鐘掛了子的必須照走，禁止因為父行程沒了就連帶停子。〔裁決 2026-09-04〕
- **S-08-11** 一塊地同時只准一筆走著的登記，同一個 `path` 禁止出現兩次。〔主編補〕
- **S-08-61** 新的脫節工作必須一律由 daemon 起；第二個代價必須明寫：daemon 不在時新的起不來，既有的照走。〔主編補〕
- **S-08-84** `runner` 是 `llm-serve` 的那筆，daemon 起的必須是 `aos llm serve <地>` 不是 `aos run`；那塊地不用接力棒也不走三種步，見 [09](09-llm-world.md)。〔主編補〕

## 登記表

- **S-08-12** 所有時鐘必須登記在同一份 `$AOS_HOME/.aos/registry.json`；禁止另發明第二個登記處。〔裁決 2026-09-04〕
- **S-08-13** 登記表必須長成 `{"format_version":1,"daemon_pid":N|null,"entries":[…]}`；正本是 `schemas/registry.schema.json`。〔主編補〕
- **S-08-14** 每筆的 `path` 必須是真實路徑（realpath），禁止記 symlink 路徑。〔主編補〕
- **S-08-15** 每筆的 `pid` 必須是替它走鐘那支 run 的行程編號；還沒起寫 `null`。〔預設 2026-09-05，G-03〕
- **S-08-16** 每筆的 `state` 必須是 `pending`、`running`、`stopped` 之一。〔預設 2026-09-05，G-03〕
- **S-08-17** 每筆的 `clock` 必須寫時鐘規格：`kind` 是 `steps`／`every`／`until`／`once`，各自帶 `steps`／`every_ms`／`until`（`idle` 或 `never`）；沒鐘寫 `null`。〔預設 2026-09-05，G-03〕
- **S-08-18** 每筆的 `budget` 必須是這支 run 最多走幾格，不設上限寫 `null`。〔主編補〕
- **S-08-19** 每筆的 `parent` 必須是登記它那塊地的真實路徑，使用者登記的寫 `null`。〔主編補〕
- **S-08-20** 每筆的 `registered_at`、`updated_at` 必須是 ISO 8601 UTC 含毫秒，改狀態必須更新 `updated_at`。〔主編補〕
- **S-08-64** 每筆必須多一欄 `pid_start`：那個 pid 的啟動時間，讀 `/proc/<pid>/stat` 第 22 欄、字串存；沒 pid 寫 `null`。〔主編補〕
- **S-08-65** 每筆必須多一欄 `land_id`：開跑時讀那塊地 `.aos/layout.json` 的 `land_id`，讀不到寫 `null`。〔主編補〕
- **S-08-83** 每筆必須多一欄 `runner`：`run`（預設，起 `aos run`）或 `llm-serve`（起 `aos llm serve`）。〔主編補〕
- **S-08-85** 每筆必須收一個可選的布林欄 `resume`：被 `aos daemon stop` 停掉時設 `true`，意思是「下次 start 要接回去」。〔主編補〕
- **S-08-66** 每筆的 `ext` 必須收三個約定鍵：`result`（起脫節子地時 exec 寫的父指定落點）、`exec_id`（`aos daemon exec` 那筆的 id）、清理紀錄。〔主編補〕
- **S-08-21** 登記表的寫者有四方（exec 登 `pending`、`aos run --register`、門房、daemon），四方都必須先用 O_EXCL 建 `$AOS_HOME/.aos/registry.lock` 拿鎖、改完刪鎖；拿不到就等，禁止硬寫，例外見 [08b](08b-daemon-reconcile.md)。〔主編補〕
- **S-08-22** 寫登記表必須原子改名：寫 `registry.json.tmp` → fsync → rename → fsync 目錄。〔主編補〕
- **S-08-23** 登記表禁止進 git，回滾一份含行程編號的檔會讓 daemon 認錯活人。〔主編補〕

## 出生先登記再走

- **S-08-24** 每支 `aos run <地> --register` 起來第一件事必須把那筆改成 `running`，填 `pid`、`pid_start`、`land_id`；沒那筆就自己補一筆。〔裁決 2026-09-04〕
- **S-08-25** 這支 run 結束時必須把那筆改成 `stopped`、`pid` 與 `pid_start` 設回 `null`；順序反過來會留下看不見的時鐘。〔裁決 2026-09-04〕
- **S-08-87** `--register` 時登記表已有那筆的，准更新的只有 `pid`、`pid_start`、`state`、`last_started_at` 四欄；禁止改 `clock`、`budget`、`runner`。時鐘規格是登記者說了算。〔主編補〕
- **S-08-26** `pending` 必須解成「登記了，等 daemon 來起」，而且只有兩個來源：脫節呼叫登記子地的鐘、`aos daemon exec`。〔主編補〕
- **S-08-27** 門房偵測到一塊地出生必須登記成 `stopped`、`pid` 與 `clock` 寫 `null`；daemon 只起 `pending`，這筆不會被起。〔主編補〕
- **S-08-28** `daemon_pid` 不在或那支 daemon 已死時，`call async` 必須立刻失敗並寫狀態檔 `reason: no_daemon`；禁止 exec 自己 detach 起 run。〔主編補〕
- **S-08-29** `stopped` 必須解成「時鐘停了、地還在」；禁止當「地死了」用，地死了是那筆被刪掉。〔主編補〕
- **S-08-30** 想知道脫節子地的鐘還在不在走，必須查那筆的 `state` 與 `pid`，禁止用別的辦法。〔預設 2026-09-05，F-07〕
- **S-08-31** agent 預設必須自己用 `aos run --register` 登記一筆；登記表上看得到它、`aos stop <地>` 停得到它。只有父用 `call` 步 `mode:"sync"` 帶著走的 agent 才沒有自己那筆（見 [10](10-agent.md)）。〔裁決 2026-09-05〕

## 並行上限

- **S-08-43** daemon 起子行程前必須數登記表裡 `running` 有幾筆；超過使用者層 `max_parallel` 就先不起、留 `pending`。〔預設 2026-09-05，G-06〕
- **S-08-44** daemon 禁止數 LLM 併發；它只保證 LLM 世界那支 run 活著，併發由該世界自己管，見 [09](09-llm-world.md)。〔主編補〕

## `aos daemon add`、`exec`、`ls`

- **S-08-50** `aos daemon exec <地>` 必須往登記表投一筆 `clock.kind` 是 `once` 的 `pending`，由 daemon 起它一次。〔預設 2026-09-05，G-02〕
- **S-08-67** `aos daemon exec` 必須帶一個 `id` 寫進那筆的 `ext.exec_id`；同 `id` 再投必須拒絕並告訴投的人。〔主編補〕
- **S-08-86** `aos daemon add <地> --steps N｜--every <ms>｜--until idle｜--until never [--budget N]` 必須只登記成 `pending`、不開跑；登記與起時鐘是兩個動作，這支補「只登記」那個。〔主編補〕
- **S-08-51** `aos daemon ls` 必須把登記表逐筆列出來，禁止另維護一份給人看的表。〔主編補〕

## 控制收件匣

- **S-08-56** 控制訊息必須走投遞協定進 `<地>/.aos/control/`：寫 `<id>.json.temp` → 刷 → 改名。〔預設 2026-09-05，L-05〕
- **S-08-57** 訊息必須長成 `{"format_version":1,"id":"…","op":"stop","from":"…","at":"…"}`；正本是 `schemas/control.schema.json`，第一版 `op` 只有 `stop`。〔主編補〕
- **S-08-58** run 必須在每格的邊界看一次控制收件匣，禁止在一格中途中斷。〔預設 2026-09-05，L-05〕
- **S-08-59** run 看到 `stop` 必須收掉那則訊息、把這格做完、寫停止原因檔、再把那筆改 `stopped`。〔主編補〕
- **S-08-60** 只有「立刻殺掉」（`aos stop --kill <地>`）禁止走控制收件匣，它直接送 SIGKILL；殺完的收拾在 [08b](08b-daemon-reconcile.md)。〔預設 2026-09-05，L-05〕

## 登記表範例

```json
{
  "format_version": 1,
  "daemon_pid": 40412,
  "entries": [
    { "path": "/home/me/proj", "pid": 40530, "pid_start": "918233",
      "land_id": "3f2a91c0", "state": "running",
      "clock": { "kind": "every", "every_ms": 5000 }, "budget": 1000, "parent": null,
      "registered_at": "2026-09-05T09:00:00.000Z", "updated_at": "2026-09-05T09:00:00.480Z" },
    { "path": "/home/me/proj/fetch", "pid": null, "pid_start": null,
      "land_id": "77b0de41", "state": "pending",
      "clock": { "kind": "once" }, "budget": 20, "parent": "/home/me/proj",
      "registered_at": "2026-09-05T09:02:11.000Z", "updated_at": "2026-09-05T09:02:11.000Z",
      "ext": { "result": "/home/me/proj/data/fetch.json" } },
    { "path": "/home/me/proj/old", "pid": null, "pid_start": null,
      "land_id": "0c5e8ab2", "state": "stopped",
      "clock": null, "budget": null, "parent": null,
      "registered_at": "2026-09-04T21:40:00.000Z", "updated_at": "2026-09-04T21:41:07.250Z" }
  ]
}
```

## 待使用者拍板

- S-08-01 常駐、家在 `$AOS_HOME`。〔主編補〕
- S-08-04 只准一支 daemon。〔主編補〕
- S-08-05 `daemon_pid` 兩處寫。〔主編補〕
- S-08-07 時鐘規格換算旗標。〔主編補〕
- S-08-11 一個 `path` 只准一筆。〔主編補〕
- S-08-61 沒 daemon 就起不了新脫節工作。〔主編補〕
- S-08-13 表的形狀。〔主編補〕
- S-08-14 記 realpath。〔主編補〕
- S-08-15 `pid` 欄。〔預設，G-03〕
- S-08-16 `state` 三值。〔預設，G-03〕
- S-08-17 `clock` 欄。〔預設，G-03〕
- S-08-18 `budget` 欄。〔主編補〕
- S-08-19 `parent` 欄。〔主編補〕
- S-08-20 兩個時間戳。〔主編補〕
- S-08-64 `pid_start` 欄。〔主編補〕
- S-08-65 `land_id` 欄。〔主編補〕
- S-08-66 `ext` 的三個約定鍵。〔主編補〕
- S-08-21 鎖檔。〔主編補〕
- S-08-22 原子改名。〔主編補〕
- S-08-23 不進 git。〔主編補〕
- S-08-26 `pending` 只有兩個來源。〔主編補〕
- S-08-27 門房登記成 `stopped`、沒有鐘。〔主編補〕
- S-08-28 沒 daemon 時 `call async` 直接失敗。〔主編補〕
- S-08-29 `stopped`＝停了沒死。〔主編補〕
- S-08-30 查鐘就查登記表。〔預設，F-07〕
- S-08-43 數 `running` 擋上限。〔預設，G-06〕
- S-08-44 daemon 不數 LLM 併發。〔主編補〕
- S-08-83 `runner` 欄。〔主編補〕
- S-08-84 `llm-serve` 起 `aos llm serve`。〔主編補〕
- S-08-85 `resume` 欄。〔主編補〕
- S-08-86 `daemon add` 只登記不開跑。〔主編補〕
- S-08-87 `--register` 不准改鐘。〔主編補〕
- S-08-50 一次性入口投 `once`。〔預設，G-02〕
- S-08-67 `daemon exec` 帶 id、同 id 拒絕。〔主編補〕
- S-08-51 `ls` 就是列表。〔主編補〕
- S-08-56 控制訊息走投遞協定。〔預設，L-05〕
- S-08-57 控制訊息欄位。〔主編補〕
- S-08-58 格邊界看控制收件匣。〔預設，L-05〕
- S-08-59 看到 `stop` 怎麼做。〔主編補〕
- S-08-60 `--kill` 直接送 SIGKILL。〔預設，L-05〕
- 矛盾：`stopped` 同時當「跑完了」「被停掉」「還沒有鐘」。我選一個字通用、細節看 `clock` 與 `pid` 兩欄，多加狀態值會逼讀者多記一組。

## 現況對照

今天每塊地各寫自己的 `.aos/run.pid`，`aos stop <地>` 只停一塊，沒有總登記表也沒有一次全停。今天的登記沒有地的 id，也沒有行程啟動時間，pid 被系統重用就會認錯人。
