# 任務：試用 L2——用 aos 指揮與管理一個 agent 團隊，記所有做不到與不順手

> 交接書是唯一契約。判準 [usability-target](../../../ideas/usability-target.md) 第二級；發現格式見 [trial/README](../../trial/README.md)。**只找不修、不改 core/。**

## 唯一目標

使用者只跟一隻主 agent 說話，主 agent 派生子 agent（各住一個資料夾）、用通訊錄（`aos contact`／`aos say --to`）投任務、收回報、
從 `state.json` 看誰在忙。**對照組是現在用 Claude Code 開隊的體驗**（[team-model](../../../team-model.md)、[dispatch](../../README.md)）。
預期很多「做不到」——**做不到就是第一條發現**，寫清楚卡在哪一步、缺哪個原語。

## 團隊（你是 Opus 隊長）

codex ×3 當「使用者／主 agent 操作者」（同 L1 的呼叫方式與規矩）。你出劇本、收斂。

## 劇本

素材：`trial/sandbox/team/` 下建 `boss/`、`w1/`、`w2/` 三個世界（各 `aos agent init`，boss 用 pi 或 lmstudio、workers lmstudio）。
1. **派工**：boss 收到「把 w1 的 README 翻成英文、w2 加一個測試」→ boss 能不能自己 `aos say --to w1 …`（它得先知道通訊錄、得有那個 tool 登記）；不能就人手代打，記下缺的原語。
2. **收回報**：worker 做完怎麼回 boss（`aos say --to boss`？投 inbox？），boss 下一回合看得到嗎；三個 `aos run` 各自跑 vs 一個主世界推子世界（`every/` 放 `aos run w1 --step 1`）。
3. **看誰在忙**：一眼看全隊狀態要打幾個指令；`state.json.agents` 只有本世界。
4. **限制與排程**：三隻同時想、只有 lmstudio 一顆，會怎樣（記現象，V 隊在做排程，不必等）。
5. **對照**：同一件事用 Claude Code 開隊要幾步、少了什麼。

## 硬性限制

- 只寫 `wf/workflows/dispatch/trial/{findings-L2.csv,repro/,sandbox/team/}`；commit 到你的 worktree 分支；不 push、不 merge、不改 core/。
- 不 load／unload LM Studio、不開 GUI、不取鎖、不用 wf-lint；DeepSeek key 只從環境變數。
- **件數 gate**：發現 ≤ 40 條。

## 驗收（就這 3 條）

1. `findings-L2.csv` 存在、欄位齊；`trial/README.md` 追加 L2 摘要 ≤ 20 行（含「缺的原語」清單）。
2. 每條 `bug` 類有 `repro/<id>.sh`。
3. 劇本 1–3 都有紀錄（做不到也算）。

## 回報

最後一則訊息＝缺的原語清單＋最痛的五條＋STATUS＋worktree 路徑與分支名。
