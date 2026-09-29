# 人手打的操作 CLI：七步走查

← [CLI 入口](README.md)｜[規格入口](../README.md)

## H-036．七步走到底〔使用者方向；驗收腳本為工程預設〕

前置：非 root、proto6、git 2.35 以上、Python 3.9 以上、Linux kernel 5.14 以上、git 作者已設，DEMO 尚不存在；已有一棵準備好並交給目前帳號的 cgroup v2 子樹，絕對路徑放在 CG，終端 A 的 shell 也已在這棵子樹底下的一個葉框裡（例如 root 先建 `$CG/shell`，把 A 的 shell PID 寫進 `$CG/shell/cgroup.procs`；不放子樹根，免得擋住 daemon 開 controller；[B-605](../daemon.md)；沒有它 daemon 啟動即報錯退出，本走查不用 `--create-cgroup`）。A 跑 daemon，B 操作，C 跑 HTTP；都設 DEMO、S、CG。註解為預期輸出。

### 1. 寫 daemon 設定，先開一次空服務

終端 B：

```sh
DEMO="$HOME/aos-cli-demo"
S="$DEMO/run/aos.sock"
mkdir -p "$DEMO/run" "$DEMO/daemon-state" "$DEMO/drafts"
cat > "$DEMO/daemon.json" <<EOFJSON
{"version":1,"socket_path":"$S","state_dir":"$DEMO/daemon-state","cgroup_root":"$CG","roots":[]}
EOFJSON
```

終端 A：

```sh
aos daemon --config "$DEMO/daemon.json"
# helper_pid=none；保持前景
```

B 查詢，A 再按 Ctrl-C：

```sh
aos daemon info --socket "$S" --json
# {"jsonrpc":"2.0","id":"…","result":{"boot_id":"…"}}
# A：Ctrl-C，等 daemon 返回；echo $? 印 0
```

### 2. 建頂層 kernel、設定可重現的測試 LLM，再啟動

B 建頂層，準備測試 HTTP：

```sh
aos node new "$DEMO/top" --template kernel --user "$(id -u)" --socket "$S"
# created …/top; initial_commit=…; tasks=9
cat > "$DEMO/mock.py" <<'PY'
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
class API(BaseHTTPRequestHandler):
    def do_POST(self):
        q = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        last = q['messages'][-1]
        m = {'role':'assistant','content':'收到'}
        reason = 'stop'
        if last['role'] == 'user' and 'echo' in last['content'] and q.get('tools'):
            m = {'role':'assistant','content':None,'tool_calls':[
                {'id':'call_echo','type':'function','function':
                 {'name':'echo','arguments':'{"text":"工具完成"}'}}]}
            reason = 'tool_calls'
        elif last['role'] == 'tool':
            m['content'] = '工具完成'
        body = json.dumps({'choices':[{'message':m,'finish_reason':reason}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
HTTPServer(('127.0.0.1',18406),API).serve_forever()
PY
cat > "$DEMO/drafts/pools.json" <<'EOFJSON'
{"version":1,"pools":[{"id":"local","endpoint":"http://127.0.0.1:18406/v1","model":"demo-model","quota_scope":"local-account","max_attempts":3}]}
EOFJSON
aos node config add "$DEMO/top" --from "$DEMO/drafts/pools.json" --to config/llm-pools.json
# 各印安裝的 config/... 路徑
cat > "$DEMO/daemon.json" <<EOFJSON
{"version":1,"socket_path":"$S","state_dir":"$DEMO/daemon-state","cgroup_root":"$CG","roots":[{"node_id":"$DEMO/top","identity_grant":[$(id -u)],"interval_ms":1000}]}
EOFJSON
aos llm pool ls "$DEMO/top"
# local http://127.0.0.1:18406/v1 demo-model local-account aos
```

C 打 `python3 "$DEMO/mock.py"`；A 打 `aos daemon --config "$DEMO/daemon.json"` → helper_pid=none，自動 tick top。B 打 `aos node show "$DEMO/top" --socket "$S"` → 稍後 last_tick.completed、exit_code=0。mock 不驗真實 provider／UID 隔離。

### 3. 建 agent、給路線與份額、保存成員並登記

同 UID、LLM／工具全管；先 pause top 安裝設定。

```sh
aos node pause "$DEMO/top" --socket "$S"
# paused …/top; running=false
cat > "$DEMO/drafts/agent.json" <<EOFJSON
{"version":1,"llm":{"target_node":"$DEMO/top","pool":"local","model":"demo-model","context_tokens":32768,"max_completion_tokens":256,"timeout_ms":30000},"system_prompt":"照使用者要求回答。","tools_file":"config/tools.json","tools":{"target_node":"$DEMO/top"},"daemon_socket":"$S"}
EOFJSON
aos node new "$DEMO/a" --template agent --agent-config "$DEMO/drafts/agent.json" --user "$(id -u)"
# created …/a; initial_commit=…; tasks=2
cat > "$DEMO/drafts/routes.json" <<EOFJSON
{"version":1,"routes":[{"pool_id":"local","model":"demo-model","next_node":null,"next_pool":"local","allowed_origins":[{"node_id":"$DEMO/a","via_node":"$DEMO/a","via_uid":$(id -u)}]}]}
EOFJSON
cat > "$DEMO/drafts/member.json" <<EOFJSON
{"id":"a","node_id":"$DEMO/a","identity_grant":[$(id -u)],"quota":{"version":1,"node_id":"$DEMO/a","seq":1,"resources":{"llm":[{"pool_id":"local","concurrent_requests":1}]}}}
EOFJSON
aos node config add "$DEMO/top" --from "$DEMO/drafts/routes.json" --to config/llm-routes.json
aos kernel members add "$DEMO/top" --from "$DEMO/drafts/member.json"
# a
aos kernel members ls "$DEMO/top"
# a …/a；UID=目前使用者，無週期，local=1
aos node resume "$DEMO/top" --socket "$S"
# resume accepted …/top
aos node wake "$DEMO/top" --socket "$S"
# wake accepted …/top
aos node ls --socket "$S"
# top、a；等同步後 a registered=true
```

