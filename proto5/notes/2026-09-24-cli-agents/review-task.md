← [本提案](README.md)

# 任務書：唯讀審查「兩支 CLI 納進 aos」提案

你是唯讀審查員。**不要改任何檔、不要跑 claude 或 codex 的任務（只准 `--help`／`--version`）、不要花錢、不要碰 LM Studio。** 你的最後一則訊息就是審查報告（會被存成 review-astra.md）。用繁體中文、白話。

## 要審的

`proto5/notes/2026-09-24-cli-agents/` 裡的 README.md、as-cpu.md、uses.md、others.md、cost-safety.md、cli-facts.md。

使用者的定位（以第 3 句為準）：拿 Claude Code CLI 與 Codex CLI 當 aos-agent 的備用品，**不必共用 agent 家**，重點是**納入 kernel、daemon、aos-exec／inst-posix／指示詞這套**；並且「多想想怎麼利用」。

## 對照的規範與程式（都在這個 repo）

- `proto5/spec/cpu/`（README §9 拍板、methods.md）、`proto5/spec/kernel/`（syscall.md、cli-ops.md、daemon-link.md、terms.md、echo.md）、`proto5/spec/daemon/methods.md`
- `proto5/spec/inst-posix/`（路徑怎麼算、argv 不改寫）、`proto5/spec/aos-exec/`（逾時砍 process group）
- `proto5/spec/agent/info.md`、`proto5/spec/aos-agent/`（collect.md、settle.md、pause-clean.md）、`proto5/spec/aos-llm/`、`proto5/lib/aos_llm_call.py`
- `proto5/notes/2026-09-24-agent-access/`（access.json、bwrap、env-flow）
- `proto5-2/README.md`（池式 kernel／daemon）
- `wf/workflows/dispatch/aos-teams.md`、`wf/workflows/team-model.md`（現在調度者怎麼用 codex 與 Claude 隊）

## 審三件事

1. **對兩支 CLI 能力的描述對不對**：用 `claude --help`、`claude mcp --help`、`codex --help`、`codex exec --help`、`codex exec resume --help`、`codex exec fork --help` 對照 cli-facts.md 與其他檔裡每個旗標的說法。你對 codex 的行為（`--json` 事件、`-s workspace-write` 預設有沒有網路、resume 怎麼帶沙盒、`CODEX_HOME`）比我們清楚，錯的或「未實測」其實可以確定的請指出。
2. **對 aos 的描述對不對**：「不用新種 cpu、零程式就能跑」是否真的成立（kernel.json 加池、inst 寫法、指示詞、`aos-kernel add` 旗標、once 的 Interrupted 不重跑、rm 不停正在跑的、daemon `kill` 後不重拉、兩個 kernel 共用 daemon、check 對沒 llm 池報 bad）；階 1 的行數估計合不合理。
3. **漏掉的**：漏掉的角色或用法；權限與花錢的洞（誰能放單、額度、牢裡掛什麼會漏、危險動作擋不擋得住、重跑與取消）；會讓使用者照做就出事的地方。

## 報告格式

- **必修**（錯的、會出事的）：編號，每條「哪個檔哪一段 → 問題 → 建議改成什麼」。
- **建議**（可更好）：同上。
- **確認沒問題的**：簡短列幾條你核過的。
- 總長 ≤ 6 KB。
