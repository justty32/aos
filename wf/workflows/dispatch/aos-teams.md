# aos 的隊形（2026-08-28 改制）

← [dispatch](README.md)｜選人判準 [team-model](../team-model.md)

本專案實際怎麼開隊。派線的通用規則在 [dispatch](README.md)，這裡只記 aos 專屬的隊形、指令與硬規則；改制時改這裡並標日期。

<!-- wf-nav -->
- **我（Fable）只當調度者**，不親自做內容；一個團隊＝一個 **Opus 隊長**＋**codex 隊員**（`codex exec -m gpt-5.6-sol`）。隊長寫任務書、審 diff、跑 ctest、commit；codex 隊員**不 commit**。分級（S Fable／A Opus・gpt-sol／…）、消耗速度與 9 月退 GPT 的替代表見 [team-model](../team-model.md)。
- 開隊長：`Agent(subagent_type="general-purpose", model="opus")`，prompt 裡明講團隊規則、硬規則（不 push、只 `git add` 明確路徑、不碰別隊的資料夾）、回報格式。已驗證可用的隊員呼叫：`codex exec -m gpt-5.6-sol -C <repo> --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`（任務書從 stdin 餵、要自給自足；`-o` 收最後一則回報）。
- **同一 working tree 只能有一隊在 commit**；純規劃隊只寫自己的項目夾且不 commit，由我收；審查隊用 `isolation: "worktree"`。
- **審查／報告類產出一定要求寫進 repo 內的路徑**，不要只留在 scratchpad 或靠最後一則訊息——agent 的回報只有最後一輪會回到我手上，主篇曾因此遺失一次。
- 別用 `TaskOutput` 讀 agent 任務（會倒整份 transcript 進 context）；等通知即可。
- 實作層級的裁決我可以代裁並記進 spec 開頭「調度者裁決」；**方向性的留給使用者**（鐵律 5），記 [WAIT_USER](../../WAIT_USER.md)。

## 交接

- 派線流程、領地表、收線 → [dispatch](README.md)；外部 CLI 線的啟動與監看 → [driving-cli-agents](driving-cli-agents.md)。
- 各層派哪級模型 → [team-model](../team-model.md)；隊伍會撞的資源 → [resources](../resources.md)。
