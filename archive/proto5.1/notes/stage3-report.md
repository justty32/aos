# 第 3 段回報（2026-09-22）

已完成 aos-run／aos-daemon／aos-kernel、四個 CLI 入口、五份規範與三份測試。
KISS 範圍維持四個 daemon op、兩種 daemon 狀態、kernel 只有 rm syscall，沒有 module。
只修改 `proto5.1/`，仍在 main；未執行 git commit／push／stash／checkout。

## 檔案清單

路徑相對 `proto5.1/`。使用者提供的 `notes/stage3-task.md` 保持原檔，不列入本次產出。

| 類別 | 檔案 |
|---|---|
| 新增程式 | `lib/aos_run.py`、`lib/aos_daemon.py`、`lib/aos_kernel.py` |
| 修改執行器 | `lib/aos_exec.py`：共用終止流程、Linux 後代 groups、受控 UTF-8／NUL 錯誤；既有 API 相容 |
| 新增入口 | `cli/aos-run`、`cli/aos-daemon`、`cli/aos-daemon-ctl`、`cli/aos-kernel` |
| 新增規範 | `spec/aos-run.md`、`spec/daemon-home.md`、`spec/aos-daemon.md`、`spec/kernel-home.md`、`spec/aos-kernel.md` |
| 新增測試 | `lib/test/test_run.py`、`lib/test/test_daemon.py`、`lib/test/test_kernel.py` |
| 更新導航／API | `README.md`、`lib/README.md` |
| 實驗與回報 | `notes/findings.md`、`notes/stage3-demo.py`、`notes/stage3-trace.json`、`notes/stage3-report.md` |

共 **22 個產出檔案**；`.build/` 保留被既有 ignore 排除的建置、測試 log 與真跑之家。

## 測試

從 repo 根執行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5.1/lib python3 -m unittest discover -s proto5.1/lib/test
nice -n 19 cmake --build proto5.1/.build -j 4
ctest --test-dir proto5.1/.build --output-on-failure
```

- **Python 760/760，全綠、84.607 秒、無 skip**。原有 686 條保留，新增 run 24／daemon 25／kernel 25，共 74 條。
- 分項：agent 141、agent_info 98、cpu 14、daemon 25、directives 101、exec 94、inst 139、kernel 25、llm_ask 54、llm_cpu 29、run 24、tool_cpu 16。
- **C++ build 成功、ctest 8/8，4.86 秒**。沿用同 default 配置的 `proto5.1/.build`；根 cache 路徑問題已在 findings #7 記錄，本段未改根 build／preset。
- **15 ms 與 0 ms 輪轉壓力案例各再跑三輪，6/6 全過**（11.899 秒）。三個行程輪用兩顆 CPU，單次工作 220 ms，每個行程至少完成三次，驗無同名重疊、無非預期 TERM。
- 首輪完整回歸曾 754 條中 1 條失敗：短間隔漏看空檔使第三個行程飢餓。原測試與期限保留，補 sidecar 的完成後交接意圖與六條測試後整套全綠，詳見 findings #35。
- `git diff --check` 通過，最後變更均在 proto5.1。

測試 log：`.build/stage3-baseline.log`（686 基線）、`.build/stage3-first-tests.log`（首輪失敗）、`.build/stage3-tests.log`（760 最終全綠）、`.build/kernel-tests.log`（kernel 定點驗證）。

真進程覆蓋首次 TERM／timeout 殺子孫、父先退出仍清孫、tool CPU 的另開 session 工具、daemon 五秒 fallback／同時停機、done 先寫才刪／故障留單／已有 done 不重做、完整 inst 搬移、過期 running 快照、跨換人連敗計數、yield 交接／取消／失敗保留。

## 最後一輪 LM Studio 真跑

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto5.1/notes/stage3-demo.py
```

端點 `http://127.0.0.1:1234/v1`，模型 `qwen/qwen3-1.7b`，沒有強制 tool_choice。
腳本新建獨立之家：`proto5.1/.build/stage3-demo-1790045509426954822/`。
A＝agent、C＝llm CPU、T＝tool CPU、K＝kernel、D＝daemon；保留所有實際請求與結果。

依序 init K（ncpu=3）、add agent／llm／tool 三個完整 inst、啟動 daemon、boot K、丟 input.json。
使用預設 interval=1000 ms、timeout=0、quantum=5；kernel tick 和三個 CPU runner 全由 daemon 管理。
agent 使用 engine.cpu 與一個 `_run:"cpu"` 的 now 工具，工具內容為 `sleep 2; date`、TZ=Asia/Taipei。

