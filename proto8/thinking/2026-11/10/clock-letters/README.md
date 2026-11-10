# clock-letters：時鐘每隔 N 個 cycle 寄一封信（11-10 晚）

← [2026-11-10](../README.md)｜施工結果 [01](01-施工結果.md)

## 使用者原話（逐字）

1. 「對了，hook那塊，假如我想實現clock每隔10個cycle就觸發，我可以怎麼做」
2. （頂層答：hook 圖紙沒有時鐘事件；A 在 agent 收信格加 clock 事件／B daemon 表掛定時列／C 用 A 寄信給自己）「感覺這個hook應該放在clock那邊www。clock那邊看看能不能加上一個hook，有需要的人可以去註冊」
3. （頂層講做法：時鐘檔旁放登記表，每格「每幾個 cycle」＋「跑哪個 aos 函數」，aos-clock 寫完新數字後數字除得盡的就跑、天然對齊整數倍；並問五題：1 等不等跑完；2 誰能登記；3 登記入口與命名；4 登記的人走了怎麼辦；5 agent 那邊的 clock 事件還做不做）「時鐘這塊幫我改成寄信好了，不要用跑任意aos函數。」
4. 「指令是aos-clock-register嗎？」

其餘題使用者沒回，照通則不追問，由頂層代定（下面「代定」，可翻案）。

## 決定

- 時鐘不跑任意 aos 函數，改成**寄信**（原話 3）：時鐘檔旁一張登記表，每格「每幾個 cycle、寄到哪個 aos-post 箱子、寄什麼字」；`aos-clock` 寫好新數字後，除得盡的格各寄一封。
- 人用指令叫 **`aos-clock-register`**（原話 4），獨立一支、動作 add／rm／ls；`aos-clock FILE` 本體照舊。

## 代定（可翻案）

1. **等不等**（原 1 題）：寄信本來就不等收信的人；每封最多等 aos-post 5 秒。
2. **誰能登記**（原 2 題）：寫得到登記表就能 add／rm，不另外擋（今晚口徑「有權限就能做」）。
3. **登記的人走了**（原 4 題）：不自動清；寄不到＝時鐘每到那格印一行 warning（自行承擔）；`ls` 看得到、誰都能 `rm`。
4. **agent 那邊不加 clock 事件**（原 5 題）：要定時叫醒 agent＝登記往它的 `queue/` 寄。hook 線的檔不動。
5. **登記表**＝時鐘檔同資料夾的 `<時鐘檔名>_register.json`（根的鐘＝`<根 stack>/clock_register.json`）；格 `{every, box, text, by}`，名字當 key。
6. **box 寫法**：相對路徑從登記表所在資料夾算；可手寫指示詞物件（`$env`…，aos-directive 解），同 tools／hooks。`add --box` 相對 cwd，存表時同頂層資料夾存相對、否則絕對（同 aos-post `reply_to`）。
7. **對齊整數倍**：`新數字 % every == 0`，不從登記那刻起算。
8. **信的形狀一份兩邊收**：body＝`{"role": "user", "content": "TEXT (clock cycle N)", "from": "clock", "status": "PROGRESS", "title": "clock cycle N: NAME", "what": "TEXT", "cycle": N, "register": "NAME"}`——queue（fsm idle、aos-eca-turn）只看 role＋content；aos-mailbox 讀 from／status／title／what。不分兩種格式、不加選項。
9. **時鐘不被拖垮**：寄不到、表壞、某格壞＝`aos-clock: warning:` 一行（壞格跳過），時鐘照樣退 0；沒有登記表＝跟以前完全一樣。
10. **工具名 `clock_register`**（跟指令名）：op add／rm／ls；`box` 不給＝叫我的那隻自己的 queue；`by` 填 agent 名字。agent-fsm、eca-claude 範本預設登記（比照 self_tools）。
11. 同時兩個人改表不管（後寫的整份蓋過）；`rm` 沒那格＝`EntryMissing`、同名 add＝`EntryExists`（`--replace` 換）；`add` 時箱子還不是信箱＝warning 照加。
12. 登記表跟時鐘一起帶走（two-machines 分類 G094 carry；暫存 G095 temp）。

## 結論

- 已施工、三種腦都驗過，見 [01](01-施工結果.md)。用法在 [cmd/aos-clock-register](../../../../cmd/aos-clock-register/README.md)。
- **（11-10 深夜已解，使用者「7.不衝突，要用的人要自己分辨，這很容易分辨的。程式實作上也就自然而然。」：`aos-clock register …`＝`aos-clock-register …`，時鐘檔叫 register 的寫 `./register`，[tonight-rulings](../tonight-rulings/README.md) 題 7）** 當時記的衝突：他的通則「`aos-yyy-zzz` 和 `aos-yyy zzz` 相等」在這裡不成立——`aos-clock register …` 會被 `aos-clock` 當成時鐘檔名 `register`（`aos-clock FILE` 沒有子命令）。這次沒做等價轉發；要做的話得讓 `aos-clock` 認子命令，跟「唯一位置參數就是 FILE」打架。
