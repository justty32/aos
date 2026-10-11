# proto8 規劃（AI 提案，2026-10-11，待使用者拍板）

← [proto8](README.md)｜依據：[10-11 討論](thinking/2026-10-11-restart.md)、使用者 9/19 草稿 [fla](../thinking/2026-09-19.md)、9/23 [使用情境](../thinking/2026-09-23.md)

**這份是我趁你散步時寫的。全部是提案，一條都沒定。** 你回來從 §5 的題目開始看，答完我才動。

## 1. 一句話

proto8 ＝ **一棵資料夾樹。每個資料夾是一個計算任務（一條 POSIX argv ＋ 一份 JSON 標籤）。tick 照一張順序表起行程；順序表是另一個計算任務（排序器）寫的；資源也只是帶「容量」標籤的計算任務。** 任何人（含 LLM）用 `ls`、`cat`、改 JSON 就能看懂、操作整個世界。

今天討論的每一條都對得上：

| 今天說的 | 在 proto8 裡長成 |
|---|---|
| 計算任務＝POSIX 行程 | 一個資料夾、一份 `task.json` 寫 argv |
| 資源＝有限的處理能力，也是行程 | `llm/`、`human/` 兩個資料夾，標籤 `capacity` |
| 排序＝誰先給誰，也是行程 | `scheduler/` 資料夾，輸出寫 `.aos/order.json` |
| 一切都是計算任務 | 核心只認一種東西：有 `task.json` 的資料夾 |
| 九軸＋人類隨意附加的特性 | `task.json` 的 `axes`、`traits` 兩段 |
| 全是 JSON、模型可生成排序 | 排序器第二版讓模型照同一批檔案寫 |
| 空間＝資料夾、時間＝tick | `.aos/tick.json` 記第幾回合 |
| tick 停下來就能打包 | `.aos/snapshots/<回合>.zip` |
| agent＝S 表示式、節點可換 | agent 的 `steps.json`，每步是 argv 或 llm |
| 可預測性有主體性 | 排序器自己的 `belief.json`：它對每個任務的認識 |

## 2. 世界長什麼樣（候選）

```
world/                    ← 空間根；daemon 每 N 秒對它 tick 一次
├── .aos/                 ← 核心的本子（只有核心寫）
│   ├── tick.json         ← {"round": 1832, "at": "..."}
│   ├── procs.json        ← 活著的行程：pid ↔ 哪個資料夾
│   ├── order.json        ← 這回合起誰、先後（排序器寫的；沒有就照 ls 順序）
│   └── snapshots/        ← 1850.zip …（tick 停下來時打包）
├── painter-a/            ← 計算任務（一個 agent）
│   ├── task.json
│   ├── steps.json        ← 它的 S 表示式（之後才有）
│   ├── in/               ← 別人丟給它的
│   └── out/              ← 它產出的；stdout／stderr 也落這裡
├── painter-b/
├── llm/                  ← 資源：模型端點，capacity 1
│   ├── task.json
│   ├── in/               ← 請求 *.json
│   └── out/              ← 回覆 *.json ＋ usage.json（這就是帳本，不另做）
├── human/                ← 資源：人類輸入，capacity 1
└── scheduler/            ← 排序器
    ├── task.json
    └── belief.json       ← 它對各任務的認識（可預測性住這裡）
```

`task.json`（示意，軸的值怎麼寫還沒定）：

```json
{
  "argv": ["python3", "run.py"],
  "axes": {
    "io": "files", "life": "per-tick", "state": "own-folder",
    "needs": ["llm"], "interrupt": "safe", "guarantee": "idempotent",
    "compose": "none", "env": "own-folder", "determinism": "random"
  },
  "traits": {"good_at": ["人物"], "bad_at": ["風景"], "priority": 3}
}
```

資源的 `task.json` 多一個 `"capacity": 1`，其他一樣。

## 3. 核心只做一件事：tick

```
每 N 秒：
  round += 1
  讀 .aos/order.json（沒有 → 所有有 task.json 的資料夾，ls 順序）
  照順序：那個資料夾沒在跑 → 起 argv（cwd＝該資料夾，環境給 AOS_ROUND、AOS_ROOT）
  等「本回合會結束的」任務退出（或到期限）     ← tock
  寫 tick.json；有人要求就打包 snapshots/<round>.zip
```

**一支檔案、≤ 200 行、純標準庫。** proto2 的 exec＋loop 加起來 116 行，這個多的是順序表和打包。

任務之間怎麼講話：**只靠寫檔到對方的 `in/`。** agent 要問模型＝寫一個 JSON 到 `llm/in/`，下回合 `llm/` 跑、寫 `llm/out/`，再下回合 agent 讀到。這就是你 9/19 寫的「大操作丟到另一個資料夾讓另一個 proc 處理」。

## 4. 做的順序（每步你說「對」才下一步）

