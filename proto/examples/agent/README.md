# agent

跑這個會看到**一個 agent 就是一塊地上的一支 `aos run`**（裁決 M-01），而且它
**自己登記時鐘**、不借父地的鐘（裁決 S-02）：`aos daemon ls` 看得到它、`aos stop` 停得掉它。

用的是假後端 `echo:`，不打任何網路。要跟真的 LM Studio 玩看 [`proto/play-agent.sh`](../../play-agent.sh)。

## 怎麼跑

```sh
proto/examples/agent/run.sh
```

## 一圈長什麼樣

`main.aos.json` 四步，`act` 用 `select` 指回 `prep`，所以會繞圈：

```
prep ──► ask ──► wait ──► act ──┐
 ▲                              │ state/next.txt 寫 prep
 └──────────────────────────────┘   寫 end 就收工
```

- `prep`（inst）：`brain.py` 讀 `task.md` 跟到目前為止的紀錄，寫 `state/prompt.txt` 與 `state/req.json`，並清掉上一圈的 `state/answer.txt`。
- `ask`（inst）：`aos deliver ${llm_world} state/req.json --sender ${land}`——LLM 是**另一塊地**（裁決 F-02），要用就是投一筆請求給它。
- `wait`（await）：等 `state/answer.txt` 出現（三態：沒檔＝還沒好、有檔＝好了、有 `.status.json`＝壞了）。
- `act`（inst）：`brain.py` 看回話裡有沒有 `TOOL:` 那行。有就照白名單跑那條指令、把觀察記進 `state/transcript.md`、`state/next.txt` 寫 `prep` 再繞一圈；沒有就寫 `end` 收工（裁決 M-01：**agent 停於 LLM 不再呼叫工具**）。

假後端 `echo:` 把 prompt 原樣回，回話裡沒有 agent 自己寫的 `TOOL:` 行，所以第一圈就收工，`state/done.json` 會寫 `why: no_tool_call`。這正是要示範的停法。

## S-02 怎麼示範的

```sh
aos daemon add <agent 地> --every 200   # 只登記時鐘，狀態 pending（不當場開跑）
aos daemon start                        # daemon 看到 pending，替它起 aos run <地> --register
aos daemon ls                           # 看得到這個 agent（running / pid / 鐘）
aos stop <agent 地>                     # 投一封控制信，它在這一格跑完後停，寫 control_stop
```

`aos daemon add` 是原型自己補的子命令（見 FINDINGS「一塊地要跑起來要敲兩次」）：
`aos run --register` 會當場開跑，登不出「pending 等 daemon 來起」那一態，而 S-02 要的正是那一態。

## 地上有什麼

| 檔 | 幹嘛的 |
|---|---|
| `main.aos.json` | 那四步 |
| `brain.py` | agent 自己的腦：組 prompt、解回話、照白名單跑工具。只用標準庫，不 import `aosp` |
| `agent.json` | 圈數上限、工具白名單、tier、工具逾時 |
| `task.md` | 任務 |
| `work/` | agent 唯一動得到的東西 |
| `state/` | 每圈的 prompt／回話／紀錄（`state/rounds/<圈>/`）、`done.json`（為什麼收工） |
| `.aos/config.json` | `path` 白名單：只給 `proto/bin`（那支 `aos` 殼）跟 `/usr/bin`、`/bin`（裁決 S-04：第一版只靠 `path` 白名單） |
