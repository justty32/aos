# 唯讀審查任務書（W3-1 收尾，2026-09-25）

你是唯讀審查員。**不要改任何檔**。用中文白話寫報告。

## 審什麼

aos proto5 的兩個功能＋今天的一個翻案：

1. **T-spawn（成員生新成員）**：`proto5/lib/aos_team_spawn.py`、`proto5/tools/task/spawn_member`、規格 `proto5/spec/team/spawn.md`。
   今天翻案（使用者拍板）：**預設開、預設不用人批**，每個成員可以在名冊上各自設「能不能生、能生哪些、要不要人批」。
   相關改動：`proto5/lib/aos_team_format.py`（`_spawn_cfg`、`_member_spawn`、`builtin_templates`、`spawn_policy`、`member_may`、`may_send`）、
   `proto5/lib/aos_team.py`（`member_context`）、`proto5/lib/aos_agent_init.py`（`_spawn_tool`、`team_config`）、`proto5/spec/team/roster.md`。
   看 `git diff 60e4b81..HEAD -- proto5/lib proto5/tools proto5/spec` 就是今天的改動。
2. **T-toolsmith（工人造工具）**：`proto5/lib/aos_team_toolsmith.py`、`proto5/tools/task/tool_draft`、規格 `proto5/spec/team/toolsmith.md`。這條沒改，還是要人批。
3. 測試：`proto5/lib/test/test_team_spawn.py`、`proto5/lib/test/test_team_toolsmith.py`。

## 重點（照優先順序）

1. **逃逸**：「不用人批」以後，模型（成員）能不能用 spawn 拿到比自己大的權限？要一定擋住的：新成員權限（模板 `may`）超過申請者、`mail_to` 超過申請者、非內建模板（路徑、`..`）、超過 `limits.max_members`、夾帶 `mounts`／`tools`／`model`、新成員的生成員設定比申請者寬（例：申請者要人批，生出來的不用批；申請者只能生 importer，生出來的 lead 能生全部）、成員層被關（`spawn: false`）還能生、工人偽造申請。也看有沒有**連鎖**（A 生 B、B 再生 C）繞過任一條的路。
2. **郵差裡直接生**（`_auto_finish`→`realize`：改 team.json、跑 `aos-team init`、`aos-agent start`）：崩在中間重來會不會重複生、漏回信、名冊寫壞；會不會卡住郵差；`records` 裡 `q` 是 `null` 的紀錄在 `state()`、人數計算、`describe` 有沒有算錯。
3. **toolsmith**：牢（bwrap）、快照 sha256、逾時、名字撞內建工具、測過後換程式——有沒有洞。
4. 規格與程式對不對得上；錯字、死程式碼。

## 產出格式

```
## 必修（會造成逃逸、資料壞、測試會漏的 bug）
- [檔:行] 現象 → 怎麼重現 → 建議修法
## 建議（不修也不會壞）
- ...
## 沒問題的（一句話列你確認過的重點）
```

每條要有檔名與行號。沒把握的寫「沒把握」，不要猜成必修。
