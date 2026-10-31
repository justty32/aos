← [入口](../2026-10-22-ideas.md)｜涵蓋：5. loop（10-22）、6. daemon（10-22）、7. fsm（10-22）｜上一份 [02-3-env-基礎子集與---dotenv-ove](02-3-env-基礎子集與---dotenv-ove.md)

## 5. loop（10-22）

頂層把 loop 的四個實際問題（每拍沒有時間上限、兩個 loop 共用 state 檔會撞暫存檔名、state 寫不了吐 traceback、loop 跑途中改 `.env` 不生效）與幾處條文還標「草稿」、跟程式對不上的地方帶給使用者。使用者原話：

> loop這塊，那四個實際問題我的意見如下：1.每拍沒有時間上限沒關係，想要時間上限就自己在argv加timeout之類，這是使用者自己要承擔的風險。2.使用者自己承擔風險。3.沒關係。4.使用者要自己承擔。小地方那些我都OK，就是條文草稿那邊要去解決。

決定：

1. 四個問題都不改程式，寫成「使用者自行承擔」：每拍上限自己在 argv 接 `timeout`（或用單子的 `timeout_ms`）；共用 state 自己避免（或接 s6-setlock，頂層補的做法）；traceback 接受；`.env` 不即時生效接受，要蓋就在 `run` 指的單子 argv 寫 `--dotenv-override` 或重開 loop。落在 [NORMS/04](../../docs/NORMS/04-基礎設施-loop與daemon.md) 開頭。
2. loop 相關的條文照 bin 程式定稿（程式 > 文件）：N-13、N-17、N-28、N-32、N-33、N-54。N-17 的心跳間隔照 N-32 定為 1 秒；N-32 補寫 `interval_ms` 的語意（上一拍結束到下一拍開始，不是固定週期；ctl 改它對正在睡的那段不生效）；P-06 列 loop.json 實際的五個 key；N-28 子 loop 的輸出檔：aos 不保證不無限長，要控制大小使用者自己處理（logrotate、單子的 `stderr` key、s6-log 等是頂層補的例子）。
3. 窗一族的總則 N-14、鎖 N-15、信箱 N-16 還沒有完整實作可對，照舊標草稿。

## 6. daemon（10-22）

頂層帶給使用者 daemon 的三件：① daemon 被 SIGKILL 期間死掉的子項，daemon 再起時會被重起；② 子項名字叫 `state.json`／`ctl.json`（跟 daemon 自己的 ctl／state 同名）時 daemon 會 traceback 當掉或 ctl 被佔；③ N-28 列了卻沒做的：`policies.child_exit`、backoff、stderr 輪替、不接回時清掉舊小格、「有 argv 就包成跑一次」。使用者原話：

> daemon 照建議：1 daemon 重開時照表起，算重新開始、不算自動重起；2 子項名字擋掉跟 ctl／state 同名；3 N-28 未做的從規範拿掉、改寫自己接工具。

決定：

1. **程式不改**：「不自動重起」管的是 daemon 開著的時候；daemon 重開＝重新開始，照名單起表上缺的（含停機期間死掉的），活著且對得上的照 `adopt` 接回。測試釘住（`test_restart_starts_children_died_while_down`）。
2. **擋撞名**：會撞的名字＝daemon 的 ctl、state 落在 `$AOS_STACK` 底下時相對路徑的第一段（`state.json`、`ctl.json`、`"w/c.json"` 的 `w`；在外面的、沒開的不算；頂層照程式定）。起來時撞＝一行錯誤、退 1；ctl 的 `children` 撞＝那份 ctl 不採用、維持上一份好的、原因進 state 的 `last_warning`。
3. **N-28 沒做的從規範拿掉**：`policies.child_exit`、`backoff` 隨「不自動重起」不做；輸出的選填路徑、輪替、清舊小格不做，要的話自己在鏈上接工具（拍的單子用 `stderr` key 導走接 s6-log／svlogd、外面 logrotate；舊小格自己在起 daemon 前刪）；「沒 `run` 有 `argv` 就包成跑一次」不做，要跑一次單子寫 `{"run": "daemon.json#/children/<名字>/body", "body": 單子, "max": 1}`。

結論：bin 與 impls 的 aos-daemon 都擋撞名（測試 `tests/test_daemon.py`；起來時撞名的代號 `Conflict`，10-23 使用者認可）；N-17 六態不含 `backoff`。`.env` 預設不蓋，所以 daemon 環境裡已有的變數會壓過子項 `.env` 同名的值。

舊小格的 `ctl.json`（daemon 重新起子項、非接回時，舊的還寫著 `stop` 就一起來就停）使用者 10-22 原話：

> ctl.json 照舊，使用者自己刪，算自己承擔

決定：daemon 不自動清，使用者自己刪，算使用者自行承擔。

## 7. fsm（10-22）

頂層把 fsm 的幾個實際問題（a state 檔在但讀不了、b 某格的 `next` 指到表上沒有的狀態、c `next` 是空字串，與其餘幾件）和 fsm 條文還標「草稿」的事帶給使用者。使用者原話：

> fsm 照建議：a state 讀不了就退 1；b、c 開跑時查整張表；其餘算使用者自己承擔，條文定稿。

決定：

1. **a**：`$AOS_STACK/state` 在但讀不了（沒權限、是資料夾、不是 UTF-8…）＝fsm 自己的錯，退 1、stderr 一行、不跑格；檔不存在照舊＝從 `start` 起。
2. **b、c**：開跑時（讀表後、跑格前）查整張表——`start` 要在表上，每一格的 `next` 要是表上有的狀態名、不能是空字串；不合＝表壞、退 1、不跑格。state 檔裡的狀態不在表上照舊退 1。一起查（實作時代定）：每一格的形狀與 `val`、`next` 頭尾不能有空白、不能有換行（state 檔是純文字一行、讀回來會去頭尾空白）。
3. **其餘使用者自行承擔**，不改程式，寫在 [NORMS/07](../../docs/NORMS/07-基礎設施-組合子.md) 開頭：每格沒有時間上限（自己接 `timeout` 或用單子的 `timeout_ms`）；兩隻 fsm 共用同一個 stack 會撞暫存檔；state／trace 寫不了吐 traceback、下一拍重跑同一格；`trace.jsonl` 不設上限；loop／fsm 被 SIGKILL 時格變孤兒、重開時可能重疊；無窮轉移只有 loop 的 `max` 擋；`val` 的相對路徑從 cwd 算；`.env` 外層贏，`val` 陣列傳不了 `--dotenv-override`（要寫成 body 單子）。
4. **條文定稿**：fsm 的 N-20、N-36、N-38、N-39、N-41 照 bin 程式定稿（程式 > 文件）；a、b、c 寫進 N-36、N-38。NORMS/07 開頭補「fsm 屬標準庫」（C-74）。tasks 的 N-34 現無實作、沒有程式可對，照舊標草稿。

結論：bin 與 impls 都照這樣做（`tests/test_fsm.py`；表壞的代號 `FieldType`、state 讀不了 `ReadFailed`、state 裡的狀態不在表上 `StateUnknown`；`FieldType`、`ReadFailed` 10-23 使用者認可）。
