# 原型共用協定（2026-08-30，調度者代裁）

← [dispatch](../README.md)｜隊 A [proto-A-machine](done/proto-A-machine.md)（已收線）｜隊 B [proto-B-agent](proto-B-agent.md)

兩隊唯一的共同契約。**改這份要經調度者**；隊內小裁決記在各自交接書尾的「隊長裁決」。
原則：**最小原型、先讓使用者用得起來、先不管意外與錯誤的邊緣狀況**（使用者 2026-08-30 明示）。

## 1. 世界版面：`<folder>/.aos/`

| 路徑 | 誰寫 | 內容 |
|---|---|---|
| `inbox/` | 任何生產者 | 投遞匣。一個檔＝一條指令。**先寫 `<name>.json.tmp` 再 `rename` 成 `<name>.json`** |
| `turn` | loop | 純文字，下一回合的編號（從 1 起） |
| `batch/<turn>/insts/<id>.json` | loop | 該回合匯聚到的指令（從 inbox **搬**過來） |
| `batch/<turn>/out/<id>.json` | loop | 該指令的結果 |
| `state.json` | loop | **loop state**（見 §4） |
| `agents/<name>/` | agent 自己 | agent 自身狀態（見隊 B 交接書）。loop 只讀 `agents/*/status.json` 鏡射進 `state.json` |

`.aos/` 不存在就由 `aos run` 或 `aos agent init` 建立（不需要獨立 init 指令）。

## 2. 指令 JSON（`inbox/*.json`）

```json
{
  "id": "選填，預設＝檔名去掉 .json",
  "argv": ["必填", "..."],
  "env": {"選填": "只加不減，疊在 loop 自己的環境上"},
  "cwd": "選填，相對於 <folder>，預設 <folder>",
  "stdin": "選填字串",
  "timeout_ms": 0
}
```

執行時一律 `chdir(cwd)`；`argv[0]` 走 PATH。環境額外注入 `AOS_FOLDER=<folder 絕對路徑>`、`AOS_TURN=<回合>`。

## 3. 結果 JSON（`batch/<turn>/out/<id>.json`）

```json
{"id": "...", "exit": 0, "signal": null, "stdout": "...", "stderr": "...", "started_at": "ISO8601", "ended_at": "ISO8601"}
```

`exit` 與 `signal` 二擇一非 null。逾時＝殺整個 process group，`signal` 填 9。

## 4. loop state（`.aos/state.json`）

```json
{
  "turn": 7,
  "phase": "running | idle",
  "running": [
    {"id": "agent-bob-7", "argv0": "aos", "pid": 12345, "started_at": "...", "status": "running | done", "exit": null}
  ],
  "agents": {
    "bob": {"status": "thinking", "detail": "…一行…", "updated_at": "...", "turn": 7}
  }
}
```

- 回合開始（匯聚完、fork 完）寫一次，回合結束再寫一次；整檔用 `.tmp`＋`rename` 換掉。
- `agents` 是 `agents/<name>/status.json` 的**原樣鏡射**（那個檔的欄位就是上面四個），loop 不理解內容。
- 沒有指令的回合＝ idle 回合：不建 `batch/<turn>/`，但 `state.json` 照寫、`turn` 照加。

## 5. 一回合

匯聚（`inbox/*.json` 全部搬進 `batch/<turn>/insts/`）→ 整批**並行** fork/exec → 全部等完 → 寫 `out/` → 更新 `state.json` → `turn` +1。

## 6. 指令面

| 指令 | 誰做 | 行為 |
|---|---|---|
| `aos run <folder> [--step N] [--interval MS]` | 隊 A | 連跑 N 回合（預設 1；`--step 0`＝無限），回合間隔 MS 毫秒（預設 100）。stdout 每回合印一行摘要 |
| `aos deliver <folder> <inst.json>` / `aos deliver <folder> -- <argv...>` | 隊 A | 把一條指令原子投遞進 `inbox/`（第二形式從 argv 現做一份） |
| `aos llm` | 隊 B | stdin 進 prompt（或 `--messages <json>`），stdout 出回覆文字。打 `$AOS_LLM_URL`（預設 `http://localhost:1234/v1`）、模型 `$AOS_LLM_MODEL`（預設 `qwen/qwen3.5-9b`） |
| `aos agent <init\|step\|say\|listen\|talk\|state>` | 隊 B | 見隊 B 交接書 |

## 7. 小專案與領地

| 小專案 | 隊 | 子命令 |
|---|---|---|
| `core/exec` | A | （純函式庫）POSIX 執行器 |
| `core/wire` | A | （純函式庫）指令／結果／state 的 JSON 序列化 |
| `core/loop` | A | `run`、`deliver` |
| `core/llm` | B | `llm` |
| `core/agent` | B | `agent` |

兩隊都會在 `core/CMakeLists.txt` 各加自己的 `add_subdirectory()` 行——隊 B rebase 時解這個一行衝突。
舊的 `core/inst`／`core/llms`／`core/tooljson`／`reference/` **兩隊都不碰**（不刪不改；`core/exec` 可以**抄** `core/inst/src/exec.cpp`、`spawn_prep.cpp`、`wait.cpp` 的內容）。
