# 公司那台（WSL）的隊形與 slug（2026-11-06）

← [aos-teams](../aos-teams.md)

## slug 實測

**公司那台（WSL）有兩支 codex（11-06 更正，上午誤測）**：`~/.local/bin/codex`（0.153.4，舊版，非互動 `bash -lc` 會抓到它，不認得新模型，回「not supported」）；`~/.nvm/versions/node/v24.19.0/bin/codex`（0.166.0，使用者互動 shell 用的，`~/.codex/config.toml` 預設 `gpt-6.1-sol`）。**agent 叫 codex 一律用 nvm 那支的完整路徑**（或先把它放 PATH 前面）。用新版實測可用：`gpt-6.1-sol`、`gpt-6-sol`、`gpt-6-luna`、`gpt-6-astra`、`gpt-5.6-sol`／`-terra`／`-luna`（gpt-5.5 只在舊版測過、未重測）。使用者原話：「gpt-6.1-sol用不了？我直接開wsl ubuntu，跑codex，模型預設就是gpt-6.1-sol」。

## 隊形（使用者 11-06 兩段原話）

先說：「具體來說仍然是走team路線，也就是派一個opus去當隊長，隊員用這些。盡量用codex gpt啦」。後定案：「所以我會建議，一個隊伍內，opus就是我們自家subagent，隊員就兩個，一個codex gpt-sol-6.1，另一個就claude opus-5.5。然後這兩個隊員都可以再派出agent」。

- 一隊＝opus 隊長（自家 subagent）＋兩名隊員：codex 一個、claude 一個。
- codex 隊員照使用者原意用 `gpt-6.1-sol`（用 nvm 新版 codex）。
- claude 隊員＝WSL 另一帳號：`claude -p --model claude-opus-5-5 '…' </dev/null`（實測可用，Claude Code 2.1.318，`~/.local/bin/claude`）。
- 兩名隊員可在自己程序裡再派子 agent。

## 子 agent 規則（使用者 11-06 新規則）

原話：「隊員仍然遵循我們的要通讀wf/規矩的規定，包括其子agent。然後codex那邊，允許他跑無上限個子agent，普通工作交給sol，簡單工作交給terra。claude這邊也是無上限，普通工作交給opus，簡單工作交給sonnet。盡量把工作都派給codex。」

頂層的落實：
- 普通 sol＝`gpt-6.1-sol`、簡單 terra＝`gpt-5.6-terra`（都用 nvm 新版 codex）。
- 隊員與其子 agent 的任務書開頭都要求先通讀 wf/ 規矩。
- 子 agent 在隊員自己的程序裡跑，所以「每隊同時最多兩個 nodejs 程序」照舊。
- 盡量派 codex，claude 隊員補位。

## 程序數要少

使用者原話：「因為他們都是用nodejs做的，所以建議總數不要太多。因為一方面這是在WSL上，另一方面這台電腦我還要做其他工作，效能上要注意。」每隊同時最多這兩個 nodejs 程序（取代先前頂層定的「每隊最多 1 個」）。

## 沙箱

- 派 codex 改用 `-s workspace-write`（它自己的沙箱），不要用繞過沙箱的旗標（上面 09-22 那條作廢）。
- 公司 WSL 另有 `claude`（`~/.local/bin/claude`，Claude Code 2.1.318），是**另一個帳號**；`claude -p '…' </dev/null` 實測可用，可當 Claude 工人。
