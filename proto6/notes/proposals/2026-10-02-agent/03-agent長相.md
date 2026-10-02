# agent 的長相：資料夾、身分、對應零件

← [提案入口](README.md)｜上一份：[方案取捨](02-方案取捨.md)｜下一份：[一格做什麼](04-一格做什麼.md)

**一句話：agent 就是一個工作資料夾，`tasks.json` 寫成「agent 的一步」，由某個 daemon 的一項定期叫 `aos-tick` 跑。** tick 與 daemon 程式裡不出現「agent」這個詞，它只是 T-10 的「其他任務」。

## 資料夾布局（沿 P-200 的 `config/`、`state/`、`work/`、`public/`）

```text
/srv/agents/alice/              ← 資料夾路徑就是身分
  .aos/inst.json                ← daemon 叫它用：{"argv":["aos-tick"]}
  .aos/tasks.json               ← 這個 agent 的一步（見下）
  .aos/tick/current|last/       ← 核心紀錄（kernel 從這裡讀 seq、各項結束碼）
  config/agent.json             ← 模型、端點、上限；金鑰用 $env 拿
  config/system.md              ← 人格與工作原則（模型改不到）
  config/tools.json             ← 工具清單＝inst 範本
  state/history.jsonl           ← 對話記憶（一行一則 message）
  state/notes.md                ← 長期記憶
  state/inbox/                  ← 收到的信落檔（take 之後）
  work/                         ← 本格接力檔：request.json、response.json、tools/<id>/
  public/status.json            ← 給別人看的狀態（kernel、主管、人）
  doors/                        ← 這個 agent 的門（socket）放這；資料夾權限＝誰能寄
```

## 需求 → 現有零件對照

| agent 需要 | 用什麼 | 要新造嗎 |
|---|---|---|
| 身分 | 資料夾絕對路徑；daemon 帳號模組指定的 Linux 帳號 | 不用 |
| 定期跑、一步一格 | daemon 一項 inst → `aos-exec` → `aos-tick` | 不用 |
| 狀態 | `.aos/tick/last/record.json`（seq、結束碼）＋ `state/`、`public/status.json` | 只定檔案格式 |
| 收信 | `aos-mq take $AOS_DAEMON_MQ_<自己的門>` | 不用 |
| 寄信 | `aos-mq send <對方門的路徑> <JSON>` | 不用；信的欄位要約定 |
| 睡 | 格做完就結束；`interval_ms` 很長，不自醒 | 不用 |
| 醒 | kernel `aos-ctl wake`；或有人寄信到它訂的門 → daemon 合併叫醒 | 不用 |
| 連續做幾步 | summary 寫 `ready:true` 讓 kernel 叫；沒 kernel 時 `aos-ctl wake --keep-schedule` 叫自己 | 不用 |
| 跟 kernel 講 | `after_all` 寄 summary 到 `$AOS_DAEMON_MQ_KERNEL`；收 grant 看額度（[07](07-kernel介面.md)） | 新造 `aos-agent summary` |
| 硬停 | 人放 `.aos/tick-blocked` | 不用 |
| 權限 | 資料夾權限＋帳號（T-08）；門的資料夾決定誰能寄 | 不用 |
| 資源框 | daemon 收屍模組（每項一框、可設上限） | 不用 |
| 版本／回溯 | hooks `after_all` 跑 git | 不用 |
| 呼叫 LLM | `aos-llm`：讀 request、寫 response | **新造** |
| 組 context、解回應、做工具、寫記憶 | `aos-agent inbox`／`think`／`act`／`remember`／`summary`（一支程式五個子命令） | **新造** |

## `tasks.json`（一步）

```json
{"_metainfo": {"_type": "aos-tasks", "_version": 1},
 "stderr": {"$opt": "append", "$val": "state/log/err.log"},
 "tasks": [
   {"id": "inbox",    "kind": "agent", "argv": ["aos-agent", "inbox"]},
   {"id": "think",    "kind": "agent", "argv": ["aos-agent", "think"]},
   {"id": "llm",      "kind": "llm",   "argv": ["aos-llm", "work/request.json", "work/response.json"]},
   {"id": "act",      "kind": "agent", "argv": ["aos-agent", "act"]},
   {"id": "remember", "kind": "agent", "argv": ["aos-agent", "remember"]}],
 "hooks": {
   "after_all": [{"id": "summary", "argv": ["aos-agent", "summary"]},
                 {"id": "git", "argv": ["sh", "-c", "git add -A state public && git commit -qm tick || true"]}]}}
```

- `kind` 兩種：`agent`（接線）、`llm`（打模型）。kernel 或 agent 自己要擋 LLM 就寫 `tasks-blocked` `{"kinds":["llm"]}`。
- 沒事做時 `inbox` 寫 `.aos/tick/tasks-blocked`（全擋），後面全跳過、`after_all` 照跑（summary 照寄）。格結束就是睡。
- `hooks` 也可以整個 `$ref` 指到 kernel 管的檔（`"hooks": {"$ref": "/srv/kernel/policy/agent-hooks.json"}`），開格時展開：kernel 改政策不用碰每個 agent。

## daemon 那側（kernel 的 daemon 管兩個 agent；形狀照 kernel 提案）

```json
{"interval_ms": 3600000,
 "modules": {
   "control": {"socket": "./ctl.sock"}, "reload": {}, "cgroup": {},
   "mq": {"KERNEL": "./doors/kernel/s", "TEAM": "./doors/team/s",
          "ALICE": "./agents/alice/doors/s", "BOB": "./agents/bob/doors/s"},
   "account": {"user": "aos", "allow": ["agent-*"]}},
 "insts": {
   ".":            {"interval_ms": 10000, "mq": ["KERNEL"]},
   "agents/alice": {"mq": ["ALICE", "TEAM"], "account": {"user": "agent-alice"}},
   "agents/bob":   {"mq": ["BOB", "TEAM"],   "account": {"user": "agent-bob"}}}}
```

`"."` 是 kernel 自己（它的資料夾就是設定檔所在）。agent 的 `interval_ms` 一小時只是保底，正常靠 kernel `wake` 或信叫醒；閒置的 agent 只佔磁碟。每個 agent 一扇自己的門（grant 與私信寄這裡），`TEAM` 才是廣播。
