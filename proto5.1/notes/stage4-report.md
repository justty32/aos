# 第 4 段回報（2026-09-22）

第 4 段做完。依 [任務書](stage4-task.md) 與 [唯一決策來源](../../proto5/notes/2026-09-22-decisions.md)，完成模型代號、CPU models、移除同步 LLM、consume 暫停、固定結果不明、run.json／ctl.json、可選 kill_tree 與 kernel 防重疊。
只修改 `proto5.1/`；沒有 commit、push、stash、checkout，沒有改母本或 wf。

## 檔案清單

路徑相對 proto5.1；共 **38 個檔案**。任務書原檔未修改，`.build/` 內測試 log 與真跑家沿用 ignore。

| 類別 | 檔案 |
|---|---|
| 程式 10 | `lib/aos_agent_info.py`、`lib/aos_agent.py`、`lib/aos_llm_ask.py`、`lib/aos_llm_cpu.py`、`lib/aos_cpu.py`、`lib/aos_tool_cpu.py`、`lib/aos_exec.py`、`lib/aos_run.py`、`lib/aos_daemon.py`、`lib/aos_kernel.py` |
| 測試 9 | `lib/test/_util.py`、`test_agent_info.py`、`test_agent.py`、`test_llm_ask.py`、`test_llm_cpu.py`、`test_tool_cpu.py`、`test_run.py`、`test_daemon.py`、`test_kernel.py`（後八項同在 lib/test） |
| 規範 13 | `spec/agent.md`、`spec/aos-agent.md`、`spec/aos-llm-ask.md`、`spec/llm-cpu.md`、`spec/aos-llm-cpu.md`、`spec/cpu-queue.md`、`spec/tool-cpu.md`、`spec/aos-tool-cpu.md`、`spec/aos-run.md`、`spec/daemon-home.md`、`spec/aos-daemon.md`、`spec/kernel-home.md`、`spec/aos-kernel.md` |
| 導航／API 2 | `README.md`、`lib/README.md` |
| 實驗／回報 4 | `notes/findings.md`、`notes/stage4-demo.py`、`notes/stage4-trace.json`、`notes/stage4-report.md` |

格式與程式分開：agent 的內容格式集中於 agent.md；LLM／tool／daemon／kernel 各自有家與程式規範。aos-run 的兩份家檔照任務集中在同份「家」一節。規範沒有修訂記錄。

## 測試

使用指定命令：

```sh
cd /home/guanyu/projs/aos/proto5.1/lib
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test
```

**780/780 全綠，109.757 秒，無 skip**。完整輸出在 `.build/stage4-tests.log`。

| 模組 | 測試數 |
|---|---:|
| agent | 144 |
| agent_info | 98 |
| cpu | 14 |
| daemon | 30 |
| directives | 101 |
| exec | 94 |
| inst | 139 |
| kernel | 27 |
| llm_ask | 53 |
| llm_cpu | 35 |
| run | 28 |
| tool_cpu | 17 |

覆蓋模型代號／CPU 環境解 KEY／未知代號、再次暫停、已知失敗與結果不明；ctl hold／stop；kill-tree 關時跨 session 孫程式存活、開時死亡；首次訊號等本次完成、第二次 TERM；daemon 並行 5＋5／5 秒停機；0 interval＋2 秒 X 換槽後，讀 run.json 確認不能重疊排到另一顆。

審查發現並補測三個實作問題：idle 的解析與換槽競態、idle 完成差值誤灌入新人連敗、agent 提前用自己環境解析 CPU models。第一輪完整測試是 780 條、109.640 秒、1 條失敗，原因是遷移測試的 Y 太快完成而合法換回 X；改為兩秒的替代工作以固定條件，沒有放寬期限、沒有改排程規則。首輪保留在 `.build/stage4-first-tests.log`，詳見 findings #44。

修後 kernel **27/27、16.384 秒**；2 秒／0 interval 關鍵案例另外 **3/3、18.659 秒**。全部 Python 語法與規範／README 的本地檔案連結檢查通過，`git diff --check` 通過。

## LM Studio 真跑

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto5.1/notes/stage4-demo.py
```

LM Studio 已在 `http://127.0.0.1:1234/v1` 提供 `qwen/qwen3-1.7b`，未另啟 server。
A＝agent、C＝LLM CPU、T＝tool CPU、K＝kernel、D＝daemon。初始化 K、add 三個完整 inst、啟動 daemon、boot、丟 input；三顆工作 CPU 與 kernel 自己的 runner 都由 daemon 管。
使用 interval=1000 ms、quantum=5、timeout=0、kill_tree=false 的預設；now 工具是 `_run:"cpu"` 的 `sleep 2; date`，TZ=Asia/Taipei，沒有強制 tool_choice。

真跑家：`/home/guanyu/projs/aos/proto5.1/.build/stage4-demo-1790050692435986018`。

agent engine 只有：

```json
{
  "model": "small",
  "cpu": "../C",
  "params": {
    "temperature": 0,
    "max_tokens": 1024
  }
}
```

C/info.json 的 models.small 保存 endpoint、真實 model、api_key:null、timeout_ms:120000。
兩份 C/done 請求實查都只有 model／body／result，model=small，body 不含 model。

