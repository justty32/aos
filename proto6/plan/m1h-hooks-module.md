# 第一段之二：hooks（外掛掛點）

← [plan 入口](README.md)｜**接在 [m1-tick-core](m1-tick-core.md) 之後。**｜依據：[verdicts 11 篇末「第六批：tick 的 hooks（外掛掛點）」](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第六批tick-的-hooks外掛掛點)｜結束碼：[C-08](../spec/settled/conventions.md)｜spec 正本：[B-635](../spec/settled/tick/hooks.md)、格式 [P-202、P-203、P-213](../spec/settled/protocol/tick.md)

**做完的樣子**：任務表 `.aos/tasks.json` 頂層多一個可選鍵 `hooks`（跟 `tasks` 同層）。寫了 `"hooks": {"after_all": [...]}`，`aos-tick` 照表跑完（含被停格檔停下）之後就照順序跑那一串，每項的碼記進本格紀錄的 `hooks.after_all`。沒寫 `hooks` 時 `aos-tick` 就是 m1 原樣。

> **使用者裁定（2026-10-01，原話）**：「那就做外掛掛點，這個hooks就是模組」「after_cell？我以為是after_all，我們有cell嗎？ 2.可以一串。 3.吃，hooks中的掛點所提供的，比如"after_cell":[{},{},...]，就比照tasks。4.會記錄。 剩下都建議」。同日改：「所以目前唯一的模組就是hooks...就不讓他當模組了，直接讓他變頂層key」。
>
> 1～4 的意思：掛點叫 `after_all`（沒有 cell 這回事）；一個掛點可以掛一串；每項吃 tasks.json 頂層預設、寫法比照 `tasks`；碼要記錄。「剩下都建議」＝下面標「AI 隊定」的照建議做。改裁定：hooks 不放 `modules` 底下、不叫模組，直接是頂層鍵。

> **POC 總原則**：默認一切正常，不寫邊緣處理。

> **結束碼**：hooks 不新增任何碼；tick 照舊只回 0／1，hook 回幾都不影響。

## 步驟 1：讀表與極簡檢查

- **要做到**：讀表時順便讀頂層 `hooks`，格式不對就在開格前 `bad_table`、回 1。
- **寫法**：

  ```json
  {
    "envs": {"LANG": "C.UTF-8"},
    "tasks": [{"id": "build", "argv": ["make"]}],
    "hooks": {"after_all": [
      {"id": "notify", "argv": ["./notify.sh"]},
      {"argv": ["sh", "-c", "date >> logs/ticks.log"]}
    ]}
  }
  ```

  - `after_all` 是陣列，每元素一個 inst 物件，跟 `tasks` 每一項一樣：`id` 可省（沒寫＝在 `after_all` 的位置轉字串，從 `"0"` 起）；吃頂層預設（淺層合併、項蓋過）。
  - **展開時機比照 `tasks`**：`hooks` 本身、`after_all`、每一元素讀表時各解一層；值的內部跑到時、合併後才照 inst 規則展開。
  - 只開 `after_all`；`hooks` 裡其他鍵（`before_all`…）照收不理、不解。
- **極簡檢查**：`hooks` 是物件；`after_all` 是陣列；每項是物件；合併預設後有 `argv`；讀表那一層解得開。其他不查。
- **要使用者裁定的點**：無。
- **驗收**：`after_all` 不是陣列、某項不是物件、合併後沒 `argv`、`hooks` 不是物件、`$ref` 解不開：stderr 一行 `bad_table:`、回 1，一項都不跑、紀錄與 `seq` 不動。頂層有 `argv` 時只寫 `id` 的 hook 照跑。寫在 `modules.hooks` 底下的不跑。

## 步驟 2：什麼時候跑、怎麼跑

- **要做到**：紀錄收尾（`ended:true`、`exit:0`，被停下的還有 `stopped_after`）之後，照順序跑 `after_all` 每一項，跑法跟任務一模一樣（同一個 `run_one`）。
- **規則**：
  - 照表跑完、被停格檔停下：跑。擋板、busy、tick 自己出錯：走不到這裡，不跑。
  - 不看停格檔：hook 之間不查，hook 自己建停格檔也不擋下一個 hook（留著的由下一格開頭刪）。
  - 每項的碼照實記、接著跑下一項；tick 照舊回 0。
  - 環境：`AOS_TICK_CWD`；`AOS_TASK_ID`／`AOS_TASK_INDEX` 是這個 hook 自己在 `after_all` 的 id／位置。
  - 沒跑成（125／126／127）stderr 印 `exec_failed: after_all/<id>: …`〔AI 隊定〕。
  - hook 跑到時展開失敗：照任務的規則自然丟錯、回 1〔AI 隊定，照總原則不另處理〕。
