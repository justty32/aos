← [本提案](README.md)｜[notes 索引](../README.md)｜範本 [templates/cli-agents](../../templates/cli-agents/README.md)｜教程 [07](../../tutorials/07-cli-agents.md)

# 階 0 做完的報告（2026-09-24）

照使用者拍板的五條（普通 cpu 池、牢外保守旗標、另一個 kernel 家 claude 1／codex 2、每次從上一次成功的分岔、不讀他自己的設定）把階 0 做出來。**`lib/`、`spec/`、`cli/` 一行沒改。**

## 做了什麼

| 件 | 檔 |
|---|---|
| 範本（放 `templates/`：要被人複製去用，不是 agent 工具包也不是紀錄） | [templates/cli-agents/](../../templates/cli-agents/README.md)：`kernel2.json`、`claude-job.json`、`claude-next.json`（分岔）、`codex-review.json`、`codex-review-next.json`（分岔）＋README（旗標為什麼、成功怎麼判） |
| 教程 | [tutorials/07-cli-agents.md](../../tutorials/07-cli-agents.md)，開頭就是「三個洞」；tutorials／proto5 README 各加一列 |
| 一條龍腳本 | [stage0-run.sh](stage0-run.sh)：`bash stage0-run.sh [W] [--with-claude]` |
| 審查 | [review2-task.md](review2-task.md)／[review2-astra.md](review2-astra.md) |

範本的旗標：claude `-p --output-format json --model sonnet --max-turns 8 --max-budget-usd 0.50 --safe-mode --permission-mode acceptEdits --permission-prompts none --disallowedTools "Bash(git push:*)"`；
codex `exec --json -m gpt-6-astra -s read-only --skip-git-repo-check -C <WS> -o <JOB>/out/answer.md -`。「跳過權限」類旗標一個都沒有。
cpu 的環境用 `$opt: clear` 只留 `PATH`、`HOME`、`LANG`（codex 再加專用 `CODEX_HOME`），順便擋掉 API 金鑰與 `CLAUDECODE`／`CLAUDE_CODE_*`。

## 五條驗證（cli-facts 末尾），各一句

1. **claude 吃 stdin、json 欄位**：吃（`claude -p < task.md`）；欄位有 `type`、`subtype`（`success`／`error_max_budget_usd`）、`is_error`、`result`、`session_id`、`total_cost_usd`、`num_turns`、`terminal_reason`、`usage`、`modelUsage`。`--max-turns` help 沒列但認得。`--resume <id> --fork-session` 給新 id、記得上一次。
2. **訂閱下 `--max-budget-usd`**：**有用**。設 0.001 → `is_error: true`、`subtype: error_max_budget_usd`、`terminal_reason: budget_exhausted`、退 1；但它是呼叫**完**才算（那次照算 0.019 美元），擋不住第一次呼叫。`total_cost_usd` 訂閱下也印（`costBasis: list`＝照定價算，不是真的扣錢）。
3. **巢狀 claude**：**不會被擋**。在 Claude Code 裡直接跑（帶著 `CLAUDECODE=1` 和一串 `CLAUDE_CODE_*`，含 `CLAUDE_CODE_MESSAGING_SOCKET`）照常回 `ok`。範本仍把它們清掉：那些變數指向父 session 的通訊管道，子程式沒必要碰。**清掉不算違反第 2 條**——第 2 條禁的是放寬權限的旗標，清環境變數只是讓它更像一個乾淨的新行程，權限沒變大。
4. **codex 接續時沙盒、被砍時殘留**：`codex exec -s read-only … fork <id> -`（`-s` 放在 `fork` 前面）**有效**——叫它 `touch` 一個檔被拒、檔不在；換 `-s workspace-write` 再分岔，session 檔記的就是 `workspace-write`：**每次照這次給的，不跟上一次**。用 `aos-exec --timeout-ms` 在它跑 `sleep 45` 中途砍，3 秒後沒有留下 codex、`sleep` 或背景 server（但同時間別隊的 codex 身上看得到一支 `codex-code-mode-host`，自己一個 process group，砍整組砍不到它；這次沒留下，不保證）；`codex exec` 沒用共用的背景 server（沒看到 app-server 行程）。事件名跟官方一致：`thread.started`（`thread_id`）、`turn.started`、`item.started`／`item.completed`（`agent_message`、`command_execution`）、`turn.completed`（`usage`）。
5. **bwrap 牢**：照指示跳過（牢還沒做）。

## 一條龍真跑（節錄，`stage0-run.sh … --with-claude`）

```text
== 一般 kernel 家 K（kernel 池那顆自動叫 k）          booted 2 cpus
== 花錢的 kernel 家 K2（kernel 池那顆叫 k2）          booted 4 cpus
== 放一張 codex 唯讀審查單
cli-1790239478440401266-1081994.json …/K2/responses/cli-1790239478440401266-1081994.json
health ok
cpu     4 顆：忙 1、閒 2、kernel 1
  kernel  k2   tick  -          running
  claude  cc   閒    -          running
  codex   cx0  忙    review-ls  running
          cx1  閒    -          running
回音（等了約 55 秒）：{"code": 0, "kind": "child", "timed_out": false, "stopped": false, "ms": 55918}
"type":"turn.completed","usage":{"input_tokens":139425,…
- proto5/tools/base/ls:26：os.path.isdir() 會跟隨子項目的符號連結，若連結指向根目錄外 …
- proto5/tools/base/ls:27：檔名未跳脫換行字元 …
- proto5/tools/base/_common.py:125–126：父目錄無搜尋權限時誤報 NotFound …
== claude 單 c1   {"code": 0, …, "ms": 3511}   {'subtype': 'success', 'result': 'ok', 'session_id': '0c31125f-…', 'total_cost_usd': 0.0195}
== claude 單 c2：從 c1 分岔   {"code": 0, …}   {'subtype': 'success', 'result': 'ok', 'session_id': 'f155e58e-…'}
== 停機   stopped ×3
```

