← [proto5 README](../../README.md)｜教程 [07 claude／codex 當 cpu](../../tutorials/07-cli-agents.md)｜提案 [cli-agents](../../notes/2026-09-24-cli-agents/README.md)

# 範本：Claude Code／Codex 當一種普通 cpu（階 0）

**不是新程式**：一份另一個 kernel 家的設定、四張單子（inst.json）範本。照 [教程 07](../../tutorials/07-cli-agents.md) 用。
放這裡（不放 `tools/`、不放 notes）：`tools/` 是 agent 的工具包，notes 是紀錄；範本是要被人複製去用的，所以另開 `templates/`。

## 檔案

| 檔 | 是什麼 | 要換的字 |
|---|---|---|
| [kernel2.json](kernel2.json) | 花錢的 kernel 家 K2：`k2`（kernel 池）、`cc`（claude 池 1 顆）、`cx0`／`cx1`（codex 池 2 顆） | `@W@`＝工作目錄 |
| [claude-job.json](claude-job.json) | 一張新的 `claude -p` 單子 | `@JOB@`＝這張單子的資料夾、`@WS@`＝讓它工作的資料夾 |
| [claude-next.json](claude-next.json) | 接著聊：從**上一次成功的**那次分岔（`--resume <id> --fork-session`） | 同上＋`@SESSION@` |
| [codex-review.json](codex-review.json) | 一張 `codex exec` 唯讀審查單 | `@JOB@`、`@WS@` |
| [codex-review-next.json](codex-review-next.json) | 接著審：`codex exec … fork <id> -` | 同上＋`@SESSION@` |

換字用 `sed`（路徑只用英數與 `/ . _ -`：`&`、`|`、引號、空白會把 sed 或 JSON 弄壞），**全部換成絕對路徑**（inst 裡 `stdin`／`stdout` 是相對 `cwd`，也就是工作資料夾，不是單子資料夾）：

```sh
sed -e "s|@JOB@|$J|g" -e "s|@WS@|$WS|g" claude-job.json > $J/inst.json
```

## 旗標為什麼這樣選

使用者 09-24 拍板：第一版跑在牢外、用他自己的登入，**「跳過權限」那類旗標一律不出現**（`--dangerously-skip-permissions`、`bypassPermissions`、codex 的 `--dangerously-bypass-approvals-and-sandbox`）。

| 旗標 | 為什麼 |
|---|---|
| claude `-p --output-format json` | 一次問完就退；結果是一個 JSON（欄位見下） |
| `--max-turns 8` | help 沒列，但真跑確認認得；一張單子最多來回幾輪 |
| `--max-budget-usd 0.50` | **訂閱登入下也有效**（09-24 真跑）：超過就 `is_error: true`、`subtype: error_max_budget_usd`、退 1。它是呼叫完才算，擋不住第一次呼叫 |
| `--safe-mode` | 不讀使用者自己的 CLAUDE.md、記憶、skill、hook、MCP；登入照常 |
| `--restricted` | 拿掉 Bash 等會跑程式的工具與 WebFetch，檔案工具只能碰工作資料夾，也不讀使用者／專案的設定檔。**不要**再用 `--tools` 把執行工具加回來（會把這道牆拆掉）。09-24 審查後加，真跑確認照常回話 |
| `--permission-mode acceptEdits --permission-prompts none` | 會問人的動作一律被拒（沒人按「允許」）；`acceptEdits` 准它改工作資料夾裡的檔。光靠這兩個**擋不住**唯讀指令與部分檔案指令，所以才要上一行 `--restricted` |
| 想讓它跑測試？ | 得拿掉 `--restricted` 再加 `--allowedTools "Bash(make test)"`。**這等於准它跑工作區裡的任意程式**：它能先改 Makefile 或測試，再跑「被允許的」`make test`。只在你信得過工作區內容、又能接受「牢外、改到工作區以外也擋不住」時才這樣做 |
| `--disallowedTools "Bash(git push:*)"` | 多一道；但換個寫法就繞過，真正的牆是上一行（不准跑指令）與以後的牢 |
| codex `-s read-only` | 它跑的指令只能讀。**放在 `fork` 前面也有效**（09-24 真跑：每次都照這次給的，不跟上一次） |
| codex `-m gpt-6-astra` | 這台只有 astra 能用 |
| codex `CODEX_HOME`（在 kernel2.json 的 cpu 環境裡） | 專用設定資料夾，裡面只放一個指向 `~/.codex/auth.json` 的**符號連結**；不讀使用者家裡的 `config.toml`（那份預設 `danger-full-access`）與 `AGENTS.md`。**只隔開使用者家那份**：工作區自己的 `AGENTS.md`、專案與系統層的設定照讀。連結有風險：codex 若用「寫新檔再改名」換新憑證，連結會變成一般檔、兩份從此分家。**別放在 `/tmp` 底下**：codex 會警告不建輔助程式 |
| 三顆工作 cpu 的環境 `$opt: clear`（`k2` 不清） | 只留 `PATH`、`HOME`、`LANG`（codex 再加 `CODEX_HOME`）：擋掉剛好在環境裡的 `ANTHROPIC_API_KEY`／`OPENAI_API_KEY`（免得改走付費 API），也擋掉從 Claude Code 裡開 daemon 時帶進來的 `CLAUDECODE`、`CLAUDE_CODE_*`。代價：代理（`HTTPS_PROXY`）、自訂憑證路徑之類也一起清掉，你的環境要靠它們才連得上，就在 `$val` 裡逐項補回 |

## 結果在哪、成功怎麼判

| | 回音（`K2/responses/…`） | 答案 | 成功 | 下一次要的 id |
|---|---|---|---|---|
| claude | `kind` 是 `child`、`code` 0、`timed_out`／`stopped` 都 `false`（`code` 1＝失敗，含超過預算） | `out/result.json` 的 `result` | `is_error: false`、`subtype: success` | `session_id` |
| codex | 同上 | `out/answer.md`（`-o` 寫的最後一則） | `out/events.jsonl` 有 `turn.completed`（失敗是 `turn.failed`） | 第一行 `thread.started` 的 `thread_id` |

**回音和輸出兩層都過**才算成功；**只有成功的那次才拿來當下一次的 `@SESSION@`**；失敗、逾時、被砍的那次不算（使用者拍板：失敗的那次不算）。
