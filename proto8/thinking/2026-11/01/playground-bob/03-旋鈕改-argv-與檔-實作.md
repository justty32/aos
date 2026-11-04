# 環境變數：格自己的旋鈕改掉、刪掉 aos-round（11-01 晚實作，隊長代做）

← [入口](README.md)｜上一份 [02-要使用者裁的問題](02-環境變數要使用者裁的問題.md)｜每個變數改成什麼記在 [env-vars.json](env-vars.json) 的 `done` 欄

## 使用者原文（11-01 晚，逐字）

> 3.這就是濫用...除非真的有必要的，否則不要用。

> 明明現有的機制組合一下就能搞定，偏偏在那邊亂搞一通

> 幾支小程式，每個都一大堆機制，搞到最後亂成一團

> 一大堆東西根本就是不需要的

刪 aos-round：

> aos round這東西還沒刪掉嗎

> 這應該整個都不需要吧

頂層列出牽連範圍後，使用者回「刪掉」。

## 怎麼改（照原文定的做法）

1. **先問能不能刪**：沒有程式或 demo 把它設成預設以外的值、只有測試在調它 → 寫死成程式裡的常數。測試改成在預設值下測，例如把輸入做大，讓它超過門檻。
2. 刪不掉的才改：**argv**（`--kebab-case 值`，一支程式最多 3 個）或**現有的檔**（stack 裡一行的 `.txt`，跟 `endpoint.txt` 同一種）。不發明新的設定檔格式，也不加解析層。
3. 不留舊名相容層：程式不再讀那個環境變數。測試裡留一案「設了舊變數也沒作用」。

## 結果：範圍內 42 個

刪掉（寫死）26、改 argv 11、改檔 3、不動 2（`AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN`，已隨主人封存）。每個寫死成多少記在 [env-vars.json](env-vars.json) 的 `done` 欄。範圍外照舊：aos-exec 給的 5 個、腦三個（第 2 題）、hub 型（第 1 題）、`AOS_ENTRY`（第 5 題）、topdown 的 33 個。沒有哪個變數核出來其實是跨層必要。

### 改 argv 與改檔（14 個）

| 舊變數 | 新寫法 |
|---|---|
| `AOS_ENDPOINT_NAME` | endpoint 的第 2 個位置參數：`aos-exec <endpoint 格> <agent> <槽名>`。roundlib 會給；openai 寫進 usage.jsonl，沒給就用資料夾名；fake 收下不用 |
| `AOS_COMPACT_MAX_BYTES` | `compact [--max-bytes N] [--force] <agent>`，沒給＝65536，壞值＝`ArgumentsBad`（`SettingBad` 拿掉） |
| `AOS_ACT_MAX_PARALLEL` | `act [--max-parallel N] <agent>`。要設就把 parts.json 的 act 槽寫成 aos-exec 的 argv 陣列，例 `["../../lib/agent/act", "--max-parallel", "2"]`（實測過） |
| `AOS_ASK_AGENT`、`AOS_ASK_MAX_STEPS`、`AOS_ASK_WS` | `ask_round [--agent 路徑] [--max-steps N] [--ws 路徑]`。固定問一隻＝工具小資料夾的 `_entry` 放一份不加 +x 的 JSON argv 陣列 |
| `AOS_AI_JSON_EDITOR` | `aos-ai edit 名 檔 --editor 命令` |
| `AOS_IMPROVE_TARGET` | 判準檢查程式：`aos-exec <check> <函數複本路徑>`（最後一個參數） |
| `AOS_S6_BIN`、`AOS_ME`、`AOS_RUNNER` | `setup.sh --s6-bin 路徑 --me 名 --runner 名`，跟 `--mailbox`、`--apply` 用同一個迴圈 |
| `AOS_PYFIX_DIR` | 檔：pyfix 寫子 agent 的 `stack/pyfix_dir.txt`（一行絕對路徑），act 讀 `$AOS_STACK/pyfix_dir.txt` |
| `AOS_THOUGHT_DEPTH`、`AOS_THOUGHT_BUDGET` | 檔：launch 起小念頭時寫進小念頭 stack 的 `thought_depth.txt`、`thought_budget.txt`（一行一個值），沒有＝母體 |

