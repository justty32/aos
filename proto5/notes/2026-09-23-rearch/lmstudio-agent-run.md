# T9 第 4 段：LM Studio 真跑 agent 一整圈（2026-09-24）

結論：**通**。兩次皆完成 daemon → kernel → agent tick → aos-llm-call → date 工具 → aos-llm-call → idle，退出碼 0。第二次沿用同一份 D／K／agent-bob，記憶由 4 則累積至 8 則；兩次的新增記憶皆為 user、assistant(tool_calls)、tool、assistant(非空純文字)。沒有修改產品程式或規範，沒有 commit／push。

## ① 模型與設定

LM Studio 原已在 `localhost:1234` 服務；兩次 `/v1/models` 都含 `google/gemma-4-e4b`，未另起 server、未 load 或切換模型。`llm-home/llm.json` 的 small 指向 `http://127.0.0.1:1234/v1`，HTTP timeout 180000 ms；agent 的執行 timeout 190000 ms，params 為 `temperature: 0`、`max_tokens: 2048`。

K 有 k（kernel）、0（default）、llm（llm）三顆 cpu；0 與 llm 的 PATH 均以 `$fmt`＋`$env` 前置 `proto5/cli`，llm 另帶 `AOS_LLM_CONFIG` 絕對路徑。kernel tick 200 ms、預設行程 interval 500 ms、agent tick interval 500 ms。

## ② 指令（可複製重跑）

從 repo 根目錄執行（前提是 LM Studio 已啟動且模型已載入）：

```sh
curl -s localhost:1234/v1/models
proto5/notes/2026-09-23-rearch/lmstudio/agent-run.sh /tmp/t9-agent-run
proto5/notes/2026-09-23-rearch/lmstudio/agent-run.sh /tmp/t9-agent-run
```

入口：[agent-run.sh](lmstudio/agent-run.sh)（可執行），設定：[agent-kernel-info.template.json](lmstudio/agent-kernel-info.template.json)。未給引數時採 `$T4`，再未設則 `./t4`。所有執行產物在工作目錄下，回音快照另存在 `runs/run-XXXXXXXX/`。

腳本第一次 init K 後寫範本，之後沿用既有家與設定，不清記憶；若已有未完成當批、未消費輸入或關著的門，會報錯並停機。每次以投件前記憶長度為基準，只驗新增四則，並核對 date 的工具名、call id、非空結果與最後回答。input 以 JSON 字串原子 rename 投入。state 與記憶每 50 ms 輪詢，300 秒上限；時間表是觀測到狀態的時間，並非內部轉態的精確時間。

正常收尾順序：agent stop → kernel stop → 等 phase=stopped → 等 daemon children={} → daemon stop → wait 退出 → pgrep 本次目錄為空。EXIT trap 也會嘗試依序停機；同一工作目錄有 flock 防止同時重跑。既有 LM Studio 服務保留。

## ③ 兩次時間

| 項目 | 第一次 | 第二次（沿用家與記憶） |
|---|---:|---:|
| aos-agent start | 0.221 s | 0.220 s |
| 投件→第一次 think | 1.002 s | 0.050 s |
| 投件→act | 2.907 s | 1.956 s |
| 投件→第二次 think | 4.863 s | 3.911 s |
| 投件→idle（一整圈） | **6.769 s** | **5.817 s** |
| 停機（agent stop→daemon 退） | 0.519 s | 0.501 s |
| 腳本起始→停完 | 7.898 s | 6.852 s |

## ④ 回音原文（含記憶全文）

以下原樣收錄每次 transcript，包含 start／stop、state 變化的絕對時間與相對秒數、最後記憶全文，以及累積的 `log/agent.err`／`log/llm.err` 內容。兩次皆為空檔。

### 第 1 次

原始產物：`/tmp/t9-agent-run/runs/run-OZ4rDlk6`。

```text
== LM Studio：2026-09-24T10:46:11+08:00 ==
google/gemma-4-e4b 已在模型清單
chain 1790217972187340598-232491  phase running  last_seq 0  daemon alive
kernel cpu k  current k-1790217972187340598-232491-1.json  requests 1
cpu k  pool kernel  idle  running
cpu 0  pool default  idle  running
cpu llm  pool llm  idle  running
queue -
$ AOS_K=$K aos-agent start agent-bob
aos-agent start 退出碼 0（stdout/stderr 空）；start：0.221 秒
{"time": "2026-09-24T10:46:12.536+08:00", "seconds": 0.0, "event": "投件前", "state": "idle", "history_len": 0}
{"time": "2026-09-24T10:46:12.536+08:00", "seconds": 0.0, "event": "投件", "state": "idle", "history_len": 0}
{"time": "2026-09-24T10:46:13.538+08:00", "seconds": 1.002, "event": "state 變化", "state": "think", "history_len": 1}
{"time": "2026-09-24T10:46:15.443+08:00", "seconds": 2.907, "event": "state 變化", "state": "act", "history_len": 2}
{"time": "2026-09-24T10:46:17.399+08:00", "seconds": 4.863, "event": "state 變化", "state": "think", "history_len": 3}
{"time": "2026-09-24T10:46:19.305+08:00", "seconds": 6.769, "event": "state 變化", "state": "idle", "history_len": 4}
--- 最後記憶全文 ---
[
  {
    "role": "user",
    "content": "現在幾點？請用工具查。"
  },
  {
    "role": "assistant",
    "content": "",
    "reasoning_content": "",
    "tool_calls": [
      {
        "type": "function",
        "id": "MBk6u0HeCpwabpQiLIVc57gLftFWHGVc",
        "function": {
          "name": "date",
          "arguments": "{}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "MBk6u0HeCpwabpQiLIVc57gLftFWHGVc",
    "content": "2026-09-24 10:46:16\n"
  },
  {
    "role": "assistant",
    "content": "現在是 2026 年 9 月 24 日，上午 10 時 46 分 16 秒。",
    "reasoning_content": ""
  }
]

投件→idle 整圈：6.769 秒
$ aos-agent stop agent-bob
aos-agent stop 退出碼 0（stdout/stderr 空）
$ aos-kernel stop K
$ aos-daemon stop --home D
stopped
daemon 退出碼 0
停機：0.519 秒
起 daemon→停完：7.898 秒
--- log/agent.err ---
（空檔）
--- log/llm.err ---
（空檔）
pgrep（本次 /tmp/t9-agent-run）：空
結果退出碼 0；原始回音：/tmp/t9-agent-run/runs/run-OZ4rDlk6
```

