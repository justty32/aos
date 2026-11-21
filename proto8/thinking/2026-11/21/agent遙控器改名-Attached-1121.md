agent 遙控器的類別 `aos.py.agent.Agent` 改名 `Attached`，跟寫定義的 `defs.Agent` 分開；不留舊名，`defs.Agent` 沒動。

← [2026-11-21](README.md)｜出處 [aos-pylib-plan-1120/01](../20/aos-pylib-plan-1120/01-程式庫長相.md)「邊緣」第四條（同名不同物）｜線 `top-1121-attached`

## 使用者原話（11-21，逐字）

- 頂層用選項框問「要不要改名分開？」，他選「改遙控器那個」（`defs.Agent` 留著，遙控器的類別換名字）。
- 頂層給了 `Remote`／`Handle`／`Live` 幾個方向後，他說：「aos.py.agent.Attacher?」
- 頂層指出 `Attacher` 字面是「去接上的那個」，而 `agent.attach("ann")` 回來的是「已經接上的」，同一路還有 `Attached`；並說沒查過除了 `attach` 還有哪裡會回這個類別。他答：「那就Attached」。

## 改了什麼

| 檔 | 改的 |
|---|---|
| `py/aos/py/agent/__init__.py` | `class Agent` → `class Attached`；`attach()` 回 `Attached(...)`；檔頭示意碼那行「defs.Agent（定義）跟下面的 Agent（遙控器）同名不同物」改成「遙控器 a 的類別叫 Attached（agent.attach 回的），寫定義的是 defs.Agent」；檔頭補一行改名出處；類別說明補「接上＝記住名字與 daemon，不查那隻在不在」 |
| `py/aos/agent_spec_agent.py` | 檔頭「跟把手 aos.py.agent.Agent（活的那隻）同名不同物」改成「活的那隻的遙控器是另一個類別 aos.py.agent.Attached（11-21 改名分開）」 |
| `py/README.md` | 「`defs.Agent` 跟遙控器類別 `aos.py.agent.Agent` 同名不同物」改成遙控器類別叫 `Attached`、出處 |
| `templates/agent-python/README.md` | 英文那句「same name, different things」改成 the handle … is a different class, `aos.py.agent.Attached`；「變數別取名 `agent`」那半句留著（模組名還是會被蓋） |
| `py/tests/test_aos_py.py` | 加 `test_attach_gives_an_attached`：`type(agent.attach(...)) is agent.Attached`、`agent` 模組上沒有 `Agent` |

沒找到要改的：知識庫 `knowledge/`、教學 `docs/tutorial`、`templates/docs`、`py/docs`、`aos-gdb` README 都只說「遙控器 `a = agent.attach(名)`」，沒寫類別名。`proto8/docs/` 條文沒有提到這個類別名，沒有要補的字。`thinking/` 舊紀錄（含規劃稿 01 第 141 行）不回頭改。

## 除了 `agent.attach(...)`，還有哪裡會回這個類別（查實，只列事實）

- **建它的只有一處**：`aos.py.agent.attach(name, daemon=None)`。整個 `py/`（含 `aos/py`、`aos/gdb`、`apps/gdb`、`apps/eca`、`tools/`）沒有別的地方 `Attached(...)`。
- **經過 `agent.attach` 拿到它的**：`aos-gdb NAME` 開的 REPL 裡放好的 `a`（`apps/gdb/__init__.py` 第 70 行就是 `agent.attach(...)`）。
- **長得像但回的不是它**：
  - `aos.py.breakpoint.attach(name, daemon)`＝`agent.attach(name, daemon).bp`，回的是斷點（`aos.gdb.Breakpoints`），中間那個 `Attached` 用完就丟。
  - `aos.py.daemon_ctl.attach(daemon)` 回的是通用代理 `_shell.Proxy`（綁好 `--daemon`），不是這個類別，也沒有自己的類別名。
  - 遙控器上的 `a.ctl`、`a.tools`…是 `_shell.Proxy`；`a.look` 是 `aos.gdb.StackLook`；`a.bp` 是 `Breakpoints`。
- **生子 agent、fork、工廠函數**：`aos.py` 底下沒有。起一隻 agent 是 `agent.ctl.add(...)`＝跑 `aos-agent ctl add`，回的是那條指令的輸出（印出的 stack 路徑字串），不回遙控器；要遙控器得再 `agent.attach(名)`。`aos.py.kernel` 只有寫 kernel 定義的 `defs`，沒有 attach。
- **跟名字有關的兩個事實**：
  1. `agent.attach` 不跑指令、不查那隻在不在、有沒有掛上 daemon；拿一個不存在的名字也照樣回 `Attached`，第一條指令才會失敗。
  2. 知識庫的用語裡「attach」另有一個意思：`knowledge/aos/cli/agent.json` 把 `aos-agent ctl add` 寫成「ctl add: attach one agent」（把一隻 agent 掛上 daemon、建 stack）。也就是同一個字在指令那邊是「掛上 daemon」、在 Python 這邊是「遙控器接上那隻」；而 `ctl add`（指令那邊的 attach）不回 `Attached`。

## 同模組其他名字

- `__repr__` 印的是 `<aos-agent --daemon D --target 名>`，錯誤訊息用 `<aos-agent …>` 與 `a.bp`、`a.look`，都沒帶類別名，不用改。
- 沒改、列著：模組層找不到名字時的錯誤訊息列的是「attach, say, defs」，沒列 `Attached`（類別本來就不是給人直接建的，照舊）。`aos.py` 入口檔頭說「agent＝aos-agent 的薄殼與遙控器」，沒寫類別名，沒動。`aos/apps/agent/common.py` 另有一個內部的 `class Agent`（指令那邊用的），跟這次無關，沒動。

## 測試

乾淨複本 `~/.aos/scratch/top-1121-attached/`（`base`＝HEAD `dff53b667` 原樣、`mine`＝疊這次的檔），各自 `install.py`、清掉 `AOS_*` 後逐夾 `python3 -m unittest discover`，兩份先後跑（不同時）。

- 相關夾：`py/tests` 744 → 745（多的是新測試）、`py/tests/apps/gdb` 66、`templates/tests` 30，兩邊都過。
- 全套 78 夾：base 3,137 支、mine 3,138 支；逐夾結束碼完全相同。兩邊都紅的是 `py/tests/apps/eca`（3 failures、1 error）、`py/tests/apps/feedback`（18 errors），原樣那份一樣，跟這次無關；`image-move-check`、`templates/kernel/tests` 不是 unittest（0 支、退 5）。
