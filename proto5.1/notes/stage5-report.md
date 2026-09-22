# 第 5 段回報（2026-09-22）

依 [任務書](stage5-task.md)、[fable 重審](review-fable.md) 與[使用者決策](../../proto5/notes/2026-09-22-decisions.md)，完成本段指定修改。R4、R10～R13 按任務不做。只修改 `proto5.1/`，沒有 commit、push、stash、checkout。

## R 編號逐條對照

| 編號 | 結果 | 怎麼做／證據 |
|---|---|---|
| R1 | 做了 | 有 home 的 runner 檢查父 PID，父離開便做完本次後停；daemon 啟動掃舊 runner PID，活著回 AlreadyRunning。真進程測 kill -9、自停與拒重啟。 |
| R2 | 做了 | 壞共同欄位搬 bad、stderr 一行、繼續下一單、tick 最後退 1；結果寫入 OSError 仍搬 done。合法 result 的壞 payload 認領後回 BadPayload。 |
| R3 | 做了 | hold 固定 50 ms，held 只在變化時寫；0 ms interval 的半秒 mtime 測試通過。 |
| R4 | 按任務不做 | runner 被 KILL 後其他 session 子程序的保證，留 backlog。 |
| R5 | 做了 | 完成快照加 last_target；kernel 忙碌時也對帳，重讀同一 runs 不重算。保留每份新快照最多計一次。 |
| R6 | 做了 | 拿掉 daemon 主迴圈無條件 save；狀態變動才寫，半秒閒置 mtime 不變。 |
| R7 | 做了 | add 固化 inst；tick 讀驗後相同不寫，測 inode／mtime 不變。手放未固化檔才寫回。 |
| R8 | 做了 | CPU／daemon／kernel syscall 失敗都用 ok:false＋code＋msg；CPU 有 Reaped／UnknownModel／Timeout／EngineFailed／BadPayload。agent 看 Reaped，模型看見的原工具文字保持。 |
| R9 | 做了 | daemon info 身分；ctl／kernel 驗家；boot 記 daemon 絕對路徑，tick／ls／rm 不跟環境換家；kernel state 與 rm syscall 的 pid 改 name。 |
| R10 | 按任務不做 | CPU 收 TERM 主動回音，留 backlog。 |
| R11 | 按任務不做 | kernel 與工作 CPU 拆 interval，留 backlog。 |
| R12 | 按任務不做 | idle 改 true，留 backlog。 |
| R13 | 按任務不做 | 收屍時鐘問題，留 backlog，沒有改期限算法。 |
| R14 | 做了 | 同名明確丟 AgentError ReadFailed，規範與程式一致。 |
| R15 | 做了 | submit 驗 result 父目錄存在，缺少回 ReadFailed。 |
| R16 | 做了 | aos-kernel.md 明寫只看 daemon 最後快照的 pid，不探測存活。 |
| R17 | 做了 | kernel remove 等回音逾時改 ReadFailed，與 daemon ctl 一致，請求保留。 |
| R18 | 做了 | 規範補 bad 隔離／發布失敗後交件者可能繼續等，以及 hold 固定輪詢的後果。 |
| R19 | 做了 | agent.md 的導覽文字改 proto5.1 README。 |
| R20 | 做了 | kernel-home 移除 since，實作同步 R23。 |
| R21 | 做了 | daemon 檔案請求只剩 add／remove／stop；ctl ls 直接讀 state。 |
| R22 | 做了 | runner 無用 reason 變數拿掉。 |
| R23 | 做了 | kernel 不再寫 since／bad_exit，計數只留實際使用欄位。 |
| R24 | 做了 | 拿掉 llm_cpu.queue_lock 別名與 aos-llm-ask --dry-run；已測舊旗標退用法錯 2。 |
| R25 | 做了 | 檔案 ls op 拿掉，已測投遞會回 FieldTypeMismatch。 |
| R26 | 做了 | agent 交件去掉 inst.stdin／stdout；CPU 不讀驗／使用這兩格，管線接輸入輸出。 |
| R27 | 做了 | 共用 tick 的 validate 參數拿掉；LLM payload 驗證移入 execute。 |

