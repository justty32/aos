---
name: aos
description: 操作 aos（proto8 的資料夾程式）的工具 aos-ai，含概念速成。Use when the user asks to spawn/create an aos agent, give an aos agent a question/task, run aos-exec or an agent once, check aos loop/daemon/fsm state or trace, start/stop a background agent, read an aos agent's answer or error line, generate aos JSON (inst/loop.json/fsm.json/daemon.json/_metainfo/tool.json) or scaffold a tool/fsm cell/function folder, or explain aos concepts like AOS_WS/AOS_ENTRY/AOS_STACK/AOS_CF/AOS_CD/AOS_CO（「起一隻 agent」「丟題給 agent」「aos-exec 跑一次」「看 agent 狀態」「生成 loop.json」「加一個工具」「WS／STACK 是什麼」）。
---

# aos：用 aos-ai 操作 agent

`aos-ai` 在 aos repo 的 `proto8/ai_tools/bin/aos-ai`（不在 PATH 就用完整路徑）。**每個命令在 stdout 印一行 JSON**；
它自己的錯是 stderr 一行 `aos-ai: 代號 原因（下一步：…）`、退 1——照「下一步」做就好。不必讀 NORMS。

## 先知道三件事

- **只在一個工作資料夾（root）裡動**：`--root DIR`（放在命令前面），沒給用 `$AOS_AI_ROOT`，再沒有用 cwd。root 外面的東西不寫。
- **agent＝資料夾**：`spawn` 把範本（預設 `agent-dan`：會用工具的問答 agent）複製到 `root/agents/<名>/agent/`，
  工作區是 `root/agents/<名>/ws/`（題目 `new/`、做到一半 `cur/`、答案 `out/`、做完的題目 `done/`；執行狀態在 `ws/.stack/`）。
- **腦**：沒設 `AOS_BRAIN_URL`＝假腦（回 `FAKE ANSWER to: …`，測流程用）。真腦：`AOS_BRAIN_URL=http://localhost:4000/v1`（家機 LiteLLM）。

## 最常用的一串

```bash
aos-ai --root ~/code/try/x spawn helper                 # 起一隻（--from 範本、--tool ask_agent 加工具）
aos-ai --root ~/code/try/x ask helper --id q1 '17*23 等於多少'   # 丟題（文字加引號，zsh 會吃 *；是 - 就從 stdin 讀）
aos-ai --root ~/code/try/x run helper --timeout 120      # 前景跑到題目做完，回 answers、errors、hint
aos-ai --root ~/code/try/x answer helper q1              # 讀答案
```

`run` 的 JSON：`ok`、`code`（0＝好）、`answers[{id,text,path}]`、`waiting`（還沒做完的題）、`fsm_state`、
`errors[{prog,code,reason}]`（各層 stderr 的 `程式名: 代號 原因` 拆好的）、`hint`。**agent 失敗 aos-ai 照樣退 0**，看 `ok`。
失敗後 agent 停在出錯那格（例 `fsm_state: think`）；修好原因再 `run` 一次就從同一題接著做。

## 其他命令

| 命令 | 做什麼 |
|---|---|
| `templates` | 列範本與可加的工具 |
| `status [名]` | 一隻的詳細狀態（狀態機格、各資料夾的題、最近一次 run、背景列、trace 尾巴、可改的設定檔）；不給名字＝列全部 |
| `trace 名 [-n N]`／`history 名 [-n N]` | 狀態機每格紀錄／跟腦的對話（工具呼叫看這裡） |
| `start 名 [--interval-ms N]` | 交給背景（root 一個 aos-daemon，沒起就起），之後 `ask` 的題它會自己做 |
| `wait 名 題名 [--timeout 秒]` | 等背景做完那題、回答案 |
| `stop 名`／`daemon down`／`daemon status` | 停一隻／停整個背景／看背景 |
| `exec [--ws WS] 目標 [參數...]` | 直接 `aos-exec` 跑一次任何資料夾程式，回 `code`、`stdout`、`errors` |
| `edit 名 檔 ...` | 改設定檔的接口（交給 `$AOS_AI_JSON_EDITOR`；沒接時直接用你的編輯工具改 `status` 給的路徑） |
| `doctor` | 檢查程式建好沒、腦連不連得到 |
| `make …`／`explain …` | 見上面兩節 |

