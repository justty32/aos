← [入口](README.md)｜實作步驟（給隊長；fable 不實作）｜上一份 [04-spawn-agent](04-spawn-agent.md)

# 實作步驟（11 步；全在我們領地，不改 aos-daemon／daemon-ctl／exec／post／loop／json／lock／fsm／install.sh）

通則：每步一個 commit、build 得過（[testing](../../../../../wf/workflows/testing.md)：impls 照依賴順序建）＋手跑；程式輸出一律英文；改了檔同 commit 補 code map（[proto8 分冊](../../../../../wf/workflows/common/code-map/proto8.md)）；改寫條文不派 sonnet。工人提示要它先讀 [本資料夾 README](README.md)＋對應分檔。**同一檔不給兩人同時寫**：S2→S3 同檔串行；其餘標 ∥ 的可並行。真腦都標「使用者試」（LM Studio 可能開；claude 經 LiteLLM haiku，整輪 ≤0.5 美金）。

| 步 | 內容 | 動哪些檔 | 做到什麼算完（可觀察） | 派 | 依賴 |
|---|---|---|---|---|---|
| S1 ∥ | endpoint 函數：`llm_http` 的 `body`→`fixed`（request 先、fixed 蓋上、model 一律用包的）；`llm_fake` 認包的 `script`（[02 代定 7](02-endpoint-packs.md)） | `lib/base/llm_http/_entry`、`lib/base/llm_fake/_entry`、`lib/docs/02-索引-base與索引-aos.md`、code map 09-lib | `echo '{"endpoint":{"script":[{"content":"A"},{"tool_calls":[{"name":"clock","arguments":{}}]}]},"request":{"messages":[{"role":"user","content":"hi"}]}}' \| lib/base/llm_fake/_entry` 印 `A`；messages 多一則 assistant 再餵＝印 tool_calls；用 `python3 -m http.server` 式 mock 看 llm_http 送出的 body 裡 temperature 是包的 | sonnet | — |
| S2 | kernel 認包：`fixed`／`slots`／`budget`／`speed`／`cost`／`context`／`summary`；`exec`／`slots`／`budget`／`speed` 拿掉後才交函數；`request.model` 或撞 `fixed` 的 key＝`RequestBad`；`proc.json` 記 `endpoint`；`used.json` 加 `packs`；寫窗 `$AOS_STACK/endpoints.json`；驗整組 `$ref` 能解 | `impls/aos-llm-kernel/src/{letter,serve,budget}/*`、`docs/01`、`docs/02`、`docs/03`（錯誤表）、code map 01-impls-3 | 假腦信照答；信寫 `temperature` 寄給有 `fixed.temperature` 的包＝回 `RequestBad temperature is fixed by endpoint X`；`cat endpoints.json` 有 speed／cost；`used.json.packs.fake.counter_calls` 增加 | opus | — |
| S3 | 排程：順序加 speed、包 `slots` 滿＝跳過補下一封、包 `budget` 到頂＝那封 `BudgetMissing`（[03 代定 1～3](03-scheduling.md)） | `impls/aos-llm-kernel/src/{queue,serve}/*`、`docs/02`、`docs/04` | 兩包 `slots: 1` 各寄 3 封、kernel `slots: 4`：`aos-daemon-ctl --daemon <stack> ls` 同時各一封在飛、不是一包佔滿；同級兩封 fast 的先掛；包 `max_calls: 1` 第二封回 `BudgetMissing endpoint …` | opus | S2 |
| S4 ∥ | `aos-llm ls`：讀 `$AOS_LLM_KERNEL/endpoints.json` 一行一包（`代號 speed cost context slots summary`、`--json`）；沒窗＝`EndpointsMissing` | `impls/aos-llm/src/*`、`docs/01-用法等`、README、code map 01-impls-3 | kernel 起來後 `aos-llm ls` 列出範本的包 | sonnet | S2（窗的格式；可先照 02 的形狀寫，S2 完再合跑） |
| S5 ∥ | `aos-agent ctl who [--stack S] [--json]`（[01 代定 1](01-self-tools.md)）；`ctl state` 加一行 overlay 統計 | `extras/agent/bin/aos-agent`、`extras/agent/README.md`、`docs/01-用法例子`、code map 06 | 掛一隻 fsm1 後 `AOS_STACK=<fsm1 stack>/tools/x/ aos-agent ctl who` 印 `fsm1`；不在表下＝`InstanceMissing`；沒 daemon＝`DaemonMissing` | opus | — |
| S6 ∥ | 工具 `lib/agent/self_tools/`（三件套；op add／rm／ls；path 從 `$AOS_WS` 算或 `lib/` 絕對） | `lib/agent/self_tools/{_entry,_tooldef.json,_metainfo.json}`、`lib/docs/03-索引-agent等.md`、code map 09-lib | 人殼 `aos-agent tools add self_tools …` 塞進 fsm1；`echo '{"op":"add","name":"math","path":"tools/math"}' \| AOS_WS=<ws> AOS_STACK=<fsm1 stack>/tools/self_tools/ aos-exec lib/agent/self_tools` 後 `aos-agent tools ls --target fsm1` 多了 math；路徑不在＝stdout 一行 `self_tools: … PathMissing` 退 1 | opus | S5 |
| S7 ∥ | 工具 `lib/agent/agents/`（op add／say／ask／rm／ls；`children.json`；`endpoint`／`tools` 明寫才設）（[04 代定 1](04-spawn-agent.md)） | `lib/agent/agents/{_entry,_tooldef.json,_metainfo.json}`、`lib/docs/03`、code map 09-lib | `echo '{"op":"add","name":"kid","def":"<repo>/proto8/demo/agent-fsm","endpoint":"fake"}' \| AOS_DAEMON=… AOS_WS=… AOS_STACK=/tmp/c/ aos-exec lib/agent/agents` 後 `aos-agent ctl ls` 有 kid、`aos-agent llm show --target kid` 是 fake；`ask` 拿到 FAKE ANSWER；`rm` 不在 children＝`ChildUnknown`；`AOS_KERNEL` 指判官且滿額＝印 `AddRejected … SlotMissing` | opus | — |
| S8 ∥ | agent-fsm 拿掉 `model` 鍵（brain.py 不寫 `request.model`、wait.py 只比 endpoint）；docs/02、aos-agent README `llm` 段、P-23 那句 | `demo/agent-fsm/{brain,wait}.py`、`demo/docs/02-agent-fsm.md`、`extras/agent/README.md`（llm 段）、code map 13-demo | `aos-agent llm set model=x` 仍能寫（aos-agent 不認鍵），但 brain 送的 request 沒有 `model`；舊流程 say／listen 照答 | sonnet | S2（語意）；檔跟 S5 都碰 aos-agent README 不同段，先後 commit 即可 |
| S9 | 範本 kernel.json 改成包（`smart-high`、`stupid-fast`、`fake`、`fake-demo-self`、`fake-demo-spawn`、`luna`／`sol`）；demo/docs/03 改寫；新 `demo/docs/05-feat-proto.md`：三段手跑劇本（件 1：掛 fsm1→人殼塞 `self_tools`→`llm set endpoint=fake-demo-self`→say「給自己加 math」→`tools ls` 多了 math；件 3：兩包 slots 演補位；件 4：判官 `demo/daemon-judge` `max_running` 4→say「生一隻 kid 問時間」→kid 上表、回答、收掉；第 5 隻被擋）；真腦段標「使用者試」 | `demo/llm-kernel/kernel.json`、`demo/docs/03-llm-kernel.md`、`demo/docs/05-feat-proto.md`、`demo/README.md`、`demo/daemon-judge/judge.json`、code map 13-demo | 三段劇本在 WSL `/tmp` 從頭跑一遍全綠（假腦、零成本）；LM Studio 開著就順手跑 `stupid-fast` 一句 | opus | S1～S8 |
| S10 | 條文：N-42 (1) 補包與排序（含 speed、包 slots、不降級＝使用者裁前照推薦）；P-23 `model` 那句、`body`→`fixed`；C-42 加「11-05 落實：self_tools、agents 兩工具」一句；C-46／C-61 加 `ctl who` 一句；N-63 實例補 `ctl who` 只查表；本資料夾 README 狀態改「已實作」＋實作結果分檔（代定、實測、已知限制） | `docs/NORMS/09-kernel.md`、`docs/CONVENTION/02-…/05-P-23～P-26.md`、`docs/CONCEPTS/05-agent/*.md`、`thinking/2026-11/05/feat-proto/{README,05-實作結果}.md` | 原字不動、只加「11-05 午」註；`wf-lint` broken=0 | opus | S9 |
| S11 | 收尾：wf-lint、日誌一行、WAIT_USER 加「真腦跑 05-feat-proto（LM Studio／LiteLLM haiku ≤0.5 美金）」、SESSION-LOG | `wf/session_logs/2026-11/2026-11-05.md`、`wf/WAIT_USER.md`、`wf/SESSION-LOG.md` | `wf/tools/wf-lint.sh` broken=0、oversize=0 | sonnet | S10 |

## 並行建議

- 第一波（4 人）：S1、S2、S5、S7。第二波：S3（S2 完）、S4、S6（S5 完）、S8。第三波：S9 → S10 → S11。
- 需要真腦的只有 S9 的「使用者試」段；工人不等它。LM Studio 開著可自己跑 `stupid-fast`；claude 只在使用者在時跑。

## demo 放哪

- 範本與劇本都在 `demo/llm-kernel/kernel.json`（包＋劇本假腦）、`demo/daemon-judge/judge.json`（上限 4）；劇本文件 `demo/docs/05-feat-proto.md`。不新增 agent 範本資料夾（留題 5 推薦不內建：件 1 本身就是「跑著時加工具」）。
- 工具在 `lib/agent/self_tools/`、`lib/agent/agents/`；`lib/README` 索引 agent 段各加一列。

## 需要邊緣隊改的檔

沒有。用到的 daemon 行為（給子項 `AOS_DAEMON`、表上 `stack`／`def`／`ws` 絕對路徑、`ctl add` 回信、`stopped`＋`reason`）11-05 早已在。
