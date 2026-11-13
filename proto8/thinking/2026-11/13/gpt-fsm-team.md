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
