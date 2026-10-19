# proto8-2 — 從 proto8 長出來的第二輪

← [proto8](../proto8/README.md)｜原話 → [thinking/ideas](thinking/2026-10-19-ideas.md)｜慣例 → [CONVENTION.md](CONVENTION.md)｜要使用者決定的 → [CONFLICTS.md](CONFLICTS.md)

**2026-10-19 開。** 使用者原話：「我這邊想開proto8-2，我有些新想法。」

## 與 proto8 的關係

從 proto8 長出來。proto8 的[概念](../proto8/CONCEPTS.md)與[規範](../proto8/NORMS.md)照舊有效；跟今天決定相撞的六條列在 [CONFLICTS.md](CONFLICTS.md)，等使用者裁定。proto8-2 放新想法。

## 現況

10-19 使用者定了：資料夾＝程式、入口＝`$AOS_ENTRY`（預設 `.aos/exec`）、三個環境變數、`aos-exec DIR [WS]`、inst 四種用法可選並存、慣例拍板點 1～3。原話在 [thinking/ideas](thinking/2026-10-19-ideas.md)；整套 aos agent 慣例（結論版，條號 P-01～P-30）在 [CONVENTION.md](CONVENTION.md)，程式還沒照它改的地方列在它第十節；那四項怎麼做、分幾步、每步要同步哪幾條，在 [PLAN.md](PLAN.md)（10-19 fable 規劃，只規劃、還沒動手）。方向、範圍、是否接替 proto8 都還沒定。

## 原型怎麼跑（10-19）

資料夾＝程式；入口＝資料夾裡 `$AOS_ENTRY`（預設 `.aos/exec`）指的可執行檔。在 WSL／Linux：

```
sh proto8-2/demo/run.sh                       # 建暫時工作區、放一題、跑 agent-bob、印工作區內容
python3 -m unittest discover -s proto8-2/tests
proto8-2/bin/aos-exec proto8-2/demo/agent-bob <工作區>    # 自己跑
cd workspace && aos-exec ../agent-bob             # 慣例用法（WS 省略＝-、沒設 AOS_WS 就用 cwd，使用者 10-19）
```

