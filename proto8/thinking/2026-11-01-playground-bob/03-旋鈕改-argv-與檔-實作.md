# 環境變數：格自己的旋鈕改掉、刪掉 aos-round（11-01 晚實作，隊長代做）

← [入口](../2026-11-01-playground-bob.md)｜上一份 [02-要使用者裁的問題](02-環境變數要使用者裁的問題.md)｜每個變數改成什麼記在 [env-vars.json](env-vars.json) 的 `done` 欄

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
4. 條文不改原意，只加 11-01 註（C-54 R8、R13；CONVENTION 02、06；NORMS 01、05、07、10）。

## 結果：範圍內 42 個

| 組 | 個數 | 有哪些 |
|---|---|---|
| **刪掉（寫死）** | 26 | 見下面「刪掉的旋鈕」 |
| **改 argv** | 11 | 見下面對照表 |
| **改檔** | 3 | `AOS_PYFIX_DIR`、`AOS_THOUGHT_DEPTH`、`AOS_THOUGHT_BUDGET` |
| **不動** | 2 | `AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN`（傳話筒，第 4 題使用者還沒裁） |

範圍外照舊：
- aos-exec 給的 5 個。
- 腦三個（第 2 題：到時候再說）。
- hub 型（第 1 題）。
- `AOS_ENTRY`（第 5 題）。
- topdown 的 33 個。

這次沒有哪個變數核出來其實是跨層必要。

### 刪掉的旋鈕（26 個，寫死成多少）

- `AOS_ROUND_MAX_RETRIES`：think 問腦最多重來 3 次。
- `AOS_ENDPOINT_TIMEOUT_MS`：openai 一次請求 120000 毫秒。代號 `TimeoutBad` 跟著拿掉。
- lib compact 與 agent-hal compact 共用的 9 個：
  - `AOS_COMPACT_SEG_KB` 8、`KEEP_TURNS` 2、`KEEP_MAX` 3、`KEEP_FINAL_MAX` 12、`KEEP_LINE_MAX` 1500、`RESULT_CUT` 2000。
  - `MODEL_NOTE`、`MODEL_SEG`、`MODEL_FINAL`：lib 不帶 model，用 endpoint 自己的；hal 寫死 luna-low、luna-low、sol。
- `AOS_COMPACT_ENDPOINT`：lib compact 照 `$AOS_STACK/endpoint.txt` ＞ default 找 endpoint，跟 think 用同一個腦。
- agent-hal compact 自己的 3 個：
  - `AOS_COMPACT_URL`：只看 `AOS_BRAIN_URL`。
  - `AOS_COMPACT_TIMEOUT_S`：120 秒。
  - `AOS_COMPACT_OVER_KB`：32 KB。
  - `demo/agent-hal/compact/.env` 整份刪掉。
- `AOS_AI_ASK_TIMEOUT`：ask_agent 等 50 秒。
- `AOS_JSON_EDIT_MAX_ROUNDS`：json_edit 最多 12 輪。
- `AOS_KAI_FULL_UNDER`：agent-kai 的 history 在 1500 token 以內就全送。
- `AOS_RECALL_HISTORY`：recall 讀 `$AOS_STACK/../history.jsonl`，靠 P-17「工具的 stack＝`<agent 的 stack>/<名>/`」，act 不再設這個變數。
- agent-gus 的 6 個上限：`AOS_THOUGHT_MAX_STEPS` 4、`MAX_DEPTH` 2、`MAX_TOTAL` 10、`PARALLEL` 3、`TIMEOUT_S` 900、`MAX_CHARS` 1500。`.env` 只留腦的模型名。
- `AOS_ROUND_AGENT`：aos-round 刪掉，這個變數跟著沒了（見下一節）。

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

`parts.json` 那槽的 `.env` key 還留著。這次腦的三個變數不動，`endpoint` 槽還要靠它設 `AOS_BRAIN_URL`／`MODEL`；而且這是 aos-exec 本來就有的機制。agent-nia 的 `hook/pre_think` 原本用 `.env` 設 65536，跟預設一樣，現在改成直接寫路徑字串。

## 刪掉 aos-round（11-01 晚）

aos-round 原本做三件事，改用現有機制組合：

