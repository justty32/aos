# aos agent 慣例（上）：保證的底、入口與 loop／fsm、題目與答案、stack——一條一兩句

← [proto8](../README.md)｜下半：[慣例（下）](CONVENTION/00-慣例-下.md)｜proto8 原則：[CONCEPTS](CONCEPTS.md)、[NORMS](NORMS.md)

**aos 本身只保證六個環境變數和一支 `aos-exec`（已升成規範 N-57～N-62），其餘全是慣例**：我們自己人寫 agent 時照抄的標準形狀，照抄的人不用想、看別人的 agent 一眼就懂。**標準＝[templates/agent-fsm](../templates/README.md#agent-fsm) 現在的樣子（走 queue），stack 裡面自由。** 這兩份只放條文本體；例子、細節、原話、出處在每組標題連的分檔（前言、依據寫法、實作說明、命名原文在 [00-前言-命名-實作](CONVENTION/00-前言-命名-實作.md)）。條號不重編。

## 保證的底、佈局、命名

**[一、aos 保證的；二、佈局](CONVENTION/01-保證佈局入口/01-一-aos-保證的與二-佈局.md)**（[命名](CONVENTION/00-前言-命名-實作.md)）
- **P-01～P-04** aos 保證的底（六個環境變數、`aos-exec` 命令列、它只做的那幾件事、退 1 的情形）已升成規範：P-01＝N-57、P-02＝N-58、P-03＝N-59、P-04＝N-60；找入口（N-61）、`#/`（N-62）沒有 P 號。條號只留給別處引用。
- **佈局** 一個 agent＝一個資料夾程式：狀態表一律寫在 `fsm.json`，每格是一個資料夾程式或一張單子（P-09），範本的格是單子、叫範本裡的一支程式；stack 裡（直接 aos-exec 時預設 `$AOS_WS/.stack/`，掛 daemon 見 P-18）有 `stage.txt` 記 fsm 停在哪格、`queue/`、`history.jsonl`、`think/`、工具小格 `tools/<登記名>/`；stack 樹就是呼叫樹；fsm 不寫 trace。
- **時鐘** 只放在根 daemon（daemon.json 的 `procs` 一列跑 `aos-clock`，根的 `.env` 設 `AOS_CLOCK`）；子 daemon 範本（[`templates/daemon-sub/`](../templates/daemon-sub/README.md)）預設不帶、聽外層的鐘（有特殊需求的由人手動加），aos-daemon 程式不認時鐘。
- **命名** loop.json 與 fsm 格要跑的東西都叫 `exec`；時間點叫 `<發生了什麼>_at`，計數說「次」；純文字檔帶 `.txt`；指示詞的檔內位置寫在 `#` 右邊；入口預設名 `_entry`，不認得的 key 一律忽略，`_` 開頭沒有特別意思。

## 入口、loop、fsm

**[三、入口、loop、fsm](CONVENTION/01-保證佈局入口/02-三-入口-loop-fsm.md)**
- **P-05** 標準範本的入口 `_entry` 是沒 `+x` 的 JSON 單子，叫 `aos-agent ctl add <這個資料夾>`（cwd＝`AOS_WS`）：`aos-exec` 這個資料夾＝把這隻掛上 daemon、掛好就回來；身體的入口是 `body.json`＝`["aos-loop", "loop.json"]`。JSON 入口不寫 shebang、不設 `+x`；也可以把入口寫成帶 shebang 的可執行檔，不經 daemon、直接 `exec aos-loop loop.json`。
- **P-06** `loop.json` 認九個 key：`exec`、`max`（沒寫＝不限）、`interval_ms`、`ctl`／`state`／`state_flux`（三個窗的檔名，沒寫有預設名、`null`＝不開）、`on_start`、`on_stop`、`on_timeout_ms`（前兩格的期限，沒寫＝5000、0＝不限）；其他 key loop 不看、給 aos-exec 用。`exec` 三種寫法：字串＝aos-exec 的目標、陣列＝目標加參數、單子物件＝在自己行程內跑；loop 看每次的結束碼決定下一步。
- **P-07** fsm 一次只跑一格：讀 `$AOS_STACK/stage.txt`（沒有＝`start`）跑那格；格的碼被 `next` 接住（0 或表上明寫的碼）就寫下一個狀態、退 0，沒接住的非 0 不換狀態、以原碼退。標準＝`aos-fsm fsm.json`，表長 `{"start","states":{名:{"exec","next"}}}`，`exec` 同 P-06 三種，不寫 trace；shell 版 fsm 用同一個 `stage.txt`、可互換。
- **P-08** 標準四格 `idle → think → wait → act`（act 執行工具後回 think、交答案後回 idle）；加狀態＝`fsm.json` 加一格，表一定明寫。`idle` 是起點也是終點；叫工具還是交答案由腦決定、act 照做，不另加格；`wait` 是為了非同步收腦的回信。
- **P-09** 每一格是一個資料夾程式或一張單子（字串 `exec` 經 aos-exec 跑，單子物件由 fsm 行程內跑）；fsm 只看格的結束碼，不讀格的 stderr、不管格裡面怎麼做。
- **P-10** 格之間要傳的東西寫成 stack 裡的檔，不走 stdout。

## 題目與答案

**[四、題目與答案](CONVENTION/02-題目stack停錯腦/01-P-11～P-14.md)**
- **P-11** aos agent 的輸入是 queue：`$AOS_STACK/queue/`，有順序的信箱，一封信＝一則 OpenAI message；接進 `history.jsonl` 那刻就把信收掉。回答就是 history 裡的 assistant，回哪封信只看最終回答（沒有 `tool_calls` 的那則）的 `aos.answer_to`，沒有別的回答通道；檔案成品落在工作區。
- **P-12** 一次收一批（queue 裡現有的全部、照順序），答完才收下一批；`cur/` 裡認領了還沒接進 history 的先接，思考中來的信等回 idle 再收（範本的預設）。外部 coding agent 例外：信交給 CLI 就算完成、當場收，中途掛掉不自動重答。
- **P-13** 附檔可以放在信資料夾的其他檔；標準範本只讀 `body`、不讀附檔，要給它檔案就放工作區、在信裡寫路徑。
- **P-14** agent 自己的各格只寫 `$AOS_STACK`；腦經工具動哪些檔由掛了哪些工具決定（範本預設四包全開、不擋工作區外的路徑，想收緊自己從 `tools.json` 拿掉）。queue 要留紀錄的信進 `archive/`、只進不出，清理是人的事。

**[P-42](CONVENTION/02-題目stack停錯腦/02-P-42.md)、[P-43](CONVENTION/02-題目stack停錯腦/03-P-43-本文.md)（[續：aos-agent 介面](CONVENTION/02-題目stack停錯腦/03-P-43續-11-04-aos-agent.md)）、[P-48](CONVENTION/02-題目stack停錯腦/10-P-48.md)**
- **P-42** 對話協議：人或程式對跑著的 agent 說話、看、停，只碰它 stack 裡的三樣——queue、history、ctl／state 窗；agent 本身仍是函數、沒有 ctl。人經 `aos-agent say`／`listen`／`chat`（只限掛在 daemon 上的）；aos-agent 只認定義的 `interfaces.json` 宣告、不驗內容；跑完要不要結束寫在定義裡；外部 coding agent 也只碰這三樣。
- **P-43** 外部 coding agent（eca：claude code、codex 這類）包成一個資料夾程式（範本 `templates/eca-claude`）：`_entry` 直接是 aos-loop，`loop.json` 叫 `aos-eca-turn`，`cli.json` 寫 `kind` 與旗標；跟 agent-fsm 一樣有開三個窗的 `loop.json`、stack 三樣、`tools.json`，入口不同（agent-fsm 是 `ctl add`＋`body.json`）；它是平級的另一隻 agent、內部黑盒，aos 只碰它 stack 的三樣與它的 session 檔。aos-eca-turn 一次替它答一批，交給 CLI 就算完成。
- **P-48** agent 之間的往來走信箱 `<stack>/mailbox/`（aos-post 箱子，跟 queue 分開、不自己進 history）；信是 JSON、STATUS 六種，人用 `aos-mailbox`、腦用 `mailbox_*` 工具，自己決定何時看；範本預設每 1 分鐘看一次信箱、有新信才提醒。a2a 協議先不原生支援，頂多做中轉。

## stack

**[五、stack](CONVENTION/02-題目stack停錯腦/04-五-stack與六-停與錯.md)**（[P-15](CONVENTION/02-題目stack停錯腦/04-五-stack續-P-15.md)）
- **P-15** 執行中的一切只寫 `$AOS_STACK`，定義資料夾不被寫，所以同一個 agent 可以同時被兩個工作區跑；`aos-agent tools`／`llm`／`system` 改的是那一隻 stack 裡的那份（改過的不跟定義變，`reset` 刪掉），改定義是人有意的事。實例只指向定義，我們的工具、範本、試驗場不主動存定義副本。
- **P-16** agent 自己的格共用同一個 `$AOS_STACK`；stack 裡放什麼、叫什麼，agent 自訂。
- **P-17** 叫別的資料夾程式時給它自己的小格 `$AOS_STACK/tools/<登記名>/`（`tools` 是 stack 頂層的保留名），被叫的只看到自己的 stack；經 aos-tools call 的小格等工具真的寫東西才建，叫完不自動收。
- **P-18** 一個工作區同時跑兩個 agent，由呼叫方給不同的 `AOS_STACK`；掛上 daemon 的 stack 預設在 `<daemon 的 stack>/procs/<名字>/`。
