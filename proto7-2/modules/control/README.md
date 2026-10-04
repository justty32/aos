# 控制包（control）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)（第 6 節：kill）

**restart／reload 在請求端做。** 核心的任務控制只剩 kill（`run` 必填）；這包把「重起同一個槽」組成兩步：先在 tasks.json 加一項釘同槽的 once，再寫 kill。kernel 可以直接 import，人用 `aos7-ctl task <槽> restart`。

| 項目 | 內容 |
|---|---|
| 接法 | C 工具＋函式庫：`aos7_control.restart(...)`；工具包的 `aos7-ctl task … restart` 呼叫它（工具包依賴這包） |
| 預設 | 開（隨工具包） |
| 依賴 | 核心的 kill（`run` 必填）、tasks.json 的 `slot`（once 釘槽）與 `x` 透傳、執行中加掛的 `dyn` 標記 |
| 程式 | `aos7_control.py` |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/control/tests`） |

## restart(node, slot, why="", reload=False, req_id=None, by=None)

1. 讀槽的 `birth.json` 拿現在的 run 與定義（`name`、`argv`／`inst`、`x`、`mounts`——執行中加掛的也抄進宣告，新 run 照樣有）。讀不到、壞掉＝不做。
   - `reload=True`：定義改取 tasks.json 裡同名的第一個非 once 項，用核心的 `aos7_tick.check_item` 完整驗證過才用，去掉排程欄位（`mode`、`from_round`、`until_round`、`max_live`、`enabled`、`launch`、`slot`）；掛載＝項目宣告加上沒被宣告接管的執行中加掛（birth 裡標 `dyn` 的）。找不到、讀不懂、不合格＝不做（不 kill），回 `ok: false` 說原因；成功時回 `diff`（`argv`、`inst`、`mounts`、`x` 有變的欄）。
2. 拿 `tasks.json.lock`（最多等 1 秒）加一項 `{"mode": "once", "slot": 同槽, "x": {…, "restart_of": 原 run id, "req_id": 請求 id}}`。
   - **去重**：表上已有同槽同 `req_id` 的 once＝不重加；槽現在的 birth 已帶同一個 `req_id`（這件已經重起過）＝什麼都不做，回 `once: "done"`。新請求用新 id（預設自動產生），重送同一件才沿用原 id。
   - 表讀不到、不是一般檔、壞掉＝不知道原本有什麼，拒寫（G1），不做第 3 步。
3. 寫槽的 `ctl.json`＝`{"op": "kill", "run": 原 run, "by", "why", "id": req_id}`。tick／tock 收掉原 run 後，下一個 tick 先處理 once、在同一個槽起新 run（任務自己寫的 state 接得上）；新 birth 帶 `x.restart_of`、`x.req_id`。

回 `{"ok", "msg", "run", "req_id", "ctl", "once": "added"|"dup"|"done", "diff"?}`；`ok` 只表示請求端這兩步做完了，真的重起看 ctl-done.json 與下一回合的總結。

## 被打斷時（方案 6.1 第 1 點）

- **請求端在加完 once、寫 kill 之前死掉**：once 項等槽空才起（`skipped` 記 busy），不會「殺了沒重起」；但也不會自己重起——**重試責任在請求端**：用同一個 `req_id` 再呼叫一次（once 不重加，補寫 kill）。原 run 自己結束的話，once 照樣會起。
- **tick／tock 處理 kill 到一半被殺**（寫完回條、還沒刪請求）：下一次再執行同一份 kill——因為帶著 `run`，只對原 run（已結束就只是補收），不會打到新 run。
- 以前在核心時（A2-05、A3-01、A3-04、A3-05）靠 `ctl_id`、`ctl-seen.json`、檔案 inode＋mtime 雜湊辨認重播；搬到請求端之後都不需要了，見 [problems](../../notes/problems.md)「控制包與 once 保證包」。

## 界線

- kill 的 `run` 必填，所以「不帶 run 的 kill 在重播窗口打到新 run」不存在了。
- reload 之後再 reload：新 run 的 birth 只把加掛的掛載當成宣告（不再標 `dyn`），第二次 reload 照新項目的宣告，不會再帶它們。
