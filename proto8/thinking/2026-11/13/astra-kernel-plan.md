# astra 當 kernel（線核 11-13 晚規劃，未施工）：用現成的 kernel_gate 把門掛在 astra 身上，sol 做完寄「停自己」的請求當門鈴、astra 表態＝驗收；sol 的腦走機器隊站 llm-t1、不經 astra；全是活樹新增、不改 aos 程式；8 題 11-13 22:15 使用者全照推薦

← [11-13 日索引](README.md)｜前一份：[gpt-fsm-team](gpt-fsm-team.md)（現行 subagent 做法與「下一步想法」節）｜相關：[eca-as-kernel](eca-as-kernel.md)（kernel_gate 的來歷）、[kernel-framework-開工](kernel-framework-開工.md)、[aos 問題總表](aos-issues-1113.md)

> 流程照使用者 11-13 晚定的：opus 帶隊（線核）→ 四隻 sonnet 唯讀搜集 → opus 匯總成備料 → fable 只讀備料做設計 → opus 細化對到檔案 → **到此停**。全程沒起 aos 行程、沒叫真腦、沒寄信、沒碰活樹（只讀）。

## 使用者原話（11-13 晚，逐字）

1. 「然後我這邊還有新的想法，就是說astra指揮sol，目前是默認他們都在同個daemon底下，或是走aos-subagents工具，我在想，或許可以讓astra變成kernel，然後他底下掛sol們，這樣試試看。不過這比較大膽，可以下一步再做。」
2. 「astra當kernel都可以先去跑。」
3. 流程：「先派opus帶隊，指揮sonnet搜集訊息，然後opus整理匯總，交給fable規劃與設計架構，然後opus深化細化架構，最後再來實作。」

## 使用者裁定（11-13 22:15，逐字）

「astra八題這塊都按照推薦。限制資源這塊十一題：cgroup這塊要可選。群組這塊可以再多挖一些用法。要root的做法可以想想，但先以沒有root的情況做規劃。」

→ 前半句定了這份：Q1～Q8 全照推薦（逐題落定見 [06](astra-kernel-plan/06-待裁與衝突.md#使用者裁定11-13-2215)）。後半句是 [kernel-limits-plan](kernel-limits-plan.md) 的。

## 一張圖

```
隊長 opus（出圖紙、起 astra、看門、重驗、commit）
 └ astra（gpt-lead-k，腦 astra-high；身上掛 kernel_gate＝門）
    │  subagent add／say／rm sol ──直寄──▶ ws daemon（手）
    │                                        ▲
    │  門：hooks/kernel_gate/requests ──pass 後機器轉寄──┘
    │     ▲ sol 做完：agents_ctl stop 自己（timeout 600 秒）＝門鈴
    └ sol-a、sol-b（gpt-worker-k；.env 寫死 AOS_KERNEL＝astra 的門、AOS_LLM_KERNEL＝llm-t1）
         │ 問腦
         ▼
      llm-t1（隊問腦站，機器規則、全隊額度）──llm_forward──▶ llm-gpt（總閘）──▶ LiteLLM proxy
      astra 自己問腦直寄 llm-gpt；astra 的 AOS_KERNEL 不設（不自己判自己）
```

**跟現在比**：現在 astra 主動 `say` 後一直 `listen` 等（撞 T3、T24、T28，花費是 sol 的 2～8 倍）；改成 astra 派完單就結束回合，sol 做完「按門鈴」把它叫醒，它讀工單回報欄驗收，`pass`＝讓 sol 停下（然後 rm）、`refuse`＋`say`＝退件。腦請求不經 astra 本人（問腦那包不能「留著等表態」，AK1；而且每步都等 astra 會更貴）。

**最大的洞**：門分不出是哪隻 sol 寄的「停」（ctl 信的寄件人是工作區，全是 repo，AK9），也不擋「停別人」（AK11）——sol 請求停 `eca_main` 只能靠 astra refuse。階段 2 放一題考它。

## 分檔

| 分檔 | 內容 |
|---|---|
| [01-備料](astra-kernel-plan/01-備料.md) | 四隻 sonnet 搜集、opus 匯總的事實＋出處（kernel 與請求的路、kernel_gate、子 daemon、現行 subagent 做法與痛點、掛在 kernel 下要什麼、相關問題條目）；fable 唯一的輸入 |
| [02-fable設計](astra-kernel-plan/02-fable設計.md) | fable 交稿原樣（形狀三案、怎麼掛、比較表、權限額度、失敗卡住、四階段試法、預見問題 15 條、裁題 8 題） |
| [03-opus細化](astra-kernel-plan/03-opus細化.md) | 讀程式驗掉 fable 的六項待驗；跟 fable 不同的六處；活樹新增檔逐檔對照；兩份 system 要加的話；十二條邊緣狀況 |
| [04-施工與驗收](astra-kernel-plan/04-施工與驗收.md) | 階段 0 接線、1 門的機關（假腦）、2 真跑（真腦）、3 分額度與換指揮（等停樹換執行檔）、4 選做規則站；每步驗收 |
| [05-試驗紀錄](astra-kernel-plan/05-試驗紀錄.md) | 撞到的 aos 問題 AK1～AK13（只記不改）；fable 預見 15 條的核對 |
| [06-待裁與衝突](astra-kernel-plan/06-待裁與衝突.md) | 要你裁的 8 題（選項＋推薦）；跟現行規矩的衝突 7 條 |

## 已裁（11-13 22:15 全照推薦；全文見 06）

- Q1 形狀：**甲先跑**（agent 兼門，現成）／丙（前面機器站、astra 只看例外）／乙（子 daemon 當手）。
- Q2 經過 astra 的請求：**只有起停（門鈴）**／腦請求也要（要改 aos）。
- Q3 sol 怎麼叫 astra：**門鈴（停自己的請求）**／限隊信箱的 mailbox／照舊 listen。
- Q4 astra 改不改得了每隻 sol 的額度：**第一輪不能**。
- Q5 sol 名字：**每單新名字，階段 3 改固定格位**（要 purge＝刪檔，要你說）。
- Q6 astra 的工作區：**照舊 `teams/t1`**（不改既有額度設定）。
- Q7 階段 3 等停樹換執行檔：**等**。
- Q8 換 sol 當門：**astra 當門省了才試**。

## 還沒做的

- 全部施工（04）；8 題已裁（照推薦），施工另等放行（鐵律 2「不開新工作」）。標「待驗」的（tools.json 能不能單列一支工具、`.env` 寫空值的意思、ctl 信實際 sender）留給階段 0。
- wf 條文（aos-teams、07 分檔）要跟著改的只列在 06 衝突表，沒動 wf/。