- **要使用者裁定的點**：無。
- **驗收**：三個 hook 依序在任務之後跑，沒寫 id 的用位置；頂層 `envs` 當預設、項自己的 `envs` 整包蓋過；hook 的環境變數是自己的 id／位置。任務建停格檔：後面任務不跑、hook 照跑。hook 回 3、被 SIGKILL、找不到程式都照記、下一個照跑、tick 回 0。擋板、busy、表壞時不跑。

## 步驟 3：紀錄

- **要做到**：`current.json` 多一個 `hooks` 鍵，跟 `tasks` 分開。
- **格式**〔AI 隊定〕：收尾之後先寫 `"hooks":{"after_all":[]}`，每跑完一個加一項，格式同 `tasks` 每項：

  ```json
  {"version":1,"seq":7,"started_at_ms":1790000000000,
   "tasks":[{"id":"a","exit":0},{"id":"b","exit":0}],
   "ended":true,"exit":0,"stopped_after":"b",
   "hooks":{"after_all":[{"id":"notify","exit":0},{"id":"1","exit":3}]}}
  ```

  > **2026-10-01 第八批補註**（[verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第八批紀錄只記非-0)）：使用者「tasks如果結果是0，那就不用紀錄了。hooks也是。」上面的例子是當時的格式。現在 `tasks`、`hooks.after_all` 只記結束碼不是 0 的，每筆加 `index`；另有 `ran`（只算 tasks，hooks 不記 ran）。同一格現在寫成：
  > `{"version":1,"seq":7,"started_at_ms":1790000000000,"ran":2,"tasks":[],"ended":true,"exit":0,"stopped_after":"b","hooks":{"after_all":[{"id":"1","index":1,"exit":3}]}}`
  > 另外，hook 跑到時展開失敗→tick 回 1、但紀錄已是 `ended:true`／`exit:0`，兩邊對不上：使用者 2026-10-01：先不管（POC 默認一切正常）。
  >
  > **2026-10-01 第九批補註**（[verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第九批紀錄拆檔)）：使用者「current.json這邊，也要引入指示詞，把容易被改動的弄成$ref指向其他檔案，不容易被改動的留在current.json」。上面講的 `current.json`／`last.json` 現在是資料夾 `tick/current/`／`last/`；`hooks` 實際存在 `hook-exits.json`，收尾那次先寫好 `{"after_all":[]}`、`record.json` 同時加 `"hooks":{"$ref":"hook-exits.json"}`（`record.json` 只在開格、收尾各寫一次，不再另有「開始跑 hooks 前」那次寫）；沒寫 `after_all` 的格沒有這個檔也沒有這個 `$ref`。

  - 表裡沒寫 `after_all` 的格沒有 `hooks` 鍵；`hooks` 只會出現在 `ended:true` 的紀錄裡（schema 管）。
  - 因為寫在收尾之後，hook 讀 `current.json` 看得到整格結果與前面 hook 的碼。
  - 換紀錄時跟著整份進 `last.json`。
- **要使用者裁定的點**：無。
- **驗收**：hook 讀到的紀錄是 `ended:true`、有前面 hook 的碼；下一格 `last.json` 帶著上一格的 `hooks`；紀錄過 `tick-record` schema。

## 步驟 4：整段驗收

- 步驟 1～3 的驗收寫成 `src/py/tests/test_tick_hooks.py`；m1 的 `tests/test_tick.py` 一字未改照樣全過。
- spec：新篇 [B-635](../spec/settled/tick/hooks.md)；P-202、P-203、P-213 擴充；schema `tick-tasks`、`tick-record` 與範例。

檔案：讀表與極簡檢查放 `lib/aos_tick_table.py`（`check_table()` 多回 `Table.after_all`，跟 `tasks` 共用 `_items()`）；跑放新的 `lib/aos_tick_hooks.py`（`run_after_all()`）；紀錄 `lib/aos_tick_record.py` 多 `start_hooks()`、`add_hook()`；`lib/aos_tick.py` 收尾後呼叫。

## 這段不做的

| 不做 | 這版的樣子 |
|---|---|
| `before_all`、`before_task`、`after_task` 等其他掛點 | 只開 `after_all`；其他鍵照收不理 |
| hook 能影響 tick 的結束碼或擋後面的 hook | 碼只記下；不看停格檔 |
| 擋板、busy、表壞時也跑 | 不跑 |
| `AOS_HOOK_*` 之類專屬變數 | 跟任務同一組變數 |

## 待問

無（使用者「剩下都建議」）。

## 做完了沒

**做完了**（2026-10-01，AI 隊）：步驟 1～4 照上面做了，測試 `tests/test_tick_hooks.py` 全過；四項檢查（全部測試、`check_ids.py --strict`、範例 `validate.py`、`wf-lint`）都過。同日改裁定（不當模組、改頂層鍵、展開時機比照 tasks）已照改。等使用者看。
