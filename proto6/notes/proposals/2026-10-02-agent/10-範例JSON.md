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
  "_inst": {"argv": ["tools/wc.sh"], "stdin": "args.json", "stdout": "out", "exit": "exit"}},
 {"type": "function",
  "function": {"name": "note", "description": "寫一句到長期記憶", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}}},
  "_inst": {"argv": ["tools/note.sh"], "stdin": "args.json", "stdout": "out", "exit": "exit"}},
 {"type": "function",
  "function": {"name": "say", "description": "寄信給通訊錄裡的人", "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "text": {"type": "string"}}}},
  "_inst": {"argv": ["tools/say.sh"], "stdin": "args.json", "stdout": "out", "exit": "exit"}}]
```

`act` 把 `_inst` 寫成 `work/tools/<call_id>/inst.json`（補 `_metainfo`、`cwd` 指回 agent 資料夾）再 `aos-exec work/tools/<call_id>`。`say.sh` 裡就是 `aos-mq send $(通訊錄查 to) <信>`。

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

## kernel 政策檔 `agent-hooks.json`（強制額度時，agent 的 `tasks.json` 用 `$ref` 掛）

```json
{"before_kind": {"llm": [{"id": "budget", "argv": ["/srv/kernel/bin/check-budget"]}]},
 "after_kind":  {"llm": [{"id": "meter",  "argv": ["/srv/kernel/bin/meter"]}]},
 "after_all":   [{"id": "git", "argv": ["sh", "-c", "git add -A state public && git commit -qm tick || true"]}]}
```

## 第 0 階段回聲 agent 的 `tasks.json`（零新程式、沒有 kernel）

```json
{"tasks": [
  {"id": "inbox", "argv": ["sh", "-c",
    "aos-mq take \"$AOS_DAEMON_MQ_ECHO\" > work/in.jsonl; [ -s work/in.jsonl ] || : > .aos/tick/tasks-blocked"]},
  {"id": "reply", "argv": ["sh", "-c",
    "while read -r m; do d=$(printf %s \"$m\" | jq -r .reply_door); printf %s \"$m\" | jq '{type:\"result\",version:1,from:env.AOS_DAEMON_INST,text:.text,ref:.ref}' | aos-mq send \"$d\" -; done < work/in.jsonl"]}]}
```

daemon 那項 `interval_ms` 設一小時，靠信叫醒；沒信那格只跑 `inbox` 就擋掉。