codex 那三條是審查員對 `tools/base/ls` 的真意見，**這次沒去修**（不在範圍），留給 tools 那條線判斷。

另外用免費的 `sleep 77` 在 claude 池試了取消（教程第 6 步）：`aos-kernel rm` 當下回 `Removed`，`sleep` 照跑；往 daemon 放 `kill cc` 後**約 5 秒**（`stop_wait_ms`：先溫和停、等 5 秒才 TERM）`sleep` 才死，kernel 下一格就補拉一顆新的 `cc`。

## 撞到的坑

| 坑 | 怎麼處理 |
|---|---|
| 兩個 kernel 家共用 daemon，kernel 池那顆都叫 `k` 會 `NameTaken` | 範本 K2 明寫 `"k2": {"pool": "kernel"}`；教程第 1 步講 |
| `add --name X` 之後回音檔名仍是 kernel 取的 `cli-….json`，`ack X` 報 `NotFound` | 規範本來就這樣（`--name` 只是行程名）。腳本改成用 `add` 印的第一欄 ack；教程常見錯誤加一列 |
| `aos-kernel check` 對 K2 報 `bad pools: llm 池沒有 cpu`、退 1 | 教程說忽略；要不要改規範留給使用者（下表 #2） |
| `CODEX_HOME` 在 `/tmp` 底下，codex 警告「不在暫存資料夾建輔助程式」 | 只是警告；教程與範本 README 註明放家目錄底下 |
| codex 登入檔複製一份的話，其中一邊換新憑證可能讓另一邊失效 | 用**符號連結**；這次前後 `~/.codex/auth.json` 的 md5 沒變。codex 若改用「寫新檔再改名」更新，連結會被換成一般檔，主檔變舊——**還沒碰到，列為風險** |
| 使用者自己的 `~/.codex/config.toml` 預設 `sandbox_mode = "danger-full-access"` | 專用 `CODEX_HOME` 就不讀它；範本每張單子都明寫 `-s read-only` |
| inst 的 `stdin`／`stdout` 相對的是 `cwd`（工作區） | 範本全用 `@JOB@`／`@WS@` 換成絕對路徑 |

## 階 1（`aos-cli`）開工前要注意

- **成功要看兩層**：回音 `code=0` 之外，claude 看 `is_error`，codex 看 `turn.completed`；只有兩層都過才把 session 往前推（本次實測的欄位名可直接用）。
- **預算擋不住第一次呼叫**；額度用完時的退出碼與訊息這次沒碰到（沒去燒額度），`aos-cli` 要把「`code=0` 但輸出說失敗」和「看不懂的輸出」都當失敗。
- **取消**：現有唯一的路是 daemon `kill <cpu>`，要等 `stop_wait_ms`（5 秒）；之後 kernel 立刻補拉。`aos-cli cancel` 要在砍前再確認那顆 cpu 手上還是這張（競態仍在），長遠要 kernel「按單號砍」。
- **K2 的 check**：要嘛 `aos-cli` 自己做一份檢查（`claude`／`codex` 在 daemon 的 PATH、`CODEX_HOME/auth.json` 在），要嘛改 `aos-kernel check`。
- **登入檔**：`CODEX_HOME` 用符號連結的風險（上表）要在 `aos-cli init` 時檢查一次「還是不是連結」。
- 測試用假的 `claude`／`codex` 腳本就夠：輸出形狀照本報告第 1、4 條。

## 花了多少

claude 真跑 **4 次**（直接 2：stdin／json、預算；經 kernel 2：c1、c2），每次都只回 `ok`，照定價算共約 0.09 美元。
codex 真跑 **6 次**（直接 4：只回 ok、分岔試沙盒 ×2、逾時砍；經 kernel 1：審 `tools/base/ls`；F 審查 1）。

## 要使用者拍的

| # | 題目 | 我的預設 |
|---|---|---|
| 1 | 範本放 `proto5/templates/cli-agents/`（新開的 `templates/`） | **是** |
| 2 | K2 沒有 llm 池時 `aos-kernel check` 報 bad：改成「kernel 家裡有 agent 才要 llm 池」，還是就讓它 bad、教程說忽略 | **先忽略**；階 1 由 `aos-cli` 自己檢查 |
| 3 | codex 登入用符號連結（共用一份、會跟著換新）還是複製（兩份、可能互相讓對方失效） | **符號連結** |
| 4 | claude 範本預設不准跑任何指令（只准改檔），要跑測試得逐條加 `--allowedTools` | **是** |
| 5 | 範本的 `--max-budget-usd 0.50`、`--max-turns 8`、逾時 30 分鐘 | **照這組**，用一陣子再調 |
