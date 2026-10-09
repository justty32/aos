← [up](README.md)

## 操作與契約

Python 3.11+、純標準庫；在 repo 根跑。缺工作流模板時先裝
`git clone git@github.com:justty32/workflows.git ~/repo/workflows`，或設 `AOS7_WF_HOME`。

- `aos7-up /tmp/aos/bob -d`：背景跑，確認 bob 被叫醒後印三行離開。
- `aos7-up stop /tmp/aos/bob`：停整個房子的心跳與它起的全部任務，包含其他 node；不刪任何檔。
- `aos7-up /tmp/aos/real --model chatgpt-gpt-6-luna -d`：真 AI；先起 LiteLLM。認證見 [llmcall](../../packs/llmcall/README.md)。
- 已有心跳只接上看；Ctrl-C 只停觀看，停心跳用 stop。入口自己起的前景心跳在 Ctrl-C／SIGTERM 後收掉。
- `ask`／`brain` 交給同目錄 `aos7_up_brain.main([子命令, …])`（ask 在 `aos7_up_ask.py`，回信邏輯與 prompt 在 `prompts/`）。

安裝只透過各包公開 CLI。brain 用 llmcall 必須有帳，因此保留 budget-llm。
compact 在工作簿變厚時自動整理。routines 只裝它的 keep 任務、不加任何例行列（表空就什麼都不做；之後 `aos7-routines add` 才有事）。跨包副作用一律由 up 做：各包自己不再裝任務、不替別人建 events/。

## 建了什麼、停了什麼

- `<node>/AGENTS.md`、`CLAUDE.md`、`.claude/`、`wf/`：工作簿模板與入口。AGENTS.md 是導入完成的標記，已有它就不再 init。
- `<node>/inbox/`、`tools/`：信箱與工作流工具；`<node>/events/`：信的提醒通道（mail 用）。
- `<node>/skills/`：三本技能連結與 `index.json`；已有同名項（含壞連結）不改。
- `<node>/budget/llm/`：grant、ledger 與帳的證據；假／真 AI 已開帳後不能互換，換名字另起。
- `<node>/.aos/`：`tasks.json`、`up.json`、`up.lock` 與核心執行證據。
- `<node>/llmcall/`、`brain/`、`compact/`：之後執行任務時產生。
- `<房子>/you/inbox/`、`you/events/`：人的回信箱與提醒通道。
- `<房子>/.aosd/`：心跳的鎖、紀錄、狀態與 `up-daemon.log`。
- 常駐程式：心跳一個，node 上 `budget-llm`、`brain`、`compact`、`routines` 四個 keep 任務（brain 的 argv 凍結為 `python3 <proto7-2>/modules/up/aos7-up brain <node>`）。

stop 收掉心跳與它起的全部任務，不刪任何檔。全清先 stop，再刪 node 與 you；房子沒別的 node 時也可刪 `.aosd/`。

## 設定與重接

安裝與啟動拿 `<node>/.aos/up.lock`；up 自己寫的 JSON 都用暫存檔＋rename。
重跑只補缺的 grant、ledger、技能連結與任務，更新技能 index，保留原信件。
SIGKILL 心跳後重跑，核心接手收掉舊任務；不重新開帳。up 不寫 timeline。

`<node>/.aos/up.json` 必須是完整物件：

| 欄位 | 意思 |
|---|---|
| `v` | 固定 1 |
| `node`、`house`、`name` | 絕對 node 路徑、上一層房子路徑、資料夾名 |
| `you`、`mail_root` | 固定人的名字 you、房子路徑 |
| `model` | 字串或 null；null 是假 AI；不給 --model 保留原值 |
| `litellm_url` | 環境變數 AOS7_LITELLM_URL 有設優先，其次舊值，再預設 http://localhost:4000/v1 |
| `budget`、`holder` | 固定 budget/llm、brain |
| `gateway` | llm.fake 或 llm.litellm，依 model 選 |

grant 固定 1000 萬 token，已有 grant 永不改。真 AI 同 gateway 可以換模型。
名字只准英數、`.`、`_`、`-`，不能以 `.` 開頭，you 留給人。

register 後最多等 15 秒，必須看到 node 的 round.json 回合號 ≥1 且大於開始前。
持鎖不是醒來的證據。自己起的心跳在交接前任何失敗都送 SIGINT，等 30 秒，逾時 SIGKILL。
前景觀看中中斷且收乾淨退 0；收尾逾時退 3，可能仍有工作在跑，下次 up 由核心接手。
子指令獨立 process group；中斷送整組 SIGTERM，等 5 秒再 SIGKILL，不留孫程序。
所有 Python 子程序使用 -B，不在程式目錄留 __pycache__。

status 六行唯讀；體檢 OK 只報 OK，有問題附 check 指令。用量取 budget status 的 used，讀不到顯示 —。
觀看直接掃信件，包含 you/inbox/done 回信，不更新 mail 的讀取快照。

## 錯誤與退出

錯誤 stderr 一行 `aos7-up: 發生什麼。怎麼辦`，不印 traceback。

| 退出 | 意思與處理 |
|---|---|
| 0 | 做到了；前景正常停也算 |
| 1 | 做不到：缺模板、子指令確定失敗（附 stderr 最後一行）、心跳起不來（附 log）；照訊息處理 |
| 2 | 參數不對：名字、換假／真 AI、up.json 形狀錯、status 沒 node；修正再跑 |
| 3 | 不確定：準備中斷、子指令退 3、讀寫故障、停不下來或沒看到 node 醒來；檔案留著，照原樣再跑會接續 |

up.json 壞了時刪掉該檔再 up。未知結果不清檔、不重送。

## 程式與驗證

| 檔案 | 職責 |
|---|---|
| `aos7-up` | 薄入口 |
| `aos7_up.py` | 冪等安裝、起停、起動證據與回收 |
| `aos7_up_cli.py` | 參數、錯誤與 ask／brain 分派 |
| `aos7_up_brain.py`、`aos7_up_ask.py`、`prompts/`、`examples/` | brain 一回合與 ask（另一份交接，測試 `tests/test_brain*.py`） |
| `aos7_up_status.py` | 六行狀態、觀看、設定驗證、子指令與 atomic |
| `tests/test_up.py` | 起停、信與已花預算 SIGKILL 重接、唯讀摘要 |
| `tests/test_up_model.py` | 模型、端點保存、拒絕 gateway 變更、經 up 的 ask 假 AI 一圈 |
| `tests/test_up_edges.py` | 重跑保信、壞設定、共享心跳、訊號、並行與唯讀 |
| `tests/test_up_errors.py` | 子指令摘要、未知讀寫、stop 逾時、壞名字無副作用 |
| `tests/test_up_dispatch.py` | 分派、真檔觀看事件、啟動／收尾逾時、中斷與程序組 |

從 repo 根跑：

```sh
systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/tests/run_all.py modules/up/tests
bash wf/tools/wf-lint.sh proto7-2/modules/up
```

缺模板會 skip 整合測試；交付前應確認沒有 skip。
