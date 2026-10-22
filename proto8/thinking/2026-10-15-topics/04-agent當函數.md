← [回入口](../2026-10-15-topics.md)｜上一份：[03-試146-qwen與LM-Studio](03-試146-qwen與LM-Studio.md)

## 11. agent 當函數＋binding、當工具

**原文**（10-15，照記）：
- 「我會把 agent 的使用當作函數＋binding，表現形式就像：agent_call(system, history, engine, tools)，然後可以做 binding：agent_bob = {system:"...", history:"...", ...}, agent_bob.call(history, engine_args, tools_append)。具體體現在有一個 bob/ 資料夾，裡面存放相關東西，具體要使用的時候，可以把 cwd 指定到另一個地方，讓 history 等東西在另一個地方累積，而 bob/ 資料夾不變，這樣 bob 就是一個可重複使用的函數。」
- 「history 累積的地方，可以和實際的 cwd 不一樣，也就是 history 累積那塊，很像是函數本體的 stack。相對路徑那塊就是技術問題，概念我剛剛訂下了，規範我們慢慢來。」
- 「然後 tools 本身又是函數的一些包裝，對於 agent_bob.call 來說，更像是傳進去的，可以給他使用的函數。tools 中又可以包含其他 agent 的呼叫...」

**決定**
- 概念進 [C-46](../../CONCEPTS/05-agent.md#agent函數binding)：定義（bob/，不變）、frame（history 等累積處，像 stack）、cwd 三處分開；tools＝傳進 call 的函數，bob 綁的只是預設，裡面可以是別的 agent。規範之後再說。
- agent 當工具，使用者「照預設做」，六點：① `aos_agent_lib.py ask bob/agent.json` 當工具 inst（說明放 `_tool`），stdin `{"question"}`；② 每次一個新 frame（預設父 agent 的 `work/ask-<n>/`，或 `--frame`），每次新對話，bob/ 不動；③ 本行程一拍一拍敲子 agent 的 fsm 到 `end`，回 `{"reply", "ticks"}`；④ frame 的 lock 拿整趟，同 frame＝`Busy`、不同 frame 可同時；⑤ 三道上限 `--max-ticks`（20）、子 agent 的 `max_steps`、工具 inst 的 `timeout_ms`（demo 120 秒），到了＝`MaxTicks`＋`partial`；遞迴 `AOS_ASK_DEPTH` 超過 3＝`TooDeep`；⑥ 子 agent 出錯／停住＝回它的 last_error、不重試；父 agent 只看到最後一句，完整對話留在 frame。
- 程式：`aos_agent_call.py`（agent.md（已刪，見 git 歷史 5546be29））；demo/fsm 加報時員 `clerk/`，外層工具只剩 clerk（tools 裡包含其他 agent 的呼叫）。測試 12 個。沒碰任何 endpoint。

**動工自定點**（等使用者看）
- **路徑怎麼分**：不動 inst／loop／`$ref` 的通則（照 cwd 算）；改由前端把定義攤開——表上的格、brain、tools、system（含 `$ref`）從 bob/ 算、讀成內嵌 inst，**沒寫 cwd 的就在 bob/ 跑**（argv 的相對路徑才對得上）。state、history、work 指進 frame，lock＝`frame/lock/` 由前端拿整趟。
- 所以 bob 綁的工具預設在 bob/ 跑；呼叫時傳進來的工具（`tools`／`tools_append`）路徑從 cwd 算、在 cwd 跑。工具若要在呼叫者那邊寫檔，目前得自己寫 `cwd`。
- 只攤開最上層的表：內層 fsm 的執行期 key 不會被指進 frame，所以 `clerk/` 寫成單層表 `thinking → route → tool`；為此格庫多一格 `route`（有 tool_calls＝tool，否則 idle）。
- `history` 給了＝換掉 frame 的 history 並刪 state（從 start 來）；沒給＝接著 frame 的，frame 沒有＝`NoHistory`。
- `engine_args`：list＝接在腦的 argv 後，dict＝蓋過腦 inst 的 key。`tools` 給了整份取代、`tools_append` 再加。
- `ask` 的錯誤寫在 stdout（`{"error", "msg"}`、退 1），父 agent 的 tool 訊息才看得到；frame 預設放 `$AOS_WORK`（tool 格給工具的環境變數）。
- 父 agent 的 tool 格 `timeout_ms` 改 150 秒（要蓋過 clerk 的 120 秒）；`loop.json` 的 20 秒假腦夠，真腦要加大。

（10-20 註：`aos_agent_call.py` 與 `aos_agent_lib.py ask` 同日稍晚已退場——[意見 1～4](../2026-10-15-opinions-1-4.md)「aos_agent_call.py 退場」，`ask` 搶號建資料夾併進 tool 格；上面講的 frame 後來改名 stack〔[agent-inherit § 四](../2026-10-16-agent-inherit.md#四使用者決定10-16)〕。lib 程式 10-19 已整套刪，見 git 歷史 5546be29。）