| aos-round 做的事 | 現在怎麼做 |
|---|---|
| 挑表（`--on-empty stop\|idle`） | agent 的 loop.json 直接叫 aos-fsm，指要哪張表：`{"exec": {"argv": ["aos-fsm", "fsm-stop.json"], "cwd": "../../lib/agent/round", "timeout_ms": 600000}, …}`；要 idle 就寫 `fsm-idle.json`。repo 外的 agent 把 `cwd` 寫成絕對路徑。`--on-empty` 跟著消失（aos-eca-turn 的 `--on-empty` 是另一支程式，沒動） |
| 傳話筒 `AOS_ROUND_AGENT` | 兩張表的五格改成 `["idle", {"$env": "AOS_CD"}]`：loop 跑那張單子時 `AOS_CD`＝loop.json 的資料夾＝agent。表留在 `lib/agent/round/`，沒有複製進 agent |
| cd 到 lib/agent/round、exec aos-fsm、把相對的 stack 轉絕對 | 單子的 `cwd` 換過去；相對的 `AOS_WS`／`AOS_STACK` 由 aos-fsm 自己轉 |

叫它的地方：
- `lib/aos/ask_round`：改叫 `aos-exec <agent>/loop.json#/exec`，照那隻 agent 自己的 loop.json 走一格。答完就停，看的是信不見了，所以 agent 用 idle 表也照樣停。
- `bin/aos-daemon-ctl add`：遇到內嵌的單子，改成指回原檔 `<XXX>/loop.json#/exec`，`AOS_CD` 和相對路徑都照原地算。原本那套「複製單子、補 cwd、把 `{"$env": "AOS_CD"}` 釘成 XXX」的 `pin_cd` 刪掉。

其餘提到 aos-round 的都只是註解或說明，已經改掉。

## 代定（隊長與工人照原則定的，可翻案）

1. lib compact 只留 `--max-bytes`：`KEEP_TURNS` 與 `ENDPOINT` 也刪了，因為沒人設。`MODEL_*` 刪掉以後，compact 不能再另外挑模型；真要換，再加回 `--endpoint`。
2. agent-hal compact 寫死「留最近 2 題」以後，「全壓」那個分支走不到了，所以刪了。
3. endpoint 名用位置參數（不用旗標），因為 endpoint 本來就是 `[<agent>]` 一個位置參數。
4. act 的 `--max-parallel` 壞值＝`ParallelBad`。compact 的 `--max-bytes` 收 0 以上：0＝有東西就壓。
5. ask_round 的旗標用 `bin/aos_flags.py` 解。壞值退 `ArgumentsBad`，不認得的旗標退 `FlagUnknown`，`SettingBad` 拿掉。
6. pyfix：`agent_tool.run_agent` 開子 agent 的 stack 改成「已經在就沿用」，pyfix 才能先把檔放進去。
7. gus 的深度與額度用兩個一行檔。`thought.py` 讀叫它的人給的 `$AOS_STACK`（沒有就算母體），不去猜上層的佈局。
8. recall 靠 P-17 往上一層找 history；那份檔不在＝`HistoryMissing`（原本是回空的）。
9. aos-round 的表留在 lib，agent 用 loop.json 單子的 `cwd` 指過去（沒有複製進 agent、也沒有用 `$ref`）。
10. daemon-ctl 改成指回原檔，不再在小格裡改寫單子。

### 刪掉的測試案

基線是 798 OK／8 skip，現在 803 OK／8 skip，多 5 案：
- `test_round_bin.py` 改名成 `test_round_loop.py`：測 loop.json → aos-fsm 這條路，留下 5 案。測 aos-round 自己的兩案刪掉（`test_fsm_not_on_path`、`test_own_errors`）。
- test_gus 的 `test_thought_timeout` 刪掉：寫死 900 秒，測不了。
- 新增 8 案：
  - test_sandbox：`test_bad_flags`、`test_flags_and_old_env_ignored`
  - test_round_queue：`test_max_bytes_bad`、`test_old_env_ignored_default_65536`
  - test_round_endpoint：`test_name_argument_taken_unused`
  - test_nia：`test_old_env_ignored`
  - test_round_act：`test_parallel_from_parts_argv`
  - test_gus：`test_thought_entry_depth_from_stack`
- 只改名的兩案：`test_add_pins_aos_cd` → `test_add_inst_points_back`、`test_fixed_agent_by_cell_env` → `test_fixed_agent_by_cell_argv`。

## 留著的

- `AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN`：傳話筒（第 4 題，使用者還沒裁）。
- 順手看到一個舊 bug，這次沒修：lib compact 的 report.json 寫 `"endpoint": ep[0]`，但 `ep` 是字串，所以只記到第一個字元。
