# hooks：外掛掛點

← [通用 tick 核心](../tick.md)｜[tick 子篇入口](README.md)｜格式：[tick 協議](../protocol/tick.md) P-202、P-213｜plan：[m1h-hooks-module](../../../plan/m1h-hooks-module.md)

**狀態：已實作**（`aos-tick` 內建，`lib/aos_tick_table.py` 讀、`lib/aos_tick_hooks.py` 跑，[src/py](../../../src/py/README.md#hooks外掛掛點m1h)）。

## B-635：hooks：一格裡各個時機跑的一串

〔使用者裁定 2026-10-01〕「那就做外掛掛點」。設定放在任務表的**頂層鍵 `hooks`**，跟 `tasks` 同層。使用者起初說「這個hooks就是模組」、要放 `modules.hooks`，同日改成頂層鍵：「所以目前唯一的模組就是hooks...就不讓他當模組了，直接讓他變頂層key」。所以 hooks **不是模組**；`modules` 照舊照收不理（[B-620](../tick.md)「頂層 `modules`」），寫在 `modules.hooks` 底下的東西不會跑。

沒寫 `hooks`、或 `hooks` 裡一個掛點都沒寫：`aos-tick` 的行為跟原本完全一樣。

### 掛點

〔使用者 2026-10-01 第十七批〕使用者原話：「那確實是需要AOS_TASK_EXIT」「"hooks":{"after_task":{"a":..., "b":...}}，然後是after_every_task。」「都照你說的」。目前開四個：

| 掛點 | 寫法 | 什麼時候跑 |
|---|---|---|
| `before_all` | inst 陣列 | 開格（換好紀錄）之後、第一項任務（含 tasks-blocked 的檢查）之前，跑一次 |
| `after_task` | 物件：鍵＝任務 id（沒寫 id 的任務 id 是位置字串，所以位置也能當鍵），值＝inst 陣列（只有一個也寫陣列） | **那一項**任務跑完之後。寫了不存在的 id＝永遠不跑，tick 不報錯 |
| `after_every_task` | inst 陣列 | **每一項**任務跑完之後；同一項也有 `after_task` 時，先 `after_task.<id>`、再 `after_every_task` |
| `after_all` | inst 陣列 | 照表跑完之後——含被 tasks-blocked 擋下、沒跑完整張表的那格 |

- 擋板檔、鎖被佔（`busy`）、任務表壞（整格沒開）時，四個都不跑。
- **被 tasks-blocked 擋下、沒跑的任務不觸發** `after_task`、`after_every_task`（[B-620](../tick.md)「tasks-blocked 與擋板檔」）；hooks 自己不看 tasks-blocked（hook 寫了也不擋下一個 hook，只擋下一項任務）。
- `hooks` 裡不認得的鍵（例如 `before_task`）照收不理、不解、不跑。
- 使用者原話裡的 `after_cell` 就是 `after_all`：「after_cell？我以為是after_all，我們有cell嗎？」

### 寫法：比照 `tasks`

```json
{
  "envs": {"LANG": "C.UTF-8"},
  "tasks": [{"id": "build", "argv": ["make"]}],
  "hooks": {
    "after_all": [
      {"id": "notify", "argv": ["./notify.sh"]},
      {"argv": ["sh", "-c", "date >> logs/ticks.log"]}
    ]
  }
}
```

- 每個掛點的值是**陣列**（「可以一串」；`after_task` 是每個任務 id 一個陣列），每個元素是一個 inst 物件，跟 `tasks` 的每一項一樣：
  - 可以寫 `id`；沒寫時 id＝它在自己那個陣列的位置轉字串，從 `"0"` 起。跟 `tasks` 的 id 各算各的，撞了不管。
  - **吃 tasks.json 頂層預設**：淺層合併，項自己寫了某個鍵就整個蓋過（`envs` 也整包換），跟 `tasks` 一樣。
  - 跑到時照 inst 規則展開、執行：同樣的 cwd 規則（合併後沒有 cwd 時是工作資料夾；頂層 `cwd` 是預設）、同樣的串流預設、`exec_failed`（125／126／127）。
- **環境變數**〔使用者裁定 2026-10-01 第十批〕：`AOS_TICK_CWD` 跟任務一樣；另外給 hook 自己的三個，**取代** `AOS_TASK_ID`／`AOS_TASK_INDEX`：

  | 變數 | 值 |
  |---|---|
  | `AOS_HOOK_POINT` | 掛點名：`before_all`、`after_task`、`after_every_task`、`after_all`（使用者暫名 `AOS_HOOK_TYPE`；值就是掛點名，所以叫 POINT，跟「掛點」一致） |
  | `AOS_HOOK_INDEX` | 這個 hook 在它自己那個陣列裡的位置，十進位，從 0 起（`after_task` 每個任務 id 各自從 0 數；跟 `tasks` 各算各的） |
  | `AOS_HOOK_ID` | 這個 hook 的 id；沒寫時是位置字串；不是字串時轉成字串 |

  - **跟任務有關的兩個掛點**（`after_task`、`after_every_task`）〔使用者 2026-10-01 第十七批〕另給剛跑完那一項的 `AOS_TASK_ID`、`AOS_TASK_INDEX`、**`AOS_TASK_EXIT`**（它的結束碼；被訊號 N 殺＝128+N）。`AOS_TASK_EXIT` 只有這兩個掛點有：一般任務、`before_all`、`after_all` 都不給。
  - `before_all`、`after_all` 不屬於任何任務，所以 hook **拿不到** `AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`；tick 自己的環境裡剛好有（例如這個 tick 本身是別的 tick 的任務）也先拿掉，不會漏給 hook。反過來，一般任務拿不到 `AOS_HOOK_*`（繼承來的同樣拿掉）。`envs` 清空時一個都不放、inst 的 `envs` 最後疊上去，跟任務一樣。
  - 跑每一項（任務或 hook）前，`AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`、`AOS_HOOK_*` 一律先從繼承的環境拿掉，再放這一項該有的（第十批那條規則，第十七批多一個 `AOS_TASK_EXIT`）。
  - 之後若開 `before_task` 這類「某項之前」的掛點：在那一項之前被 tasks-blocked 擋下時，那一項相關的 hook 都不跑〔第十六批〕；沒開、沒實作。
- **指示詞展開時機比照 `tasks`**（[B-620](../tick.md)「指示詞什麼時候展開」）：讀表時 `hooks` 本身、每個掛點（`after_task` 再多一層：每個任務 id 的陣列）、每一元素各解一層（所以 `hooks`、整串、整項都可以 `$ref`；這一步 `$ref:""`／`#…` 指整份 tasks.json、相對檔名以工作資料夾為起點）；`hooks` 裡其他鍵不解。值的內部（`argv` 元素的 `$fmt`、`envs` 裡的 `$env`…）跑到那一項、合併頂層預設後才照 inst 規則展開，這時 `$ref:""`／`#…` 指合併後的這一項。不用 `modules` 那種整個展開。

### 極簡檢查（開格前）

跟 `tasks` 一起在讀表時查（[B-620](../tick.md)「讀表：極簡檢查」），不過就是 `bad_table`、回 1、不開格（不換紀錄、不加 `seq`、一項都不跑）：

- `hooks` 是物件；
- `before_all`、`after_every_task`、`after_all`（有寫時）是陣列；`after_task`（有寫時）是物件、每個值是陣列；
- 每一項是物件；
- 每一項合併頂層預設後有 `argv`；
- 上面各層讀表時那一層指示詞解得開。

其他一概不查，跟 `tasks` 一樣。

### 什麼時候跑、不跑

| 這格怎麼了 | `after_all` |
|---|---|
| 照表跑完 | 跑 |
| 被 tasks-blocked 擋下 | **照跑**——它跟任務無關〔使用者 2026-10-01 第十六批〕，這也是它存在的理由 |
| 拿不到鎖（`busy`） | 不跑 |
| 有擋板檔 | 不跑（tick 直接結束、stderr 不印〔使用者 2026-10-01 第十六批〕） |
| tick 自己出錯（`bad_table`、用法錯、中途自然丟錯…） | 不跑 |

- 跑的時機：本格紀錄已收尾（`ended:true`、`exit:0`，被擋下的還有 `blocked_before`）之後。所以 hook 讀本格紀錄（`current/`，展開 `$ref` 後）看得到整格的結果（`ran` 與失敗清單 `tasks`），也看得到前面 hook 裡結束碼不是 0 的（0 不記，第八批）。
- **不看 tasks-blocked**：hook 之間不查它，hook 自己寫了也不擋下一個 hook；after_all 跑完後核心刪掉它（整格最後，[B-620](../tick.md)）。
- **每項結束碼不是 0 的照實記（0 不記）、接著跑下一項**，跟任務一樣；**不影響 tick 的結束碼**（照舊回 0，[C-08](../conventions.md)）。
- 某個 hook 跑到時展開失敗（合併後的 inst 不合規則）：跟任務一樣自然丟錯、tick 回 1；紀錄停在已寫的樣子（`ended:true`、`exit:0`，`hooks.after_all` 只到前一項）。這時 tick 回 1 而紀錄寫著 `exit:0`，兩邊對不上——**使用者 2026-10-01：先不管**（照 POC 默認一切正常，不另處理）。

### 紀錄

記在本格紀錄（[B-633](../tick.md)、[P-213](../protocol/tick.md)），跟 `tasks` 分開，實際存在 `tick/current/hook-exits.json`，`record.json` 用 `"hooks":{"$ref":"hook-exits.json"}` 指過去。下面是展開後的樣子：

```json
{"version":1,"seq":7,"started_at_ms":1790000000000,
 "ran":2,"tasks":[{"id":"build","index":0,"exit":2}],
 "hooks":{"before_all":[],
          "after_task":[{"id":"notify","index":0,"task_index":0,"exit":1}],
          "after_every_task":[{"id":"log","index":0,"task_index":1,"signal":9}],
          "after_all":[]},
 "ended":true,"exit":0}
```

- 任務表寫了哪幾個掛點，`hooks` 就有哪幾個鍵（照 `before_all`、`after_task`、`after_every_task`、`after_all` 的順序）；一個都沒寫就沒有 `hooks`、也沒有 `hook-exits.json`。〔第十七批〕hooks 在格中也會跑，所以**開格就**寫好各掛點的 `[]`、`record.json` 開格就帶 `hooks` 的 `$ref`（原本是收尾才建）。
- **結束碼 0 的不記**〔第八批：「hooks也是」〕；不是 0 的每跑完一個加一筆（整份重寫 `hook-exits.json`）。每筆跟 `tasks` 一樣有 `id`、`index`（它在自己那個陣列的位置；`after_task` 每個任務 id 各自從 0 數）、`exit` 或 `signal`；`after_task`、`after_every_task` 另帶 **`task_index`**＝觸發它的那一項任務的位置〔第十七批，AI 隊定〕。`after_task` 各任務 id 的筆混在同一個陣列，照跑的順序。
- hooks 不記 `ran`、不影響 tick 的結束碼。tick 跑到一半被殺時看不出 hook 跑到第幾個，照 POC 默認一切正常不管。
- 換紀錄時整個 `current/` 改名成 `last/`，`hook-exits.json` 跟著過去。

### 範例：用 hook 加普通 git 指令管版本

`aos-git` 第十七批搬暫緩區（[暫緩區 git](../deferred/git.md)），原本它做的事用 hooks 加普通 git 指令就做得到。下面只是**範例說明**，aos 不提供這些腳本、不保證它們跟哪個模組配得起來：

```json
{"tasks": [{"id": "fetch", "argv": ["./fetch.sh"]}, {"id": "report", "argv": ["./report.sh"]}],
 "hooks": {
   "before_all": [{"id": "recover", "argv": ["sh", "-c",
     "python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get(\"ended\", True) else 1)' .aos/tick/last/record.json || git checkout -- . && git clean -fdq -e .aos"]}],
   "after_every_task": [{"id": "commit", "argv": ["sh", "-c",
     "if [ \"$AOS_TASK_EXIT\" = 0 ]; then git add -A && git commit -qm \"tick: $AOS_TASK_ID\" || true; else git checkout -- . && git clean -fdq -e .aos; fi"]}]}}
```

- `before_all` 看上一格紀錄：`ended:false`（上一格跑到一半被殺）就把工作樹還原到上次 commit。
- `after_every_task` 看 `AOS_TASK_EXIT`：成功就 commit 這一項的改動，失敗就還原這一項寫到一半的東西。只想管某幾項就改用 `after_task`。
- `.aos/`（紀錄、鎖、tasks-blocked）要排除在版本外，自己寫進 `.gitignore`。

依據：使用者 2026-10-01 第十七批（`before_all`、`after_task`、`after_every_task`、`AOS_TASK_EXIT`：「那確實是需要AOS_TASK_EXIT」「"hooks":{"after_task":{"a":..., "b":...}}，然後是after_every_task。」「都照你說的，排給agent做。git這塊先不要進範本。」）；使用者 2026-10-01 第十批（hook 的環境變數：「hook這塊，幫我添加AOS_HOOK_TYPE, AOS_HOOK_INDEX, AOS_HOOK_ID……AOS_HOOK_INDEX, _ID會替代TASK_ID, INDEX。但對於hook到特定任務的前後的，還是會有AOS_TASK_INDEX, AOS_TASK_ID，只是這時候他就是指向那個被hook的任務。」，[verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十批hook-的環境變數)）；使用者 2026-10-01 第九批（紀錄拆檔，`hook-exits.json`）；使用者 2026-10-01 第六批裁定（[verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第六批tick-的-hooks外掛掛點)）：「那就做外掛掛點，這個hooks就是模組」「after_cell？我以為是after_all，我們有cell嗎？ 2.可以一串。 3.吃，hooks中的掛點所提供的，比如"after_cell":[{},{},...]，就比照tasks。4.會記錄。 剩下都建議」；同日改成頂層鍵：「所以目前唯一的模組就是hooks...就不讓他當模組了，直接讓他變頂層key」。

**驗收：**〔第十七批〕`before_all` 在第一項（與 tasks-blocked 的檢查）之前跑、擋板／busy／表壞時不跑；`after_task.<id>` 只在那一項跑完後跑、先於 `after_every_task`，不存在的 id 不跑也不報錯；兩者拿到剛跑完那一項的 `AOS_TASK_ID`／`INDEX`／`EXIT`（被 SIGKILL 是 137），被 tasks-blocked 擋下的項不觸發；`AOS_TASK_EXIT` 只有這兩個掛點有（外層帶進來的也拿掉）；不是 0 的記進紀錄、帶 `task_index`。沒寫 `hooks`（或 `hooks` 裡一個掛點都沒寫）時紀錄沒有 `hooks`、行為照舊；寫在 `modules.hooks` 底下的不跑。`after_all` 三項依序在任務之後跑，沒寫 id 的用位置字串；頂層 `argv`、`envs` 當預設，項自己寫的 `envs` 整包蓋過。`hooks`、`after_all`、某項各自 `$ref` 到別的檔照跑；項裡 `argv` 元素的 `#/k` 指合併後的這一項。hook 拿到的 `AOS_TICK_CWD` 是工作資料夾、`AOS_HOOK_POINT` 是 `after_all`、`AOS_HOOK_INDEX`／`AOS_HOOK_ID` 是自己的（沒寫 id 時是位置字串），沒有 `AOS_TASK_ID`／`AOS_TASK_INDEX`（外層環境帶進來的也沒有）；任務拿不到 `AOS_HOOK_*`。任務寫了 tasks-blocked：後面的任務不跑、`after_all` 照跑，hook 再寫也不擋下一個 hook。hook 回 3、被 SIGKILL、找不到程式（127，stderr `exec_failed: after_all/<id>:`）都照記（帶 `index`）、回 0 的不記、下一個照跑、tick 回 0。擋板、busy、表壞時一個 hook 都不跑。`after_all` 不是陣列、某項不是物件、合併後沒 `argv`、`hooks` 不是物件、讀表那一層 `$ref` 解不開：`bad_table`、回 1、紀錄與 `seq` 不動。紀錄的 `hooks.after_all` 下一格進 `last/`（`hook-exits.json`）。測試：`src/py/tests/test_tick_hooks.py`。
