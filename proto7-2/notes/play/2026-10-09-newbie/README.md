# 2026-10-09 新手試用（U 隊）

← [試玩紀錄](../README.md)

## 怎麼試

- 每個模組兩位「新手」各試一次：Claude **Haiku**（Agent 工具）與 codex **gpt-6-luna**（`model_reasoning_effort=low`）。先前用 Sonnet 或各隊自評的分數不算。
- 只准讀該模組 README（及它直接連到的 README）與 `--help`；不准讀 spec、藍圖、notes、原始碼。在 `/tmp/u-newbie/<模組>/<試用者>/work` 操作，不改 repo（試完 `git status` 乾淨、無 apprentice 分支）。
- 題目一律是「照 README『第一次跑』做一遍」；llmcall 跑真傳輸 `examples/litellm`（本機 LiteLLM），mail 另試三個日常指令。任務原文見 [raw/task-template.md](raw/task-template.md)。
- 判準：第一次跑 ≤10 分鐘、對外指令 ≤3、新概念 ≤5、分數 ≥7（五條平均，兩位取差）。
- **分鐘是組長估的人類時間**：AI 實測都在 1 分鐘內（12～36 秒），不能代表人。估法＝README 開頭＋第一次跑段落字數 ÷ 400 字／分＋指令行 × 0.25 分＋試用者回報的卡點分鐘（取多的一位）。
- 指令數：模組自己的子指令，加上第一次跑非用不可的**其他包**指令（skills、llmcall 要 `aos7-budget`）；aos 核心的 `aos7-daemon`／`aos7-ctl` 不算。概念數取兩位裡數得多的。

## 總表

| 模組 | 分鐘 | 指令 | 概念 | 分數（Haiku／luna） | 過不過 | 報告 |
|---|---|---|---|---|---|---|
| modules/wfnode | 10 | 3 | 7 | **6.8**（6.8／8.4） | 不過：概念、分數；重試第 1 輪：6／3／4／**7.4**（7.4／8.8）過 | [wfnode](wfnode.md) |
| packs/prompt | 5 | 2 | 11 | **6.8**（6.8／8.0） | 不過：概念、分數 | [prompt](prompt.md) |
| modules/compact | 6 | 3 | 5 | **6.6**（6.6／8.6） | 不過：分數 | [compact](compact.md) |
| modules/skills | 9 | 5 | 10 | **5.4**（5.4／8.2） | 不過：指令、概念、分數 | [skills](skills.md) |
| modules/routines | 10 | 3 | 8 | **6.2**（6.2／7.6） | 不過：概念、分數 | [routines](routines.md) |
| modules/metrics | 16 | 1 | 6 | **6.2**（6.2／8.0） | 不過：分鐘、概念、分數 | [metrics](metrics.md) |
| packs/author/checkers（aos 題型） | 11 | 3 | 6 | **6.2**（6.4／6.2） | 不過：分鐘、概念、分數 | [author-aos](author-aos.md) |
| packs/llmcall（真傳輸） | 17 | 5 | 15 | **5.2**（5.2／8.0） | 不過：分鐘、指令、概念、分數 | [llmcall](llmcall.md) |
| modules/events | 15 | 2 | 10 | **5.2**（5.2／7.0） | 不過：分鐘、概念、分數 | [events](events.md) |
| modules/mail（X1） | 10 | 6 | 10 | **5.6**（5.6／8.0） | 不過：指令、概念、分數 | [mail](mail.md) |

**十個全部不過。** 每個都卡在分數：Haiku 給的平均都在 5.2～6.8；luna 除 author 外都 ≥7（7.0～8.6）。兩位的差別主要在 Haiku 會把「README 後半的規則、代號、spec 連結」算進難度，luna 只看第一次跑有沒有走通。概念數只有 compact 在 5 以內。