## Findings 與分檔

新增 **10 條，#45～#54**，見 [findings](findings.md)：父 PID／保守拒重啟、壞單與遺失結果後果、last_target、失敗回音邊界、固定 daemon 家與整份 `$ref`、減少重寫與格式分檔，完整測試找到的快照競態、不可編碼的 result 路徑，失敗 boot 的本地復原，以及 pgrep 命中祖先 shell 的環境差異。

格式與程式分開：新增 [run-home](../spec/run-home.md) 保存 runner 家格式，[aos-run](../spec/aos-run.md) 只講程式；新增 [aos-cpu](../spec/aos-cpu.md) 保存共用程式 API／步驟，[cpu-queue](../spec/cpu-queue.md) 留交件與回音協議。規範採中文白話，沒有修訂記錄。

## 檔案清單

相對 `proto5.1/`，共 **37 檔**；既有任務書、重審與前段報告保留。`.build/` 的測試 log／真跑家沿用 ignore。

| 類別 | 檔案 |
|---|---|
| 程式 8 | `lib/aos_agent.py`、`aos_cpu.py`、`aos_daemon.py`、`aos_kernel.py`、`aos_llm_ask.py`、`aos_llm_cpu.py`、`aos_run.py`、`aos_tool_cpu.py`（同在 lib） |
| 測試 8 | `lib/test/test_agent.py`、`test_cpu.py`、`test_daemon.py`、`test_kernel.py`、`test_llm_ask.py`、`test_llm_cpu.py`、`test_run.py`、`test_tool_cpu.py`（同在 lib/test） |
| 規範 15 | `spec/agent.md`、`aos-agent.md`、`aos-cpu.md`（新增）、`aos-daemon.md`、`aos-kernel.md`、`aos-llm-ask.md`、`aos-llm-cpu.md`、`aos-run.md`、`aos-tool-cpu.md`、`cpu-queue.md`、`daemon-home.md`、`kernel-home.md`、`llm-cpu.md`、`run-home.md`（新增）、`tool-cpu.md`（同在 spec） |
| 導航／API 2 | `README.md`、`lib/README.md` |
| 實驗／回報 4 | `notes/findings.md`、`stage5-demo.py`、`stage5-trace.json`、`stage5-report.md`（同在 notes） |

## 測試

使用指定命令：

```sh
cd /home/guanyu/projs/aos/proto5.1/lib
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test
```

最終 **802/802 全綠，114.666 秒，無 skip**。完整 log：`.build/stage5-tests.log`。

| 模組 | 測試數 |
|---|---:|
| agent | 144 |
| agent_info | 98 |
| cpu | 18 |
| daemon | 35 |
| directives | 101 |
| exec | 94 |
| inst | 139 |
| kernel | 34 |
| llm_ask | 53 |
| llm_cpu | 38 |
| run | 30 |
| tool_cpu | 18 |

第一輪是 800 條、112.199 秒、1 個 error：換槽測試忽略 idle runner 的 busy/null 過渡；修測試前提後，關鍵案例連跑 **5/5，31.261 秒**。兩條整合審查回歸（result 路徑編碼、失敗 boot 保留綁定）再把總數增至 802。沒有放寬原測試期限或改排程迎合測試，詳見 findings #51～#53。

R1、R2、R3、R5、R8 都有直接測試；另驗 daemon 閒置不重寫、procs 不重寫、固定 daemon 家不跟環境換、整份 info `$ref` 仍保持其他設定動態解析。Python 語法、文件本地連結與 `git diff --check` 均通過。


