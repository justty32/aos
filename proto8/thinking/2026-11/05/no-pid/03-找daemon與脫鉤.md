← [入口](README.md)｜涵蓋：找 daemon 只靠環境變數的規則、環境變數脫鉤時的失敗樣子、`--env-file`／`--envs` 跟脫鉤的關係、要寫進 conventions／lib 規則的工具設計原則｜上一份 [02-轉接設計](02-轉接設計.md)｜下一份 [04-沙箱](04-沙箱.md)

# 找 daemon 與環境變數脫鉤

## 1. 找 daemon 的規則（把散在 N-63 各處的收成一條；程式只准照這條）

使用者 11-05：「至於如何找到daemon，大多時候是透過環境變數。」補充 3：「只靠環境變數找DAEMON，只是因爲這最方便，誰也限制不了你透過其他方式傳遞daemon位置。」

1. **預設這條路**：`--daemon D`（旗標、明給）＞ `$AOS_DAEMON` ＞ cwd 的 `./.stack`（11-05 portable-flow 題 3 使用者選的例外；不往上層找）。都沒有＝`DaemonMissing`。別的傳法（寫在設定檔、信裡帶路徑、argv）**都可以**——限制的不是「怎麼拿到位置」，是下面第 3 點「不准用 Linux 行程資訊去猜位置」。
2. **值＝那台 daemon 的 stack**（「daemon 的 stack 就是它本身」）。拿到後驗三件：是資料夾；有 `procs_ctl_mailbox/`（名字從 `procs_state.json` 頂層 `procs_ctl_mailbox` 欄來，表還沒寫＝預設名）；路徑轉 `realpath`（捷徑一律解開，D3 的 abspath／realpath 不一致到此收掉）。不過＝`DaemonMissing`，原因字樣說缺哪一件。
3. **不准的找法**（盤點裡全部要刪）：掃 `/proc` 的 argv／environ 反查；讀任何 pid 檔或 state 窗裡的 pid；從 stack 路徑往上爬找 `.stack`；`ps`、`pgrep`。
4. **誰設**：daemon 起子項時設給子（已做）；人殼自己 export 或 `--daemon`；定義裡要指別台就寫 `.env`（aos-exec 讀；portable-flow 原則③「環境變數盡量少」——只在真的要指別台時寫）。
5. **掛 proc 往哪寄跟問活著往哪寄是同一個地方**：`$AOS_KERNEL` 有設就寄那裡（判官轉寄 ping），沒設寄 `$AOS_DAEMON` 的 ctl 信箱（N-63 實例 `AOS_KERNEL`）。讀表永遠讀 `$AOS_DAEMON` 的（判官不代讀）。

## 2. 環境變數脫鉤時長什麼樣（使用者：「工具在設計之初，最好是要考慮到環境變數可能會脫鉤這件事」）

使用者補充 3：「理想狀態是完全脫鉤，但作爲aos體系下的工具，他仍是aos函數，只要是aos函數，我們都默認他能吃aos-exec所提供的那幾個環境變數。」所以**aos-exec 的六個（`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO`、`AOS_ENTRY`）當作一定在**——工具經 aos-exec 跑才算 aos 函數；會脫鉤的是 **hub 型**（`AOS_DAEMON`、`AOS_MEMORY`、`AOS_LLM_KERNEL`、`AOS_KERNEL`）和人殼 export 的東西。

「脫鉤」＝工具跑起來的環境沒有它以為會有的 hub 型 `AOS_*`。什麼時候會：**借給別人**（父 agent 把工具借給 thought 的子，子的環境是 daemon 給的那一套、沒有父殼裡 export 的）、**進沙箱**（aos-sandbox `--clearenv` 只帶白名單）、**搬家**（`.env` 寫了舊路徑、或人在新機器沒 export）、**人直接在殼裡跑工具試**。

| 脫鉤的變數 | 現在 | 應該 |
|---|---|---|
| `AOS_DAEMON` 沒了 | ctl／aos-agent 退回 `./.stack`；沒有就 `DaemonMissing` | 照舊；錯誤行說「set AOS_DAEMON or pass --daemon」 |
| `AOS_DAEMON` 指到一個沒 daemon 在跑的 stack（搬家後舊路徑、複製出來的副本） | 表還在、寫著 `running`；信寄進去沒人收；aos-agent 硬錯、ctl 只 warning | `state.json` 的 `polled_at` 舊 → 工具報 `DaemonMissing no sign of life from the daemon at D since <時間>`；人殼印 note、信照寄（開門照套）；寄了信等回信的，逾時＝呼叫失敗 |
| `AOS_DAEMON` 指到沙箱裡看不到的路徑 | `daemon folder not found` | 同 `DaemonMissing`，字樣提示「inside a sandbox? bind the daemon stack」 |
| `AOS_KERNEL` 沒了（本來走判官） | 直接寄 daemon（例外：不報 Missing） | 照舊——這是刻意的（daemon 是最基礎 kernel）；但模式 2 的 ctl 信箱被 Linux 權限鎖住時會 `MailboxBad`，字樣提示「this daemon takes letters through its kernel; set AOS_KERNEL」 |
| `AOS_MEMORY`、`AOS_LLM_KERNEL` 等其他 hub 沒了 | `<名字>Missing`（N-63 ②） | 照舊；**要能在登記時補回來**（下 § 3） |
| `AOS_STACK` 沒了（工具直接在殼裡跑） | `StackMissing`（11-04 定只有 aos-exec 給預設） | 照舊；回信信箱退到 `$AOS_DAEMON/procs_ctl_mailbox/reply/`（[02 § 3](02-轉接設計.md)） |

