# tonight-rulings（11-10 深夜）：總整合後的八題與一個代定，使用者答了

← [11-10](../README.md)

[總整合](../tonight/README.md)跑完攤出八題＋一個代定，使用者回來一次答完。這份只留原話、決定、結論。

## 頂層攤的題（整理）

1. 範本預設 15 支工具說明約 7600 tokens，4096 context 的小模型裝不下（少登記或說明再瘦）。
2. `self_tools` 的 `ls` 一次吐約 12 KB（每支附整份說明），要不要預設只列名字加一句說明。
3. hook「改結果」預設要不要開（現在每個 hook 要自己設 `change`）。
4. 人的預設 stack 是不是 `~/.stack`（信箱用，現可用 `$AOS_MY_STACK` 換）。
5. `agent_def new` 會把範本的 `tests/` 一起抄（agent-fsm 200 KB 中 tests 佔 76 KB），要不要略過。
6. cli-sweep Q1 確認句。
7. `aos-clock register` 寫法與「aos-yyy-zzz 等於 aos-yyy zzz」通則衝突（aos-clock 後面直接接時鐘檔）。
8. 條文 C-42 續、C-52 例外 ⑧ 沒跟上舊 `agents` 拿掉。

另列代定：self_history 的摘要那則訊息身分預設是 user。

## 使用者原話（逐字）

「我回來了。1.小模型裝不下說明，那就是去把lm studio那邊調整一下。真的裝不下的，那就代表這個小模型不適合aos體系，或是只能作爲普通的aos函數。2.好，有需要的再自己去看細項。3.幫我改成預設是開，選項名稱這塊，可以參考c#或java的hook那樣。4.改$AOS_LINUX_USER_STACK。5.啊？範本不該有tests。有的話就跟着抄。6.細說。7.不衝突，要用的人要自己分辨，這很容易分辨的。程式實作上也就自然而然。8.改。self_history的摘要這塊，身份可以是user，只是內容這塊希望能符合特定格式，比如我們現有的error那樣，就aos:...。」

後來兩次補答：

- hook 選項名（看過 A／B 對照表後）：「hook這塊，主要走A, 但filter改condition。」
- memory_write（三句依序）：「等等，等等，我還在思考memory_write。我先說說問題：爲何我不能{op:add, path:notes/bob.md, description:introduce about bob}?，我希望可以。然後memory write先這樣就好。」→「bob.md還不在，默認不建空檔，除非加上flag」→（問檔不在又沒帶旗標怎麼辦）「報錯」

## 決定與結論

| 題 | 結論 | commit |
|---|---|---|
| 1 | 不改程式。口徑：說明裝不下＝先去 LM Studio 把 context 調大；真的裝不下，那個模型就不適合當 aos agent，只能當普通 aos 函數用 | — |
| 2 | `aos-tools ls -b/--brief`：一行一支「名 TAB 說明第一句」；`self_tools {"op":"ls"}` 預設走它，`long` 照舊、細項用 `get`。範本 15 支實量 38 143 → 1 311 字元 | `ff640132f` |
| 3 | hook 改結果預設開；不能改的事件或不等的 hook 自然不看回話、不報錯 | `60c4ad792` |
| 3 續 | 選項改名（A＋condition）：on→event、exec→handler、match→condition、change→intercept、wait→async（意思反過來）、on_fail→on_error；事件 before_queue／after_queue／before_tool／after_tool。不留舊名 | `e649ea2cb` |
| 4 | `AOS_MY_STACK` 改名 `AOS_LINUX_USER_STACK`，預設 `~/.stack` 照舊 | `284a401bb` |
| 5 | 範本的 tests 搬出範本，`agent_def new` 照舊整夾抄 | 見下 |
| 6 | 細說交給 cli-sweep 那隊（10d） | — |
| 7 | `aos-clock register …` 等同 `aos-clock-register …`；時鐘檔真叫 register 的寫 `./register` | `b7c8e8e10` |
| 8 | self_history 摘要：角色照舊預設 user，內容固定 `aos: summary (lines A-B, N messages): 摘要`（`set` 不套） | 見下 |
| 8 | 條文 C-42 續、C-52 ⑧ 跟上 agents 拆分 | 見下 |
| memory_write | add 不給 value：檔在＝只補指示牌；檔不在＝NodeMissing；帶 `"create": true`＝建空檔再補。代定 D19～D22 在 [json-memory/05](../json-memory/05-步驟與代定.md) | `060605627` |

**代定**（隊長定的，可翻案）：

- 題 2：旗標叫 `-b/--brief`；第一句切在「句點＋空白＋大寫字母」，所以 `e.g.` 不會被切；沒說明印 `-`；`-b` 跟 `-l`／`--json` 擇一。
- 題 3：明寫 change:true 又不等的 hook 不報錯（改名後就是 intercept:true＋async:true）。
- 題 8：摘要的固定形狀 `aos: summary (lines A-B, N messages): TEXT`，比照錯誤行「名字: 種類: 內容」那種一眼分得出是系統寫的；只有一則時寫 `(lines 3-3, 1 message)`。

實際長相（試驗場跑 `aos-agent history -t ann summarize 2-4 "…"` 後 `ls`）：

```
2	user	aos: summary (lines 2-4, 3 messages): User asked the time again; it was 13:32Z.
```

## 第二批（11-10 深夜，頂層用選項框問）

使用者的答（選項＝選了哪一個；自填的逐字）：

1. 時鐘登記殘留（agent 走了、它登記的格寄不到每次 warning；選項：不清自行承擔／清道夫順手清／ctl rm 時一起清）——自填：「時鐘本身會每隔一定的cycle檢查自身。」
2. `aos-clock-register` 要不要也收 `-d D`（daemon 的 stack，當成 `D/clock`）——選「加 -d」。
3. `agents_children`／`agents_ctl` 的 `ls` 一列約 400 字元——選「改短版（推薦）」。
4. eca 第一次在新資料夾開畫面，claude 停在「信不信任這個資料夾」選單、aos 把題目打進去就把畫面關了——選「aos 偵測後報錯」。
5. 維持現況、不用做的四題：say／summarize／mailbox send／clock-register add 的話後不解析旗標；self_tools／self_hook 的 path_json 不加 `$` 以外的短寫法；工具失敗時附給腦的 stderr 尾巴不處理；after_queue hook 讓 agent 停下後那封信晾著不補。

| 題 | 結論 | commit |
|---|---|---|
| 1 | `aos-clock` 每 `check_every`（登記表頂層鍵，預設 100）個 cycle 檢查一次，箱子資料夾已不在的格拿掉、各一行 warning；詳見 [clock-letters 02](../clock-letters/02-自我檢查與-d.md) | `173deaf11` |
| 2 | `aos-clock-register` 收 `-d D`（＝`D/clock`），優先 `-c` > `-d` > `$AOS_CLOCK`，`-c` 和 `-d` 同給報錯；工具 clock_register 多 `daemon`；詳見 [clock-letters 02](../clock-letters/02-自我檢查與-d.md#2--d) | 見 git log |
