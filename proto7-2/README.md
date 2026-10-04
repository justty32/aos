# proto7-2 — 照使用者建議重做 daemon／tick 的第二次試做

← [proto7](../proto7/README.md)｜要合的：[核心 spec](../proto7/spec/core.md)（條號 S-）｜上一次試做：[proto7-1](../proto7-1/README.md)

**proto7-1 之後的第二次試做：照使用者 10-04 的建議（[user-advice](../proto7/user-advice.md)）重做 daemon 與 tick。10-04 照 spec 做完基礎設施（Python 3.11+ 純標準庫）；kernel／agent 這次不做。**

## 入口

- **[spec.md](spec.md)**：細部 spec，每節標 S- 條號；實作時改過的地方標 P2-。
- **[notes/problems.md](notes/problems.md)**：照 spec 做的時候碰到的問題（**2 條要你決定**：P2-01 固定 interval 時 wake 沒作用、P2-02 once 被殺在特定一段時報 lost 不重跑）。
- [notes/changes-from-7-1.md](notes/changes-from-7-1.md)：跟 proto7-1 的對照表，最後是 W1～W12（程式照推薦做）。

## 一句話看改了什麼

node 改成登記、不再掃資料夾；tock 預設照固定 interval，提前 tock 變成可選；只剩 tasks.json 一個任務表（一次性任務是裡面 `mode: "once"` 的一項）；任務資料夾照名字重用，不再每回合新增；核心只留「上一次」，更前面的歷史交給可選的歷史 module。

## 怎麼跑

```sh
P=proto7-2/bin                      # 用 proto7-2 的 bin/（程式名跟 proto7-1 一樣是 aos7-*，見下）
mkdir -p /tmp/sp/team/.aos
echo '{"tasks":[{"name":"hello","argv":["sh","-c","echo hi $AOS7_RUN"]}]}' > /tmp/sp/team/.aos/tasks.json
python3 $P/aos7-ctl daemon /tmp/sp register team    # 登記（daemon 還沒起也行，起來才處理）
python3 $P/aos7-daemon /tmp/sp &                    # 只跑 .aosd/nodes.json 登記的 node
cat /tmp/sp/.aosd/status.json /tmp/sp/team/.aos/last-round.json
python3 $P/aos7-ctl daemon /tmp/sp stop --kill
```

**程式名沿用 `aos7-*`**（`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`，加搬來的 `aos-exec`）。proto7-2 的程式彼此呼叫時一律用自己 `bin/` 的絕對路徑，任務的 `PATH` 前面也加的是 proto7-2 的 `bin/`，所以不會跟 proto7-1 混；人手在 shell 裡用時，把 `proto7-2/bin` 放在 `PATH` 最前面（或像上面直接寫路徑）。

## 測試

在 repo 根跑：

```sh
python3 -m unittest discover -s proto7-2/tests
```

離線、純標準庫，103 項約 40 秒。測試起的子程序一律**先收程序、再刪空間**（`tests/_proc.py` 的 `track`／`reap`，`tests/base.py` 收尾時再掃一次環境變數 `AOS7_ROOT` 是暫存根的程序）；暫存根在 `/tmp/aos72-test-*`，跑完會刪。

| 檔 | 測什麼 |
|---|---|
| `test_tick_tock.py` | 槽與 run 號、換 run 清基礎設施檔留任務的檔、each 跳過與 max_live 槽、keep 不雙開、from_round／enabled、once、刪槽（報完再一回合）、**200 回合檔案數不變**、tock 之後才結束的 run 照樣報、inst |
| `test_ctl.py` | kill／restart／reload／指定 run、kill 範圍（setsid 孫程序、偽造 pgid、inst 的另一個 session）、**lost 前的身分掃描（NODE＋TID＋RUN）**、掛載與執行中加掛 |
| `test_once_threestate.py` | **once 在 launch 標記後、birth 後、Popen 後、刪項目前各點 kill -9 tick**、成組 once 中途被殺；**三態**：round.json／birth.json 讀不到、starttime 讀不到、槽列不出來 |
| `test_daemon.py` | **登記／取消登記**、node 刪掉／搬走／換掉 → missing、看不到≠不存在、**early_tock 兩種**、**pause owner**、resume 順便 wake、resume rounds、stop／SIGTERM、第二個 daemon、root 搬走、回條同名蓋掉、控制檔洪水與壞檔、ctl-failed、log.on、卡住的 tick／tock、**kill -9 daemon 後新 daemon 收回合不雙開**、舊動作接管 |
| `test_subdaemon_modules.py` | **子 daemon 所有權**（owner／daemon 兩塊、allow_stop、stopped.json、人手重開沿用 owner）、subroot 檢查、counter 示範、歷史 module |

## 結構

| 位置 | 是什麼 |
|---|---|
| `bin/` | 薄入口：`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`，與搬來的 `aos-exec` |
| `lib/aos7_daemon.py`、`aos7_daemon_timeline.py` | daemon：登記、控制檔、node 消失、status；每個 node 一條時間線（第 1、2 節） |
| `lib/aos7_tick.py`、`aos7_tock.py` | 開回合（tasks.json、once 的 launch 標記）／關回合（last-round.json、刪槽）（第 3、4、7 節） |
| `lib/aos7_task.py` | 槽、三態判定、lost 前的身分掃描、任務控制、在槽裡起新 run（第 5、6 節） |
| `lib/aos7_proc.py` | 程序工具：同一個程序嗎（pid＋starttime 三態）、身分掃描、Q1 範圍的收程序 |
| `lib/aos7_run.py` | 任務的包裝：pid.json、exit.json（帶 run） |
| `lib/aos7_fs.py` | 原子寫、三態讀（`read_json3`）、flock、動作鎖與世代、測試鉤子 |
| `lib/aos7_ctl.py` | `aos7-ctl daemon／task／add`（第 10 節） |
| `lib/aos7_mount.py`、`aos7_audit.py`、`audit_site/` | 掛載（4.5）與可選的寫入紀錄 |
| `lib/aos_*.py` | 搬來的 inst 執行器 |
| `modules/counter.py` | 最小示範任務：讀同槽上一次的 state.json、收 tock.json |
| `modules/history.py` | 歷史 module 的參考實作（第 9 節）：普通 keep 任務，每個 tock 把 last-round.json 追加到 `history/` |
| `tests/` | 見上 |
| `notes/` | problems.md、changes-from-7-1.md |

## 來源（複製進來，不 import 外部路徑）

- `lib/aos_inst.py`、`aos_directives*.py`、`aos_dirname.py`、`aos_exec*.py`、`bin/aos-exec`：**原樣複製自 proto7-1**（10-04；proto7-1 當初從 proto6 複製）。
- `lib/aos7_fs.py`、`aos7_run.py`、`aos7_mount.py`、`aos7_ctl.py`、`aos7_audit.py`、`audit_site/`、`tests/_proc.py`：從 proto7-1 複製後改寫（`aos7_audit.py`、`audit_site/`、`_proc.py`、`aos7_mount.py` 幾乎沒改）。
- `lib/aos7_daemon*.py`、`aos7_tick.py`、`aos7_tock.py`、`aos7_task.py`、`aos7_proc.py`：照 proto7-1 同名檔的結構重寫（程序工具從 proto7-1 `aos7_task.py` 拆出來）。
