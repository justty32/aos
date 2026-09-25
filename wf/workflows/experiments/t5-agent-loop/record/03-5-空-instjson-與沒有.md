← [T5 agent loop 實測](../record.md)（分檔 3/4）｜所在：實際做了什麼｜[上一份](02-實際做了什麼.md)｜[下一份](04-哪幾題被實驗回答了.md)

### 5. 空 `inst.json` 與沒有 `inst.json`

```text
$ stat -c %s .aos/inst.json
0
$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=1
inst_exists=no
runi_exists=no
stderr:
aos exec: .aos/inst.json.runi: JsonSyntax

$ /mnt/c/code/mine/simple_tools/aos/build/bin/aos exec /tmp/aos-t5
exit=0
stdout:

stderr:
```

0-byte `inst.json` 是壞 JSON，實際退出 1 並清掉 `.runi`；「沒有 `inst.json`」才是規格所說的 no-op 0。

### 6. 真 agent CLI

本機候選：

```text
codex path=/home/guanyu/.local/bin/codex command_v_exit=0
pi path=missing command_v_exit=1
claude path=/home/guanyu/.local/bin/claude command_v_exit=0
```

Codex 的 help 證實 stdin、`--json`、`--output-last-message`、`--ephemeral` 與 resume 介面存在；但真呼叫沒進到模型：

```text
$ printf 'Reply with exactly REAL_CODEX_OK ...' | timeout 45 codex exec --ephemeral --json -o codex-final.txt -s read-only -C /tmp/aos-t5 --skip-git-repo-check -
exit=1
stderr:
WARNING: proceeding, even though we could not create PATH aliases: Read-only file system (os error 30)
Error: failed to initialize in-process app-server client: Read-only file system (os error 30)
jsonl:
final: missing
```

Claude 能從 stdin 回結構化單筆結果並給 session id，但帳號狀態不可用：

```text
$ printf 'Reply with exactly REAL_CLAUDE_OK ...' | timeout 45 claude -p --input-format text --output-format json --no-session-persistence --permission-mode dontAsk
exit=1
{"is_error":true,...,"session_id":"420b6757-7eb0-4a17-b8a6-f8b066a54d7e",...,"api_error_status":401,"result":"Failed to authenticate. API Error: 401 OAuth access token has expired. Re-authenticate to continue.","type":"result",...}
```

因此真模型明確是「試了但沒跑成」，不是「沒試」；取消成功呼叫、session resume 與真 tool-call event 都沒有可誠實報告的實測結果。

### 7. reliability 題的補充實驗

對 `request` 已寫、provider effect 已發生、`result.temp` 尚未 rename 三個時間點，各對同一支假三步 loop 送 SIGINT 與 SIGKILL：

```text
case=int_request signal=INT at=0.2s exit=130 files=request,
case=int_effect signal=INT at=0.6s exit=130 files=provider-effect,request,
case=int_result_temp signal=INT at=1.0s exit=130 files=provider-effect,request,result.temp,
case=kill_request signal=KILL at=0.2s exit=137 files=request,
case=kill_effect signal=KILL at=0.6s exit=137 files=provider-effect,request,
case=kill_result_temp signal=KILL at=1.0s exit=137 files=provider-effect,request,result.temp,
```

在這個只靠已落盤 marker 的假 loop 中，SIGINT 與 SIGKILL 留下同樣種類的判讀證據；hard kill 已足以逼出 request／effect／result-temp 三相狀態。這沒有測斷電與 fsync，不能外推成 power-loss durability。

假 provider 接到 key 後先記外部 ledger，再故意於回結果前斷線：

```text
--- first call: effect happened, result lost
exit=70
ledger_lines=1
provider accepted request-42, transport broke before result

--- policy A: stop
ledger_lines=1
no result produced

--- policy B: query by provider key
exit=0
result=recovered-result-for-request-42
ledger_lines=1

--- policy C: blind retry
exit=70
ledger_lines=2
ledger:
request-42
request-42
```

可對帳時查 key 能在不重做 effect 的情況下取回；盲目 retry 在這個假 provider 確實造成兩筆外部作用。

> **〈痛在哪：可直接寫成子命令的需求〉已抽成獨立檔**：見 [subcommand-specs](../subcommand-specs.md)。