**aos 只訂環境變數**（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`），入口拿到之後「這次要做啥」怎麼收、怎麼用是入口自己的事（使用者 10-19，[ideas § 4](thinking/2026-10-19-ideas.md)）；aos-exec 只是把多的 args／stdin 原樣交給它。慣例上入口是 shell 檔；inst 單子是可選的升級，見 [CONVENTION § 八](CONVENTION.md)。

- `bin/aos-exec DIR [WS [args...]]`：WS 省略＝`-`；`-`＝沿用現有 `AOS_WS`，沒設才用 `.`（呼叫當下的 cwd）；給路徑就用那個。轉絕對路徑設成 `AOS_WS`；`AOS_STACK` 沒設就用 `$AOS_WS/.aos/`（轉絕對路徑、不存在就建），有設就沿用，都 export 給子程式；`cd DIR`、exec 入口；args／stdin 原樣透傳；把自己的 `bin/` 放進 PATH，所以入口裡直接寫 `aos-loop`、`aos-exec`。入口缺／不可執行、工作區或 DIR 不存在 → 結束碼 1 並印原因。
- `bin/aos-inst FILE [args...]`（`bin/aos_inst.py`，純標準庫，proto8-2 自己的一份、不 import proto8）：讀一張單子，第一行是 `#!` 就丟掉，其餘當 JSON，跑一次。所以 `.aos/exec` 第一行寫 `#!/usr/bin/env aos-inst`、下面接 JSON、`chmod +x` 就是入口（CONVENTION P-28 (A)）。認得的 key：`argv`（必填，args 接在後面）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`stdout_append`、`stderr_append`、`timeout_ms`、`grace_ms`（沒寫 2000；逾時先 SIGTERM、過 grace 再 SIGKILL）；其他 key 忽略。單子裡任何位置的 `{"$env": 名, "path": 子路徑}` 換成該環境變數底下的路徑（P-31）。**跟 proto8 `aos inst` 不同的兩處**：沒寫的串流接呼叫者的（proto8 是接 /dev/null）；命令列結束碼＝子程式的碼（不另吐結果 JSON），aos-inst 自己的錯退 1、stderr 一行 `aos-inst: 原因`。行程內用 `aos_inst.run(單子或檔)` 回 `{"code","signal","timed_out","pid","ms"}`。
- `bin/aos-loop loop.json`（Python 純標準庫）：`{"run": 子資料夾, "max": 最多幾圈}`，每圈 `aos-exec <run>`。子程式結束碼 0＝下一圈、**10＝要求停（loop 以 0 結束）**、其他非 0＝失敗（loop 以原碼結束）；跑滿 max 圈也以 0 結束（stderr 提醒）。
- `demo/agent-bob`：入口 `aos-loop loop.json` → 每圈 `fsm/`；fsm 讀 `$AOS_STACK/state`（預設 idle）執行同名子資料夾 `idle|think|act`，成功才寫下一個狀態（idle→think→act→idle）。idle 在 inbox 空時回 10 讓 loop 停。think 把答案草稿寫進 `$AOS_STACK/plan`，預設假腦，設 `AOS_BRAIN_URL`（OpenAI 相容 base URL，另可設 `AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`）改問真模型（10-19 用本機 LM Studio 實跑過：`AOS_BRAIN_URL=http://localhost:1234/v1 AOS_BRAIN_MODEL=qwen/qwen3-1.7b sh proto8-2/demo/run.sh`，WSL mirrored 網路連得到，一輪約 12 秒；模型沒預先 `lms load` 時第一題會卡在載入、撞 brain.py 的 120 秒逾時，think 失敗、loop 以 1 結束。**之後整台 Windows 當機**（09:21 NVMe 控制器重設＋WHEA 嚴重硬體錯誤，Intel Arc 140V 內顯；使用者說是先黑屏才動不了，比較像內顯被模型推論卡死），使用者 10-19 定「放棄跑本機模型」——這台不要再開 LM Studio 跑模型，demo 預設用假腦）；act 把答案寫進 `$AOS_WS/out/`、題目搬到 `done/`。
- 執行中狀態（`state`、`trace.log`、`plan`、`current`）在 `$AOS_STACK`（預設 `$AOS_WS/.aos/`）；工作區只放交辦的東西與成果（`inbox/`、`out/`、`done/`）；定義資料夾不被寫，所以同一個 agent 可同時被兩個工作區跑。agent-bob 的 fsm／think／act 在 `AOS_STACK` 沒設時報「沒設定 AOS_STACK」並非 0 結束。結果＝工作區內容；沒有別的結果通道。

### 已定值（10-19）

- `AOS_ENTRY` 預設 `.aos/exec`（**使用者已定**），環境變數可覆寫。
- `AOS_STACK`（**使用者已定**）：預設 `$AOS_WS/.aos/`，是被叫的那個程式自己的 stack。**它的子程式的 stack 由它自己訂**（使用者 10-19 定；例如給 `$AOS_STACK/think`、`$AOS_STACK/act`），aos 不管巢狀。demo 的 agent-bob 選擇讓 fsm／think／act 共用同一個。
- 工作區變數名 `AOS_WS`（**使用者已定**，10-19：一度改 `AOS_WD`，AI 提醒 WD 容易被當成 cwd 後定回 `AOS_WS`，與 proto8 N-55 同名；也考慮過 `AOS_TARGET`，但 TARGET 在 proto8 指程式那一邊）。
- `aos-exec DIR [WS]`：WS 省略＝`-`；`-`＝沿用 `$AOS_WS`，沒設才用 `.`（使用者 10-19 定）。
- 入口用 shell 檔；loop 的停止碼 10、`loop.json` 欄位（`run`／`max`）隨拍板點 1 (b)「agent-bob 現在的形狀就是標準」成為慣例（停止碼 10 跟 C-63 相撞，見 [CONFLICTS 4](CONFLICTS.md)）。
