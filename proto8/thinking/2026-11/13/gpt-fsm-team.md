# gpt 實作隊改走 aos 的 agent-fsm（線隊 11-13 晚設計，未施工）：Claude 隊長起一隻 astra 指揮、astra 用 subagent 開 sol 照工單寫碼；兩份新定義拿掉 self／def／events 包、shell 進 bwrap 沙箱、before_tool 守門 hook 管寫入與 astra 對 sol 的操作；gpt 隊不 commit、不改設計，做完寄信，隊長重驗、審 diff、commit

← [11-13 日索引](README.md)｜相關：[aos-teams/07](../../../../wf/workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)（gpt 系改走 agent-fsm、待補三條）、[team-model](../../../../wf/workflows/team-model.md)

> 流程照使用者 11-13 晚定的：opus 帶隊（線隊）→ 四隻 sonnet 唯讀搜集 → opus 匯總成備料 → fable 只讀備料做規劃 → opus 細化對到檔案 → **到此停**。實作（建定義、改活樹、起 agent、叫真腦）要頂層放行後另派。全程沒起任何 aos 行程、沒對 proxy 發請求、沒碰活樹（知識庫唯讀）。

## 使用者原話（11-13 晚，逐字，依序）

1. 「codex這塊幫我改一下，改成走aos體系，也不用eca，就直接loop fsm」
2. 「我本地litellm proxy開起來了」
3. 「讓astra指揮sol去做，都用loop fsm agent。權限，工具，都好好設計一下。可以派fable去規劃。」
4. 稍早定的流程：「先派opus帶隊，指揮sonnet搜集訊息，然後opus整理匯總，交給fable規劃與設計架構，然後opus深化細化架構，最後再來實作。」
5. 「剛好，這是一次絕妙的試驗機會，途中遇到的問題就可以拿來改進aos」

## 一張圖

```
使用者
 └ 頂層 Claude（調度，只放行）
    └ opus 隊長（出圖紙、加 endpoint 包、建定義、寫守門、起 astra、重驗、審 diff、commit）
       │   交接：goal 一句指到 隊夾/blueprint.txt；回報：astra 寄信到 隊夾/mailbox（DONE/BLOCKED/NEEDS-USER/FAILED）
       └ gpt-lead（astra-high）×1：切工單、開收 sol、對圖紙驗收、寫 status.md
          │   派工：工單檔＋subagent say；收回報：subagent listen；收單後 subagent rm
          └ gpt-worker（sol-high）sol-T01、sol-T02…：一張單一隻，第一輪同時 1 隻（之後 ≤2）
             └ （不能再生）
```

## 每種角色的工具與權限（精簡）

| | astra（gpt-lead） | sol（gpt-worker） |
|---|---|---|
| 看（look、index、json 讀） | 有 | 有 |
| 改檔（change、json／jsonx 寫） | 有，守門只准寫隊夾 | 有，守門只准寫 repo、碰不到 `.git` |
| 刪 | 沒有 | 只有 trash（過守門） |
| shell | 有，沙箱裡 repo 唯讀、只寫隊夾、斷網 | 有，沙箱裡只寫 repo＋自己 stack、`.git` 唯讀、斷網；黑名單擋 git commit/push 等 |
| run_python、remove | 沒有 | 沒有 |
| subagent | 只有 `subagent`，守門只放行 add（只准 gpt-worker、名字 `sol-*`）／say／listen／ls／state／history ls／stop／rm（不 purge）；不准改 sol 的工具、腦、system、hook | 沒有 |
| agents_ctl、fork | 沒有 | 沒有 |
| self、def、events 包 | 沒有（整包拿掉，加不回工具、關不掉 hook） | 沒有 |
| mailbox、goal | 有 | 沒有 |
| commit／push | 不准 | 不准 |
| 腦 | `astra-high`，`--max-tool-calls 300` | `sol-high`，`--max-tool-calls 80` |

## 分檔目錄