## LM Studio 真跑

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto5.1/notes/stage5-demo.py
```

`http://127.0.0.1:1234/v1` 已在運作，指定模型 `qwen/qwen3-1.7b` 已載入，無須另啟 server。
使用第 4 段相同設定：三顆 CPU、interval=1000 ms、quantum=5、timeout=0、kill_tree=false；
agent 只帶 small 模型代號，LLM CPU 的 models 表保存連線設定；now 工具是 tool CPU 上的 `sleep 2; date`，沒有強制 tool_choice。

**12.949 秒完成** LLM → now → tool CPU → LLM 回答；C/done 2 份、T/done 1 份。
最後 agent 是 idle／waits=[]／errors=0；A、C、T 的 stderr.log 都空。
boot 後從呼叫環境刪掉 AOS_DAEMON_HOME，後續 ls 仍正常讀到 K/info.json 記下的 daemon 家。

真跑家：`/home/guanyu/projs/aos/proto5.1/.build/stage5-demo-1790053665079546115`。完整命令、ls、runner 快照與檔案清單在 [stage5-trace.json](stage5-trace.json)。

### ls 原始輸出

以下讀到的是不同檔案的即時快照，PROC／RUNNING／WAIT 不保證屬於同一瞬間。

0.275 秒，think：

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage5-demo-1790053665079546115/K ncpu=3 quantum=5 daemon=171490
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 1 0 False 0
1 idle False 1 0 False 0
2 idle False 1 0 False 0
queue: llm tool
done: -
bad: -
```

4.376 秒，act：

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage5-demo-1790053665079546115/K ncpu=3 quantum=5 daemon=171490
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 5 0 True 0
1 llm False 3 0 False 0
2 tool False 5 101 True 0
queue: -
done: -
bad: -
```

12.949 秒，idle：

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage5-demo-1790053665079546115/K ncpu=3 quantum=5 daemon=171490
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 13 0 True 0
1 llm False 9 0 False 0
2 tool False 11 101 True 0
queue: -
done: -
bad: -
```

### 最後記憶（原始 JSON）

```json
[
  {
    "role": "user",
    "content": "現在幾點？用工具查"
  },
  {
    "role": "assistant",
    "content": "",
    "reasoning_content": "好的，用户问现在几点，我需要使用提供的now工具来查询台湾的当前时间。首先，调用now函数，不需要参数。然后等待返回结果，直接把结果告诉用户。确保回答简洁明了，符合要求。\n",
    "tool_calls": [
      {
        "type": "function",
        "id": "JptsbYWaIWLfleSdFkA2CL99OynusJFO",
        "function": {
          "name": "now",
          "arguments": "{}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "JptsbYWaIWLfleSdFkA2CL99OynusJFO",
    "content": "2026-09-22 13:07:53 CST\n"
  },
  {
    "role": "assistant",
    "content": "現在時間是2026年9月22日中午1點7分53秒。",
    "reasoning_content": "好的，用户问现在几点，我用now工具查询到台湾的时间是2026年9月22日中午1点7分53秒。需要以简体中文直接回答，不需要额外说明。先检查时间格式是否正确，然后简洁回复用户当前时间。\n",
    "tool_calls": []
  }
]
```

### stop 與進程

`aos-daemon-ctl --home D stop` 退 0，stdout `{"stopped":true}`，stderr 空；daemon 退 0。
D/state.json 為 `{"pid":0,"runs":{}}`，daemon.pid 已不存在。

```text
$ pgrep -f aos-
158716
$ pgrep -A -f aos-
（無輸出；退出碼 1）
```

原始 pgrep 唯一命中的是啟動本次 Codex 的祖先 zsh，命令列含任務書的 aos- 字樣；
它在真跑前就存在，並非 aos 執行程序。已核 `/proc` 父鏈：Codex → 包裝程序 → zsh 158716。
`-A` 排除祖先後為空；`new_aos_pids_after_stop=[]`、`remaining_demo_processes=[]`。
沒有 daemon／runner／kernel／agent／CPU 殘留。這個字面驗收差異記於 findings #54，沒有殺掉上層工作程序或隱藏原始輸出。
