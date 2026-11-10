# proto8 討論紀錄：2026-11-10

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [two-machines](two-machines/README.md) | 規劃＋施工（午後方向大改）：git 或 cp 過去、`aos-exec --stack <stack> <定義>` 一行起根就接著跑，`aos-image` 作廢；路徑相對／絕對／`$env` 都收；/mnt/c 可放；kernel 不在不停；未決：專案外的 stack／定義換相對位置要 rm 再 add、真機驗證（14） |
| [aos-tools-cli](aos-tools-cli/README.md) | 規劃（fable）＋施工（opus，步 1～5 都做了，[08](aos-tools-cli/08-施工結果.md)）：甲級小修、快取搬 stack、`env_file` 只記位置、覆蓋層改 `$override`（照順序疊、後面蓋前面、null 那格不算工具）、`--replace`；lv6 受影響清單在 08 |
| [cli-sweep](cli-sweep/README.md) | 規劃報告（fable，未施工）：其餘指令照 C-85 掃一遍——每支一段白話、裝不下的、跨指令不一致與改法；使用者八題與 Q1 重擬版、三個讀法都答了（Q1＝旗標子命令前後都收、Q7＝`copy-out --template`、Q8＝`aos-agent tools add [--name] 路徑`）；都還沒施工 |
| [templates-cp](templates-cp/README.md) | 已施工（[05](templates-cp/05-施工結果.md)）：範本全改 `$env AOS_HOME` 寫法、拿掉 `tools/` 捷徑、根範本帶 `.env`，copy-out 與 copy_def 刪掉，開新 agent 就 `cp -r`、只 export `AOS_HOME` |
| [prefix-fixes](prefix-fixes/README.md) | 使用者行程有變、要提前用現行 aos：大修問題清單 207 列分桶（直接修 61、A＋B 待裁 2、擱著 30、不用修 114），直接修切五條施工線；不動環境變數、json 格式、資料夾佈局、lib 介面 |
| [json-memory](json-memory/README.md) | 討論紀錄＋圖紙（fable，[02](json-memory/02-格式規則.md)～[05](json-memory/05-步驟與代定.md)）＋已施工（[06](json-memory/06-可玩驗收.md)、[07](json-memory/07-怎麼玩與刷新試驗場.md)）：記憶庫改成資料夾＋`.json` 一棵樹、統一路徑 `檔.json#/JSON Pointer`、`_index.json`／`_index` key 當表、工具 read／ls／find 與 add／set／rm 一次維護內容與指示牌、鎖拿掉、`knowledge/aos` 直接轉；使用者 11-10 翻 D4（簡介改放 `_description.json`／`_description` key）、D6（寫入不限範圍），S5 已施工；add 的 description 維持必給、不自動補 |
| [self-family](self-family/README.md) | self_history 一家：使用者五題答「全給、這一步動不了、預設搬到旁邊、eca 縮水版、先有 `aos-agent history` 再包」；已施工（`aos-agent history`、`self_history`、eca 縮水版），三種腦都驗過 |
| [agents-split](agents-split/README.md) | 已施工：舊 `agents` 拆成 `agents_children`（我生的：記帳、配額、生殺停起、問話、出生後調子的工具／腦／歷史／hook）、`agents_ctl`（`aos-agent ctl` 完整包裝、對象不限）、`agent_def`（複製範本成新定義、檢查）；血統先不做、第三塊交流不動；代定 15 條與留給使用者的在 README |
| [mailbox](mailbox/README.md) | agent 之間（含把自己當一隻 agent 的人）的信箱：aos-post 上的純 inbox 協議、一人一格；使用者六題答「peek 工具自己看、名字＋daemon 或路徑、JSON、硬規則靠說明、先有人用的指令、預設讀完就沒」；設計 [01](mailbox/01-設計.md)：獨立指令 `aos-mailbox`、腦用 `mailbox_peek`／`mailbox_read`／`mailbox_send`；已施工、三種腦都驗過（[02](mailbox/02-施工結果.md)）；人的預設 stack `~/.stack` 未定 |
| [clock-letters](clock-letters/README.md) | 已施工（[01](clock-letters/01-施工結果.md)）：時鐘不跑函數、改寄信（使用者「時鐘這塊幫我改成寄信好了」）：時鐘檔旁 `clock_register.json`，每格 every／box／text，cycle 除得盡就 aos-post 寄一封；人用 `aos-clock-register add／rm／ls`、腦用 `clock_register`（box 不給＝叫醒自己）；寄不到只 warning；代定 12 條；未決：`aos-clock register` 跟 `aos-clock-register` 不等價 |
| [tonight](tonight/README.md) | 總整合（家機晚）：各線收攏、「今晚多了什麼、怎麼玩」一頁、整棵從零實跑（假腦 15 支全過、gemma／haiku 各 7 支）、試驗場刷新照抄（只在複本跑過）；未決：小模型 context 裝不下 15 支說明、`$` 鍵寫不出 |
| [tonight-rulings](tonight-rulings/README.md) | 總整合攤的八題，使用者深夜一次答完：self_tools ls 變短、hook 預設改結果＋選項改名（event／handler／condition／intercept／async／on_error）、`AOS_LINUX_USER_STACK`、範本 tests 搬到 templates/tests、`aos-clock register`、history 摘要 `aos: summary …`、條文跟上 agents 拆分；memory_write add 只補指示牌 |
| [tool-packs](tool-packs/README.md) | 通用工具分四包（看／改／刪／殼，lib/packs），bash→shell、json_edit→json_write、新做 remove，檔案工具拿掉工作區限制；agent-fsm 四包全開、eca 不掛；memory_write 預設登記、memory 改名 memory_read、範本庫指 knowledge/（施工中） |