`parts.json` 那槽的 `.env` key 留著：`endpoint` 槽要靠它設 `AOS_BRAIN_URL`／`MODEL`，而且這是 aos-exec 本來就有的機制。

## 刪掉 aos-round（11-01 晚）

aos-round 做的三件事改用現有機制組合：

| aos-round 做的事 | 現在怎麼做 |
|---|---|
| 挑表（`--on-empty stop\|idle`） | agent 的 loop.json 直接叫 aos-fsm，指要哪張表：`{"exec": {"argv": ["aos-fsm", "fsm-stop.json"], "cwd": "../../lib/agent/round", "timeout_ms": 600000}, …}`；要 idle 就寫 `fsm-idle.json`。repo 外的 agent 把 `cwd` 寫成絕對路徑。`--on-empty` 跟著消失（aos-eca-turn 的 `--on-empty` 是另一支程式，沒動） |
| 傳話筒 `AOS_ROUND_AGENT` | 兩張表的五格改成 `["idle", {"$env": "AOS_CD"}]`：loop 跑那張單子時 `AOS_CD`＝loop.json 的資料夾＝agent。表留在 `lib/agent/round/`，沒有複製進 agent |
| cd 到 lib/agent/round、exec aos-fsm、把相對的 stack 轉絕對 | 單子的 `cwd` 換過去；相對的 `AOS_WS`／`AOS_STACK` 由 aos-fsm 自己轉 |

叫它的地方：
- `lib/aos/ask_round`：改叫 `aos-exec <agent>/loop.json#/exec`，照那隻 agent 自己的 loop.json 走一格。答完就停，看的是信不見了，所以 agent 用 idle 表也照樣停。
- `bin/aos-daemon-ctl add`：遇到內嵌的單子，指回原檔 `<XXX>/loop.json#/exec`，`AOS_CD` 和相對路徑都照原地算，不在小格裡改寫單子。

## 代定（隊長與工人照原則定的，可翻案）

1. lib compact 只留 `--max-bytes`：`KEEP_TURNS` 與 `ENDPOINT` 也刪了，因為沒人設。`MODEL_*` 刪掉以後，compact 不能再另外挑模型；真要換，再加回 `--endpoint`。
2. agent-hal compact 寫死「留最近 2 題」以後，「全壓」那個分支走不到了，所以刪了。
3. endpoint 名用位置參數（不用旗標），因為 endpoint 本來就是 `[<agent>]` 一個位置參數。
4. act 的 `--max-parallel` 壞值＝`ParallelBad`。compact 的 `--max-bytes` 收 0 以上：0＝有東西就壓。
5. ask_round 的旗標用 `bin/aos_flags.py` 解。壞值退 `ArgumentsBad`，不認得的旗標退 `FlagUnknown`，`SettingBad` 拿掉。
6. pyfix：`agent_tool.run_agent` 開子 agent 的 stack「已經在就沿用」，pyfix 才能先把檔放進去。
7. gus 的深度與額度用兩個一行檔。`thought.py` 讀叫它的人給的 `$AOS_STACK`（沒有就算母體），不去猜上層的佈局。
8. recall 靠 P-17 往上一層找 history；那份檔不在＝`HistoryMissing`。
9. aos-round 的表留在 lib，agent 用 loop.json 單子的 `cwd` 指過去（沒有複製進 agent、也沒有用 `$ref`）。
10. daemon-ctl 指回原檔，不在小格裡改寫單子。

## 未決

- 舊 bug 沒修：lib compact 的 report.json 寫 `"endpoint": ep[0]`，但 `ep` 是字串，所以只記到第一個字元。
