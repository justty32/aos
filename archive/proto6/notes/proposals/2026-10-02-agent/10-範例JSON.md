# 範例 JSON：一次看完所有新格式

← [提案入口](README.md)｜上一份：[待決問題](09-待決問題.md)

新的只有四種檔：`config/agent.json`、`config/tools.json`、信（六個 `type`）、`public/status.json`。其餘（`tasks.json`、daemon 設定、inst、紀錄）都是現有格式。kernel 那三種信（summary、grant、request）的範例在 [07](07-kernel介面.md)。

## `config/agent.json`

```json
{"_metainfo": {"_type": "aos-agent", "_version": 1},
 "model": "deepseek-chat",
 "params": {"temperature": 0.2},
 "history_max_tokens": 32000,
 "history_keep_rounds": 3,
 "self_wake": false,
 "system": "config/system.md",
 "notes": "state/notes.md",
 "tools": ["config/tools.json"],
 "contacts": "config/contacts.json"}
```

`self_wake`：沒有 kernel 時設 `true`，`remember` 有 `continue` 就自己 `aos-ctl wake`；有 kernel 就 `false`，交給 summary 的 `ready`。

端點與金鑰不在這裡，在 `.aos/inst.json` 的 `envs` 用 `$env`：

```json
{"argv": ["aos-tick"],
 "envs": {"AOS_LLM_URL": {"$env": "LITELLM_URL"},
          "AOS_LLM_KEY": {"$env": "LITELLM_KEY"},
          "AOS_LLM_TIMEOUT_MS": "120000"}}
```

## `config/tools.json`

```json
[{"type": "function",
  "function": {"name": "wc", "description": "算一個檔的字數",
               "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
  "_inst": {"argv": ["tools/wc.sh"]}},
 {"type": "function",
  "function": {"name": "note", "description": "寫一句到長期記憶", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}}},
  "_inst": {"argv": ["tools/note.sh"]}},
 {"type": "function",
  "function": {"name": "say", "description": "寄信給通訊錄裡的人", "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "text": {"type": "string"}}}},
  "_inst": {"argv": ["tools/say.sh"]}}]
```

`_inst` 只寫 `argv`（可加 `envs`）。`act` 補成完整 inst 寫進 `work/tools/<call_id>/inst.json`：`cwd`＝agent 家的絕對路徑，`stdin`／`stdout`／`exit`＝呼叫目錄裡 `args.json`／`out`／`exit` 的**絕對路徑**（inst 的路徑欄相對 `cwd`，寫相對名會找到 agent 家而不是呼叫目錄），再 `aos-exec work/tools/<call_id>`。完整例子在 [04](04-一格做什麼.md)。`say.sh` 裡就是 `aos-mq send $(通訊錄查 to) <信>`。

## 信

```json
{"type": "say", "version": 1,
 "from": "~", "reply_door": "/srv/aos/doors/human/s",
 "text": "算一下 x.md 的字數", "ref": "h-1"}
```

回信：

```json
{"type": "result", "version": 1,
 "from": "agents/alice", "reply_door": "/srv/team-a/agents/alice/doors/s",
 "text": "x.md 共 1234 字（含標點）", "ref": "h-1"}
```

`type` 六種共用一份 schema：agent 之間 `say`／`result`／`task`，跟 kernel 之間 `summary`／`grant`／`request`。

## `public/status.json`（`remember` 每格重寫，給人看）

```json
{"version": 1, "seq": 42, "state": "working",
 "last_llm_seq": 41, "llm_calls": 17, "tokens": {"prompt": 51230, "completion": 8120},
 "pending_tool_calls": 1, "wants_human": false, "note": "等 bob 回 x.md 的來源"}
```

`state`：`idle`（沒事）、`working`（有 `continue`）、`waiting`（寄了 `task` 等回）、`blocked`（LLM 連續失敗）。kernel 不讀它（它收 summary），人與除錯用。

## `config/contacts.json`

```json
{"~": "/srv/aos/doors/human/s",
 "bob": "/srv/team-a/agents/bob/doors/s",
 "team": "/srv/team-a/doors/team/s"}
```

只是 agent 自己的通訊錄；kernel 的門不用寫，環境變數 `AOS_DAEMON_MQ_KERNEL` 就有。daemon 的 `peers` 模組使用者說先不做。

## `state/grant.json`、`state/usage.json`

`inbox` 把最新一封 grant 原樣存成 `state/grant.json`；`remember` 累用量：

```json
{"window_start_seq": 1200, "window_ticks": 10, "llm_calls": 3, "llm_tokens": 7210}
```

`think` 看 `grant.llm.calls` 減 `usage.llm_calls`（同一個 `window_start_seq` 才算）；用完就寫 `tasks-blocked` `{"kinds":["llm"]}`。

## kernel 政策檔（配合式檢查；agent 的 `tasks.json` 只把 `after_task` 這個掛點 `$ref` 過去）

```json
{"think": [{"id": "budget", "argv": ["/srv/team-a/bin/check-budget"]}],
 "act":   [{"id": "meter",  "argv": ["/srv/team-a/bin/meter"]}]}
```

agent 那邊：`"hooks": {"after_task": {"$ref": "/srv/team-a/policy/after-task.json"}, "after_all": [summary, git]}`。掛在 `after_task.think` 才擋得到**這一格**的 `llm`（`before_kind.llm` 寫的擋板只擋下一項）。`after_all` 留在本地，summary 不會被換掉。

## 第 0 階段回聲 agent 的 `tasks.json`（零新程式、沒有 kernel）

```json
{"tasks": [
  {"id": "inbox", "argv": ["sh", "-c",
    "aos-mq take \"$AOS_DAEMON_MQ_ECHO\" > work/in.jsonl; [ -s work/in.jsonl ] || : > .aos/tick/tasks-blocked"]},
  {"id": "reply", "argv": ["sh", "-c",
    "while read -r m; do d=$(printf %s \"$m\" | jq -r .reply_door); printf %s \"$m\" | jq '{type:\"result\",version:1,from:env.AOS_DAEMON_INST,text:.text,ref:.ref}' | aos-mq send \"$d\" -; done < work/in.jsonl"]}]}
```

daemon 掛狀態模組、狀態檔預置這項 `paused:true`，靠信叫醒（暫停中跑一格、跑完照樣暫停）；沒信那格只跑 `inbox` 就擋掉。
