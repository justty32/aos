已完成 proto4-7，沒有 commit、push 或開 agent。

## 檔案清單

- CLI：[aos-agent](/home/lorkhan/repo/simple_tools/aos/proto4-7/aos-agent)、[aos-user](/home/lorkhan/repo/simple_tools/aos/proto4-7/aos-user)
- CLI 實作：[aos_agent_cli.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/aos_agent_cli.py)、[aos_user_cli.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/aos_user_cli.py)
- 核心：[state_machine.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/state_machine.py)、[mailbox.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/mailbox.py)、[agent_tools.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/agent_tools.py)、[common.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/common.py)
- 測試：[test_agent.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/test/test_agent.py)、[test_tools.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/test/test_tools.py)、[test_user.py](/home/lorkhan/repo/simple_tools/aos/proto4-7/test/test_user.py)
- 文件：[proto4-7/README.md](/home/lorkhan/repo/simple_tools/aos/proto4-7/README.md)
- 第 6 站：[make.sh](/home/lorkhan/repo/simple_tools/aos/playground/stations/6-agent/make.sh)、[playground/README.md](/home/lorkhan/repo/simple_tools/aos/playground/README.md)
- 遊樂場接線：[env.sh](/home/lorkhan/repo/simple_tools/aos/playground/env.sh)、[up.sh](/home/lorkhan/repo/simple_tools/aos/playground/up.sh)

## 規格落地

- 實作 `idle → ask → wait → act` 四格，一次呼叫只做一格。
- 完成退出碼 0／101／100／1／2、`--status` 與只刪 state 的 `--reset`。
- LLM 請求使用 `aos_py.llm_submit`，名稱為 `bob-qN-sN`；解析 `ok`、`text`、`raw.choices[].message.tool_calls`。
- 完成第 600 次等待逾時、20 格重送、安全網、五次錯誤 stuck、每題步數上限。
- 信件支援單封或陣列、整封接入記憶、搬至 `read/`；壞信產生 outbox 通知。
- outbox 獨立遞增，即使 reset 也不覆蓋舊回覆。
- 工具經 `aos_py.call`／`aos-exec` 執行，涵蓋壞參數、不存在、非零退出、stderr 前 500 字及輸出截斷。
- 完成四種文字 tool call 救回入口。
- `aos-user` 完成 `say`、`listen`、`talk`、`status`、`new`；`new` 會建立 echo、sh、inst.json 與完整骨架。
- 第 6 站可建立 bob、加入 kernel、say/listen/talk，並試玩步數上限與 daemon 停機狀態。
- 所有 Python／README／測試單檔均低於 300 行；README 112 行。

## 驗證

- `python3 -m unittest discover -s proto4-7/test`：**28/28 通過**
- `cmake --build --preset default`：通過
- `ctest --preset default`：**8/8 通過**
- Shell 語法與 `git diff --check`：通過
- 未留下測試用 `.req.json`

沒有改動規格。依任務要求未打真 LLM，也未修改 `proto4-3`～`proto4-6` 或 `wf/`。