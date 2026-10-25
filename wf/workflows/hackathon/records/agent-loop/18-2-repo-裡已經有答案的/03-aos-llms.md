← [2. repo 裡已經有答案的](../18-2-repo-裡已經有答案的.md)（分檔 3/3）｜[上一份](02-批次不短路-needs.md)

**`aos llms`**

- `core/llms/README.md`〈子命令〉：`aos llms ask [--model M | --preset P] [--stream] [--system S] [--url U] [--key K] <prompt>`、`aos llms models`；`--url` 預設 `http://localhost:4000`，可直接打 `http://localhost:1234/v1`。prompt 是位置參數，CLI 層沒有 stdin、沒有 `--json`。
- 同檔〈能力、工具與 presets〉：能力查詢取 `/model/info` 與 `/v1/models` 聯集；〈串流 Reply〉：`calls[].args` 是未解析 JSON 字串，不合法時原文在 `args_raw`。
- 掛載位置：`wf/workflows/common/code-map.md` 的 `aos::llms` 段。
- `docs/roadmap.md`〈T6 — 把 LLM 內化：`aos llm exec <folder>`〉（對 `aos exec` 只是普通指令，與 T5 的外部 CLI 同位置）；〈D4〉是 T5 不用它的理由。

**`parallel: true`／tool_call_id**

- 語意：`core/inst/docs/format.md` 的 `parallel` 列、`core/inst/docs/exec.md` 開頭（批次邊界等每一筆完成）；`docs/roadmap.md`〈D3〉（回合內並行，回合邊界不變）。
- `wf/workflows/workshop/background/delivery-contract.md`〈correlation ID（串接編號／request ID）〉〈receipt（收據／completion record）〉〈TOCTOU（先檢查、後使用的競爭窗）〉。
- join 時機未定：`wf/workflows/workshop/records/agent-loop-architecture.md`〈還在生長的想法〉。

**pi 吃不吃 stdin**

- `wf/workflows/workshop/records/tool-interop.md`〈pi 與本場的已知前提〉：`-p/--print` 可吃 stdin（介面說明，非本機實測）。
- `wf/workflows/experiments/t5-agent-loop.md`〈6. 真 agent CLI〉〈OPEN #6〉：上次 pi 未安裝，排除理由是環境可用性。

**codex 的細節**

- `wf/workflows/hackathon/gotchas.md`〈codex〉：rollout 檔在 `~/.codex/sessions/<年>/<月>/<日>/rollout-*.jsonl`（UUID 在檔名）；session id 的 key 是 `thread_id`；`resume` 的 `--json`／`-o` 要放在 `resume` 前，`-s`／`-C`／`--add-dir` 不吃（繼承原 session，場地要還在）；非 git repo 要 `--skip-git-repo-check`。

**session resume vs 每回合重建（OPEN #19）**

- `wf/workflows/workshop/background/questions-agent-context.md`〈題目：第一版預設 `--no-session` 從 world 重建，還是優先使用 agent session 作續談快取？〉。
- `wf/workflows/workshop/records/tool-interop.md`〈coding agent 的 session 只可當快取〉（`--session-dir` 未核對，不寫進 skill）。

**durability 的分層**

- `wf/workflows/workshop/background/reliability.md`〈visibility atomicity 與 power-loss durability〉及 Effect、idempotency key、ledger、`unknown` 各詞條。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／6. 仍然不知道的〉；`verdicts.md`〈第 3 輪／路線判斷〉：power-cut 沒測前不把 visibility 叫 durability。

**同類黑客松的前例**

- `wf/workflows/hackathon/records/core-scope/packs.md`〈下一輪的資料包〉：同樣四塊結構。
- `wf/workflows/hackathon/records/core-scope/verdicts.md`〈第 2 輪／路線判斷〉〈第 3 輪／路線判斷〉：唯一致命的坑也是無 query／idempotency 的遠端 effect。
