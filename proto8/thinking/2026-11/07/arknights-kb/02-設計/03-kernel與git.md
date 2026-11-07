← [入口](../02-設計.md)｜涵蓋：嵌套接法與唯一要補的洞、並發閘與 80%、git 政策、自我演化迴圈｜上一份 [02-agent與工具](02-agent與工具.md)｜下一份 [04-第一輪與施工](04-第一輪與施工.md)

# kernel 嵌套、並發、git、自我演化（結論）

## 嵌套：照試驗場 `llm_team/forward` 接，只補一個洞

```
writer ──aos-llm──→ 隊 kernel（llm_team；endpoint 包 luna/sol 都是 exec: forward, to: <總機代號>）
                        └─ forward/_entry ──aos-llm ask──→ 總機 llm_kernel ──llm_http──→ LiteLLM
```

- 現況可通（01-盤點步 6）。缺的只有 **usage 回不來**（不足 #3）：`aos-llm ask` 只印 message。
- **K1**：`aos-llm ask`／`recv` 加 `--full`，印整封回信 body（`{"message", "usage", "model"}`，kernel 已存在回信裡）；forward 改用 `--full`、原樣轉出。上層 `used.json` tokens 就對了、`budget.max_tokens` 生效。C++ 一支旗標，交 gpt。
- 下游 `senders` 只見隊 kernel 一格：**不改**（代定）。一隊一額度正是嵌套的用意；隊內誰用多少看隊 kernel 自己的 `used.json.senders`（key＝各 writer 的 ws）。
- forward 先住 `~/code/playground-ak/defs/llm_forward/`（playground git），兩輪穩了收進 `proto8/lib/base/llm_forward`＋範本 `kernel/llm-kernel` 加一個 `team` 例子（代定 3 的收法）。
- 再往下嵌（隊→小隊→…）＝同一支 forward 再包一層，不用新程式；深度靠 `AOS_LLM_KERNEL` 指到哪台決定。

## 並發與 80%（16 核 60 GB → 上限 12.8 載、48 GB）

| 閘 | 設定 | 第一輪值 | 說明 |
|---|---|---|---|
| 總機 kernel | `slots`、`reserved.high` | 6、1 | LiteLLM 同時 6 封；隊長急用留 1 格 |
| 隊 kernel | `slots`、`budget.senders` | 4、每 writer ws `max_calls` 200／日 | 一隊最多 4 封在飛；跑飛了自己停 |
| 領班 daemon 判官 | `max_running`、`queue: true` | 8 | 同時 8 隻 agent proc；第一輪實際掛 1～2 隻 |
| 每列 `limits` | `mem_mb` | 512 | agent-fsm 是 Python，夠 |
| 整樹 | `systemd-run --user --scope -p MemoryMax=48G -p CPUQuota=1200% nice -n 10 aos-exec root` | — | 硬天花板；`watch.sh` 記 load／mem |

小模型 agent 一隻 idle 時幾 MB，「成千上萬可 sleep」靠 daemon 的 sleeping 列即可；第一輪不驗規模。

## git

- **一個 repo**：`~/code/playground-ak/` 整夾 `git init`（已是代定 3），`kb-ak/`、`defs/`、`agents/`、`runs/` 都在裡面；`ws/.stack/`、`run/`、`corpus/` 進 `.gitignore`（stack 照 `cmd/aos-agent/stack.gitignore`）。
- **每批一 commit，lint 過才 commit，agent 不碰 git**：`batch.py` 收齊→`kb_lint`→退 0 才 `git add kb-ak && git commit -m "kb-ak batch N: places 1-20"`；退 1 就留 working tree、把錯寫 `work/manual.md`。訊息英文（程式輸出）；要人看的放報告。
- 審查事後（裁題 3）：reviewer 退件寫 `work/rejects.md`，下批 `batch.py` 先派退件再派新檔；退件也走同一條 lint→commit。
- 歷史＝`git log -- kb-ak/ak/places/x.md`；不記 `_meta`（K7 已裁）。
- 收進 proto8 的定義另開 commit（repo 的 `git pull --rebase` 規矩照交棒檔）。

## 自我演化迴圈（每輪一圈）

```
跑一輪 ─→ round_report.py ─→ runs/<n>/report.md（四個數＋失敗＋bash top 10＋人工處）
   ↑                                   │
   │                                   ▼
 commit ◄── opus 審 ◄── gpt 施工 ◄── 隊長／fable 在 defs/PROPOSALS.md 加一條
                  defs/<name>/{_entry,_tooldef.json,README.md}
```

- **提案一條＝三句**：看到什麼數字／現象、要加或改什麼（工具／agent 定義／kernel 設定）、預期哪個數變好。誰提：前兩輪隊長／fable；第三輪起 reviewer 可用 `self_tools` 自提（寫進 `work/proposals.md`，隊長搬到 PROPOSALS）。
- **施工規矩**：一個定義一夾、`README.md` 第一行一句白話（鐵律 3）、`_tooldef.json` 英文；gpt 照 PROPOSALS 那條做，不自己改方向（aos-teams/03 原話）。
- **審**：opus 看 diff＋跑該工具的 Done when；過＝commit 到 playground main。
- **定義總覽** `defs/INDEX.md`：`defs_index.py` 從每夾 README 第一行生成（表：名、一句、輪次、狀態 playground／proto8），每輪重生、跟報告同一 commit。
- **收進 proto8 的條件**：連兩輪沒改、被用過、Done when 可重跑；收法＝複製到 `lib/`／`templates/`／`kernel/`，README 改成 repo 語氣，code map 重生。
