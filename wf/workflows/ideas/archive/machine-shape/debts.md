> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# 裁決的欠帳：兩顆 CPU 的記憶體模型、git 與暫態
← [machine-shape](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

這兩條的性質跟其他拷問不同：**它們是使用者已下的裁決兩兩相乘產生的**，單看每個裁決都
沒問題。所以它們不是待辦清單，是**已經產生的欠帳**。

## 1. 兩顆 CPU 共用一份記憶體，而沒有記憶體模型

[第三輪裁決](../call-format/cpu-analogy.md)：LLM CPU 是常駐 daemon，工作**投遞到外部
資料夾、好了之後寫回來**，「類似 CPU 與 GPU 的交流」。那是**非同步**的——LLM CPU 在
process CPU 的回合**之外**繼續跑，然後在某個時刻**寫回同一個資料夾**。

於是：**兩個獨立執行單元同時寫同一份記憶體，而這台機器沒有記憶體模型。** 沒有 barrier、
沒有 atomics、沒有 happens-before、沒有 coherence 協定——真實多核心架構最貴的那份規格。

會咬人的地方：

- **`folder(state N) + inst → folder(state N+1)` 失效**：有兩個推進者，「state N」是誰的
  N？兩顆 CPU 的回合編號之間沒有定義任何關係。
- **LLM 寫回來時 process CPU 可能正在跑**：一筆 inst 可能讀到一半的結果檔，或讀到舊值後
  被覆寫。`.temp` 只保護 `.aos/` 的投遞區，**不保護結果寫回**。
- **沒有 id 就沒有去重**：daemon 因網路重試而重送結果時認不出來——又回到
  [批需要 header](instruction.md)。

不需要完整的記憶體模型，但**至少要有一句話說明兩顆 CPU 的寫入如何排序**。目前那句話不
存在，而它是「GPU 模型」這個裁決欠下的第一筆帳。

## 2. git 當快照，撞上 `.aos/` 裡的暫態

[第四輪裁決](../call-format/handoff-and-world.md)：快照／回滾／複製都用 git。但 `.aos/`
裡混著兩種性質完全不同的東西：

| 性質 | 檔案 | 該不該進 git |
|---|---|---|
| 世界的持久狀態 | 世界本體的檔案 | 該 |
| 機器的暫態 | `.runi`（鎖）、`inst.tempd/`（飛行中的投遞）、`.bad`、未來的 events | **不該** |

**回滾到一個含有 `.runi` 的 commit，那個世界立刻死鎖**——`claim` 看到 `.runi` 就拒絕，
loop 拿到 3 直接退出（見 [loop](loop.md)）。回滾一個世界，得到一個永久拒絕啟動的世界。

反過來，`inst.json` 該不該被 git 管也是真問題：回滾會把舊的待執行批次一起復原，世界會
**重新執行一個舊回合**。按 [prior-work](../prior-work.md) 的說法那是「新的求值分支」，
可以接受——但那必須是**選的**，不是副作用。

**所以 `.gitignore` 的政策是規範的一部分，而它還沒被寫下來。**

> **2026-09-01 拿到判準**：使用者的 L1/L2 cache 類比
> （[game-process-model §九–十一](../game-process-model.md)）給出一句話的分類法——
> **刪掉它，世界語意變不變？只變節奏＝微架構狀態（機器自己的），語意變＝架構狀態
> （世界的記憶體）。** `.gitignore` 政策就是這條線：**cache 永不入 commit**；本節那個
> 死鎖的本質，是**把微架構狀態當架構狀態存了檔**。注意邊界會移動——`turn` 現在是 cache，
> 回合編號成為 PC 之後就不是。

> **第十輪補了 git 的第三筆帳**（[instruction §24](instruction.md)）：轉移函數有自由變數
> （environ、PATH、絕對路徑），**git 拍的狀態集合 ≠ 機器改的狀態集合**——回滾 folder
> 不回滾宇宙。規範至少要宣告 footprint。 現在寫成本接近零，等
`.aos/` 長出 events 與 status 之後會複雜很多。

## 3. 這台 CPU 沒有中斷線（GPU 裁決的第二筆帳）

GPU 模型定了 LLM CPU 把結果**寫回外部資料夾**。那麼——**世界怎麼知道結果回來了？**

目前答案是：**不知道**，除非下一批裡有一筆指令主動去看。於是**每一個非同步結果都需要一筆
對應的輪詢指令**，N 個外掛 CPU 就是 N 筆輪詢指令，每回合都跑，不管有沒有東西回來。

真實 CPU 與 GPU 之間有中斷、doorbell、completion queue。這裡搬了 mailbox，沒搬通知機制。
而 **loop 是最適合放這個的地方**——它本來就在輪詢，讓它輪詢「有沒有完成事件」比讓每個
世界自己塞輪詢指令便宜得多。

> **2026-09-01 可能有答案了**（觀察，非裁決；[assembly-and-chains/interrupts §七](../assembly-and-chains/interrupts.md)）：
> 現行管線**整批 claim 進 `batch/<turn>/insts/` 才執行**，外部投遞因此打不進一個 tick 的
> 中間、只能落在兩個 tick 之間——**中斷線就是 tick 之間的 inbox**，與遊戲模型「輸入在
> frame 邊界處理」是同一件事。缺的不是機制而是規範；且
> **`deliver` 的碰撞規則是它的前置**（[verdicts B14](../verdicts.md)）：鏈自投的後繼與外部
> 中斷寫的是同一格，現在 last-writer-wins、無警告。

> GPU 裁決至今欠兩筆：**記憶體模型**（第 1 條）與**中斷**（本條）。
