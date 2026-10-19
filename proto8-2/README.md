# proto8-2 — 從 proto8 長出來的第二輪

← [proto8](../proto8/README.md)｜原話 → [thinking/ideas](thinking/2026-10-19-ideas.md)｜討論稿 → [thinking/entry](thinking/2026-10-19-entry.md)

**2026-10-19 開。** 使用者原話：「我這邊想開proto8-2，我有些新想法。」

## 與 proto8 的關係

從 proto8 長出來。proto8 的[概念](../proto8/CONCEPTS.md)與[規範](../proto8/NORMS.md)照舊有效；proto8-2 放新想法。

## 現況

第一個想法（資料夾＝程式、入口＝`AOS_ENTRY`、`aos-exec workspace agent-bob`）原話在 [thinking/ideas § 1](thinking/2026-10-19-ideas.md)，討論稿（三分鐘看懂、邊緣、跟 proto8 對照、拍板點）在 [thinking/entry](thinking/2026-10-19-entry.md)，等使用者答拍板點。方向、範圍、是否接替 proto8 都還沒定。

## 原型怎麼跑（10-19）

資料夾＝程式；入口＝資料夾裡 `$AOS_ENTRY`（預設 `.aos/exec`）指的可執行檔。在 WSL／Linux：

```
sh proto8-2/demo/run.sh                       # 建暫時工作區、放一題、跑 agent-bob、印工作區內容
python3 -m unittest discover -s proto8-2/tests
proto8-2/bin/aos-exec <工作區> proto8-2/demo/agent-bob    # 自己跑
```

- `bin/aos-exec WS DIR [args...]`：WS 轉絕對路徑設成 `AOS_WD`；`AOS_STACK` 沒設就用 `$AOS_WD/.aos/`（轉絕對路徑、不存在就建），有設就沿用，都 export 給子程式；`cd DIR`、exec 入口；args／stdin 原樣透傳；把自己的 `bin/` 放進 PATH，所以入口裡直接寫 `aos-loop`、`aos-exec`。入口缺／不可執行、工作區或 DIR 不存在 → 結束碼 2 並印原因。
- `bin/aos-loop loop.json`（Python 純標準庫）：`{"run": 子資料夾, "max": 最多幾圈}`，每圈 `aos-exec - <run>`。子程式結束碼 0＝下一圈、**10＝要求停（loop 以 0 結束）**、其他非 0＝失敗（loop 以原碼結束）；跑滿 max 圈也以 0 結束（stderr 提醒）。
- `demo/agent-bob`：入口 `aos-loop loop.json` → 每圈 `fsm/`；fsm 讀 `$AOS_STACK/state`（預設 idle）執行同名子資料夾 `idle|think|act`，成功才寫下一個狀態（idle→think→act→idle）。idle 在 inbox 空時回 10 讓 loop 停。think 把答案草稿寫進 `$AOS_STACK/plan`，預設假腦，設 `AOS_BRAIN_URL`（OpenAI 相容 base URL，另可設 `AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`）改問真模型；act 把答案寫進 `$AOS_WD/out/`、題目搬到 `done/`。
- 執行中狀態（`state`、`trace.log`、`plan`、`current`）在 `$AOS_STACK`（預設 `$AOS_WD/.aos/`）；工作區只放交辦的東西與成果（`inbox/`、`out/`、`done/`）；定義資料夾不被寫，所以同一個 agent 可同時被兩個工作區跑。agent-bob 的 fsm／think／act 在 `AOS_STACK` 沒設時報「沒設定 AOS_STACK」並非 0 結束。結果＝工作區內容；沒有別的結果通道。

### 暫定值（等使用者拍板，對應 [entry 討論稿 § 五](thinking/2026-10-19-entry.md)）

- `AOS_ENTRY` 預設 `.aos/exec`（**使用者已定**），環境變數可覆寫。
- `AOS_STACK`（**使用者已定**）：預設 `$AOS_WD/.aos/`。巢狀的子程式共用同一個 `AOS_STACK`（暫定）。
- 工作區變數名 `AOS_WD`（**使用者已定**，10-19「那還是乖乖用AOS_WD好了」；考慮過 `AOS_TARGET`，但 TARGET 在 proto8 指程式那一邊）。
- `aos-exec` 的 WS 給 `-`＝沿用現有 `AOS_WD`。
- 入口用 shell 檔；loop 的停止碼 10、`loop.json` 欄位（`run`／`max`）是原型自訂。