共同原則：**沒設就當場報 `<名字>Missing`、不猜、不掃**（N-63 ② 本來就這樣寫；pid／`/proc` 那些掃法就是在「猜」）。脫鉤不是錯誤處理的例外，是工具設計時第一個要想到的狀態。

## 3. `--env-file FILE` 與 `--envs K=V`（可重複）跟脫鉤的關係

使用者 11-05 晚補充 2：「在一些需求不大的場景，稍微覆蓋一兩個環境變數也是可以，或者改成--env-file xxx搭配--envs K=V...也不錯，兩者並存吧。」

- **這兩個旗標就是「脫鉤的解藥」**：工具靠 hub 變數找東西，變數會脫鉤，所以**登記工具的那一格要能把變數補回去**——`aos-tools call` 跑工具時先套 `--env-file`（一份 `.env`，同 aos-exec 讀的格式）、再套 `--envs K=V`（零散覆蓋一兩個），套在工具子行程的環境上；`aos-agent tools add` 收同形的兩個旗標、寫進登記格的 `env`（檔路徑＋鍵值），**值不給腦看**（`tools ls` 給腦的那份只印鍵名；small-thought 第二輪「值是 `$env` 解出來的金鑰就外洩」）。
- **借給子時**：`agents`／`thought` 把工具借給子，連登記格的 `env` 一起抄（這就是 small-thought「登記格 env 借給子會掉」那題的解）；路徑型的值（`AOS_MEMORY` 相對 `$AOS_DAEMON`）照 N-63 的相對規則、不改寫。
- **跟「找 daemon」的關係**：`AOS_DAEMON` **不**走這兩個旗標補——它由 daemon 給子、人殼 export、`--daemon` 明給三條路，已經夠；工具登記格裡寫 `AOS_DAEMON` 會讓同一個工具被借到別台 daemon 下時指錯台（搬家後尤其）。conventions 寫一句：「登記格的 env 補的是工具自己的 hub（`AOS_MEMORY`、`AOS_LLM_KERNEL`…），不補 aos-exec 的六個、不補 `AOS_DAEMON`」。
- 形狀代定（可翻案）：`--env-file` 只收一個（給多個＝後面的蓋前面的，不報錯）；`--envs` 可重複、`K=V` 的 `V` 可空（＝設成空字串，不是刪）；順序永遠 file 先、envs 後；`K` 要合 `AOS_` 命名嗎？**不限**——工具可能要別人家的變數（`OPENAI_API_KEY`），但 C-54 R8 說 aos 自己的要帶前綴。

## 4. 寫進規則的那幾句（給 conventions／lib/docs/01 的草稿；寫法照 user/03、不另開條號）

- **lib 規則新增一條（草稿）**：「工具是 aos 函數，aos-exec 的六個環境變數當作一定在；找 hub 靠 `AOS_<名字>` 或明給的 argv／設定；**不讀 pid、不掃 `/proc`、不送訊號給自己沒 fork 的行程**——牽涉 Linux 行程的事一律經 daemon。沒設＝`<名字>Missing`。要判 daemon 或某個 proc 活著，讀 daemon 寫的檔（ctl 模組 `state()`）；要它做事就寄信等回信，不回＝失敗。工具設計時先列出它依賴的 hub 變數，寫進 `_tooldef.json`（新選填 key `env`：變數名陣列），讓登記的人知道要補哪些。」
- **N-17 改寫一句**（[06 衝突 1](06-衝突與邊緣.md)）：「判活著＝daemon 照 pid＋`started_at_ticks`＋`boot_id` 對 /proc（daemon 本身、adopt、接回）；**其他人讀 daemon 寫的檔**（`state.json`／`procs_state.json` 的 `polled_at`＋`phase`）或寄信等回信，不自己對 /proc。」
- **N-63 補一句**：「`AOS_DAEMON` 是唯一找 daemon 的路（`--daemon` 是它的明給形）；沒設且 cwd 沒 `.stack`＝`DaemonMissing`，程式不用別的方法找。」
