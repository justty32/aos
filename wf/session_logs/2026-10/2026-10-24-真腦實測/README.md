# 交接：開 LiteLLM 後實測、打磨 10-24 的嘗試

← [session log 10-24](../2026-10-24.md)｜[SESSION-LOG](../../../SESSION-LOG.md)｜[HANDOFF](../../../HANDOFF.md)

使用者 10-24 收工時說（原話）：「都做好後，按照wf/規矩，整理收尾。然後我要重開session，到時候我會開litellm，然後實際測試，開始打磨這些想法，讓他們可用」

10-24 的二十項嘗試幾乎都只用假腦跑過（真的叫過模型的只有 agent-dan 10-23、aos-ai 的 `claude -p`、agent-fay 的 claude／codex CLI）。本資料夾是下一個 session 的照表操課：每項的指令、看什麼算成功、風險、打磨方向。指令是 10-24 收工時照程式與試驗場核過的，**沒實跑過**，跑之前看一眼。

| 分檔 | 內容 |
|---|---|
| [01-基礎](01-基礎.md) | agent-dan、agent-pip、aos-json json_edit 兩步、agent-liv、kernel-llm（含 `_metainfo`、額度） |
| [02-組合](02-組合.md) | agent-eve（pyfix）、agent-gus、agent-meg、talk、agent-kai、agent-hal compact、self-improve（含 sandbox.json） |
| [03-外部與人](03-外部與人.md) | aos-ai（含 skill）、say／listen／chat、agent-fay（attach）、Janet、Lua 與 nvim、aos-grow、沙箱 root 那層 |
| [結果-01-基礎](結果-01-基礎.md) | 10-24 真腦實測結果：第 1～6 項（dan、pip、json_edit 兩步、liv、kernel-llm、Janet／Lua／grow）都能用；修了 stat 的時間寫法、liv 工具錯卡住、kernel-llm 收 `--max` 與 ivy 的模型名 |
| [結果-02-組合B](結果-02-組合B.md) | 10-24 真腦實測結果：agent-kai bench（kai 15/15、dan 14/15、kai0 14/15；kai 比 dan 少 25% prompt，但沒 cache 的部分差不多）、self-improve 能用；定了 self-improve 預設就關沙箱（代定）、沙箱加 `env` 白名單、修了 `mem_mb` 讓 aos-exec 起不來 |
| [結果-02-組合A](結果-02-組合A.md) | 10-24 真腦實測結果：agent-meg、agent-hal compact、agent-eve（pyfix）、talk 都能用；agent-gus 修好了（小念頭規劃回散文原本 `PlanBad` 卡住，改成當不拆） |
| [結果-03-外部](結果-03-外部.md) | 10-24 真腦實測結果：aos-ai（含 skill）、agent-fay 叫 claude／codex 都能用；修了 aos-ai spawn 工具錯卡住（`--tool-errors`） |

## 第 0 步：確認 LiteLLM 起來了

```sh
curl -s localhost:4000/v1/models | python3 -m json.tool   # 看有哪些模型名
```

- 各 agent 的 `.env` 寫 `AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low`（外面設了以外面為準；pyfix 子 agent 固定用自己 `.env` 的）。上面那份清單裡**要有這個名字**；agent-hal 的 compact 最後一步另用 `chatgpt-gpt-6-sol`，也要有。
- 腦的三個環境變數：`AOS_BRAIN_URL`（沒設＝假腦；程式接 `{URL}/chat/completions`）、`AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`（有設才送 Authorization，LiteLLM 本機不用）。例外：kernel-llm 的 agent-ivy 沒有 `.env`、不設 `AOS_BRAIN_MODEL` 會送 `default`；agent-hal compact 讀 `COMPACT_URL`／`COMPACT_MODEL_*`（沒設才用 `AOS_BRAIN_URL`）；agent-meg 的 `run.py` 網址寫死 localhost:4000、**連不上就靜靜改假腦**（看 log 第一行是不是「腦：…（LiteLLM）」）。
- 最快的冒煙：`python3 -m unittest discover -s proto8/tests -p test_dan.py -v`（連得上就會跑真模型案例，不再 skip）。

## 共用開頭（每項先貼）

```sh
R=~/repo/simple_tools/aos/proto8; I=$R/impls
export PATH=$I/aos-exec/bin:$I/aos-loop/bin:$I/aos-fsm/bin:$I/aos-daemon/bin:$I/aos-json/bin:$I/aos-kernel-llm/bin:$I/aos-gate/bin:$R/bin:$R/human/bin:$R/ai_tools/bin:$R/sandbox/bin:$R/langs/janet/bin:$PATH
export AOS_BRAIN_URL=http://localhost:4000/v1; U=$AOS_BRAIN_URL
```

