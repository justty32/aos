# trial — 大量試用：驗證＋找不順手（2026-08-30）

← [dispatch](../README.md)｜判準 [usability-target](../../ideas/usability-target.md)

**目的**：照使用者定的兩級劇本，用「使用者的方式」大量操作 aos，記**多餘的動作／看不見的狀態／錯誤不指路**，
每條附「用 pi／Claude Code 做同一件事的對照」。這階段**只找、不修**（修 bug 隊與改進隊之後另開）。

| 隊 | 劇本 | 發現檔 | 交接書 |
|---|---|---|---|
| L1 單人 coding agent | 在一個真的程式碼資料夾裡全程只用 `aos …`，lmstudio 與 pi 各跑一遍 | [findings-L1.csv](findings-L1.csv) | [proto-L1](../proto/proto-L1-solo.md) |
| L2 指揮 agent 團隊 | 主 agent 派生子 agent（各住一個資料夾）、通訊錄投遞、收回報 | [findings-L2.csv](findings-L2.csv) | [proto-L2](../proto/proto-L2-team.md) |

**發現檔格式**（`wf-table/1`，一行一條）：`id,lane,kind(bug|awkward|spec-gap|cannot),severity(1-3),step,expected,actual,compare,repro`。
`repro` 指向 `trial/repro/<id>.sh`（可重跑的最小重現，之後修 bug 隊直接當回歸）。

## L1 摘要（2026-08-30）

> **測試基準**：發現量在 `93484d4` 上跑出來；跑的期間 main 前進到 `77eea98`（隊 W 的 `say` 帶 `from`、
> `core/agent/src/{init,run_top,store,user}.cpp` 與 `core/tool` 都動了）。因此把 `main` 的 `core/`／`app/`
> 取出重編後，逐條重跑了會被影響的 repro：`L1-01`／`L1-02`／`L1-06`／`L1-07`／`L1-08`／`L1-09`／
> `L1-14`／`L1-19`／`L1-20` **在新 main 上全部照樣重現**（差別只有 say 檔案多了一行 `from:`）。

**結論：能改到檔，但使用者被關在管子外面。** pi 引擎確實一個 step、17.8 秒就改完四個檔並讓 `make` 通過——
路是通的。問題全出在**看不見**與**多打的指令**：說了什麼看不見、它在做什麼看不見、失敗了看不見，
而失敗還會把使用者的話吃掉。29 條發現：bug 13、awkward 11、spec-gap 3、cannot 2（severity 3 有 12 條）。

**最痛的五條**：

1. **一次 LLM 失敗，交代的事就永久消失**（`L1-19`＋`L1-20`）。LM Studio 沒開時 `run` 照樣 exit 0、`state` 照樣 idle，
   真錯誤只寫在 `.aos/batch/<turn>/out/*.json`；而那一回合已經把 `say/` 的訊息吃掉了，端點修好也沒有人會回答它。
2. **PATH 陷阱讓整個世界靜默空轉**（`L1-01`）。`every/agent-<name>.json` 登記的是裸 `aos`；用絕對路徑呼叫 aos 的人
   （剛編好的人就是）每回合 exit 127、stderr 空白，`run` 印的「`turn N: 1 insts (1 every)`」和成功長得一模一樣。A／B／D 三隊各自獨立踩到。
3. **一句話要打 4～19 個指令，外加一個永遠佔著的終端機**（`L1-22`＋`L1-04`）。最小一輪 4 個 `aos` 指令，
   D 隊實際做完「在 README 加一行」用了 10 個指令 15 回合 26.8 秒；`run` 沒有 daemon 模式，`--step 0` 就是佔住整個視窗。pi 全部都是 1 個指令。
4. **未讀和完成都看不見**（`L1-02`＋`L1-03`）。連說三句，`state` 一個字都不變、`listen` 印空、`log.md` 0 bytes；
   「還沒開始」「有未讀」「做完了」「放棄後空轉」四種處境的 `aos state` 輸出完全一樣。
5. **本機 lmstudio 跑不完這條劇本**（`L1-21`＋`L1-23`）。45 個回合、0 個檔案被改；
   三回合工具往返讓每次犯錯代價 ×3，「`工具 sh 的 args 必須是字串`」一條錯誤原文重複 5 次、燒掉 12 回合。

