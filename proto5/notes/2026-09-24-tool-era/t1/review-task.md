← [T1 報告](README.md)｜[工具大開發時代](../README.md)

# 審查任務書：第一波第 1 隊「骨架」（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel。** 可以跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_team_*.py'`）。用繁體中文、白話回答。

## 要審的（這一隊新增或改的）

- 規範：`proto5/spec/team/`（README、layout、roster、mail、tasks、ask、templates、route、cli、examples/）。這是**跨隊共用的契約**，第 2 隊（郵差、驗收、心跳）、第 4 隊（記憶與紀錄）照它做。
- 程式：`proto5/lib/aos_team_format.py`（讀驗、outbox 身分、信頭、原子寫）、`aos_team_task.py`（任務單狀態機、冪等）、`aos_team_ask.py`、`aos_team_requests.py`（申請登記表、權限）、`aos_team.py`（init/start/stop/ls/rm）、`aos_team_route.py`（門房）、`aos_team_task_cli.py`、`aos_team_ask_cli.py`、`aos_team_cli.py`＋`cli/aos-team`、`aos_agent_init.py` 的 `init_from_template`、`aos_agent_say.py` 的 `drop_new`。
- 工具包：`proto5/tools/task/`（handoff、board、review_result、ask_human；關在 bwrap 牢裡跑，只寫 `/work/outbox`、只讀 `/work/board`）。
- 模板：`proto5/templates/{lead,worker,reviewer,coder}/`。
- 測試：`proto5/lib/test/test_team_format.py`、`test_team_init.py`、`test_team_route.py`、`test_team_task_cli.py`。

## 對照來源

- 計畫與規格：`proto5/notes/2026-09-24-tool-era/plan.md`（第 1 隊的 7 條驗收）、`catalog.md`（T-team、T-route、T-handoff、T-ask、T-template）、`workflows-as-team.md`、`axes.md`（六軸）。
- 權限牆：`proto5/spec/agent/access.md`、`proto5/spec/aos-exec/aos-jail.md`、`proto5/lib/aos_agent_access.py`。
- 收件規則：`proto5/spec/agent/state.md` §4.1、`proto5/spec/aos-agent/cli-talk.md`（say 投檔）。
- workflows 的信件協議：`~/repo/workflows/flavors/multi-agent/workflows/inbox/PROTOCOL.md`（唯讀）。

## 請回答

1. **狀態機**：`aos_team_task.apply` 的轉移跟 `spec/team/tasks.md` 一致嗎？有沒有卡死（到不了結束狀態）或能繞過的路（舊 rev、不是負責人、審查子單回 DONE、改派中途的回報、審查結果回來時父單已改派）？冪等（同 src 回同一份後續動作）在郵差崩潰重跑的各個窗口真的成立嗎？
2. **身分與權限**：`read_outbox_file` 看資料夾認身分、`may_send` 看模板的 `may`、cancel/reassign 只准人或開單人、answer 只准人、review_result 只准子單負責人——有沒有漏？模型能不能透過工具參數冒名、寫到別人的 outbox、改到任務表？
3. **牢**：`init_from_template` 生的 `access.json`（ws／outbox／board 三個掛點、領隊與審查唯讀專案）會不會蓋到信任資料或讓工具碰到不該碰的（別人的 outbox、別人的家、團隊的 team.json）？工具包的 `config.json` 放在工具資料夾（信任資料）裡，模型改得到嗎？
4. **門房**：整句比對、兩條命中與否定詞落穿、例句全過才用；`do: tool` 的 `run` 與 `tool` 兩種會不會被 routes.json 用來跑任意程式（routes.json 只有人寫）？`fill` 的替換有沒有注入問題（群組值帶 `{}`、路徑）？
5. **init 重跑與崩潰**：生到一半崩了重跑能不能補完；已在的成員重跑只更新工具設定是否安全；`rm` 會不會留下壞名冊。
6. **共用格式**：`spec/team/` 對第 2 隊夠不夠用（郵差照它能不能做出不重投、不漏做的投遞；後續動作清單夠不夠）；有沒有自相矛盾或跟 plan.md 草稿不合、又沒說明的地方。
7. **測試**：有沒有該測沒測的（尤其崩潰窗口、權限、牢）。

## 格式

先列**必修**（會出錯、會繞過、跟規格矛盾），每條：哪個檔哪一行附近、問題、建議改法。再列**建議**。最後一段總評。不要超過 12 KB。