## 概念：先查再猜

**不懂 aos 的詞先查，別猜**：同資料夾的 [concepts.md](concepts.md) 是概念速成（每節一句白話、最小範例、常見錯、條號），
也能 `aos-ai explain <概念>` 印一節（`aos-ai explain` 列節名：env、AOS_ENTRY、AOS_WS、AOS_STACK、AOS_CF、AOS_CD、AOS_CO、entry、dotenv、inst、loop、fsm、daemon、window、exit、directive、inline、metainfo、agent、tool、heap）。
**要具體值**：`aos-ai explain --here [目標] [--ws WS]` 算出「現在 `aos-exec 目標`」會讀哪些 `.env`、挑到哪個入口、是哪一種（可執行檔／單子／argv／轉向）、
入口看到的 `AOS_WS`／`AOS_STACK`／`AOS_ENTRY`／`AOS_CF`／`AOS_CD`／`AOS_CO`（照規則模擬、不真的跑）。

## 生成 JSON 與骨架

先驗形狀再輸出；加 `--out 檔` 原子寫入（root 裡、已有的不蓋，要蓋加 `--force`），有 aos-json 就順手 `aos-json check`；輸出附 `notes`（每個欄位一句概念，`--no-notes` 關掉）。
**改既有的 JSON 用 aos-json**（`aos-json set 檔#/指標 值`），aos-ai 只生成。

```bash
aos-ai make inst --argv 'python3 brain.py' --timeout-ms 120000 --stdout '{"$env":"AOS_STACK","$path":"plan.txt"}'
aos-ai make loop --exec fsm.json --max 40 --out w/loop.json            # 自動帶 _entry，aos-exec w/loop.json 就能跑
aos-ai make fsm --cell 'idle=idle' --cell 'think={"argv":["python3","brain.py"]}' --cell 'act=act' --out w/fsm.json
#   --cell 名=exec（JSON 或字串）照順序接成環，--next 名=下一格 改；--start 改起點
aos-ai make daemon --loop 'bob={"exec":"agent-bob","max":1}' --interval-ms 500
aos-ai make metainfo --summary '排版 .py' --time-ms '{"val":300,"max":5000}' --resource cpu --side-effect true
aos-ai make tool_json --description '算算式' --param 'expr:string:要算的式子:required'
aos-ai make tool helper shout --description '轉大寫' --param 'text:string::required'   # agents/helper/agent/tools/shout/
aos-ai make cell helper log --exec '{"argv":["sh","-c","date >> $AOS_STACK/log.txt"]}' --after act   # 插在 act 後面
aos-ai make cell helper check --dir --after think       # 起一個格資料夾（_entry 骨架）
aos-ai make func funcs/hello --summary '打招呼'          # 函數資料夾：_entry＋_metainfo
```

每種都有 `--spec '{整份 JSON}'` 與 `--set key=值` 可以直接給內容。

## 常見錯怎麼辦

- `CommandMissing`：impls 沒建 → 在 repo 根照 `wf/workflows/testing.md` 建 `proto8/impls`。
- `BrainFailed`：腦連不上 → 檢查 `AOS_BRAIN_URL`，或拿掉用假腦。
- `AgentBusy`：背景正在跑那隻 → `wait`，或先 `stop`。
- `AgentExists`／`QuestionExists`：換名字或直接 `ask`。
- `SpecBad`：生成的 JSON 形狀不對，原因那句說哪一格；`FileExists`：換 `--out` 或加 `--force`。

## 不要做

- 不要刪 `agents/`、`ws/` 底下的東西（`done/` 只進不出，清理是人的事）；不要 git push。
- 不要同時用 `run` 和 `start` 跑同一隻（aos-ai 會擋）。