**14.901 秒完成**：LLM → now → tool CPU → LLM 最終回覆；C/done **2 份**、T/done **1 份**。
agent 最後 `state=idle, waits=[], errors=0`；A／C／T 的 stderr.log 都空。
完整命令、全部 ls、每次 runner run.json、檔案 ls 與記憶在 [stage4-trace.json](stage4-trace.json)。

以下是 `aos-kernel ls K` 的實際輸出。PROC 是 kernel 指派，RUNNING／RUNS／LAST_EXIT 讀 runner 家；跨檔快照不是同一瞬間的交易。

### 0.272 秒：think

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage4-demo-1790050692435986018/K ncpu=3 quantum=5 daemon=150792
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 1 0 False 0
1 idle False 1 0 False 0
2 idle False 1 0 False 0
queue: llm tool
done: -
bad: -
```

### 6.550 秒：act

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage4-demo-1790050692435986018/K ncpu=3 quantum=5 daemon=150792
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 7 0 False 0
1 llm False 3 0 False 0
2 tool False 7 101 True 0
queue: -
done: -
bad: -
```

### 14.901 秒：idle

```text
kernel /home/guanyu/projs/aos/proto5.1/.build/stage4-demo-1790050692435986018/K ncpu=3 quantum=5 daemon=150792
CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD
0 agent False 15 0 False 0
1 llm False 9 0 False 0
2 tool False 13 101 True 0
queue: -
done: -
bad: -
```

實際 `ls -lR` 中的 CPU 槽（完整檔案清單保留在 trace）：

```text
/home/guanyu/projs/aos/proto5.1/.build/stage4-demo-1790050692435986018/K/cpus:
total 12
lrwxrwxrwx 1 guanyu guanyu 89 Sep 22 12:18 0.json -> /home/guanyu/projs/aos/proto5.1/.build/stage4-demo-1790050692435986018/K/procs/agent.json
lrwxrwxrwx 1 guanyu guanyu 87 Sep 22 12:18 1.json -> /home/guanyu/projs/aos/proto5.1/.build/stage4-demo-1790050692435986018/K/procs/llm.json
lrwxrwxrwx 1 guanyu guanyu 88 Sep 22 12:18 2.json -> /home/guanyu/projs/aos/proto5.1/.build/stage4-demo-1790050692435986018/K/procs/tool.json
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
        "id": "EIrnxAmwQ8xAuVk4t4N5Pi0FpODT3SRA",
        "function": {
          "name": "now",
          "arguments": "{}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "EIrnxAmwQ8xAuVk4t4N5Pi0FpODT3SRA",
    "content": "2026-09-22 12:18:23 CST\n"
  },
  {
    "role": "assistant",
    "content": "現在時間是2026年9月22日中午12點18分23秒。",
    "reasoning_content": "好的，用户问现在几点，我用now工具查询了台湾的时间，返回的是2026年9月22日中午12点18分23秒。现在需要把结果简明扼要地回复给用户。要注意使用繁体中文，并且直接回答，不需要额外解释。所以直接告诉用户当前时间即可。\n",
    "tool_calls": []
  }
]
```

## stop 與殘留進程

`aos-daemon-ctl stop` 回 exit 0，stdout `{"stopped":true}`，stderr 空；daemon 自己 exit 0。
D/state.json 是 `{"pid":0,"runs":{}}`，daemon.pid 已不存在。

```text
$ pgrep -f aos-
（無輸出；退出碼 1）
```

啟動前與 stop 後都空；`new_aos_pids_after_stop=[]`、`remaining_demo_processes=[]`。
本次沒有上一段的 shell 包裝程序干擾，沒有 daemon／runner／kernel／agent／CPU 殘留。

## Findings：新增 9 條，#36～#44

最重要五條：

1. **#40 目標身分要固定**：procs 留實體檔，CPU 槽一律換 symlink，連 idle 都指固定檔；否則公布後換槽仍能偷換本次工作，破壞防重疊推論。
2. **#41 快照不等於完成歷史**：忙碌時的 target 與 last_* 可能屬於不同工作；只收可確認的新快照，每次最多加一次計數，避免 idle 差值讓新人首敗退件。interval=0 仍可能漏看完成碼。
3. **#36 設定由 CPU 解**：agent 只交模型代號與參數；送件前只驗 CPU 身分，KEY 在 CPU 環境才存在也能正常工作，請求不落整包連線設定。
4. **#42 停止期限要跨層一致**：預設 5＋5 秒階梯，ctl 等回音改 15 秒；kill_tree 只放內部 job，daemon entry 不重抄 runner 狀態。
5. **#39 工具結果不明不等於已知失敗**：只有失聯／收屍沒有可靠結果才給固定 JSON 文字，不重試；真的 timeout、非零與壞 payload 仍各自回報。

其餘：#37 同步 CLI 改只組 body；#38 沿既有 `$opt:"consume"` 等待格式、門開才吃檔；#43 每次 add 用新 runner 家，避免舊 ctl；#44 整套抓到測試未固定遷移條件。

與任務示意不同但必要的地方：consume 用 agent.md 既有 `$opt`／`$val` 格式；增加固定 idle.json 並保留 procs 實體檔；ctl 預設等 15 秒；失敗／等待計數按可確認快照而非不明 runs 差值。沒有增加請求 id、完成歷史、重試、清理服務或崩潰對帳。