| 分檔 | 內容 |
|---|---|
| [01-備料](gpt-fsm-team/01-備料.md) | 四隻 sonnet 搜集、opus 匯總的事實＋出處（agent-fsm 怎麼停、定義與 subagent、工具包與權限、腦與 endpoint 包、信箱、既有規矩）；fable 唯一的輸入 |
| [02-fable設計](gpt-fsm-team/02-fable設計.md) | fable 交稿全文，原樣保留（隊形、派工回報、何時停、角色權限、astra 界線、端點、失敗處理、交接、試驗紀錄、七題待裁） |
| [03-opus細化](gpt-fsm-team/03-opus細化.md) | fable 的待驗讀程式驗掉五項；跟 fable 不同的八處；兩份定義逐檔要改什麼、兩個 endpoint 包的寫法；十四條邊緣狀況 |
| [04-施工與驗收](gpt-fsm-team/04-施工與驗收.md) | 施工 0～10 步，每步驗收條件；乾跑、權限攻擊測、真工作的驗收；隊長的看門腳本 |
| [05-待裁與衝突](gpt-fsm-team/05-待裁與衝突.md) | 要使用者裁的 11 題（選項＋推薦）；跟舊規矩的衝突 13 條 |
| [06-試驗紀錄](gpt-fsm-team/06-試驗紀錄.md) | 撞到的 aos 問題 30 條（現象、出處、影響、可能改法選項；沒改 aos）；施工時續寫 |

## 還沒做的

- 全部施工（[04](gpt-fsm-team/04-施工與驗收.md) 0～10 步）；11 題待裁（[05](gpt-fsm-team/05-待裁與衝突.md)）。
- 標「待驗」的（hook 環境有沒有 `AOS_WS`、沙箱裡 rw 跟 ro 綁定的先後、`.git` 唯讀時 `git status`、改 llm kernel 設定要不要重起、推理模型收不收 temperature、proxy 實際模型名）都留給步驟 1～5 的乾跑。
- wf 條文（aos-teams、team-model、grades、07 分檔）要跟著改的地方只列在 05 的衝突清單，沒動 wf/。

## 施工紀錄（11-13 晚，線隊）

使用者放行（頂層轉）：照 04 動工，先乾跑步驟 1～5、再假工單、通了且時間夠才做一件小的真工作；活樹只新增不改不刪。

**施工時的代定**（跟 03／04 不同的地方）：

- llm kernel：活樹沒有（06 T33），也不能起第二台 daemon，所以改用 Python 版 `lib/aos/kernel_llm` 當 loop proc，掛在既有的 ws daemon 上（`~/aos-home/kernels/llm-gpt/`，proc 名 `llm-gpt`）。
- astra 的工作區改成隊夾 `~/aos-home/teams/t1`，不用 repo：腦請求的寄件人是工作區（T31），這樣 astra 才有自己的額度 key。
- jsonx 包兩種角色都不給（T35）。
- 沙箱：repo 整個唯讀，只有子夾 proto8、wf 可寫（T32）。
- 守門程式放 `~/aos-home/defs/shared/guard`，各定義用兩行包裝腳本叫它（symlink 不行，T37）。

**步驟結果**：

| 步 | 結果 |
|---|---|
| 1 proxy | 189 個模型，astra-high、sol-high 都在 |
| 2 llm kernel | 兩包都回 OK，ledger 有用量 |
| 3 守門程式 | 假事件 31 則全過（擋：repo 外、`..`、symlink 出界、`.git`、git 寫入類、`aos-*`、curl、subagent 改工具／腦／hook、purge、history rm；放行：該放的） |
| 4 定義 | `agent_def check` 兩份都 0 問題；工具清單核對過 |
| 5 沙箱 | worker：寫 proto8 成功、寫 repo 根目錄 Read-only、`git commit` index.lock Read-only、斷網。lead：寫隊夾成功、寫 repo Read-only、`git -C … status/diff` 正常、斷網 |
| 7 假工單 | 第一次起：守門程式找不到設定檔，astra 停（T37），修好後從 act 格續跑。接著 astra 照規則寄 BLOCKED：目標檔被隊長 staged 成「A」，是隊長佈置失誤，astra 判得對。commit 後叫它續做：寫工單、`subagent add sol-T01`、say、listen、自己用 tail/wc、diff、逐 byte 比對驗收、`rm sol-T01`（不 purge）、寄 DONE、goal done。約 2 分鐘；astra 29 次呼叫、37.5 萬 token，sol 6 次、4.4 萬 token |

**真工作題目**（先寫在這裡再開工）：[real1/blueprint-ledger-sum.md](gpt-fsm-team/real1/blueprint-ledger-sum.md)。在隊自己的夾裡新增 `ledger_sum.py`＋測試資料，把 llm kernel 的 ledger 按端點包×寄件人加總，給 Q1 看用量。範圍小、不碰 aos 程式和 wf/，可以逐字驗收。

