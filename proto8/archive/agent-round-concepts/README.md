> 封存 2026-11-03：程式 11-03 已刪，只留概念（使用者 11-03 晚「封存這條線，1.該刪的都刪光刪乾淨」「一起刪，剛剛那些說會整合到aos-agent的，也都可以刪一刪。只需要留下他們的概念就好，也就是不用留程式碼，留文檔就好。我沒有要用他們」）。

# 用格組起來的 aos agent（round）與 aos-ai —— 概念

這份收的是 10-28～11-03 那套「agent 不寫自己的 brain／act，而是把共用的格組起來」的做法，以及建在它上面、給 AI 用的 aos-ai。程式（`lib/agent/round/`、`parts.py`、`queue`／`history`／`act`／`compact`、`lib/endpoint/`、`lib/aos/ask_round`、`demo/agent-nia`、`extras/ai_tools/bin/aos-ai` 與 `aos_ai_*.py`、`lib/aos` 的 spawn_agent／ask_agent／agent_status／make_json／make_tool／explain_aos、Claude Code skill）與它們的測試都刪了；最後一版看 git 歷史（刪除的那個 commit 的上一個）。討論與決定照舊在 thinking：2026-10-28-agent-round、2026-10-28-agent-ops、2026-10-30-agent-lifecycle、2026-10-30-aos-round、2026-10-31-parts-round、2026-10-24-ai-tools。

同資料夾的 [aos-concepts.md](aos-concepts.md) 是當時給 AI 看的「aos 概念速成」（aos-ai explain 讀的那份，11-03 HEAD 版原樣），條文以 proto8/docs 為準。

現役的對應物：外部 coding agent 走 eca（aos-eca、aos-eca-turn，跟這裡同一個對話協議：queue 收信、history 回答）；跟 agent 講話用 aos-say／aos-listen。

## 一輪（round）是什麼

一隻 agent 的「一輪」＝認領一題 → 問腦 → 照腦的決定跑工具 → 再問腦 → 交卷。它不是一支程式，而是**一張 aos-fsm 的表加五個薄格**：

- **idle**：從 queue 認領一題（接進 history）。queue 空退 10。
- **think**：問腦一次（hook `pre_think` → endpoint → 失敗問 hook `on_error`〔retry／switch，有上限〕→ hook `post_think`），回答接進 history。有 tool_calls 退 0、沒有退 10（該交卷了）。
- **act**：有沒回的 tool_calls 才跑工具，結果逐則接進 history；插話打斷退 10。
- **more**：插話後把新信接進 history。
- **finish**：交卷（收掉那封信）、叫 hook `post_round`。

表靠 N-36 的「照結束碼分岔」接起來：idle →0 think；think →0 act、10 finish；act →0 think、10 more；more → act；finish → idle。

**為什麼拆成格、交給 fsm**（agent-ops、aos-round）：

- aos agent 本來就是 loop／fsm 疊出來的，一輪不必另寫一支「跑一輪」的程式。aos-loop 每次跑一張單子＝aos-fsm 走一格，fsm 本來就一次一格；中間那層 `aos-round` 是語法糖，11-01 刪了，loop.json 直接叫 aos-fsm。
- 每格薄、只說自己的結果與錯（C-52）；每格開頭先對 state 與資料自保（上次斷在半路也接得上）。
- **跑完要不要結束寫在定義裡**：指 `fsm-stop.json`＝queue 空時 fsm 退 10、loop 收工（射後不理）；指 `fsm-idle.json`＝idle 的 10 被表接住、fsm 退 0，aos-loop 隔 `interval_ms` 再來（停著等）。停著等、暫停、收工都是 aos-loop 給的，agent 自己仍是函數。
- 「10＝要外面的 loop 別跑了」是對**直接收到它的那層**說的；表上接住的 10 到不了 loop（NORMS 總則、CONVENTION 巢狀的 10-30 加註）。

## 格怎麼找、怎麼叫（parts）

