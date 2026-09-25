# proto5/lib — 執行與共用底層（11 支）

← [proto5/lib README](../README.md)｜上一份：[指示詞與 inst](directives.md)｜下一份：[daemon](daemon.md)

一檔一行（新增模組照這個格式插一行）：

| 檔 | 職責 |
|---|---|
| [`aos_exec.py`](../aos_exec.py) | 執行一次的上層：三種目標的解讀（`run_target`／`run_target_full`／`run_inst`）與 `aos-exec` 命令列 |
| [`aos_exec_run.py`](../aos_exec_run.py) | 執行一次的底層：前置檢查、開串流、起子行程、等待／逾時／強停整組、寫 exit 檔 |
| [`aos_exec_spawn.py`](../aos_exec_spawn.py) | daemon 的非同步入口 `spawn_target`：讀目標、開控制 pipe、交出孩子（`launcher` 決定 fd 0／1 怎麼接） |
| [`aos_home.py`](../aos_home.py) | JSON-RPC 信封、原子放單與狀態、ack／stop、開機對帳、`--target` 找家 |
| [`aos_client.py`](../aos_client.py) | 交件者：取名、放單、先查原單再等回音、讀與 ack |
| [`aos_exec_cpu.py`](../aos_exec_cpu.py) | 長命 exec cpu（`aos-cpu`）：go／stop、逐件執行、訊號與對帳、回完音往 kernel 家丟 `notify` 通知 |
| [`aos_up.py`](../aos_up.py) | （09-24 one-boot）`aos up`／`aos down`：需要的 daemon 沒在跑就開（背景、`D/daemon.log`）→ `aos-kernel boot` → 等第一格；down＝halt → 沒人用的 daemon 一起停 |
| [`aos_llm_call.py`](../aos_llm_call.py) | `aos-llm call`：讀驗 llm.json、組 body、HTTP、正規化並驗 message |
| [`aos_llm_ask.py`](../aos_llm_ask.py) | （第三波 W3-2）不需要 agent 家的「多問一次模型」：`ask`／`ask_json`／`parse_json`，給工具的模型選項共用；temperature 0、不重試 |
| [`aos_jail.py`](../aos_jail.py) | `aos-jail`：組 bwrap 參數並 exec（工具關進牢裡跑） |
| [`aos_hops.py`](../aos_hops.py) | （09-24 tick-gap）量每一跳：`AOS_HOPS` 設成檔的絕對路徑，各程式往裡追加時間戳（沒設＝什麼都不做）；`python3 lib/aos_hops.py report` 把一個 agent 的事件照時間切成一跳一跳 |

## aos_exec — 執行者（三支：aos_exec／aos_exec_run／aos_exec_spawn）

[inst-posix.md 第 6 節](../../spec/inst-posix/exec.md) 的實作＋命令列（[aos-exec.md](../../spec/aos-exec/README.md)）。
09-24 拆成三支、行為不變：`aos_exec.py` 是上層（三種目標怎麼解讀、`run_target`／`run_target_full`／`run_inst`、`main`）；
`aos_exec_run.py` 是底層（前置檢查與串流 `_execute_inst`、起子行程與等待 `_spawn`／`_wait_full`、`terminate`、
寫 exit 檔 `_finish`，以及常數 `DEFAULT_DIR_TARGET`／`GRACE`／`CHILD`／`AOS`／`USAGE`，`aos_exec` 照樣匯出這些常數）；
`aos_exec_spawn.py` 是 daemon 的非同步入口。舊同步 API 保持原回傳形狀：

```python
import aos_exec
code, kind = aos_exec.run_target(xxx, dir_target=".aos/inst.json", timeout_ms=0,
                                 on_spawn=None, stderr=None, args=None, on_target=None)
```

- `kind`：`"child"`＝子程式真的跑完了一次（它的碼／128+N／126／127／143／137，有 `exit` 就寫）、
  `"aos"`＝aos-exec 自己失敗那次沒跑（code 1，命令列換成 125，不寫 exit）、`"usage"`＝用法錯（2）。