| 步 | 做什麼 | 驗證（你用眼睛看） | 它測今天哪一條 |
|---|---|---|---|
| 0 | 你看這份、改 | — | — |
| 1 | [使用情境日記](thinking/2026-10-11-a-day.md)定稿（我已草擬） | 你讀完覺得「對，我會這樣用」 | 目標 |
| 2 | tick 一支＋兩個 echo 玩具任務 | 跑三回合，`cat .aos/tick.json`、`ls */out/` 看得懂 | 時空、一切都是計算任務 |
| 3 | `llm/` 資源（capacity 1）＋兩個 agent 搶 | 看 `order.json` 誰先、`llm/out/usage.json` 花多少 | 資源也是行程、誰先用大腦 |
| 4 | `scheduler/` 手寫 30 行 → 再讓模型照同一批檔案生成一版 | 兩版 `order.json` 比 | 排序是行程、可由模型生成 |
| 5 | agent 的 `steps.json`，把一步從 llm 換成程式 | 數節點：幾個模型、幾個程式 | S 表示式、可預測性可量 |
| 6 | 打包：tick 停下來 → zip；解開看 | `unzip -l` | 時間停止 |

每步 ≤ 半天、≤ 200 行新碼、真模型 ≤ 5 萬 token。

## 5. 要你拍板的（附預設）

1. **第 1、2 層用 proto7-2 的核心（2100 行、已驗證）還是重寫小的？** 預設：**重寫**。理由：proto7-2 核心帶著 slot／birth／tock 回條那一套慣例，會把設計拉回去；它證明過的事（用程序不用 thread、任務由 tick 起、tock 只通知不收）照抄**概念**不抄碼。
2. **真模型用哪個？** 預設：luna（最便宜），每步上限 5 萬 token。
3. **proto7-2 怎麼處置？** 預設：**留著不動**，README 頂上加一行「探針，10-11 起停」；不刪、不搬。要用再去拿。
4. **排序器第一版誰寫？** 預設：我手寫；第二版才讓模型生成，兩版比。
5. **煞車（§6）照提案走？** 預設：是。

## 6. 煞車（提案）

兩個月的教訓是「做」長得比理解快。proto8 這樣踩：

1. **不開隊。** 只有你和一個 AI，不派 codex 工人。
2. **一次一件。** 做完給你看，你說「對」才下一件；一件 ≤ 半天、≤ 200 行。
3. **開工前三句話。** 它是什麼、少了它會怎樣、它跟「一切都是計算任務」的關係。第三句寫不出來就不做。
4. **核心總行數 ≤ 300。** 要超過先問你。
5. **只寫 demo，不寫測試海。** 一支 demo 腳本印出每回合發生什麼、最後 `ls`／`cat` 給你看；不寫契約卡、意圖卡、藍圖、決策清單，文件只有 README 和 thinking/。
6. **做之前先寫日記。** 新東西要先出現在使用情境日記裡，日記裡沒有的不做。

## 7. 會長胖的地方，先說「不做」

| 以前長出來的 | proto8 的態度 |
|---|---|
| 帳本、grant、holder、預留結算 | 不做。`llm/out/usage.json` 一行一次呼叫，就是帳本 |
| 崩潰恢復、retry_lost、once 保證 | 不做。tick 重起就好；任務要自己冪等——那是它標籤上的事，不是核心的事 |
| 上鎖、並行 | 不做。只有一個 tick 行程在寫 `.aos/`；任務只寫自己的 `out/` 和別人的 `in/` |
| 權限、身份、掛載 | 不做。先全在一個 Linux 使用者底下；daemon 層以後再接 |
| 信箱包、技能包、記性包、選單包、壓縮包 | 不做。都是「`in/` 裡放什麼檔、agent 的 `steps.json` 怎麼排」的事，agent 自己的事 |
| 監督者 kernel | 不做。排序器看 `procs.json` 和各 `out/` 就知道誰卡住，那是排序器的一條規則 |
| 退出碼契約、error_path | 不做。退出碼原樣落在 `out/exit`，誰想看誰看 |
| 1444 個單元測試 | 不做。一支 demo |

## 8. 我自己擔心的

- **`in/`／`out/` 檔名和格式**會是第一個想長規矩的地方（id 怎麼取、回覆怎麼對應請求）。打算：檔名就是 `<回合>-<序號>.json`，內容隨便；對應靠回覆檔裡寫 `"re": "<請求檔名>"`。超過這個就停下來問。
- **「等本回合會結束的任務」要等多久**——那就是 life 這一軸（per-tick 的要等、service 的不等）。核心只認這兩種。
- **資源的 capacity 誰管**：資源自己管（`llm/` 的程式一次只處理一件），排序器只是「知道」它容量 1 所以不排兩個。核心不管。
- **日記寫得太順**會騙人。所以第 2 步一定要真的跑，不能只看圖。
