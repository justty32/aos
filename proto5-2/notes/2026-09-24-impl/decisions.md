# proto5-2 實作的決定（2026-09-24）

← [實作總報告](README.md)｜規範：[spec/](../../spec/README.md)

編號規則：Q1～Q9 是 [proto5-2 README](../../README.md)「要使用者拍的」九題（隊長代使用者先定）；
D-n 是實作中撞到規範沒寫或矛盾、自己選的（一律選最保守的）。為了幾隊同時寫不撞號：隊長 D-1～D-19、kernel 隊 D-20～D-49、daemon 隊 D-50～D-69、cpu 隊 D-70～D-79、其他 D-80 起。
每條寫：撞到什麼、選了什麼、為什麼保守、翻案要改哪裡。

## Q1～Q9：九題

| 題 | 定成 | 可翻案？翻案要改哪裡 |
|---|---|---|
| Q1 帳本整份讀寫 | **先不動**，照 proto5 現況（一份 `K/state.json`）；目標先以「幾百到一千顆」為準，不拆帳本 | 可。要拆：`aos_kernel_ledger.py` 的讀寫、aos-agent 偷看 `procs` 的地方（`aos_agent_runtime.ledger`、`aos_agent_status`）、spec kernel-ledger／scale |
| Q2 agent 偷看整份帳本 | **先不動**，aos-agent 照舊每格讀 `K/state.json` | 可。要改：kernel 另維護一行程一小檔、aos-agent 改看它（proto5 aos-agent.md §10） |
| Q3 一顆 cpu 一支 Python | **先不動**，照 `aos-cpu` 現況；上限以千顆為準 | 可。要改：`aos_exec_cpu.py`（一支管多家）或換語言；daemon 的 fd 預算跟著變 |
| Q4 `cpu rm NAME` | **照草稿**：`NAME`＝`P/<i>`、永久退休該號（寫進 `skip`、`count` 減 1） | 可。只要「這次收哪一顆」：改 kernel 的 cpu rm 不寫 `skip`、改成換號 |
| Q5 既有池 `cpu add --env` | **照草稿**：拒絕（`PoolExists`，用法錯 2），改環境請編 info | 可。要允許：cpu add 改寫 `pools.P.envs`，tick 第 7 步第 4 小步本來就會重寫 `envs.json`；要活的一起換再加 `aos-daemon kill --all` |
| Q6 縮池要不要 `--now` | **照草稿**：沒有，一律做完再收；卡住用 `aos-daemon kill` | 可。要加：cpu rm 多一旗標、kernel 不等 busy 直接把號從 T 拿掉，並處理卡在 running 的行程 |
| Q7 拉不起來的號卡住的工作 | **照草稿**：不另訂放棄協定，唯一解是修家 | 可。要訂：新協定（確認沒人會跑那張單就回 Interrupted），動 kernel-pools §4 |
| Q8 daemon halt 後 boot 自動拉回 | **照草稿**：要；`pool.json` 留著 | 可。要不拉：daemon boot 不照 `pool.json` 排 pending，kernel 要改回每次 boot 重宣告 |
| Q9 退休 cpu 家的清理指令 | **照草稿**：家不刪、不做清理指令 | 可。要做：`aos-kernel cpu gc` 之類，先確認不在任何成員、daemon 看不到 |

## 隊長的 D-1～D-19

- **D-1 程式與入口**：`proto5/lib` 整份複製到 `proto5-2/lib`，`proto5/cli` 複製到 `proto5-2/cli`（任務書寫「含 cli/」，但 proto5 的 cli 在 lib 旁邊）。池模板的 `argv[0]` 指 `proto5-2/cli/aos-cpu`。
- **D-2 模組分工**：daemon 相關只在 `aos_daemon*.py`；kernel 相關只在 `aos_kernel*.py`；cpu 通知只在 `aos_exec_cpu.py`；`aos_home.py`／`aos_client.py` 只准**加**函式、不改既有函式的行為。
- **D-3 錯誤回音形狀**：沿用 proto5 `aos_home.error_response`：`{"code": -32000, "message": …, "data": {"code": "NameTaken"}}`；`-32602` 用 `params_error`（`data.code`＝`FieldTypeMismatch`、`data.position`）。kernel 判錯一律看 `data.code`，沒有 `data.code` 時用 `str(code)`。

## kernel 隊 D-20～D-49

## daemon 隊 D-50～D-69

## cpu 隊 D-70～D-79

## 其他 D-80～