- 三種目標（普通檔案／`.json`／資料夾）、旗標、退出碼與 stderr 印什麼，見 [aos-exec.md](../../spec/aos-exec/README.md)。
- 行為：驗完才跑；`mkdir` 在 chdir／開檔前 `makedirs`；`append` 用 `ab`；`inherit` 傳 `None` 給
  `Popen`；`merge` 傳 `subprocess.STDOUT`（跟著 stdout 的 append／inherit）；`clear` 從空環境開始
  否則複製 `os.environ` 再疊 `envs`；`argv[0]` 走疊加後的 PATH；`start_new_session=True`；逾時
  對整個 group SIGTERM → 2 秒 → SIGKILL；exit 檔十進位＋換行、fsync 檔與父目錄。
- `on_spawn(popen)`／`on_spawn(None)`：子行程開起來／收完屍各叫一次（保留給既有呼叫者）。
- `on_target(path)`：在讀 inst 前公布選定的絕對目標，供呼叫者觀察。

`run_inst(inst, stdin_text, timeout_ms=0) -> InstResult`（三元素 tuple：`code, kind, stdout_text`）：吃 `load_obj()` 解好的 dict，
用 UTF-8 把文字送入 stdin，stdout 全收回（壞位元組以替代字元表示）。stdin／stdout 由 API 接管，
stderr／exit／cwd／envs 照 inst；stderr 沒寫就是 /dev/null、`merge` 則併進回傳的 stdout。
另帶 `.timed_out` 布林旗標，真正撞到 TimeoutExpired 才為真，不靠退出碼猜；三值解包與 tuple 相等比較保持相容。
kind 是 child／aos，錯誤跟 `run_target()` 一樣印 stderr。兩個入口共用前置檢查、mkdir、
啟動、126／127、exit 檔與逾時砍 group；管線用 `communicate()`，同時收送避免大輸出卡住。

### 完整執行結果與 daemon 啟動入口

`run_target_full(xxx, dir_target=".aos/inst.json", timeout_ms=0, on_spawn=None, stderr=None,
args=None, on_target=None, *, on_poll=None, poll_ms=20) -> TargetResult`：三種目標、base、
串流與 Usage 判定同 `run_target`，物件提供 `.code`、`.kind`、`.timed_out`、`.stopped`、`.ms`。
`on_poll(popen)` 定期讀控制狀態，回真值要求強停；逾時與強停只處理工作的 process group。
`.timed_out` 是實際期限旗標，即使 TERM 後退出 0 仍為真；已退出的孩子不標 `.stopped`。

`aos_exec_spawn.spawn_target(xxx, dir_target=".aos/inst.json", launcher=None) -> Spawned`：給 daemon 的非同步入口。
`launcher` 省略時 `.process`（Popen）的 stdin／stdout 是兩條控制 pipe；daemon 的池式孩子傳
`aos_daemon_pools._launch`（只留 fd 0、fd 1 接 `/dev/null`），`aos_daemon_pools.spawn_child()` 就是這樣叫它。
四端 CLOEXEC、`close_fds=True`，孩子獨立 pgid、與 daemon 同 session。inst 顯式寫 stdin／stdout 即拒絕；
stderr、cwd、envs、exit 沿用 inst。登記、送 go、輪詢及收屍由 daemon 負責；收屍後 `Spawned.finish(code=None)`
寫 exit、回 `(code, kind)`。起不了 Popen 丟 `SpawnError(code, msg)`，不登記假 pid；與同步 126／127 的差異見
[實作發現](../../notes/2026-09-23-rearch/impl-findings.md)。目標不存在（含非 `.json`）、資料夾缺 dir_target 也是
`SpawnFailed`（同步入口仍是 Usage）。

## aos_home — 共用家與信封

- `read_request(path) -> Envelope`：`.name`、`.id`、`.notify`、`.method`、`.params`、`.error`。
  壞 JSON／信封回 -32700／-32600；合法 notification 即使 method／params 壞也不回音。
- `result_response(id, result)`、`error_response(id, code, message, data=None)`、
  `params_error(id, msg, position, code="FieldTypeMismatch")` 組完整 JSON-RPC 回音。