impls 沒建好先照 [testing § proto8](../../../workflows/testing.md#proto8不在-ctest-裡) 建。試驗場都在 `~/code/try/<名>/`（不進 git）；每項都**另開新的 ws**，不要動假腦那次留下的現場。

## 建議順序

先測最底層、最多東西靠它的；一項過了再往上。成本：低＝個位數次、中＝十幾到幾十次、高＝上百次或很長、付費＝另花 Anthropic／OpenAI 的錢。

| # | 項目 | 為什麼排這裡 | 腦呼叫 | 親手 |
|---|---|---|---|---|
| 1 | agent-dan | 其他 agent 幾乎都從它抄；10-23 真跑過，先確認環境 | 低（2～3） | |
| 2 | agent-pip | lib/base 十二條工具的真用法 | 中（5～15） | |
| 3 | aos-json json_edit 兩步 | 自己會問腦的工具，pip／gus 以後要用 | 低 | |
| 4 | agent-liv | 庫的捷徑引用 | 低（2～4） | |
| 5 | kernel-llm | 閘門、排序、token 帳本；要先改 daemon `max` | 低（3） | |
| 6 | Janet、Lua 編譯物、aos-grow | 都是「跟 agent-dan 形狀一樣」的對照 | 低（各 4～8） | |
| 7 | say／listen／chat | 人用的介面，接在 dan 上 | 低 | 是 |
| 8 | agent-meg、agent-hal | 記憶、壓縮；hal 用貴模型 | 中（meg 3～4、hal 約 30） | |
| 9 | agent-eve（pyfix）、agent-gus | agent 疊 agent、念頭樹 | 中～高（eve 約 10、gus 50+） | |
| 10 | talk | 三隻互寄信 | 中（6～10，可能繞圈） | |
| 11 | agent-kai bench | 15 題 × 3 隻 | 高（60～100） | |
| 12 | self-improve（先定沙箱預設） | 最貴、會改程式 | 高（10～100、上限 50 萬 token） | |
| 13 | aos-ai、agent-fay | 叫 claude／codex | 低～中 付費 | 是（attach） |
| 14 | nvim 外掛、沙箱 root 那層 | 使用者親手 | 低／0 | 是（root） |

需要使用者親手的：say／listen／chat（看順不順手）、agent-fay attach（要在 Claude Code 外的終端機、要 tmux）、nvim、沙箱 `sudo setup.sh --apply`——這四項 [WAIT_USER](../../../WAIT_USER.md) 各有一行。

## 不在實測裡、仍掛著的殘項

- **代定待落條文**（[NORMS 08-待定](../../../../proto8/docs/NORMS/08-待定.md) 各一行）：fsm exec 直接放單子、`_metainfo`、函數成長、工具＝函式庫、Linux 權限與沙箱。使用者看過才落，改條文派 opus 以上、改完再審。
- **沙箱與 kernel**（[sandbox S14～S18](../../../../proto8/thinking/2026-10-24-sandbox.md)；10-24 晚照使用者「存取控制純靠linux」重看）：沙箱預設看不到 kernel 信箱，設定把信箱綁進來就能用（沒有另外的開關）；沙箱裡的 agent 經 kernel 問腦走得通了（寄信人看 `sender.lock` 的檔案鎖、不看 pid；真腦實跑過）；跨帳號照 `setup.sh --mailbox` 設群組與權限；沒寫 `env` 也只帶 PATH、語系與 aos 的六個。還剩：`accept` 跟「純靠 Linux」衝突、暫留待使用者（S18）；`accept` 裡的腦照信裡的 `AOS_WS` 動檔；同一個信箱的人看得到彼此的信。「self-improve 預設就關」見 [S11](../../../../proto8/thinking/2026-10-24-sandbox.md)。
- **compact 與 P-41 擦邊**：agent-hal 把舊 history 輪替進 `compact/<run>/`、另起新檔；另兩條路是照 kai「紀錄照長、送腦的另外組」或 brain 改讀摘要檔（[compact](../../../../proto8/thinking/2026-10-24-compact.md)）。等使用者看。
- **bash-boxed**：10-24 晚 [sandbox/README](../../../../proto8/extras/sandbox/README.md) 改指 `lib/base/bash`、補了 `cpu_s`（CPU 時間）跟 `timeout_s`（牆鐘）不同種；環境照 S16 預設白名單。
- **agent-gus 的小念頭**沒收進 lib（是 gus 自己的入口；10-25 定案不搬，[理由與翻案](../../../../proto8/thinking/2026-10-24-tool-lib.md#10-25-agent-gus-的小念頭不搬)）；json_edit 兩步的第二步預定換成 gus 的 `thought.json`。
- 方向題（tasks、通用 kernel）、腦的工具呼叫三題 → [WAIT_USER](../../../WAIT_USER.md)。