**11.713 秒完成**：agent 送 LLM → 模型叫 now → tool CPU 執行 → 結果接記憶 → LLM 最終回話。
C/done **2 份**、T/done **1 份**；最後 agent `state=idle, waits=[], errors=0`，A／C／T 的 stderr log 都空。
完整 CLI 與每次狀態變化、全部 ls 在 [stage3-trace.json](stage3-trace.json)。

下列是三次 `aos-kernel ls K` 的實際原文。RUNNING／LAST_EXIT 來自 daemon 快照，WAIT／BAD 來自 kernel 快照，兩者可能差一格，所以不是同一瞬間的交易快照。

### 0.270 秒：state=think

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage3-demo-1790045509426954822/K ncpu=3 quantum=5 daemon=96760
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 1 0 False 0
1 llm False 1 101 False 0
2 tool False 1 101 False 0
queue: -
done: -
bad: -
```

### 4.387 秒：state=act

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage3-demo-1790045509426954822/K ncpu=3 quantum=5 daemon=96760
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 5 0 False 0
1 llm False 3 101 True 0
2 tool False 5 101 True 0
queue: -
done: -
bad: -
```

### 11.713 秒：state=idle

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage3-demo-1790045509426954822/K ncpu=3 quantum=5 daemon=96760
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 12 0 True 0
1 llm True 8 0 False 0
2 tool False 10 101 True 0
queue: -
done: -
bad: -
```

## 最後記憶（原始 JSON）

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
        "id": "pt3YggGnMiWKJivRbn6W5vOEukqcBUTe",
        "function": {
          "name": "now",
          "arguments": "{}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "pt3YggGnMiWKJivRbn6W5vOEukqcBUTe",
    "content": "2026-09-22 10:51:56 CST\n"
  },
  {
    "role": "assistant",
    "content": "現在時間是2026年9月22日中午10:51。",
    "reasoning_content": "好的，用户问现在几点，我用now工具查询到台湾的时间是2026年9月22日中午10点51分56秒。需要直接回答，所以简要说明时间即可。确保使用繁体中文，保持简洁明了。\n",
    "tool_calls": []
  }
]
```

「中午」是模型原文；工具的實際時間是 `2026-09-22 10:51:56 CST`。

## 停止與殘留進程

`aos-daemon-ctl stop` 實際回 exit 0、stdout `{"stopped":true}`、stderr 空；daemon 自己也 exit 0。
停止後 D/state.json 是 `{"pid":0,"runs":{}}`，daemon.pid 不存在。

```text
$ pgrep -f aos-
82087
$ ps -p 82087 -o pid,ppid,stat,comm
    PID    PPID STAT COMMAND
  82087    3008 Ss   zsh
```

pgrep 的退出碼是 **0，不是空輸出**：82087 是啟動本次工作、命令文字含 aos- 的既有 zsh 包裝程序，
真跑開始前 pgrep 就只有同一 PID。開始前／停止後清單相同、new_aos_pids_after_stop=[]、remaining_demo_processes=[]。
已確認沒有本次 daemon／runner／kernel／agent／CPU 殘留。

## Findings：新增 9 條，#27～#35

最重要五條：

1. **#35 短間隔飢餓**：全套抓到 a／b 各跑 44 次、c 一次都輪不到。既有鎖檔用一 byte Y 請 run 完成本次後等交接，0 ms 也能輪轉，不延長測試期限、不 TERM 正常工作。
2. **#27 防重疊**：running=false 只是過期得了的快照；穩定槽鎖＋remove 成功回音，才足以換檔並排空舊事件。
3. **#28 砍到底**：tool CPU 的工具另開 session，Linux /proc 快照後代 groups，一起 TERM／兩秒 KILL；父先退出也不能忘掉孫進程。
4. **#30 連敗跟行程走**：runner 完成次數重建歸零，行程的 waiting／bad／aos 計數留在 state.waiting，換回來繼續累計；最新碼快照仍不是逐次歷史。
5. **#29 回音不失單**：done 先發布再刪原單，已有 done 不重做；remove／stop 等收屍才成功。op 與 done 之間仍非交易，不承諾崩潰自動收養或 exactly-once。

其他：#31 完整 inst 以來源家解好再搬移、#32 125 與 UTF-8／NUL 受控錯誤、#33 停機預算／spawn／I/O／home 跨層一致、#34 kernel 自己不套工作 timeout 與 init／rm 邊界。

第 3 段已完成。保留的明確界線：Linux 終止快照不追捕事前已脫離親子樹的程序；kernel 若崩在 Y 之後，runner 可能停在兩格間，重跑 tick 可續；daemon 重啟收養、跨檔交易、逐次結果對帳沒有新增。第 2 段 CPU 請求身分／中斷限制也沒有擴張實作。