**真工作結果**（21:03～21:10，約 7 分鐘）：

- astra 寫了 T02 工單、起 sol-T02。sol 寫出 [real1/ledger_sum.py](gpt-fsm-team/real1/ledger_sum.py) 和 `testdata/ledger-sample.jsonl`。
- astra 自己驗：照圖紙跑樣本，另外多驗了空輸入、預設值、排序、行號、非物件 JSON。驗完寫 status.md、`rm sol-T02`、寄 DONE。
- 隊長重驗：stdout 跟圖紙逐字相同（diff 空）、stderr 一行、退出碼 0；讀不到檔與不給參數都退 2；樣本 7 行逐 byte 對；全程式讀過，跟圖紙一致；`git status` 只有這兩個新檔；沒有 commit。
- 用量：astra 31 次、約 52 萬 token；sol 19 次、約 23 萬 token。拿這支新工具對真 ledger 加總：全晚 86 次、116 萬 token。
- 圖紙沒規定、程式也沒處理的一處：`usage` 是 `null` 時會出錯。真 ledger 目前沒有這種行，留著不修。
- 觀察：astra 中途也講過一句不帶工具的話（T28 的形狀），靠 goal 提醒接回來。sol 第一下就想用 `apply_patch`（codex 的習慣），沒有這個指令，就改用 shell 寫檔（見 06 的 T43）。

**收尾**：

- 已收：`ctl rm gpt-lead`；sol-T01、sol-T02 都由 astra rm。三者都沒 purge，stack 留作紀錄。
- `aos-daemon-ctl rm llm-gpt`：pid 124830 已退。
- 表上只剩原有的 _sweeper、eca_main、repo-aos。
- 活樹新增檔都留著：`~/aos-home/kernels/llm-gpt/`、`~/aos-home/defs/{shared,gpt-lead,gpt-worker}/`、`~/aos-home/teams/t1/`。daemon stack 下另有 `procs/{llm-gpt,gpt-lead,sol-T01,sol-T02}/`，以及 `procs/repo-aos/daemon_reply/`（T42）。

## 下一步想法（未排）

使用者 11-13 晚原話（逐字，頂層轉）：「然後我這邊還有新的想法，就是說astra指揮sol，目前是默認他們都在同個daemon底下，或是走aos-subagents工具，我在想，或許可以讓astra變成kernel，然後他底下掛sol們，這樣試試看。不過這比較大膽，可以下一步再做。」

線隊初步看法（沒驗，只讀了知識庫 `aos/kernel.json` 的 what、gate、write_your_own 三節）：

- **跟現在比**：現在是 astra 用 `subagent` 工具**主動**加、叫、收 sol，權限靠守門程式擋。改成 kernel 後，astra **被動**：sol 的 `AOS_KERNEL`（起停、喚醒）或 `AOS_LLM_KERNEL`（問腦）指到 astra 的收件夾，每封請求由 astra pass 或 refuse。這樣管得更細（每次叫腦、每次起停都要 astra 點頭），但 astra 就從「派工的」變成「批公文的」，派工本身還是要有人做。
- **會撞到的 aos 機制**：
  - `kernel_gate` 工具不在任何現成定義裡，要靠 `self_tools` 加。但這隊把 self 包整包拿掉了，所以只能改寫進 gpt-lead 的 tools.json，守門程式也要放行它的 pass／refuse。
  - 收件站是 on_clock hook：astra 在回合中或睡著時不跑。astra-high 一個回合可能好幾分鐘，`aos-agent ctl` 預設 30 秒期限，請求會以 `SlotMissing` 被拒。期限要拉長，或讓規則先放行，只把例外留給 astra。
  - 信件 `from` 不驗證，寄件身分又是 `$AOS_WS` 優先（06 的 T31）。所有 sol 的 ws 都是 repo，astra 分不出是哪一隻寄來的。
  - 如果要管腦，得在 llm-gpt 前面加一站（類似 `kernel/llm-team/`），讓 astra 那一站的 `next` 指到 llm-gpt。
- **建議的下一步做法**：先只讓 sol 的**腦請求**經過 astra（規則自動放行、超過額度才留給 astra 裁），起停仍然用現在的 subagent 做法。這樣改動最小，就能看出「astra 當 kernel」值不值得。
