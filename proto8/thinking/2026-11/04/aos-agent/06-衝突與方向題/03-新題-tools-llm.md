← [回入口 06-衝突與方向題.md](../06-衝突與方向題.md)｜段落：11-04 晚追加 `aos-agent tools`／`llm` 後的新題（衝突 1 條、方向題 1 題；使用者原文逐字在入口）｜上一份：[02-新題-11-04-晚](02-新題-11-04-晚.md)｜下一份：—

### 衝突 3：`tools add`／`llm set` 改定義資料夾，對上 P-15

- **哪條**：P-15「執行中的一切只寫 `$AOS_STACK`，**定義資料夾不被寫**；所以同一個 agent 可以同時被兩個工作區跑」；C-50「資料夾布局和 json 那塊仍要保持單純」。
- **衝突在哪**：`aos-agent tools --target bob add clock …`、`aos-agent llm --target bob set model=qwen` 改的是 bob 的定義資料夾裡的 `tools.json`、`.env`／`cli.json`——定義被寫了。P-15 的理由正好被打到：兩隻 agent 共用同一份定義（`add --name ann …/bob`、`add --name bob …/bob`）時，改一隻等於改兩隻。
- **(a) 算人改定義、P-15 加註（fable 選的）**：P-15 管的是 agent **自己跑的時候**不寫定義；aos-agent 是人的指令，跟人開編輯器改 `tools.json` 是同一件事。共用定義的多隻一起變是**刻意的**（11-03 你說「不應該有定義(template)這東西」——add 的 XXX 就是那隻 agent，要不一樣就複製一份），aos-agent 用 daemon 表的 `exec` 欄找出同定義的其他名字、stderr 提醒一行。代價：P-15 加一句註；共用定義的人要看那行提醒。
- **(b) 改 stack 裡的副本**：`llm set` 寫 `<stack>/.env`、`tools add` 寫 `<stack>/tools.json`，每隻各自一份。代價：兩種身體都要學「stack 有就用 stack 的」（fsm 三格、cli_session 都要改）、多一條找設定的規則（C-56 不藏暗路）、stack 裡多了不是執行狀態的東西（C-65）。
- **例子**：bob、ann 都從 `…/agents/bob` add。(a) `aos-agent llm --target bob set model=qwen` 之後兩隻下一題都換模型，stderr：「注意 ann 也用這份定義」；(b) 只有 bob 換。
- **建議 (a)**。

### 方向題 3：`llm` 走入口（各自一支小程式）還是統一 `.env`？

- **背景**：工具箱兩邊已經是同一種登記檔，宣告檔在哪就好。腦不是：eca 的模型寫在 `cli.json` 的 `--model` 旗標、種類是 CLI（claude／codex）；agent-fsm 的寫在 `.env` 的 `AOS_BRAIN_URL`／`MODEL`／`KEY`（P-23）。原則推不出要哪一種統一法。
- **(a) 入口（fable 選的）**：像 `screen`，宣告一個入口，`show`／`set 鍵=值` 的 argv 契約統一，裡面各自實作（eca 改 `cli.json`、fsm 改 `.env`）。好處：aos-agent 不懂任何一邊的格式；兩邊都是改了下一題就生效；以後第三種腦（kernel）照樣接。代價：每個範本多一支十幾行的小程式（eca 進 bin、fsm 放範本裡）。
- **(b) 統一 `.env` 的 `AOS_BRAIN_*`**：宣告 `"llm": ".env"`，aos-agent 自己讀寫 dotenv 那三個鍵，不用小程式。代價：eca 要學會吃 `AOS_BRAIN_MODEL`（cli_session 加旗標）、`URL`／`KEY` 對 eca 沒意義；eca 的 `loop.json` exec 是內嵌單子、aos-loop 不重讀 `.env`，改了要 `stop`／`start` 才生效；`.env` 不蓋外面已設的（N-59），daemon 環境有設時改了沒用。
- **例子**：`aos-agent llm --target e1 show`——(a) 印 `kind=claude`、`model=sonnet`；(b) 印 `AOS_BRAIN_MODEL=sonnet`，`url`／`key` 空著。
- **建議 (a)**。