**可用的**：pi 引擎那條路是真的能用（改對四檔、`make` 通過、追問記得前文）；`status=tool`／`等工具結果` 是準的；
`aos llm --slots` 是唯一會主動告訴你去哪裡設定的錯誤訊息。

**對照 pi**：同一件事 pi 都是一個 `pi -p`（追問再一個 `pi -c -p`），前台就看得到思考、工具與 diff，
失敗當場報錯、話還在 shell history 裡。aos 目前把「知道它在幹嘛」整件事留給使用者自己 `cat .aos/`。

**如果之後要做 pi 插件讓它跟 aos 對接**，這四條就是接縫（都有實測證據）：兩套記憶（`L1-25`：`history.json` 8 則
vs pi session 32 則含 15 個 toolResult）、兩套工具帳（`L1-26`：`aos tool rm` 全清＋白名單 `[]`，pi 照樣改檔、照樣走出世界）、
兩個預設模型（`L1-27`：裸 pi 走 openai-codex／gpt-5.6-sol，`--engine pi` 走 deepseek）、
錯誤只會原樣穿過來（`L1-17`／`L1-18`：pi 叫人去跑 `/login`，而 aos 這邊要的是 `DEEPSEEK_API_KEY`）。

## L2 摘要（2026-08-30）

**結論：投遞的管子通了，團隊的語意還沒有。** `aos say --to`／`aos deliver`／`every/` 推子世界三條路都實測可用，
但「一隻主 agent 指揮兩隻子 agent」整條劇本走不完——不是哪裡壞掉，是**缺件**。

**缺的原語**（依痛感排序）：

1. **訊息信封**——`say()` 只寫純文字，沒有 `from`／來源世界／message-id。boss 分不出 w1 的回報、w2 的回報與使用者的新指令（`L2-05`）。沒有寄件人＝沒有回信地址。
2. **agent 看得到通訊錄**——只有頂層 CLI 讀 `contacts.json`；system prompt 只列工具、從不列聯絡人，agent 不知道隊上有誰（`L2-03`）。pi 引擎更徹底：完全不讀登記表，還明講「不要去動 `.aos/`」——通訊錄正好住在那裡（`L2-04`）。
3. **未讀信要看得見**——狀態只反映上一次跑完的 step，堆了 3 封未讀仍報 `idle`；`listen` 讀的是 log，未讀信在任何 `aos` 指令下都是隱形的（`L2-07`、`L2-12`）。使用者要讀信得先燒一次 LLM。
4. **隊層級的名冊與彙總**——沒有 `aos contact status`；`state.json.agents` 只涵蓋本世界。實測答「誰在忙」用掉 9 個指令，最少也要 3 個，而且答案還是錯的（`L2-25`、`L2-07`）。
5. **開箱即用的投遞能力**——新世界預設只裝 `cat`／`ls`／`sh`，沒有 `aos`／`deliver`／`contact`，boss 要派工得先由人幫它 `aos tool add`（`L2-02`）。
6. **雙向登記**——通訊錄單向，worker 要回報得有人先進 worker 世界補 `contact add boss`（`L2-06`）。
7. **「只有信箱、沒有 CPU」的端點**——使用者當收件人（住 `~`）必須先被 `agent init` 成一隻完整 LLM agent；`--to` 又吃名字不吃路徑、shell 還會先展開 `~`（`L2-11`）。
8. **建子世界這件事本身**——`agent init` 會往上找最近的 `.aos/`，在既有世界的子資料夾裡跑會把 agent 靜默建到祖先世界（`L2-01`）。

**可用的**：`every/` 放 `{"argv":["aos","run","sub","--step","1"]}` 推子世界正常（每回合 3 insts、子世界 turn 跟著走、exit 0），
`find_folder` 也正確選最近的 `.aos/`（`L2-16`）。三隻同時打一顆 lmstudio 不會壞，只是排隊完全不可見（`L2-17`）。

**對照 Claude Code**：那邊 spawn／派任務／回報／全隊狀態由宿主承擔，操作者不碰地址；aos 目前把這四件事全留給使用者用資料夾和相對路徑手工維持。
