# hooks：外掛掛點

← [通用 tick 核心](../tick.md)｜[tick 子篇入口](README.md)｜格式：[tick 協議](../protocol/tick.md) P-202、P-213｜plan：[m1h-hooks-module](../../../plan/m1h-hooks-module.md)

**狀態：已實作**（`aos-tick` 內建，`lib/aos_tick_table.py` 讀、`lib/aos_tick_hooks.py` 跑，[src/py](../../../src/py/README.md#hooks外掛掛點m1h)）。

## B-635：hooks：照表跑完之後跑的一串

〔使用者裁定 2026-10-01〕「那就做外掛掛點」。設定放在任務表的**頂層鍵 `hooks`**，跟 `tasks` 同層。使用者起初說「這個hooks就是模組」、要放 `modules.hooks`，同日改成頂層鍵：「所以目前唯一的模組就是hooks...就不讓他當模組了，直接讓他變頂層key」。所以 hooks **不是模組**；`modules` 照舊照收不理（[B-620](../tick.md)「頂層 `modules`」），寫在 `modules.hooks` 底下的東西不會跑。

沒寫 `hooks`、或 `hooks` 裡沒寫 `after_all`：`aos-tick` 的行為跟原本完全一樣。

### 掛點

- **目前只開一個：`after_all`**。照表跑完之後跑——含被停格檔停下、沒跑完整張表的那格。
- 其他掛點（`before_all`、`before_task`、`after_task`…）先不開；`hooks` 裡不認得的鍵照收不理（寫了也不跑）。
- 使用者原話裡的 `after_cell` 就是 `after_all`：「after_cell？我以為是after_all，我們有cell嗎？」

### `after_all` 的寫法：比照 `tasks`

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

- 值是**陣列**（「可以一串」），每個元素是一個 inst 物件，跟 `tasks` 的每一項一樣：
  - 可以寫 `id`；沒寫時 id＝它在 `after_all` 陣列的位置轉字串，從 `"0"` 起。跟 `tasks` 的 id 各算各的，撞了不管。
  - **吃 tasks.json 頂層預設**：淺層合併，項自己寫了某個鍵就整個蓋過（`envs` 也整包換），跟 `tasks` 一樣。
  - 跑到時照 inst 規則展開、執行：同樣的 cwd 規則（合併後沒有 cwd 時是工作資料夾；頂層 `cwd` 是預設）、同樣的串流預設、`exec_failed`（125／126／127）。
- **環境變數跟任務一樣**：`AOS_TICK_CWD`；`AOS_TASK_ID`、`AOS_TASK_INDEX` 是**這個 hook 項自己**在 `after_all` 裡的 id 與位置（不是 `tasks` 的）。不另開 `AOS_HOOK_*`。
- **指示詞展開時機比照 `tasks`**（[B-620](../tick.md)「指示詞什麼時候展開」）：讀表時 `hooks` 本身、`after_all`、它的每一元素各解一層（所以 `hooks`、整串、整項都可以 `$ref`；這一步 `$ref:""`／`#…` 指整份 tasks.json、相對檔名以工作資料夾為起點）；`hooks` 裡其他鍵不解。值的內部（`argv` 元素的 `$fmt`、`envs` 裡的 `$env`…）跑到那一項、合併頂層預設後才照 inst 規則展開，這時 `$ref:""`／`#…` 指合併後的這一項。不用 `modules` 那種整個展開。

### 極簡檢查（開格前）

跟 `tasks` 一起在讀表時查（[B-620](../tick.md)「讀表：極簡檢查」），不過就是 `bad_table`、回 1、不開格（不換紀錄、不加 `seq`、一項都不跑）：

- `hooks` 是物件；
- `after_all`（有寫時）是陣列；
- 每一項是物件；
- 每一項合併頂層預設後有 `argv`；
- 上面各層讀表時那一層指示詞解得開。

其他一概不查，跟 `tasks` 一樣。

### 什麼時候跑、不跑

| 這格怎麼了 | `after_all` |
|---|---|
| 照表跑完 | 跑 |
| 被停格檔停下 | **照跑**——這是它存在的理由 |
| 拿不到鎖（`busy`） | 不跑 |
| 有擋板檔（`blocked`） | 不跑 |
| tick 自己出錯（`bad_table`、用法錯、中途自然丟錯…） | 不跑 |

- 跑的時機：本格紀錄已收尾（`ended:true`、`exit:0`，被停下的還有 `stopped_after`）之後。所以 hook 讀 `current.json` 看得到整格的結果（`ran` 與失敗清單 `tasks`），也看得到前面 hook 裡結束碼不是 0 的（0 不記，第八批）。
- **不看停格檔**：hook 之間不查停格檔，hook 自己建了停格檔也不擋下一個 hook；留著的停格檔照舊由下一格開頭刪（[B-620](../tick.md)）。
- **每項結束碼不是 0 的照實記（0 不記）、接著跑下一項**，跟任務一樣；**不影響 tick 的結束碼**（照舊回 0，[C-08](../conventions.md)）。
- 某個 hook 跑到時展開失敗（合併後的 inst 不合規則）：跟任務一樣自然丟錯、tick 回 1；紀錄停在已寫的樣子（`ended:true`、`exit:0`，`hooks.after_all` 只到前一項）。這時 tick 回 1 而紀錄寫著 `exit:0`，兩邊對不上——**使用者 2026-10-01：先不管**（照 POC 默認一切正常，不另處理）。

### 紀錄

記在本格紀錄 `current.json`（[B-633](../tick.md)、[P-213](../protocol/tick.md)），跟 `tasks` 分開：

```json
{"version":1,"seq":7,"started_at_ms":1790000000000,
 "ran":2,"tasks":[],
 "ended":true,"exit":0,"stopped_after":"b",
 "hooks":{"after_all":[{"id":"1","index":1,"exit":3}]}}
```

（任務 `a`、`b` 都回 0、`b` 建了停格檔；hook `notify` 回 0 不記，第 2 個 hook 沒寫 id、回 3。）

- 有寫 `after_all` 的格，收尾之後先寫 `hooks.after_all: []`，每跑完一個結束碼不是 0 的 hook 加一筆（整份重寫，跟任務一樣）；格式跟 `tasks` 每筆相同（`id`、`index`＝它在 `after_all` 的位置，加 `exit` 或 `signal`）。**結束碼 0 的不記**〔使用者 2026-10-01 第八批：「hooks也是」〕。
- hooks 不記 `ran`：hooks 不看停格檔、一定全跑，先寫好的 `after_all: []` 就表示開始跑了；tick 跑到一半被殺時看不出跑到第幾個，照 POC 默認一切正常不管。
- 表裡沒寫 `after_all` 的格，紀錄沒有 `hooks` 鍵；`after_all` 是空陣列時是 `"hooks":{"after_all":[]}`。
- 換紀錄時跟著整份進 `last.json`。
- `hooks` 只會出現在 `ended:true` 的紀錄裡。

依據：使用者 2026-10-01 第六批裁定（[verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第六批tick-的-hooks外掛掛點)）：「那就做外掛掛點，這個hooks就是模組」「after_cell？我以為是after_all，我們有cell嗎？ 2.可以一串。 3.吃，hooks中的掛點所提供的，比如"after_cell":[{},{},...]，就比照tasks。4.會記錄。 剩下都建議」；同日改成頂層鍵：「所以目前唯一的模組就是hooks...就不讓他當模組了，直接讓他變頂層key」。

**驗收：**沒寫 `hooks`（或 `hooks` 裡沒 `after_all`）時紀錄沒有 `hooks`、行為照舊；寫在 `modules.hooks` 底下的不跑。`after_all` 三項依序在任務之後跑，沒寫 id 的用位置字串；頂層 `argv`、`envs` 當預設，項自己寫的 `envs` 整包蓋過。`hooks`、`after_all`、某項各自 `$ref` 到別的檔照跑；項裡 `argv` 元素的 `#/k` 指合併後的這一項。hook 拿到的 `AOS_TICK_CWD` 是工作資料夾、`AOS_TASK_ID`／`AOS_TASK_INDEX` 是自己的。任務建了停格檔：後面的任務不跑、`after_all` 照跑，hook 再建停格檔也不擋下一個 hook。hook 回 3、被 SIGKILL、找不到程式（127，stderr `exec_failed: after_all/<id>:`）都照記（帶 `index`）、回 0 的不記、下一個照跑、tick 回 0。擋板、busy、表壞時一個 hook 都不跑。`after_all` 不是陣列、某項不是物件、合併後沒 `argv`、`hooks` 不是物件、讀表那一層 `$ref` 解不開：`bad_table`、回 1、紀錄與 `seq` 不動。紀錄的 `hooks.after_all` 下一格進 `last.json`。測試：`src/py/tests/test_tick_hooks.py`。