### 第 2 次

原始產物：`/tmp/t9-agent-run/runs/run-C6i86vmZ`。

```text
== LM Studio：2026-09-24T10:46:23+08:00 ==
google/gemma-4-e4b 已在模型清單
chain 1790217983621676497-232686  phase running  last_seq 0  daemon alive
kernel cpu k  current k-1790217983621676497-232686-1.json  requests 1
cpu k  pool kernel  idle  running
cpu 0  pool default  idle  running
cpu llm  pool llm  idle  running
queue -
$ AOS_K=$K aos-agent start agent-bob
aos-agent start 退出碼 0（stdout/stderr 空）；start：0.220 秒
{"time": "2026-09-24T10:46:23.960+08:00", "seconds": 0.0, "event": "投件前", "state": "idle", "history_len": 4}
{"time": "2026-09-24T10:46:23.960+08:00", "seconds": 0.0, "event": "投件", "state": "idle", "history_len": 4}
{"time": "2026-09-24T10:46:24.011+08:00", "seconds": 0.05, "event": "state 變化", "state": "think", "history_len": 5}
{"time": "2026-09-24T10:46:25.916+08:00", "seconds": 1.956, "event": "state 變化", "state": "act", "history_len": 6}
{"time": "2026-09-24T10:46:27.871+08:00", "seconds": 3.911, "event": "state 變化", "state": "think", "history_len": 7}
{"time": "2026-09-24T10:46:29.777+08:00", "seconds": 5.817, "event": "state 變化", "state": "idle", "history_len": 8}
--- 最後記憶全文 ---
[
  {
    "role": "user",
    "content": "現在幾點？請用工具查。"
  },
  {
    "role": "assistant",
    "content": "",
    "reasoning_content": "",
    "tool_calls": [
      {
        "type": "function",
        "id": "MBk6u0HeCpwabpQiLIVc57gLftFWHGVc",
        "function": {
          "name": "date",
          "arguments": "{}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "MBk6u0HeCpwabpQiLIVc57gLftFWHGVc",
    "content": "2026-09-24 10:46:16\n"
  },
  {
    "role": "assistant",
    "content": "現在是 2026 年 9 月 24 日，上午 10 時 46 分 16 秒。",
    "reasoning_content": ""
  },
  {
    "role": "user",
    "content": "現在幾點？請用工具查。"
  },
  {
    "role": "assistant",
    "content": "",
    "reasoning_content": "",
    "tool_calls": [
      {
        "type": "function",
        "id": "Mca0cxMhihjDgqMjaDRTSHZj6oRciUFC",
        "function": {
          "name": "date",
          "arguments": "{}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "Mca0cxMhihjDgqMjaDRTSHZj6oRciUFC",
    "content": "2026-09-24 10:46:27\n"
  },
  {
    "role": "assistant",
    "content": "現在是 2026 年 9 月 24 日，上午 10 時 46 分 27 秒。",
    "reasoning_content": ""
  }
]

投件→idle 整圈：5.817 秒
$ aos-agent stop agent-bob
aos-agent stop 退出碼 0（stdout/stderr 空）
$ aos-kernel stop K
$ aos-daemon stop --home D
stopped
daemon 退出碼 0
停機：0.501 秒
起 daemon→停完：6.852 秒
--- log/agent.err ---
（空檔）
--- log/llm.err ---
（空檔）
pgrep（本次 /tmp/t9-agent-run）：空
結果退出碼 0；原始回音：/tmp/t9-agent-run/runs/run-C6i86vmZ
```

## ⑤ 撞到的問題

**0 條；沒有實際失敗或程式 bug，也沒有因此發現規範問題。** 本次直接配置了任務書提醒的 default 池 PATH、足夠的 max_tokens 與較長的 agent timeout，兩次都未出現空的最終回答、找不到 CLI、工具失敗或逾時。模型第一則 assistant 的空 content 搭配非空 tool_calls 正常被接收，下一次得到工具結果後產生中文回答。

## ⑥ 驗證與變更範圍

- `bash -n lmstudio/agent-run.sh` 通過；兩次真跑退出碼均為 0，兩次本次目錄 pgrep 均空。
- 完成後依驗收全域檢查：

  ```sh
  pgrep -fa 'aos-cpu|aos-daemon|aos-kernel|aos-agent|aos-llm-call' | grep -Ev '(zsh|bash|sh) -c|pgrep'
  ```

  輸出空；未停掉其他 session 的任何行程。
- 新增三份檔案：上述 shell、kernel JSON 範本與本文。未改 `proto5/lib/aos_agent*.py`、`aos_llm_call.py` 或其他產品程式，因此本次沒有觸發修 bug 後的 unittest 要求。未碰 README、spec、code-map、proto5.1。
- `-o` 回報路徑從本次 Codex 行程啟動參數確認為 `/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/f594f460-c0a3-4df1-b41f-e70375230e84/scratchpad/t9/seg4-out.md`。
