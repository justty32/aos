# proto8/py/aos/apps/agent_fsm — agent-fsm 的四格（idle、think、wait、act）與它們共用的模組、hook 點宣告；每一隻 agent-fsm 的定義都從 `$AOS_HOME/lib/aos/apps/agent_fsm/` 跑這幾支

← [templates/agents/agent-fsm](../../../../templates/agents/agent-fsm/README.md)（範本：給人抄的定義）｜範本說明 [templates/docs/02](../../../../templates/docs/02-agent-fsm.md)｜hook 總文件 [hook/docs](../hook/docs/README.md)

11-24 從 agent-fsm 範本的夾裡搬來（使用者 11-23「3.a」：趁 templates 三分把 agent-fsm 執行期用的東西搬出 `templates/`、放進 `lib/`）。`install.py` 照舊把整個 `py/` 抄成 `lib/`，裝好在 `lib/aos/apps/agent_fsm/`。這幾支是**當腳本跑的格**，不是套件（沒有 `__init__.py`）：格把自己所在的夾放在 `sys.path` 最前面找共用模組，再經 `$AOS_HOME/lib` 找 `aos.*`。

| 檔 | 是什麼 |
|---|---|
| `idle.py` | idle 格：收信、排 queue，沒事就睡 |
| `brain.py` | think 格：組請求、寄給 llm kernel |
| `wait.py` | wait 格：等腦回信、接進 history |
| `act.py` | act 格：依序叫工具、結果接進 history |
| `cell_common.py`、`atomic_file.py`、`compact.py`、`llm_settings.py` | 四格共用：讀 history 與工具登記檔、原子寫檔、`/compact` 與 `/clear`、腦設定轉成請求信的 body（`defs check` 也照這份查） |
| `hooks.json` | 這幾格會發哪些 hook 點（宣告，只是參考；`aos-hook fire` 與引擎不讀它） |

**定義怎麼指到這裡**（動態連結；範本 `agent-fsm`、`std.fsm()` 編譯出來的、`reviewer`、`start-api` 的 ann 都是這種）：`fsm.json` 每格的 `argv` 寫 `["python3", {"$env": "AOS_HOME", "$path": "/lib/aos/apps/agent_fsm/idle.py"}]`，`interfaces.json` 的 `hooks` 寫 `{"$env": "AOS_HOME", "$path": "/lib/aos/apps/agent_fsm/hooks.json"}`。

**要一份靜態的**（整份抄走、自己改某一格）：把這九個檔抄進定義夾，`fsm.json` 的 `argv` 改成相對檔名（`["python3", "idle.py"]`），`interfaces.json` 的 `hooks` 那一項改成 `"hooks.json"`；只改一格也一樣（那支加它 import 的共用檔）。靜態的格照樣經 `$AOS_HOME/lib` import `aos.*`，lib 的介面變了它會壞。