- `post_request(home, name, obj)`：同目錄 `.tmp` → `os.link`，已存在丟 `RequestExists`。
  `link_json(path, obj)` 同樣有就失敗；`write_json(path, obj)` 是 `.tmp` → 原子替換。
- `read_state(home, default=None)`：缺檔回預設（未指定時 current=null、runs=0）；
  `write_state(home, state)` 原子替換。`ensure_queue(home)` 建 requests／responses。
- `scan_controls(home, on_stop)` 掃 ack-／stop-：ack 先刪回音、再刪通知；不存在視為完成。
  `reconcile_actions(current, request_exists, response_exists)` 是開機五列表的純判定；
  `reconcile(home, current)` 補 Interrupted／刪原單。
- `load_info(home, kind)` 解共用設定指示詞、驗身分與 poll_ms／timeout_ms；錯誤統一
  `HomeError(code, msg)`。kernel 有保留 envs 原文的專用 `load_info`。

## aos_client — 交件者

```python
import aos_client
response = aos_client.call(cpu_home, "aos-exec", {"target": "/abs/job.json"},
                           client="agent", timeout_ms=5000, poll_ms=20)
```

`call(home, method, params=None, *, name=None, client="client", timeout_ms=None, poll_ms=20,
acknowledge=True)` 完成取名、放單、等回音、讀、放 ack，回完整 response（含 error，交件者自行判定）。
等待先確認原單不在，再讀回音；等待逾時不取消工作。ack 是放通知，不同步等待主人刪回音。

要先記帳再 ack，可傳 `acknowledge=False`，或分別用 `new_name(prefix="client")`、
`submit(home, method, params=None, *, name=None, client="client")`（回 request 檔名）、
`wait_response(home, name, *, timeout_ms=None, poll_ms=20)`、`ack(home, name)`。
名稱是 `<名>-<epoch ns>-<pid>.json`；名稱不可重用。客戶端錯誤為 `ClientError(code, msg)`。

## aos_exec_cpu — exec cpu 的主人

`run(home)`／`main(argv=None)`；CLI：`aos-cpu [DIR]`（fix-r4：省略＝目前資料夾）。stdin 是 pipe 時先等 JSON-RPC go，
EOF 先到則不碰家；啟動後控制 fd 搬高位並設 CLOEXEC，工作 stdin 接 /dev/null、stdout 接 cpu 的 stderr。
stdin 不是 pipe 時直接啟動。info 身分是 `exec_cpu`。

每件依序寫 current、`run_target_full`、寫回音、刪原單、清 current／更新 runs；開機先對帳。
result 含 code／kind／timed_out／stopped／ms；Usage 映射 -32602，kind=aos 仍是 result。
pipe stop／EOF、stop- 檔與第一次訊號溫和停；再次訊號強停工作 group，回音照寫。
控制行要是合法信封（jsonrpc 2.0、字串 method、合法 id，stop 不可帶 id）才算數，否則忽略並在 stderr 記 BadControl。
正常停退 0、主人讀寫錯退 1、CLI 用法錯退 2。
回完音若 info 有 `notify`（kernel 家的絕對路徑），往那裡丟一張 `resp-` 通知讓 kernel 下一格就收；開機補丟上一任沒丟到的（[spec/cpu/notify.md](../../spec/cpu/notify.md)）。

## aos_llm_call — 問模型一次

`load_config(path, env=None)` 讀驗整份模型表；`build_request(agent_dir, config, env=None, *, with_alias=False)` 回 `(body, entry)`（`with_alias` 多回模型代號），保留欄位不讓 params 覆寫。
`call(agent_dir, env=None)` 從環境 `AOS_LLM_CONFIG` 找模型表、打一次 HTTP、正規化並驗證 assistant message 後回傳；不寫記憶、不重試、不跑工具。`EngineFailed`／`Timeout` 訊息尾附 endpoint 與「代號→真名」，不含金鑰。`main(argv=None)` 提供 `aos-llm call [AGENT_DIR]`（fix-r4；裸 `aos-llm` 退 2）。
