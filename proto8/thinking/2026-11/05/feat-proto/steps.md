← [入口](README.md)｜實作步驟（給隊長；fable 不實作）｜上一份 [05-資源份額](05-資源份額.md)｜下一份 [06-實作結果](06-實作結果.md)

# 實作步驟（13 步；S1～S13 全在我們領地；件 5 的 daemon 半邊見 [05 請邊緣隊改](05-資源份額.md)）

通則：每步一個 commit、build 得過（[testing](../../../../../wf/workflows/testing.md)）＋手跑；程式輸出一律英文；改了檔同 commit 補 code map（proto8 分冊）；改寫條文不派 sonnet。工人先讀 [README](README.md)＋對應分檔。**同一檔不給兩人同時寫**：S2→S3→S12 同檔串行；標 ∥ 的可並行。真腦標「使用者試」（LM Studio；LiteLLM haiku ≤0.5 美金）。

| 步 | 內容 | 動哪些檔 | 做到什麼算完（可觀察） | 派 | 依賴 |
|---|---|---|---|---|---|
| S1 ∥ | endpoint 函數：`llm_http` 的 `body`→`fixed`（request 先、fixed 蓋上、model 用包的）；`llm_fake` 認包的 `script`（[02 代定 7](02-endpoint-packs.md)） | `lib/base/llm_http/_entry`、`lib/base/llm_fake/_entry`、lib docs 02、code map 09 | 餵 `{"endpoint":{"script":[{"content":"A"},{"tool_calls":[{"name":"clock","arguments":{}}]}]},"request":{"messages":[…]}}` 第一次印 `A`、messages 多一則 assistant 再餵＝印 tool_calls；mock http server 看 llm_http 送的 body 裡 temperature 是包的 | sonnet | — |
| S2 | kernel 認包：`fixed`／`slots`／`budget`／`speed`／`cost`／`context`／`summary`；kernel 專用 key 拿掉才交函數；`request.model` 或撞 `fixed`＝`RequestBad`；`proc.json` 記 `endpoint`；`used.json` 加 `packs`；寫窗 `$AOS_STACK/endpoints.json`；驗整組 `$ref` 能解 | `impls/aos-llm-kernel/src/{letter,serve,budget}/*`、docs 01～03、code map 01-impls-3 | 假腦信照答；信寫 `temperature` 給有 `fixed.temperature` 的包＝`RequestBad temperature is fixed by endpoint X`；`cat endpoints.json` 有 speed／cost；`used.json.packs.fake.counter_calls` 增加 | opus | — |
| S3 | 排程：順序加 speed、包 `slots` 滿＝跳過補下一封、包 `budget` 到頂＝`BudgetMissing`（[03 代定 1～3](03-scheduling.md)） | `impls/aos-llm-kernel/src/{queue,serve}/*`、docs 02／04 | 兩包 `slots: 1` 各寄 3 封、kernel `slots: 4`：`aos-daemon-ctl --daemon <stack> ls` 各一封在飛；同級兩封 fast 先掛；包 `max_calls: 1` 第二封 `BudgetMissing endpoint …` | opus | S2 |
| S4 ∥ | `aos-llm ls`：讀 `$AOS_LLM_KERNEL/endpoints.json` 一行一包（`--json`）；沒窗＝`EndpointsMissing` | `impls/aos-llm/src/*`、docs 01、README、code map | kernel 起來後 `aos-llm ls` 列出範本的包 | sonnet | S2（格式；可先照 02 寫） |
| S5 ∥ | `aos-agent ctl who [--stack S] [--json]`（[01 代定 1](01-self-tools.md)）；`ctl state` 加 overlay 統計與 `limits` 行（表上有才印） | `extras/agent/bin/aos-agent`、README、docs 01、code map 06 | 掛 fsm1 後 `AOS_STACK=<fsm1 stack>/tools/x/ aos-agent ctl who` 印 `fsm1`；不在表下＝`InstanceMissing`；沒 daemon＝`DaemonMissing` | opus | — |
| S6 ∥ | 工具 `lib/agent/self_tools/`（三件套；op add／rm／ls；path 從 `$AOS_WS` 算或 `lib/` 絕對） | `lib/agent/self_tools/*`、lib docs 03、code map 09 | 人殼 `aos-agent tools add self_tools …` 塞進 fsm1；餵 `{"op":"add","name":"math","path":"tools/math"}`（`AOS_STACK=<fsm1 stack>/tools/self_tools/`）後 `aos-agent tools ls --target fsm1` 多 math；路徑不在＝stdout 一行 `self_tools: … PathMissing` 退 1 | opus | S5 |
| S7 ∥ | 工具 `lib/agent/agents/`（op add／say／ask／rm／ls；`children.json`；`endpoint`／`tools`／`limits` 明寫才送）（[04 代定 1](04-spawn-agent.md)） | `lib/agent/agents/*`、lib docs 03、code map 09 | 餵 `{"op":"add","name":"kid","def":"<repo>/proto8/demo/agent-fsm","endpoint":"fake"}` 後 `aos-agent ctl ls` 有 kid、`llm show --target kid` 是 fake；`ask` 拿到 FAKE ANSWER；`rm` 不在 children＝`ChildUnknown`；`AOS_KERNEL` 指判官且滿額＝`AddRejected … SlotMissing` | opus | — |
| S8 ∥ | agent-fsm 拿掉 `model` 鍵（brain 不寫 `request.model`、wait 只比 endpoint）；docs 02、aos-agent README `llm` 段 | `demo/agent-fsm/{brain,wait}.py`、`demo/docs/02`、`extras/agent/README.md`（llm 段）、code map 13 | brain 送的 request 沒有 `model`；say／listen 照答 | sonnet | S2（語意）；跟 S5 碰 README 不同段，先後 commit |
| S9 | 範本 kernel.json 改成包（`smart-high`、`stupid-fast`、`fake`、`fake-demo-self`、`fake-demo-spawn`、`luna`／`sol`）；demo/docs/03 改寫；新 `demo/docs/05-feat-proto.md` 三段假腦劇本（件 1：掛 fsm1→塞 `self_tools`→`llm set endpoint=fake-demo-self`→say「給自己加 math」→`tools ls` 多 math；件 3：兩包 slots 補位；件 4：判官 `demo/daemon-judge` `max_running` 4→say「生 kid 問時間」→上表、回答、收掉、第 5 隻被擋）；真腦段標「使用者試」 | `demo/llm-kernel/kernel.json`、`demo/docs/{03,05}`、`demo/README.md`、`demo/daemon-judge/judge.json`、code map 13 | 三段在 WSL `/tmp` 從頭跑全綠（假腦零成本）；LM Studio 開著順手跑 `stupid-fast` 一句 | opus | S1～S8 |
| S10 | 條文：N-42 (1) 補包、排序、寄件人額度；P-23 `model`、`body`→`fixed`；C-42 加「11-05 落實：self_tools、agents」；C-46／C-61 加 `ctl who`；N-63 實例補 `ctl who` 只查表；C-64 加「份額＝daemon 表的 `limits`」一句；本資料夾 README 狀態改「已實作」＋ `06-實作結果.md`（代定、實測、已知限制） | `docs/NORMS/09-kernel.md`、`docs/CONVENTION/02-…/05-P-23～P-26.md`、`docs/CONCEPTS/05-agent/*.md`、`docs/CONCEPTS/01-設計理念/05-…檔案權限.md`、本資料夾 README／06 | 原字不動、只加「11-05 午」註；wf-lint broken=0 | opus | S9、S12、S13 |
| S11 | 收尾：wf-lint、日誌一行、WAIT_USER（真腦跑 05-feat-proto ≤0.5 美金；件 5 等邊緣隊 E1～E3）、SESSION-LOG | `wf/session_logs/2026-11/2026-11-05.md`、`wf/WAIT_USER.md`、`wf/SESSION-LOG.md` | `wf/tools/wf-lint.sh` broken=0、oversize=0 | sonnet | S10 |
| S12 | 件 5 kernel 半邊：`budget.senders: {sender: {max_calls, max_tokens}}`（窗同 `budget.window`；`used.json` 加 `senders`；到頂＝`BudgetMissing sender X …`）（[05 代定 4](05-資源份額.md)） | `impls/aos-llm-kernel/src/{budget,serve}/*`、docs 02、demo kernel.json 加一例 | 同一寄件人 `max_calls: 1`：第二封回 `BudgetMissing sender …`、別的寄件人照答 | opus | S3（同檔） |
| S13 | 件 5 aos-agent 半邊：`interfaces.json` 選填 `limits` 宣告、`ctl add --limits JSON`（E2 沒到前只讀宣告、stderr 提醒一行）；`ctl state` 印表上 `limits`；`agents add` 的 `limits` 原樣轉；README、demo/docs/05 加「件 5 演法：`ulimit -v` 起 daemon→子項 `python3` 吃 300 MB→表上 `stopped`＋`reason`」 | `extras/agent/bin/aos-agent`、README、`lib/agent/agents/_entry`、`demo/docs/05`、code map 06／09 | 宣告 `limits` 的定義 `ctl add` 不報錯；E2 到了之後 `aos-agent ctl state` 看得到 `limits` | opus | S5、S7；E1／E2 到了再補送 |

## 並行建議

- 第一波（4 人）：S1、S2、S5、S7。第二波：S3、S4、S6、S8。第三波：S12、S13、S9。第四波：S10 → S11。
- 需要真腦的只有 S9 的「使用者試」段；工人不等它。件 5 的 daemon 半邊（E1～E3）由邊緣隊排，S13 不等它也能先做宣告那半。

## demo 放哪

- 範本與劇本都在 `demo/llm-kernel/kernel.json`（包＋劇本假腦）、`demo/daemon-judge/judge.json`（上限 4）；劇本文件 `demo/docs/05-feat-proto.md`。不新增 agent 範本資料夾（留題 5：件 1 本身就是「跑著時加工具」）。
- 工具在 `lib/agent/self_tools/`、`lib/agent/agents/`；`lib/README` 索引 agent 段各加一列。

## 需要邊緣隊改的檔

只有件 5 的 E1（aos-daemon）、E2（aos-daemon-ctl）、E3（N-28 一句），精確清單在 [05](05-資源份額.md)。件 1～4 用到的 daemon 行為 11-05 早已在。