a 摘要為 idle。

### 4. 說一句話，看 tick，再聽回覆

```sh
aos agent say '請回覆收到' --target "$DEMO/a" --from-node "$DEMO/top"
# …/a/requests/<input_id>.json
# 可立即請 top 重看：
aos kernel schedule recheck "$DEMO/top" --from-node "$DEMO/a"
# submitted <recheck_id>
aos node show "$DEMO/a" --socket "$S"
# last_tick=completed、exit_code=0；短格可能看不到 running
aos node log "$DEMO/a"
# … aos-tick group agent..agent
aos agent listen --target "$DEMO/top" --last 1
# 等循環完成後：收到
aos agent replies "$DEMO/a"
# final succeeded 收到
aos llm pool usage "$DEMO/top"
# JSON：local-account，active_requests=0、unknown_requests=0；窗口計數依查詢時刻
```

尚無回話用 `aos agent listen --target "$DEMO/top" --wait 300`；--follow 持續看，Ctrl-C 停觀看。


### 5. 加工具，真的呼叫一次，再看工具結果

```sh
cat > "$DEMO/drafts/tools.json" <<EOFJSON
{"version":1,"tools":[{"name":"echo","description":"回傳收到的 JSON","parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"],"additionalProperties":false},"argv":["/bin/cat"],"cwd":"$DEMO/a","result":{"kind":"json","schema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"],"additionalProperties":false}},"timeout_ms":5000,"output_limit_bytes":4096}]}
EOFJSON
aos agent tools add "$DEMO/a" --from "$DEMO/drafts/tools.json"
# config/tools.json
aos agent tools ls "$DEMO/a"
# echo 回傳收到的 JSON
aos agent say '請呼叫 echo，內容為工具完成' --target "$DEMO/a" --from-node "$DEMO/top" --wait 300
# 投件位置；工具完成
aos agent listen --target "$DEMO/a" --last 10 --show-calls-full
# 看得到 echo({"text":"工具完成"})、tool 結果 JSON、assistant「工具完成」
aos agent replies "$DEMO/a"
# progress 正在使用 echo；final succeeded 工具完成
aos node ls --socket "$S"
# once：registered=false、completed、exit_code=0
```

證據在 top/state/work、.aos/jobs/。

### 6. 製造設定待辦、修好再恢復

```sh
aos node pause "$DEMO/a" --socket "$S"
python3 - "$DEMO/drafts/agent.json" "$DEMO/drafts/bad-agent.json" <<'PY'
import json,sys
q=json.load(open(sys.argv[1])); q['llm']['context_tokens']=1
open(sys.argv[2],'w').write(json.dumps(q))
PY
aos node config add "$DEMO/a" --from "$DEMO/drafts/bad-agent.json" --to config/agent.json
# config/agent.json；下格驗領域欄位
aos agent config recheck "$DEMO/a"
# invalid llm.context_tokens；exit 1，寫 a/.aos/attention/
aos attend ls --socket "$S" --source "$DEMO/a" --json > "$DEMO/issues.jsonl"
cat "$DEMO/issues.jsonl"
# {…"reason":"config_invalid","message":"設定無效","suggestion":"修好後重驗設定","status":"open"}
ISSUE=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).readline())["issue_id"])' "$DEMO/issues.jsonl")
aos node config add "$DEMO/a" --from "$DEMO/drafts/agent.json" --to config/agent.json
aos attend show "$DEMO/a" "$ISSUE" --socket "$S"
# 顯示問題與建議處理
# aos 的建議只供閱讀，修理由人或 agent 下指令：
aos agent config recheck "$DEMO/a"
# valid
aos attend done "$DEMO/a" "$ISSUE" --socket "$S"
# done …/a <ID>
aos attend show "$DEMO/a" "$ISSUE" --socket "$S"
# status=done
```

打 `aos node resume "$DEMO/a" --socket "$S"` → resume accepted；recheck 本身不 resume。

### 7. 清理、Ctrl-C 停機、重開後接著說話

```sh
aos node pause "$DEMO/a" --socket "$S"
printf '{"version":1,"archive_dir":"%s/archive-a"}\n' "$DEMO" > "$DEMO/drafts/clean-a.json"
aos clean run "$DEMO/a" --config "$DEMO/drafts/clean-a.json" --json
# {"version":1,"node_id":"…/a","outcome":"unchanged","archived_items":0,"deleted_items":0}
# A：Ctrl-C，等 daemon 退出；echo $? 應為 0
```

範本已執行過清理，未到下一次間隔，故 unchanged。A 重開 `aos daemon --config "$DEMO/daemon.json"` → helper_pid=none，頂層自動 tick。B：

```sh
aos daemon info --socket "$S"
# boot_id 和上次不同
aos node ls --socket "$S"
# top、a 已恢復／同步；a paused=true，舊 once 診斷不在本次記憶體
aos node resume "$DEMO/a" --socket "$S"
# resume accepted …/a
aos agent say '重開後請回覆收到' --target "$DEMO/a" --from-node "$DEMO/top" --wait 300
# 投件位置；收到
aos agent listen --target "$DEMO/top" --last 1
# 收到
aos attend ls --socket "$S" --source "$DEMO/a"
# 空表：先前 done 事項不回到 open
# 結束驗收：A 再 Ctrl-C，等 0；C Ctrl-C 停 mock
```

意外中斷及真實服務另驗；unknown 不因重開重做。