兩位都跑通的：九個。沒跑通的：author aos 題型（luna 在沒有 user scope 的環境裡，第二關直接失敗，README 沒教加 `--no-scope`）。

## 共通的卡點（新手視角）

1. **第一次跑就被迫碰別的包**：skills、llmcall 要先開帳、起帳任務；routines、events 要先起 daemon、寫 timeline.json／tasks.json。新手的概念數多半是從這裡來的。
2. **README 後半跟第一次跑擠在同一頁**：契約卡、已知限制、內部代號（mail 的 D1／F5／W0、metrics 的 window_unknown）、退出碼表，新手一眼就看到，又不知道可以停在哪。
3. **「見 spec」**：不讀 spec 就看不懂的詞，新手只能照抄（llmcall 最多）。
4. **預期輸出對不上或沒解釋**：routines 寫 5 行、實跑 6 行；compact 的 trigger 欄位；prompt 示範只省 6%；wfnode 印「未定 97 處」又說 OK。
5. **寫進 repo 的風險沒標**：llmcall `run.sh ./evidence`、author `publish` 預設寫真 repo、wfnode 範例 run.sh。

## ELI5 之後仍複雜的

兩位新手對十個模組都答「ELI5 之後仍複雜」。依組長看，分兩種：

- **ELI5 講得完、但 README 把複雜的露出來**（改 README 就能過）：compact、prompt、wfnode、metrics、mail（只看日常三指令時）。
- **ELI5 講完，第一次跑仍需要 ELI5 以外的東西**（光改字不夠，要改第一次跑的路徑）：skills（帳）、llmcall（reserve／settle／receipt／退出碼 3、4）、events（daemon＋obs／must＋ack）、routines（daemon＋回合）、author（scope／reviewer／publish 寫哪）。

頂層問的 mail「日常 3＋進階 3」：兩位都判**仍複雜**。日常三個本身 ELI5 講得完；複雜來自同一頁的 roster／team、6 種 STATUS、「done 要先 read」、內部代號與沒有 `--help`。詳見 [mail.md](mail.md)。

## 一頁 ELI5：整個 aos（9 框）

給五歲小孩：aos 是一棟讓 AI 小幫手上班的房子。

```text
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│1 心跳        │  │2 房間        │  │3 鬧鐘        │
│daemon 定時醒 │→ │node＋任務表  │← │routines     │
│一次＝一回合  │  │醒來照表做事  │  │隔幾回合／定時│
└─────────────┘  └─────────────┘  └─────────────┘
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│4 工作筆記本  │  │5 日記本      │  │6 郵局        │
│wfnode       │  │events       │  │mail         │
│停在哪、下一步│  │發生過什麼    │  │誰請誰做事    │
└─────────────┘  └─────────────┘  └─────────────┘
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│7 問大模型    │  │8 備料        │  │9 量尺與關卡  │
│llmcall＋帳本│← │prompt 拼信   │  │metrics 量用量│
│先預留再扣帳  │  │compact 收舊的│  │author 學徒三關│
│              │  │skills 挑說明書│  │             │
└─────────────┘  └─────────────┘  └─────────────┘
```

心跳讓房間裡的任務按時跑；任務要問 AI 時，先用備料把信寫好，再經「問大模型」送出並記帳；做完的事寫進日記本和筆記本，要別人幫忙就寄信；量尺事後算花了多少，關卡擋住學徒交來的壞工具。

## 回改單

各模組報告的「回改」段，狀態全為**未改**；交頂層轉各隊。改完由 U 隊用同兩位新手重試，分數 ≥7 才算 done。

- [wfnode](wfnode.md#回改)
- [prompt](prompt.md#回改)
- [compact](compact.md#回改)
- [skills](skills.md#回改)
- [routines](routines.md#回改)
- [metrics](metrics.md#回改)
- [author-aos](author-aos.md#回改)
- [llmcall](llmcall.md#回改)
- [events](events.md#回改)
- [mail](mail.md#回改)
