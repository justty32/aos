← [本提案](README.md)

# 成本與權限

## 1. 錢花在哪

| 來源 | 怎麼算 | 誰在一起用 |
|---|---|---|
| Claude 訂閱登入（現在 `~/.claude` 的） | 方案的時段額度與每週額度，用完就被擋到重置 | **跟使用者自己、跟調度者（現在這個頂層 session）共用同一份** |
| Codex（ChatGPT 方案登入，`~/.codex/auth.json`） | 同上，方案額度 | 跟調度者派的 codex 隊員共用 |
| API key（`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`--bare`＋apiKeyHelper） | 照 token 付真錢 | 只有 aos |
| `claude ultrareview`、`--cloud` | 雲端，另計 | — |

**登入來源要明定**：cpu 整包繼承 daemon 的環境時，環境裡剛好有 API key，就可能改走付費 API（誰優先**未實測**）。claude／codex 池的 cpu 在 `envs` 裡明寫要的變數、其他清掉。

**最大的風險是搶額度**：aos 半夜排了十張 claude 單子，隔天早上使用者自己開 Claude Code 發現額度沒了。先分清兩種用法：

| | 手動佇列（階 0） | 受控投遞（階 1 的 `aos-cli`） |
|---|---|---|
| 怎麼放 | 人一次把十張 `aos-kernel add --once` 塞進 kernel | aos-cli **一張一張放**，前一張收回才放下一張 |
| 連敗會停嗎 | **不會**，已經在 kernel 裡的照跑 | 會，停止放新的 |
| 額度 | 只靠池大小與每張逾時 | 放之前可以先扣自己記的配額 |

煞車（由強到弱）：
1. **池的大小**：`claude` 池 1 顆＝同時最多 1 張。它**不限總額度**，也不限一張單子裡它自己開的子 agent，更擋不住有人直接在終端機開 claude。
2. **單子的逾時**：每張最多燒多久。
3. **受控投遞＋連敗暫停**：額度用完→連續失敗→ aos-cli 不再放新單（[as-cpu §9](as-cpu.md#9-失敗)）。
4. **挑便宜的模型**：單子預設 `--model sonnet`；codex 預設 terra 級，審查才用 astra。
5. `--max-budget-usd`：help 寫「API 呼叫」，訂閱下有沒有用**未實測**，不能當主要煞車。

aos 現在**沒有**「花了多少」的帳：claude 的 json 有費用欄（名字未實測）、codex 的 `turn.completed` 有 usage，aos-cli 逐張記進 cli 家，先記、不擋。

## 2. 誰能叫它們

**任何能往 `K/requests/` 放檔的行程，都能放一張 `--pool claude` 的單子**；而且能放任意 inst＝能跑任意指令。kernel 不問是誰放的，也沒有「這個池只准誰用」。
這包括 agent 的工具：照 [agent-access 的 env-flow](../2026-09-24-agent-access/env-flow.md)，工具通常繼承得到 `AOS_KERNEL_HOME`。
更根本的是：同一個使用者身分的行程**本來就能直接開 `claude`**，不必經過 kernel。所以真正要擋的是「agent 的工具」這種不受信的行程，靠的是**隔離**，不是藏路徑。

使用者要看的「priority／`_pool`」筆記（`notes/2026-09-24-priority-and-shared-cpu/`）**在 main 上還沒有**，我沒讀到；這裡只用現有的池。

| 做法 | 是什麼 | 擋得住誰 |
|---|---|---|
| 花錢的池放**另一個 kernel 家** K2（掛同一個 daemon；cpu 名不能跟 K1 撞，同名會被回 `NameTaken`，[kernel daemon-link](../../spec/kernel/daemon-link.md)） | **管理上分區**：省錢的池與花錢的池分開看、分開停 | 誰都擋不住：同身分的行程讀得到 daemon 帳本、找得到 K2 |
| agent 的工具清環境、關進牢、牢裡不掛任何 K（agent-access） | 隔離 | agent 的工具 |
| **受信任的投遞入口**：`delegate` 工具不收任意 inst，只收「任務書文字」，池、模型、程式、工作區、額度都寫死在入口那邊，由牢外的程式替它放單 | 隔離＋白名單 | agent 叫它時只能做那一件事 |

建議：第一版 K2 當**管理分區**用（零程式）；要讓 agent 叫它們，**一定要**配受信任的投遞入口＋agent-access 的牢，不能只靠 K2。
小毛病：`aos-kernel check` 把「沒有 `llm` 池」算 bad（[kernel cli-ops](../../spec/kernel/cli-ops.md)），K2 會一直被標 bad；要嘛 K2 也放一顆 llm cpu，要嘛 check 改成「有 agent 才要 llm 池」（幾行）。

## 3. 跑在牢裡還是牢外

**牢外（階 0、階 1 的預設）**：它就是「使用者自己在那個資料夾開了一個 claude」，能碰使用者能碰的一切；範圍只靠旗標與 cwd。
**牢裡（階 2，接 agent-access 的 `aos-jail`）**：照 [agent-access contract](../2026-09-24-agent-access/contract.md) 清環境、不整份掛 `/etc`、排除 socket，只掛——

| 掛什麼 | 讀寫 | 為什麼 |
|---|---|---|
| 工作區（一份 clone，或不准 commit 的 worktree） | 寫 | 它要改的東西 |
| 任務書與 inst | **讀** | 不讓它改自己的單子 |
| 這張單子的輸出資料夾 | 寫 | 結果 |
| **一份專用的設定資料夾**（claude 的、`CODEX_HOME`），只放登入與它自己的 session | 寫 | 登入要換 token、寫 session；**不掛整個 `~/.claude`**——那裡有使用者所有對話與記憶。claude 換設定資料夾的環境變數名**未實測** |
| `/usr` 等 | 讀 | 跑程式 |
| 網路 | 開，最好只准連 API 的網址 | 它要連 API；開了就碰得到本機服務（LiteLLM、LM Studio 等），這要另外擋 |

牢裡 codex 自己的沙盒可能開不起來（牢中牢，**未實測**）；那時用 `--dangerously-bypass-approvals-and-sandbox`——help 說這是給「外面已經有沙盒」的環境用的。
擋不住的明講：登入檔在牢裡、網路開著＝它讀得到 token 也送得出去。這是用它們的代價。

## 4. 危險動作怎麼擋

| 動作 | 牢外 | 牢裡 |
|---|---|---|
| `git push` | `--disallowedTools "Bash(git push:*)"` 只擋直接寫法，`sh -c` 就繞過；codex `workspace-write` 預設關的是**它跑的指令**的網路（可被設定打開） | 不掛 `SSH_AUTH_SOCK`、`~/.ssh`、gh token、git 憑證，push **通常**會失敗；但工作區自己的 `.git/config`（remote 網址裡的 token、credential helper）、網路開著時仍可能推得出去——**工作區的 remote 要清乾淨** |
| 刪檔、亂改 | 工作區用 git worktree 或 clone，壞了丟掉；claude `--restricted`、codex `-s read-only`（審查） | 只有工作區與輸出可寫 |
| **worktree 的坑** | worktree 的 `.git` 指回主 repo；能 commit 就能 `branch -D`、改別的分支 | 給它一份 clone，或 worktree 但不掛主 repo 的 `.git`（不准 commit） |
| 動到 aos 自己 | 看得到 K、D、agent 家就能亂放單、改帳本 | 牢裡不掛 |
| 讀到使用者的私人設定 | claude 沒加 `--safe-mode` 會載入 `~/.claude` 的 CLAUDE.md、自動記憶；codex `--ignore-user-config` **只跳過 `config.toml`**，不擋 `AGENTS.md` 與專案裡的設定 | 專用設定資料夾，裡面只放允許的東西 |
| 被陌生 repo 帶著跑 | `-p` **跳過信任對話框**，那個 repo 的 `.claude/settings.json` hooks 照跑；`--safe-mode` 關 hooks；codex 會讀工作區的 `AGENTS.md` | 同左，外加牢 |
| 旗標被加回 | `--restricted` 拿掉的執行工具，`--tools` 仍能明列加回；MCP 另要 `--strict-mcp-config` 限 | 同左 |
| 巢狀 | daemon 若從 Claude Code 的 Bash 開，cpu 會繼承 `CLAUDECODE` 之類的環境，再開 claude 可能被擋（**未實測**） | 牢裡清環境 |

**預設旗標（我的建議，要拍）**，分兩種：
- **封閉任務**（寫程式、審查）：claude `-p --output-format json --permission-mode acceptEdits --permission-prompts none --safe-mode --allowedTools "<要跑的測試指令>" --disallowedTools "Bash(git push:*)"`；
  codex `exec --json --skip-git-repo-check --ignore-user-config -s workspace-write`，用**專用的 `CODEX_HOME`**（只放登入與 session），審查改 `-s read-only`。
- **准用 aos 工具**：拿掉 `--safe-mode`、加 `--strict-mcp-config --mcp-config <只列 aos 的>`，其他同上。
- `bypassPermissions`、`--dangerously-*` **只准在牢裡**。