- 一隻 agent 用哪些格，登記在它資料夾的 `parts.json`（aos-exec 格式：槽值＝路徑字串或 `{".env", "_entry"}`，`hook`、`endpoint` 巢狀）；沒寫的槽找同名的固定名字（捷徑）。註冊檔與固定名字共存、註冊檔優先（使用者「全部走註冊檔好了，捷徑就是方便使用」「註冊檔案中沒寫的，那就是走固定名字」）。
- 叫法一律 `aos-exec <agent>/parts.json#/<槽> <agent 資料夾絕對路徑> [子命令]`：格不是給腦叫的工具（沒有 `_tooldef.json`），agent 資料夾當第一個參數，各格共用 agent 的 `$AOS_STACK`。
- **endpoint 也是 aos 函數**（使用者「各種單位都要跟aos函數對上，也就是aos-exec可以跑的單位目標。包括endpoint」）：stdin 一份 OpenAI 請求體、stdout 一則 assistant message。換腦＝在 stack 寫一行 `endpoint.txt` 指另一個槽（例：假腦 `default` 換成 LiteLLM）。
- **history 只有 compact 可以改寫**：compact 掛在 `pre_think`，超過門檻才壓，舊的收進 `history_archive/`。

## 對話協議（queue 收信、history 回答）

agent-lifecycle 定的（CONVENTION P-42），eca 現在也照它：

- 輸入是 `$AOS_STACK/queue/`（N-16 有順序的信箱），一封信的 body＝一則 OpenAI message；認領時原樣接進 history。
- 回答＝`history.jsonl` 最新那則沒有 tool_calls 的 assistant，不另寫 `out/`。
- 壞信丟掉、原因記 `$AOS_STACK/mailbox_warning.txt` 一行（只留最後一封）。

## agent-nia（範本）

demo 裡唯一用格組起來的 agent：`_entry`＝`aos-loop loop.json`，loop.json 叫 aos-fsm 跑 round 的表（`cwd` 指表所在、表裡的 `{"$env": "AOS_CD"}`＝agent），`parts.json` 掛 lib 的 queue、history、act、compact（pre_think）、假腦與 LiteLLM 兩個 endpoint，`tools.json` 給腦 clock、math。題目經 queue 格放、答案看 history。

## ask_round（把 agent 當外部接口）

agent-round § 6「round 當外部接口」：一支工具同步問一隻格組起來的 agent 一題——push 一封信，一格一格叫 `aos-exec <agent>/loop.json#/exec`，每格後看信還在不在（不見了＝交卷了），印答案；agent 不必常駐。登記進 aos-mcp 的登記檔，Claude Code 就能「問一隻 aos agent」。

## aos-ai（給 AI 用的 aos 工具集）

使用者 10-24「做一套方便AI使用我們這套aos工具的工具集」「我隨便說，你隨便做，反正只是嘗試」。

- 一個工作資料夾（root）裡管多隻 agent：`agents/<名>/agent/`（範本的複本，預設 agent-nia）、`agents/<名>/ws/`（工作區，stack 在 `ws/.stack/`），背景用一個 aos-daemon。
- 一串用法：spawn（複製範本、範本裡指出去的相對路徑改絕對）→ ask（寄信進 queue）→ run（前景跑到 queue 空）／start（交給背景 daemon）→ answer、status、history、wait、stop。
- 另有生成（make：inst、loop、fsm、daemon、工具骨架、fsm 加格，先驗形狀）與查概念（explain，`--here` 模擬 aos-exec 會給的值）。
- 每次輸出一行 JSON；agent 跑失敗不是 aos-ai 的錯（`ok`／`code` 看結果），下層 stderr 拆成 `errors`，失敗附一句下一步。
- 同樣的能力包成給 agent 掛的六個 lib 工具（spawn_agent、ask_agent、agent_status、make_json、make_tool、explain_aos），與一份 Claude Code skill。
- 留下來的：**aos-mcp**（把 aos-tools 登記的工具當 MCP tools，eca 接 aos 工具用的）仍在 `extras/ai_tools/bin/`；**aos_ws**（寄信、等答案、讀 stack）留給 aos-say／aos-listen。
