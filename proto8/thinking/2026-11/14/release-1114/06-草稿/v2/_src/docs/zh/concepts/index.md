# 概念：aos 的五個東西

跑完[開始用](../get-started.md)，你已經碰過這五個東西：函數資料夾、定義、stack、樹（daemon）、kernel 與信。這頁把它們串起來。

<!-- source: proto8/knowledge/aos/_description.json（八個詞）、world.json（daemon＝硬體、stack＝記憶體、定義＝原始碼）、kernel.json、mailbox.json。這頁是寫給人看的入門；給模型讀的正本是那幾個知識庫檔。 -->

## 1. 資料夾，就是函數

資料夾裡放一支叫 `_entry` 的可執行檔，它就能被呼叫：用 `aos-exec <資料夾>` 叫它，輸入從 stdin 進，結果從 stdout 出。旁邊放的說明檔跟著它走：

| 檔 | 做什麼 |
|---|---|
| `_entry` | 真正執行的程式，什麼語言都行 |
| `_tooldef.json` | 給模型看的用法：叫什麼名字、收哪些參數 |
| `_metainfo.json` | 這個函數的性質：會不會改東西、大概多久跑完 |

agent 用的每個工具都是這樣一個資料夾。開始用第 7 步叫的 `peek_now_time`、`math` 就在 `proto8/lib/base/` 底下，你可以直接打開來看。

## 2. 定義與 stack：程式碼和記憶體

- **定義**是一個資料夾，說一隻 agent 是什麼：用哪個腦、有哪些工具、系統提示寫什麼。像原始碼。開始用裡的 `defs/ann/` 就是。
- **stack** 是 agent 跑起來之後放一切的資料夾：狀態、對話紀錄、收件匣。像記憶體。開始用裡的 `stacks/root/procs/ann/` 就是。

同一份定義可以跑很多隻，每隻有自己的 stack。改 stack 不會動到定義。因為全部都是檔案，一棵樹可以停下來、整個複製到別處，再接著跑。

## 3. 樹：daemon 和它底下的行程

- **daemon** 像機器：它負責起行程、記一張表（誰在跑、在哪個階段、為什麼）。`aos-daemon-ctl -d <stack> ls` 看的就是這張表。
- **proc** 是 daemon 底下跑著的一個東西。一隻跑著的 agent 就是一個 proc；`_clock`、`_sweeper` 也是。
- 一個 daemon 和它底下的 proc，加上它們的資料夾，就是一棵**樹**。

## 4. kernel 與信：所有請求都走一扇門

- **信**是一個資料夾（裡面有 `letter.json`），放進對方的信箱資料夾就算寄出。agent 之間、人和 agent 之間都用信。
- **kernel** 是你寄請求去的地方，由它決定要不要做、什麼時候做。daemon 本身就是最簡單的 kernel：叫它起什麼它就起什麼。
- 問模型也是寄一封信，寄給 **llm kernel**。開始用第 3 步起的 `llms/` 就是它。額度、優先順序、換哪個模型，都在這扇門上管。

## 5. 工作區

**工作區（workspace）**是 agent 做事用的資料夾，像外接硬碟。幾隻 agent 給同一個工作區，就能共用檔案。開始用裡 `ctl add -w .` 的 `.` 就是把 `tree/` 當成 ann 的工作區。

## 再往下

- 每個定義檔各管什麼：`proto8/knowledge/aos/definition.json`
- 腦的請求怎麼走、endpoint pack 是什麼：`proto8/knowledge/aos/brain.json`
- agent 不能做什麼、為什麼：`proto8/knowledge/aos/rules.json`

這些知識庫檔本來是寫給 agent 讀的（英文、偏精簡），人讀也行。
